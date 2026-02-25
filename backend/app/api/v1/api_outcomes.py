"""
Outcome API

用于回填/同步真实效果指标，形成闭环数据。
Outcome → Thompson Sampling 闭环已打通。
"""

import uuid
import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.models.user import User, UserRole
from app.ml.training.schemas import GenerationTrace, Outcome


router = APIRouter(prefix="/api/v1/outcomes", tags=["outcomes"])


class OutcomeUpsertRequest(BaseModel):
    trace_id: str = Field(..., description="GenerationTrace.id")
    time_bucket: str = Field(default="24h", description="时间窗口: 1h/6h/24h/7d")
    measured_at: Optional[datetime] = None

    impressions: int = 0
    clicks: int = 0
    read_time_avg: float = 0.0
    completion_rate: float = 0.0

    likes: int = 0
    comments: int = 0
    saves: int = 0
    shares: int = 0
    follows: int = 0
    dms: int = 0
    purchases: int = 0


def _calc_engagement_score(req: OutcomeUpsertRequest) -> float:
    # 简单可解释的综合互动分（可后续替换为更科学口径）
    score = (
        req.likes * 1.0
        + req.comments * 2.0
        + req.saves * 2.5
        + req.shares * 2.0
        + req.follows * 3.0
        + req.dms * 3.0
        + req.purchases * 5.0
    )
    # 归一化到一个大致可读范围
    denom = max(req.impressions, 1)
    return float(score / denom * 1000.0)


async def _assert_trace_access(db: AsyncSession, trace_id: str, user: User) -> GenerationTrace:
    result = await db.execute(select(GenerationTrace).where(GenerationTrace.id == trace_id))
    trace = result.scalar_one_or_none()
    if not trace:
        raise HTTPException(status_code=404, detail="trace 不存在")
    if user.role == UserRole.ADMIN:
        return trace

    constraints = getattr(trace, "constraints", None) or {}
    owner = constraints.get("user_id")
    if owner is None:
        raise HTTPException(status_code=403, detail="该 trace 未绑定 owner，普通用户不可回填")
    if str(owner) != str(user.id):
        raise HTTPException(status_code=403, detail="无权限回填该 trace")
    return trace


@router.post("/upsert")
async def upsert_outcome(
    request: OutcomeUpsertRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    trace = await _assert_trace_access(db, request.trace_id, current_user)

    measured_at = request.measured_at or datetime.utcnow()
    engagement_score = _calc_engagement_score(request)

    # 幂等 upsert：按 (trace_id, time_bucket) 查找
    stmt = select(Outcome).where(
        Outcome.trace_id == request.trace_id,
        Outcome.time_bucket == request.time_bucket,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing:
        existing.impressions = request.impressions
        existing.clicks = request.clicks
        existing.click_rate = float(request.clicks / request.impressions) if request.impressions else 0.0
        existing.read_time_avg = request.read_time_avg
        existing.completion_rate = request.completion_rate
        existing.likes = request.likes
        existing.comments = request.comments
        existing.saves = request.saves
        existing.shares = request.shares
        existing.follows = request.follows
        existing.dms = request.dms
        existing.purchases = request.purchases
        existing.engagement_score = engagement_score
        existing.measured_at = measured_at
        outcome = existing
    else:
        outcome = Outcome(
            id=str(uuid.uuid4()),
            trace_id=request.trace_id,
            impressions=request.impressions,
            clicks=request.clicks,
            click_rate=float(request.clicks / request.impressions) if request.impressions else 0.0,
            read_time_avg=request.read_time_avg,
            completion_rate=request.completion_rate,
            likes=request.likes,
            comments=request.comments,
            saves=request.saves,
            shares=request.shares,
            follows=request.follows,
            dms=request.dms,
            purchases=request.purchases,
            engagement_score=engagement_score,
            time_bucket=request.time_bucket,
            measured_at=measured_at,
        )
        db.add(outcome)

    await db.flush()

    # ===== Outcome → Thompson Sampling 闭环 =====
    rl_synced = False
    if engagement_score > 0 and request.time_bucket in ("24h", "7d"):
        try:
            from app.ml.rl.outcome_reward_bridge import sync_outcome_to_rl
            rl_synced = await sync_outcome_to_rl(
                db=db,
                trace_id=request.trace_id,
                engagement_score=engagement_score,
                time_bucket=request.time_bucket,
            )
            if rl_synced:
                outcome.rl_synced = 1
                outcome.rl_synced_at = datetime.utcnow()
                await db.flush()
        except Exception as e:
            logger.warning(f"RL sync failed (non-blocking): {e}")

    return {
        "success": True,
        "trace_id": request.trace_id,
        "time_bucket": request.time_bucket,
        "engagement_score": outcome.engagement_score,
        "rl_synced": rl_synced,
        "measured_at": outcome.measured_at.isoformat() if outcome.measured_at else None,
    }

