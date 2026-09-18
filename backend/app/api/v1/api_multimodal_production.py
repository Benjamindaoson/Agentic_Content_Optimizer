"""Task API for multimodal content production."""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.config import get_settings
from app.core.database import get_db
from app.engine.agents.workflow.multimodal_persistence import (
    serialize_production_state,
)
from app.engine.agents.workflow.multimodal_publishers import TikTokContentPublisher
from app.engine.agents.workflow.multimodal_service import (
    get_multimodal_artifact_store,
    get_multimodal_checkpoint_store,
    get_multimodal_production_service,
)
from app.ml.rl.outcome_reward_bridge import sync_outcome_to_rl
from app.models.user import User, UserRole


router = APIRouter(
    prefix="/api/v1/multimodal-production",
    tags=["multimodal-production"],
)


class SubmitProductionJobRequest(BaseModel):
    brief: Dict[str, Any]
    platform: str = Field(default="douyin", min_length=1, max_length=32)
    job_id: Optional[str] = Field(default=None, max_length=64)
    trace_id: Optional[str] = Field(default=None, max_length=128)


class TikTokPublishRequest(BaseModel):
    privacy_level: Optional[str] = Field(default=None, max_length=64)
    caption: Optional[str] = Field(default=None, max_length=2200)
    brand_content_toggle: bool = False
    brand_organic_toggle: bool = False


class TikTokFeedbackRequest(BaseModel):
    video_id: str = Field(..., min_length=1, max_length=128)
    time_bucket: str = Field(default="24h", max_length=16)


def _assert_owner(state, user: User) -> None:
    if user.role == UserRole.ADMIN:
        return
    owner_id = state.metadata.get("owner_id")
    if owner_id is None or str(owner_id) != str(user.id):
        raise HTTPException(status_code=403, detail="无权访问该任务")


def _get_service_or_503():
    try:
        return get_multimodal_production_service()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def submit_job(
    request: SubmitProductionJobRequest,
    current_user: User = Depends(get_current_active_user),
):
    service = _get_service_or_503()
    try:
        metadata = {}
        if request.trace_id:
            metadata["trace_id"] = request.trace_id
        job_id = await service.submit(
            brief=request.brief,
            platform=request.platform,
            owner_id=str(current_user.id),
            job_id=request.job_id,
            metadata=metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "job_id": job_id,
        "status": "accepted",
    }


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
):
    state = await get_multimodal_checkpoint_store().load(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    _assert_owner(state, current_user)
    return serialize_production_state(state)


@router.post("/jobs/{job_id}/approve", status_code=status.HTTP_202_ACCEPTED)
async def approve_job(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
):
    store = get_multimodal_checkpoint_store()
    state = await store.load(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    _assert_owner(state, current_user)

    service = _get_service_or_503()
    try:
        await service.approve(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {"job_id": job_id, "status": "approved_and_resuming"}


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
):
    store = get_multimodal_checkpoint_store()
    state = await store.load(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    _assert_owner(state, current_user)

    service = _get_service_or_503()
    try:
        cancelled = await service.cancel(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return serialize_production_state(cancelled)


@router.post("/jobs/{job_id}/resume", status_code=status.HTTP_202_ACCEPTED)
async def resume_job(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
):
    store = get_multimodal_checkpoint_store()
    state = await store.load(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    _assert_owner(state, current_user)

    service = _get_service_or_503()
    try:
        await service.resume(job_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {"job_id": job_id, "status": "resuming"}


def _get_tiktok_publisher(privacy_level: Optional[str] = None) -> TikTokContentPublisher:
    settings = get_settings()
    if not settings.TIKTOK_CONTENT_POSTING_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TikTok Content Posting is disabled",
        )
    if not settings.TIKTOK_ACCESS_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TIKTOK_ACCESS_TOKEN is not configured",
        )
    return TikTokContentPublisher(
        access_token=settings.TIKTOK_ACCESS_TOKEN,
        api_base=settings.TIKTOK_API_BASE,
        privacy_level=privacy_level or settings.TIKTOK_PRIVACY_LEVEL,
        artifact_store=get_multimodal_artifact_store(),
    )


@router.post("/jobs/{job_id}/publish/tiktok")
async def publish_tiktok(
    job_id: str,
    request: TikTokPublishRequest,
    current_user: User = Depends(get_current_active_user),
):
    store = get_multimodal_checkpoint_store()
    state = await store.load(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    _assert_owner(state, current_user)

    publisher = _get_tiktok_publisher(request.privacy_level)
    try:
        result = await publisher.publish(
            state,
            caption=request.caption,
            brand_content_toggle=request.brand_content_toggle,
            brand_organic_toggle=request.brand_organic_toggle,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (httpx.HTTPError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    state.publish_result = result
    state.metadata["tiktok_publish_id"] = result.get("publish_id")
    state.metadata["last_publish_result"] = result
    await store.save(state)
    return result


@router.get("/jobs/{job_id}/publish/tiktok/status")
async def tiktok_publish_status(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
):
    store = get_multimodal_checkpoint_store()
    state = await store.load(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    _assert_owner(state, current_user)

    publish_id = state.metadata.get("tiktok_publish_id")
    if not publish_id:
        raise HTTPException(status_code=409, detail="任务尚未提交到 TikTok")

    publisher = _get_tiktok_publisher()
    try:
        result = await publisher.fetch_publish_status(str(publish_id))
    except (httpx.HTTPError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    state.metadata["last_publish_status"] = result
    post_ids = result.get("publicaly_available_post_id") or []
    if post_ids:
        state.metadata["tiktok_post_ids"] = [str(item) for item in post_ids]
    await store.save(state)
    return result


@router.post("/jobs/{job_id}/feedback/tiktok")
async def ingest_tiktok_feedback(
    job_id: str,
    request: TikTokFeedbackRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    store = get_multimodal_checkpoint_store()
    state = await store.load(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    _assert_owner(state, current_user)

    publisher = _get_tiktok_publisher()
    try:
        metrics = await publisher.query_video_metrics(request.video_id)
    except (httpx.HTTPError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    views = max(int(metrics.get("view_count") or 0), 1)
    likes = int(metrics.get("like_count") or 0)
    comments = int(metrics.get("comment_count") or 0)
    shares = int(metrics.get("share_count") or 0)
    engagement_score = (
        likes * 1.0 + comments * 2.0 + shares * 2.0
    ) / views * 1000.0

    trace_id = state.metadata.get("trace_id")
    rl_synced = False
    if trace_id:
        rl_synced = await sync_outcome_to_rl(
            db=db,
            trace_id=str(trace_id),
            engagement_score=engagement_score,
            time_bucket=request.time_bucket,
        )

    feedback = {
        "platform": "tiktok",
        "video_id": request.video_id,
        "metrics": metrics,
        "engagement_score": engagement_score,
        "time_bucket": request.time_bucket,
        "trace_id": trace_id,
        "rl_synced": rl_synced,
    }
    state.metadata["latest_platform_feedback"] = feedback
    await store.save(state)
    return feedback
