"""Credentialed live E2E for the multimodal production stack.

This script performs paid external calls. It is intentionally fail-closed and
will not run unless RUN_LIVE_MULTIMODAL_E2E=1 is explicitly set.

It exercises:
Runway -> local/durable artifact -> ElevenLabs -> FFmpeg -> evaluation
and optionally the OpenAI multimodal judge.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path

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


class FixedLivePlanner:
    """Small deterministic planner so live E2E isolates provider integration."""

    async def create_script(self, brief, platform):
        topic = str(brief.get("topic") or "AI agent")
        return {
            "title": topic,
            "hook": "A quick visual demo",
            "body": "A clean product-style scene demonstrates the concept.",
            "cta": "Learn more",
            "narration": f"A short demonstration of {topic}.",
            "target_duration_seconds": 2,
        }

    async def create_storyboard(self, script, platform):
        return [
            StoryboardShot(
                shot_id="live-shot-1",
                narration=str(script["narration"]),
                visual_prompt=(
                    "A clean cinematic product-style shot of a glowing AI "
                    "workflow diagram on a dark studio desk, subtle camera "
                    "push-in, realistic lighting, no text, no logos"
                ),
                duration_seconds=2,
            )
        ]


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


async def main() -> None:
    if os.getenv("RUN_LIVE_MULTIMODAL_E2E") != "1":
        raise RuntimeError(
            "live E2E is disabled; set RUN_LIVE_MULTIMODAL_E2E=1 explicitly"
        )

    output_dir = os.getenv(
        "MULTIMODAL_ARTIFACT_DIR",
        "backend/runtime/multimodal-live-e2e",
    )
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    video = RunwayVideoGenerator(
        api_secret=required("RUNWAYML_API_SECRET"),
        output_dir=output_dir,
        api_base=os.getenv(
            "RUNWAYML_API_BASE",
            "https://api.dev.runwayml.com",
        ),
        api_version=os.getenv("RUNWAYML_API_VERSION", "2024-11-06"),
        model=os.getenv("RUNWAYML_MODEL", "gen4.5"),
        ratio=os.getenv("RUNWAYML_RATIO", "720:1280"),
        poll_interval_seconds=5,
    )
    tts = ElevenLabsTTSGenerator(
        api_key=required("ELEVENLABS_API_KEY"),
        voice_id=required("ELEVENLABS_VOICE_ID"),
        output_dir=output_dir,
        api_base=os.getenv(
            "ELEVENLABS_API_BASE",
            "https://api.elevenlabs.io",
        ),
        model_id=os.getenv(
            "ELEVENLABS_MODEL_ID",
            "eleven_multilingual_v2",
        ),
    )
    assembler = FFmpegVideoAssembler(
        output_dir=output_dir,
        ffmpeg_bin=os.getenv("FFMPEG_BIN", "ffmpeg"),
        render_subtitles=True,
    )

    artifact_store = None
    if os.getenv("RUN_LIVE_MINIO_E2E") == "1":
        artifact_store = MinIOArtifactStore(
            endpoint=required("MINIO_ENDPOINT"),
            access_key=required("MINIO_ACCESS_KEY"),
            secret_key=required("MINIO_SECRET_KEY"),
            bucket=os.getenv("MULTIMODAL_ARTIFACT_BUCKET", "videos"),
            cache_dir=output_dir,
            secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
        )

    media = ProductionMediaToolkit(
        video_generator=video,
        tts_generator=tts,
        assembler=assembler,
        artifact_store=artifact_store,
    )

    judge = None
    if os.getenv("RUN_LIVE_MULTIMODAL_JUDGE") == "1":
        judge = OpenAIMultimodalJudge(
            api_key=required("OPENAI_API_KEY"),
            model=os.getenv("MULTIMODAL_JUDGE_MODEL", "gpt-5.6-luna"),
            ffmpeg_bin=os.getenv("FFMPEG_BIN", "ffmpeg"),
            sample_count=2,
        )

    evaluator = MultimodalEvaluationHarness(
        ffprobe_bin=os.getenv("FFPROBE_BIN", "ffprobe"),
        judge=judge,
    )
    agent = MultimodalContentProductionAgent(
        planner=FixedLivePlanner(),
        media_toolkit=media,
        evaluator=evaluator,
        checkpoint_store=InMemoryCheckpointStore(),
        require_human_approval=False,
        max_retries=1,
        retry_backoff_seconds=1.0,
        max_parallel_shots=1,
    )

    state = await agent.run(
        brief={"topic": os.getenv("LIVE_E2E_TOPIC", "multimodal AI agent")},
        platform="tiktok",
        job_id="live-multimodal-e2e",
    )

    if state.final_video is None or state.quality_report is None:
        raise RuntimeError("live E2E finished without final video/evaluation")
    if not state.quality_report.passed:
        raise RuntimeError(
            "live E2E failed quality gate: "
            + json.dumps(
                {
                    "score": state.quality_report.score,
                    "issues": state.quality_report.issues,
                },
                ensure_ascii=False,
            )
        )

    recovery = None
    if artifact_store is not None:
        final_path = Path(state.final_video.uri)
        original_hash = hashlib.sha256(final_path.read_bytes()).hexdigest()
        durable_uri = state.final_video.metadata.get("durable_uri")
        if not durable_uri:
            raise RuntimeError(
                "MinIO E2E enabled but final artifact has no durable_uri"
            )

        final_path.unlink()
        if final_path.exists():
            raise RuntimeError(
                "failed to delete local final artifact before recovery test"
            )

        recovered = await artifact_store.materialize(state.final_video)
        recovered_path = Path(recovered.uri)
        recovered_hash = hashlib.sha256(recovered_path.read_bytes()).hexdigest()
        if recovered_hash != original_hash:
            raise RuntimeError("recovered MinIO artifact hash does not match original")
        state.final_video = recovered
        recovery = {
            "durable_uri": durable_uri,
            "recovered_path": str(recovered_path),
            "sha256": recovered_hash,
            "passed": True,
        }

    summary = {
        "status": state.status.value,
        "final_video": state.final_video.uri,
        "durable_uri": state.final_video.metadata.get("durable_uri"),
        "quality_score": state.quality_report.score,
        "quality_issues": state.quality_report.issues,
        "judge": state.quality_report.metadata.get("judge"),
        "recovery": recovery,
    }

    report_path = Path(output_dir) / "live_e2e_report.json"
    report_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
