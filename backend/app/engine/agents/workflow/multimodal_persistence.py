"""Persistence helpers for multimodal production checkpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Optional

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.multimodal_production import MultimodalProductionJob

from .multimodal_content_workflow import (
    AssetKind,
    MediaAsset,
    ProductionStage,
    ProductionState,
    ProductionStatus,
    QualityReport,
    StoryboardShot,
)


def serialize_production_state(state: ProductionState) -> Dict[str, Any]:
    """Convert a ProductionState into JSON-safe data."""

    return {
        "job_id": state.job_id,
        "brief": state.brief,
        "platform": state.platform,
        "status": state.status.value,
        "stage": state.stage.value,
        "script": state.script,
        "storyboard": [asdict(shot) for shot in state.storyboard],
        "visual_assets": {
            key: {
                **asdict(asset),
                "kind": asset.kind.value,
            }
            for key, asset in state.visual_assets.items()
        },
        "voice_asset": (
            {
                **asdict(state.voice_asset),
                "kind": state.voice_asset.kind.value,
            }
            if state.voice_asset is not None
            else None
        ),
        "final_video": (
            {
                **asdict(state.final_video),
                "kind": state.final_video.kind.value,
            }
            if state.final_video is not None
            else None
        ),
        "quality_report": (
            asdict(state.quality_report) if state.quality_report is not None else None
        ),
        "approved": state.approved,
        "publish_result": state.publish_result,
        "attempts": state.attempts,
        "errors": state.errors,
        "metadata": state.metadata,
    }


def _asset_from_dict(data: Optional[Dict[str, Any]]) -> Optional[MediaAsset]:
    if data is None:
        return None
    return MediaAsset(
        asset_id=str(data["asset_id"]),
        kind=AssetKind(data["kind"]),
        uri=str(data["uri"]),
        provider=str(data["provider"]),
        metadata=dict(data.get("metadata") or {}),
    )


def deserialize_production_state(data: Dict[str, Any]) -> ProductionState:
    """Reconstruct ProductionState from persisted JSON."""

    storyboard = [
        StoryboardShot(
            shot_id=str(shot["shot_id"]),
            narration=str(shot.get("narration") or ""),
            visual_prompt=str(shot.get("visual_prompt") or ""),
            duration_seconds=float(shot.get("duration_seconds") or 0.0),
            metadata=dict(shot.get("metadata") or {}),
        )
        for shot in data.get("storyboard", [])
    ]

    visual_assets = {
        str(key): _asset_from_dict(asset)
        for key, asset in (data.get("visual_assets") or {}).items()
    }

    quality_data = data.get("quality_report")
    quality_report = (
        QualityReport(
            score=float(quality_data.get("score") or 0.0),
            passed=bool(quality_data.get("passed")),
            issues=list(quality_data.get("issues") or []),
            metadata=dict(quality_data.get("metadata") or {}),
        )
        if quality_data
        else None
    )

    return ProductionState(
        job_id=str(data["job_id"]),
        brief=dict(data.get("brief") or {}),
        platform=str(data.get("platform") or "douyin"),
        status=ProductionStatus(data.get("status") or ProductionStatus.PENDING.value),
        stage=ProductionStage(data.get("stage") or ProductionStage.PLAN_SCRIPT.value),
        script=dict(data.get("script") or {}),
        storyboard=storyboard,
        visual_assets={
            key: asset for key, asset in visual_assets.items() if asset is not None
        },
        voice_asset=_asset_from_dict(data.get("voice_asset")),
        final_video=_asset_from_dict(data.get("final_video")),
        quality_report=quality_report,
        approved=bool(data.get("approved")),
        publish_result=data.get("publish_result"),
        attempts=dict(data.get("attempts") or {}),
        errors=list(data.get("errors") or []),
        metadata=dict(data.get("metadata") or {}),
    )


class SQLAlchemyCheckpointStore:
    """PostgreSQL-backed checkpoint store using the project's AsyncSession."""

    def __init__(self, session_factory=AsyncSessionLocal) -> None:
        self.session_factory = session_factory

    async def load(self, job_id: str) -> Optional[ProductionState]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(MultimodalProductionJob).where(
                    MultimodalProductionJob.job_id == job_id
                )
            )
            record = result.scalar_one_or_none()
            if record is None:
                return None
            return deserialize_production_state(record.state_json)

    async def save(self, state: ProductionState) -> None:
        payload = serialize_production_state(state)
        owner_id = state.metadata.get("owner_id")

        async with self.session_factory() as session:
            result = await session.execute(
                select(MultimodalProductionJob).where(
                    MultimodalProductionJob.job_id == state.job_id
                )
            )
            record = result.scalar_one_or_none()

            if record is None:
                record = MultimodalProductionJob(
                    job_id=state.job_id,
                    owner_id=str(owner_id) if owner_id is not None else None,
                    platform=state.platform,
                    status=state.status.value,
                    stage=state.stage.value,
                    state_json=payload,
                    version=1,
                )
                session.add(record)
            else:
                record.owner_id = (
                    str(owner_id) if owner_id is not None else record.owner_id
                )
                record.platform = state.platform
                record.status = state.status.value
                record.stage = state.stage.value
                record.state_json = payload
                record.version = int(record.version or 0) + 1

            await session.commit()
