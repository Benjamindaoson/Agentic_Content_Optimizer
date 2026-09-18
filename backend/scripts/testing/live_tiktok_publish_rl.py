"""Credentialed TikTok publish -> metrics -> RL validation.

This script performs an external side effect. It is fail-closed and only runs
when RUN_LIVE_TIKTOK_E2E=1 is explicitly set. The default privacy is SELF_ONLY.
For a complete metrics loop TikTok must return a post ID, which normally
requires a publicly viewable post and the necessary app audit/scopes.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.core.redis import redis_client
from app.engine.agents.workflow.multimodal_content_workflow import (
    AssetKind,
    MediaAsset,
    ProductionState,
    QualityReport,
    StoryboardShot,
)
from app.engine.agents.workflow.multimodal_publishers import TikTokContentPublisher
from app.ml.rl.action_space import action_space
from app.ml.rl.outcome_reward_bridge import sync_outcome_to_rl
from app.ml.rl.thompson_persistence import load_selector
from app.ml.rl.thompson_sampling import ThompsonSamplingConfig
from app.ml.training.schemas import GenerationTrace, Outcome


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def artifact_root() -> Path:
    return Path(
        os.getenv(
            "MULTIMODAL_ARTIFACT_DIR",
            "backend/runtime/multimodal-live-e2e",
        )
    )


def find_final_video() -> Path:
    configured = os.getenv("LIVE_TIKTOK_VIDEO_PATH", "").strip()
    if configured:
        path = Path(configured)
    else:
        path = artifact_root() / "live-multimodal-e2e" / "assembly" / "final.mp4"
    if not path.exists():
        raise FileNotFoundError(f"live E2E final video not found: {path}")
    return path


async def ensure_tables() -> None:
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


async def create_trace() -> str:
    trace_id = f"live-tiktok-{uuid.uuid4().hex[:16]}"
    async with AsyncSessionLocal() as db:
        db.add(
            GenerationTrace(
                id=trace_id,
                platform="tiktok",
                persona="integration-test",
                niche="ai",
                topic="multimodal content production agent",
                prompt="Credentialed end-to-end production hardening validation",
                system_prompt="",
                constraints={
                    "user_id": 999001,
                    "content_style": "integration-test",
                    "target_audience": "developer",
                },
                retrieved_context=[],
                output="Generated multimodal E2E video",
                title="Multimodal Agent E2E",
                tags=["ai", "agent"],
                cover_text="",
                cta="",
                policy_id="H01-B01-C01",
                model_id="live-e2e",
                adapter_id="runway-elevenlabs-ffmpeg",
                generation_time_ms=None,
                token_count=None,
            )
        )
        await db.commit()
    return trace_id


async def wait_for_publish(
    publisher: TikTokContentPublisher,
    publish_id: str,
) -> dict:
    timeout_seconds = int(os.getenv("TIKTOK_STATUS_TIMEOUT_SECONDS", "360"))
    poll_seconds = int(os.getenv("TIKTOK_STATUS_POLL_SECONDS", "10"))
    deadline = time.monotonic() + timeout_seconds
    last = {}

    while time.monotonic() < deadline:
        last = await publisher.fetch_publish_status(publish_id)
        status = str(last.get("status") or "")
        if status == "FAILED":
            raise RuntimeError(
                "TikTok publish failed: "
                + str(last.get("fail_reason") or last)
            )
        if status == "PUBLISH_COMPLETE":
            return last
        await asyncio.sleep(poll_seconds)

    raise TimeoutError(
        f"TikTok publish did not complete within {timeout_seconds}s: {last}"
    )


async def wait_for_metrics(
    publisher: TikTokContentPublisher,
    video_id: str,
) -> dict:
    timeout_seconds = int(os.getenv("TIKTOK_METRICS_TIMEOUT_SECONDS", "180"))
    poll_seconds = int(os.getenv("TIKTOK_METRICS_POLL_SECONDS", "15"))
    deadline = time.monotonic() + timeout_seconds
    last_error = None

    while time.monotonic() < deadline:
        try:
            return await publisher.query_video_metrics(video_id)
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(poll_seconds)

    raise RuntimeError(
        f"TikTok metrics unavailable after {timeout_seconds}s: {last_error}"
    )


async def verify_rl_update(
    *,
    trace_id: str,
    metrics: dict,
) -> dict:
    views = max(int(metrics.get("view_count") or 0), 1)
    likes = int(metrics.get("like_count") or 0)
    comments = int(metrics.get("comment_count") or 0)
    shares = int(metrics.get("share_count") or 0)
    engagement_score = (
        likes * 1.0 + comments * 2.0 + shares * 2.0
    ) / views * 1000.0

    await redis_client.connect()
    try:
        async with AsyncSessionLocal() as db:
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
                time_bucket="24h",
                measured_at=datetime.utcnow(),
                rl_synced=0,
            )
            db.add(outcome)
            await db.flush()

            synced = await sync_outcome_to_rl(
                db=db,
                trace_id=trace_id,
                engagement_score=engagement_score,
                time_bucket="24h",
            )
            outcome.rl_synced = 1 if synced else 0
            outcome.rl_synced_at = datetime.utcnow() if synced else None
            await db.commit()
            outcome_id = outcome.id

        selector = await load_selector(
            user_id=999001,
            n_hooks=len(action_space.HOOKS),
            n_bodies=len(action_space.BODIES),
            n_ctas=len(action_space.CTAS),
            config=ThompsonSamplingConfig(
                use_hierarchical=True,
                temperature=1.0,
                min_pulls=3,
            ),
        )
        arm = selector.triplet_stats[(0, 0, 0)]
        if not synced or arm.n_pulls < 1:
            raise RuntimeError(
                "platform metrics were stored but RL selector was not updated"
            )

        return {
            "outcome_id": outcome_id,
            "engagement_score": engagement_score,
            "rl_synced": synced,
            "arm": {
                "action": "H01-B01-C01",
                "n_pulls": arm.n_pulls,
                "sum_reward": arm.sum_reward,
            },
        }
    finally:
        await redis_client.close()


async def main() -> None:
    if os.getenv("RUN_LIVE_TIKTOK_E2E") != "1":
        raise RuntimeError(
            "TikTok live E2E disabled; set RUN_LIVE_TIKTOK_E2E=1 explicitly"
        )

    video_path = find_final_video()
    privacy = os.getenv("TIKTOK_LIVE_PRIVACY", "SELF_ONLY").strip()
    access_token = required("TIKTOK_ACCESS_TOKEN")

    trace_id = await create_trace()
    state = ProductionState(
        job_id="live-tiktok-p3",
        brief={"purpose": "credentialed integration validation"},
        platform="tiktok",
        script={
            "title": "",
            "hook": "",
            "body": "",
            "cta": "",
            "narration": "Multimodal content production integration test.",
        },
        storyboard=[
            StoryboardShot(
                shot_id="live-shot-1",
                narration="Multimodal content production integration test.",
                visual_prompt="AI workflow visualization",
                duration_seconds=2,
            )
        ],
        final_video=MediaAsset(
            asset_id="live-final",
            kind=AssetKind.FINAL_VIDEO,
            uri=str(video_path),
            provider="ffmpeg",
        ),
        quality_report=QualityReport(
            score=1.0,
            passed=True,
            issues=[],
        ),
        approved=True,
        metadata={
            "trace_id": trace_id,
            "explicit_user_consent": True,
        },
    )

    publisher = TikTokContentPublisher(
        access_token=access_token,
        api_base=os.getenv(
            "TIKTOK_API_BASE",
            "https://open.tiktokapis.com",
        ),
        privacy_level=privacy,
    )

    publish_result = await publisher.publish(
        state,
        caption="",
        brand_content_toggle=False,
        brand_organic_toggle=False,
    )
    publish_id = str(publish_result["publish_id"])
    status_result = await wait_for_publish(publisher, publish_id)

    post_ids = [
        str(item)
        for item in status_result.get("publicaly_available_post_id") or []
    ]
    if not post_ids:
        report = {
            "publish_id": publish_id,
            "privacy_level": privacy,
            "publish_status": status_result,
            "trace_id": trace_id,
            "metrics": None,
            "rl": None,
            "blocked_at": "public_post_id",
            "reason": (
                "TikTok did not return a publicly available post ID. "
                "For SELF_ONLY/unaudited clients this is expected; a public, "
                "audited Direct Post plus video.list scope is required for "
                "the real metrics -> RL leg."
            ),
        }
        report_path = artifact_root() / "p3_tiktok_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        raise RuntimeError(report["reason"])

    video_id = post_ids[0]
    metrics = await wait_for_metrics(publisher, video_id)
    rl_result = await verify_rl_update(
        trace_id=trace_id,
        metrics=metrics,
    )

    report = {
        "publish_id": publish_id,
        "privacy_level": privacy,
        "publish_status": status_result,
        "video_id": video_id,
        "trace_id": trace_id,
        "metrics": metrics,
        "rl": rl_result,
        "blocked_at": None,
    }
    report_path = artifact_root() / "p3_tiktok_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
