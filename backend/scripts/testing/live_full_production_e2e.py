"""Credentialed end-to-end proof for P1-P3.

Runs only when RUN_FULL_PRODUCTION_E2E=1.

P1: Runway -> ElevenLabs -> FFmpeg
P2: MinIO persistence -> local deletion -> recovery -> multimodal judge
P3: explicit TikTok SELF_ONLY publish -> status -> metrics -> Outcome -> RL
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, engine
from app.core.redis import redis_client
from app.engine.agents.workflow.multimodal_artifacts import MinIOArtifactStore
from app.engine.agents.workflow.multimodal_content_workflow import (
    InMemoryCheckpointStore,
    MultimodalContentProductionAgent,
    StoryboardShot,
)
from app.engine.agents.workflow.multimodal_eval import (
    MultimodalEvaluationHarness,
    OpenAIMultimodalJudge,
)
from app.engine.agents.workflow.multimodal_media import (
    ElevenLabsTTSGenerator,
    FFmpegVideoAssembler,
    ProductionMediaToolkit,
    RunwayVideoGenerator,
)
from app.engine.agents.workflow.multimodal_publishers import TikTokContentPublisher
from app.ml.rl.outcome_reward_bridge import sync_outcome_to_rl
from app.ml.training.schemas import GenerationTrace, Outcome


class FixedPlanner:
    async def create_script(self, brief, platform):
        return {
            "title": "Multimodal AI Agent",
            "hook": "From brief to finished video",
            "body": "An AI agent plans, generates, assembles, reviews, and publishes.",
            "cta": "Built with recoverable agent execution.",
            "narration": "An AI agent turns a brief into a reviewed short video.",
            "target_duration_seconds": 2,
        }

    async def create_storyboard(self, script, platform):
        return [
            StoryboardShot(
                shot_id="proof-shot-1",
                narration=script["narration"],
                visual_prompt=(
                    "A cinematic close-up of a computer screen showing an abstract "
                    "AI workflow made of glowing nodes and connecting lines, dark "
                    "studio environment, subtle camera push-in, realistic, no text, "
                    "no logos, vertical social video"
                ),
                duration_seconds=2,
            )
        ]


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


async def ensure_rl_tables() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: GenerationTrace.__table__.create(
                bind=sync_connection,
                checkfirst=True,
            )
        )
        await connection.run_sync(
            lambda sync_connection: Outcome.__table__.create(
                bind=sync_connection,
                checkfirst=True,
            )
        )


async def create_trace(session: AsyncSession, state) -> str:
    trace_id = f"live-proof-{uuid.uuid4().hex[:12]}"
    trace = GenerationTrace(
        id=trace_id,
        platform="tiktok",
        persona="portfolio-e2e",
        niche="ai",
        topic="multimodal AI agent",
        prompt=json.dumps(state.brief, ensure_ascii=False),
        system_prompt="credentialed live production proof",
        constraints={"user_id": 1, "content_style": "technical"},
        retrieved_context=[],
        output=json.dumps(state.script, ensure_ascii=False),
        title=state.script.get("title"),
        tags=["ai", "agent"],
        cover_text=state.script.get("hook"),
        cta=state.script.get("cta"),
        policy_id="H01-B01-C01",
        model_id="live-multimodal-stack",
        adapter_id="runway-elevenlabs-ffmpeg",
        generation_time_ms=0,
        token_count=0,
        created_at=datetime.utcnow(),
    )
    session.add(trace)
    await session.commit()
    return trace_id


async def persist_outcome_and_sync(
    session: AsyncSession,
    *,
    trace_id: str,
    metrics: dict,
) -> dict:
    views = max(int(metrics.get("view_count") or 0), 1)
    likes = int(metrics.get("like_count") or 0)
    comments = int(metrics.get("comment_count") or 0)
    shares = int(metrics.get("share_count") or 0)
    engagement_score = (
        likes + 2.0 * comments + 2.0 * shares
    ) / views * 1000.0

    outcome = Outcome(
        id=str(uuid.uuid4()),
        trace_id=trace_id,
        impressions=views,
        clicks=0,
        click_rate=0.0,
        read_time_avg=0.0,
        completion_rate=0.0,
        likes=likes,
        comments=comments,
        saves=0,
        shares=shares,
        follows=0,
        dms=0,
        purchases=0,
        engagement_score=engagement_score,
        time_bucket="1h",
        measured_at=datetime.utcnow(),
        rl_synced=0,
    )
    session.add(outcome)
    await session.flush()

    synced = await sync_outcome_to_rl(
        db=session,
        trace_id=trace_id,
        engagement_score=engagement_score,
        time_bucket="1h",
    )
    outcome.rl_synced = 1 if synced else 0
    outcome.rl_synced_at = datetime.utcnow() if synced else None
    await session.commit()

    return {
        "outcome_id": outcome.id,
        "engagement_score": engagement_score,
        "rl_synced": synced,
    }


async def wait_for_tiktok_post(
    publisher: TikTokContentPublisher,
    publish_id: str,
) -> tuple[dict, str | None]:
    last = {}
    for _ in range(18):
        last = await publisher.fetch_publish_status(publish_id)
        ids = (
            last.get("publicaly_available_post_id")
            or last.get("publicly_available_post_id")
            or []
        )
        if ids:
            return last, str(ids[0])

        status = str(last.get("status") or "")
        if status in {"FAILED", "PUBLISH_FAILED"}:
            raise RuntimeError(f"TikTok publish failed: {last}")
        await asyncio.sleep(10)

    return last, None


async def main() -> None:
    if os.getenv("RUN_FULL_PRODUCTION_E2E") != "1":
        raise RuntimeError("set RUN_FULL_PRODUCTION_E2E=1 to run paid live proof")

    output_dir = Path(
        os.getenv(
            "MULTIMODAL_ARTIFACT_DIR",
            "runtime/full-production-e2e",
        )
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    artifact_store = MinIOArtifactStore(
        endpoint=required("MINIO_ENDPOINT"),
        access_key=required("MINIO_ACCESS_KEY"),
        secret_key=required("MINIO_SECRET_KEY"),
        bucket=os.getenv("MULTIMODAL_ARTIFACT_BUCKET", "videos"),
        cache_dir=str(output_dir / "cache"),
        secure=False,
    )

    media = ProductionMediaToolkit(
        video_generator=RunwayVideoGenerator(
            api_secret=required("RUNWAYML_API_SECRET"),
            output_dir=str(output_dir),
            api_base=os.getenv(
                "RUNWAYML_API_BASE",
                "https://api.dev.runwayml.com",
            ),
            api_version=os.getenv("RUNWAYML_API_VERSION", "2024-11-06"),
            model=os.getenv("RUNWAYML_MODEL", "gen4.5"),
            ratio=os.getenv("RUNWAYML_RATIO", "720:1280"),
            poll_interval_seconds=5,
        ),
        tts_generator=ElevenLabsTTSGenerator(
            api_key=required("ELEVENLABS_API_KEY"),
            voice_id=required("ELEVENLABS_VOICE_ID"),
            output_dir=str(output_dir),
            api_base=os.getenv(
                "ELEVENLABS_API_BASE",
                "https://api.elevenlabs.io",
            ),
            model_id=os.getenv(
                "ELEVENLABS_MODEL_ID",
                "eleven_multilingual_v2",
            ),
        ),
        assembler=FFmpegVideoAssembler(
            output_dir=str(output_dir),
            ffmpeg_bin=os.getenv("FFMPEG_BIN", "ffmpeg"),
            render_subtitles=True,
        ),
        artifact_store=artifact_store,
    )

    judge = OpenAIMultimodalJudge(
        api_key=required("OPENAI_API_KEY"),
        model=os.getenv("MULTIMODAL_JUDGE_MODEL", "gpt-5.6-luna"),
        ffmpeg_bin=os.getenv("FFMPEG_BIN", "ffmpeg"),
        sample_count=2,
    )

    evaluator = MultimodalEvaluationHarness(
        ffprobe_bin=os.getenv("FFPROBE_BIN", "ffprobe"),
        judge=judge,
        artifact_store=artifact_store,
    )
    agent = MultimodalContentProductionAgent(
        planner=FixedPlanner(),
        media_toolkit=media,
        evaluator=evaluator,
        checkpoint_store=InMemoryCheckpointStore(),
        require_human_approval=False,
        max_retries=1,
        retry_backoff_seconds=1,
        max_parallel_shots=1,
    )

    state = await agent.run(
        brief={"topic": "multimodal AI content production agent"},
        platform="tiktok",
        job_id=f"full-proof-{uuid.uuid4().hex[:10]}",
    )
    if state.final_video is None or state.quality_report is None:
        raise RuntimeError("P1 failed: no final artifact/evaluation")
    if not state.quality_report.passed:
        raise RuntimeError(
            f"P1/P2 failed quality gate: {state.quality_report.issues}"
        )

    # P2: delete local final file and prove recovery from MinIO.
    final_path = Path(state.final_video.uri)
    original_hash = hashlib.sha256(final_path.read_bytes()).hexdigest()
    durable_uri = state.final_video.metadata.get("durable_uri")
    if not durable_uri:
        raise RuntimeError("P2 failed: final artifact has no durable URI")
    final_path.unlink()
    recovered = await artifact_store.materialize(state.final_video)
    recovered_path = Path(recovered.uri)
    recovered_hash = hashlib.sha256(recovered_path.read_bytes()).hexdigest()
    if recovered_hash != original_hash:
        raise RuntimeError("P2 failed: recovered artifact hash mismatch")
    state.final_video = recovered

    # P3: this script is manually triggered, which is the explicit human
    # approval boundary for the SELF_ONLY TikTok post.
    state.approved = True
    tiktok = TikTokContentPublisher(
        access_token=required("TIKTOK_ACCESS_TOKEN"),
        privacy_level="SELF_ONLY",
        artifact_store=artifact_store,
    )
    publish = await tiktok.publish(
        state,
        caption="Multimodal AI Agent — end-to-end production proof #AI #Agent",
        brand_content_toggle=False,
        brand_organic_toggle=False,
    )
    publish_status, video_id = await wait_for_tiktok_post(
        tiktok,
        str(publish["publish_id"]),
    )
    if not video_id:
        raise RuntimeError(
            "P3 publish submitted but no TikTok post ID became available: "
            f"{publish_status}"
        )

    metrics = await tiktok.query_video_metrics(video_id)

    await ensure_rl_tables()
    await redis_client.connect()
    try:
        async with AsyncSessionLocal() as session:
            trace_id = await create_trace(session, state)
            rl = await persist_outcome_and_sync(
                session,
                trace_id=trace_id,
                metrics=metrics,
            )
    finally:
        await redis_client.close()

    report = {
        "p1": {
            "passed": True,
            "final_video": str(recovered_path),
            "quality_score": state.quality_report.score,
        },
        "p2": {
            "passed": True,
            "durable_uri": durable_uri,
            "sha256_before": original_hash,
            "sha256_after_recovery": recovered_hash,
            "judge": state.quality_report.metadata.get("judge"),
        },
        "p3": {
            "passed": bool(rl["rl_synced"]),
            "publish": publish,
            "publish_status": publish_status,
            "video_id": video_id,
            "metrics": metrics,
            "rl": rl,
        },
    }
    report_path = output_dir / "p0_p3_live_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if not rl["rl_synced"]:
        raise RuntimeError("P3 failed: platform metrics did not sync into RL")


if __name__ == "__main__":
    asyncio.run(main())
