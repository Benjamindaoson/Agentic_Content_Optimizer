"""Task API for multimodal content production."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_active_user
from app.engine.agents.workflow.multimodal_persistence import (
    serialize_production_state,
)
from app.engine.agents.workflow.multimodal_service import (
    get_multimodal_checkpoint_store,
    get_multimodal_production_service,
)
from app.models.user import User, UserRole


router = APIRouter(
    prefix="/api/v1/multimodal-production",
    tags=["multimodal-production"],
)


class SubmitProductionJobRequest(BaseModel):
    brief: Dict[str, Any]
    platform: str = Field(default="douyin", min_length=1, max_length=32)
    job_id: Optional[str] = Field(default=None, max_length=64)


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
        job_id = await service.submit(
            brief=request.brief,
            platform=request.platform,
            owner_id=str(current_user.id),
            job_id=request.job_id,
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
