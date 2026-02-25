"""
Dashboard API (Real data)

为前端策略进化看板提供可视化数据（基于数据库聚合）。
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.api.deps import get_current_active_user
from app.models.user import User, UserRole
from app.ml.training.schemas import GenerationTrace, Outcome

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


def _date_start(days: int) -> datetime:
    return datetime.utcnow() - timedelta(days=max(days, 1))


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def _quantiles(values: List[float]) -> Tuple[float, float, float]:
    """返回 q1/median/q3（简单实现，values 可为空）。"""
    if not values:
        return 0.0, 0.0, 0.0
    xs = sorted(values)
    n = len(xs)
    def pick(p: float) -> float:
        idx = int(round((n - 1) * p))
        return xs[max(0, min(n - 1, idx))]
    return pick(0.25), pick(0.50), pick(0.75)


@router.get("/dashboard/thompson-sampling/history")
async def get_thompson_history(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """返回 Thompson Sampling 的臂选择历史（用 policy_id 近似臂；若缺失则降级为 model_id）。"""
    start = _date_start(days)
    # 取 top4 arms
    arm_col = GenerationTrace.policy_id
    top_stmt = (
        select(arm_col, func.count(GenerationTrace.id).label("cnt"))
        .where(GenerationTrace.created_at >= start)
        .group_by(arm_col)
        .order_by(func.count(GenerationTrace.id).desc())
        .limit(8)
    )
    if current_user.role != UserRole.ADMIN:
        top_stmt = top_stmt.where(GenerationTrace.constraints["user_id"].astext == str(current_user.id))
    top = (await db.execute(top_stmt)).all()
    arms_raw = [r[0] for r in top if r[0]]
    if not arms_raw:
        arm_col = GenerationTrace.model_id
        top_stmt = (
            select(arm_col, func.count(GenerationTrace.id).label("cnt"))
            .where(GenerationTrace.created_at >= start)
            .group_by(arm_col)
            .order_by(func.count(GenerationTrace.id).desc())
            .limit(8)
        )
        if current_user.role != UserRole.ADMIN:
            top_stmt = top_stmt.where(GenerationTrace.constraints["user_id"].astext == str(current_user.id))
        top = (await db.execute(top_stmt)).all()
        arms_raw = [r[0] for r in top if r[0]]

    # 固定输出 key，附带 mapping 说明
    keys = ["hook_focus", "cta_focus", "story_focus", "balanced"]
    mapping = {keys[i]: (arms_raw[i] if i < len(arms_raw) else None) for i in range(4)}

    # 聚合按日
    day = func.date_trunc("day", GenerationTrace.created_at).label("day")
    stmt = (
        select(day, arm_col, func.count(GenerationTrace.id).label("cnt"))
        .where(GenerationTrace.created_at >= start)
        .group_by(day, arm_col)
        .order_by(day.asc())
    )
    if current_user.role != UserRole.ADMIN:
        stmt = stmt.where(GenerationTrace.constraints["user_id"].astext == str(current_user.id))
    rows = (await db.execute(stmt)).all()

    by_day: Dict[str, Dict[str, int]] = {}
    for d, arm, cnt in rows:
        label = d.strftime("%m-%d") if hasattr(d, "strftime") else str(d)
        by_day.setdefault(label, {})
        by_day[label][arm or "unknown"] = int(cnt)

    history = []
    for label in sorted(by_day.keys()):
        counts = by_day[label]
        total = sum(counts.values())
        arms = {}
        for k in keys:
            raw = mapping.get(k)
            arms[k] = round(_safe_div(counts.get(raw, 0), total), 4) if raw else 0.0
        history.append({"time": label, "arms": arms, "arms_meta": mapping})

    return {"days": days, "history": history}


@router.get("/dashboard/reward/trends")
async def get_reward_trends(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """返回奖励趋势数据（真实世界/质量/综合）+ 延迟（真实聚合）"""
    start = _date_start(days)

    # real_world: Outcome.engagement_score 均值
    day = func.date_trunc("day", GenerationTrace.created_at).label("day")
    stmt = (
        select(
            day,
            func.avg(Outcome.engagement_score).label("engagement"),
            func.avg(Outcome.completion_rate).label("completion"),
            func.avg(GenerationTrace.generation_time_ms).label("latency_ms"),
        )
        .select_from(GenerationTrace)
        .join(Outcome, Outcome.trace_id == GenerationTrace.id, isouter=True)
        .where(GenerationTrace.created_at >= start)
        .group_by(day)
        .order_by(day.asc())
    )
    if current_user.role != UserRole.ADMIN:
        stmt = stmt.where(GenerationTrace.constraints["user_id"].astext == str(current_user.id))
    rows = (await db.execute(stmt)).all()

    trends: List[Dict[str, Any]] = []
    for d, engagement, completion, latency_ms in rows:
        label = d.strftime("%m-%d") if hasattr(d, "strftime") else str(d)
        real_world = float(engagement or 0.0)
        quality = float((completion or 0.0) * 100.0)  # completion_rate 0-1 -> 0-100
        blended = real_world * 0.6 + quality * 0.4
        # 简化 CI：用样本不足时返回同值
        ci = 0.0
        trends.append(
            {
                "time": label,
                "real_world": round(real_world, 2),
                "quality": round(quality, 2),
                "blended": round(blended, 2),
                "ci_lower": round(blended - ci, 2),
                "ci_upper": round(blended + ci, 2),
                "latency_ms": int(latency_ms) if latency_ms is not None else None,
            }
        )

    return {"days": days, "trends": trends}


@router.get("/dashboard/quality/distribution")
async def get_quality_distribution(
    window: str = Query(default="weekly", pattern="^(daily|weekly|monthly)$"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """返回内容质量分数分布（用 Outcome.completion_rate/engagement_score 近似质量）。"""
    # 拉取近 90 天 outcomes
    start = datetime.utcnow() - timedelta(days=90)
    stmt = (
        select(GenerationTrace.created_at, Outcome.engagement_score, Outcome.completion_rate)
        .select_from(GenerationTrace)
        .join(Outcome, Outcome.trace_id == GenerationTrace.id, isouter=True)
        .where(GenerationTrace.created_at >= start)
        .order_by(GenerationTrace.created_at.asc())
    )
    if current_user.role != UserRole.ADMIN:
        stmt = stmt.where(GenerationTrace.constraints["user_id"].astext == str(current_user.id))
    rows = (await db.execute(stmt)).all()

    # 分桶
    buckets: Dict[str, List[float]] = {}
    for created_at, engagement_score, completion_rate in rows:
        if created_at is None:
            continue
        if window == "daily":
            k = created_at.strftime("%m-%d")
        elif window == "weekly":
            k = f"{created_at.strftime('%Y')}-W{created_at.isocalendar().week:02d}"
        else:
            k = created_at.strftime("%Y-%m")

        # 质量代理：completion_rate*100 优先，否则用 engagement_score
        if completion_rate is not None:
            score = float(completion_rate) * 100.0
        else:
            score = float(engagement_score or 0.0)
        buckets.setdefault(k, []).append(score)

    distribution = []
    for k in sorted(buckets.keys())[-12:]:
        xs = buckets[k]
        q1, med, q3 = _quantiles(xs)
        distribution.append(
            {
                "bucket": k,
                "min": round(min(xs), 2) if xs else 0.0,
                "q1": round(q1, 2),
                "median": round(med, 2),
                "q3": round(q3, 2),
                "max": round(max(xs), 2) if xs else 0.0,
                "n": len(xs),
            }
        )

    return {"window": window, "distribution": distribution}


@router.get("/dashboard/ab-comparison")
async def get_ab_comparison(
    baseline_date: str,
    current_date: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """返回策略优化前后的对比数据（按日期范围对比 Outcome + 生成延迟）。"""
    # 简化：按 day 分界，baseline_date~baseline_date+1d vs current_date~current_date+1d
    base_start = datetime.fromisoformat(baseline_date)
    base_end = base_start + timedelta(days=1)
    cur_start = datetime.fromisoformat(current_date)
    cur_end = cur_start + timedelta(days=1)

    async def agg(start: datetime, end: datetime) -> Dict[str, Any]:
        stmt = (
            select(
                func.avg(Outcome.engagement_score).label("engagement"),
                func.avg(Outcome.completion_rate).label("completion"),
                func.avg(GenerationTrace.generation_time_ms).label("latency_ms"),
                func.count(GenerationTrace.id).label("n"),
            )
            .select_from(GenerationTrace)
            .join(Outcome, Outcome.trace_id == GenerationTrace.id, isouter=True)
            .where(GenerationTrace.created_at >= start, GenerationTrace.created_at < end)
        )
        if current_user.role != UserRole.ADMIN:
            stmt = stmt.where(GenerationTrace.constraints["user_id"].astext == str(current_user.id))
        row = (await db.execute(stmt)).one()
        engagement = float(row.engagement or 0.0)
        completion = float(row.completion or 0.0) * 100.0
        latency = int(row.latency_ms) if row.latency_ms is not None else 0
        return {
            "engagement_rate": engagement / 100.0,  # 以 0-1 输出，便于前端展示百分比
            "quality_score": completion,
            "generation_latency_ms": latency,
            "n": int(row.n or 0),
        }

    baseline = await agg(base_start, base_end)
    current = await agg(cur_start, cur_end)

    return {
        "baseline_date": baseline_date,
        "current_date": current_date,
        "baseline": baseline,
        "current": current,
        "improvements": {
            "engagement_rate_pct": round(_safe_div((current["engagement_rate"] - baseline["engagement_rate"]), baseline["engagement_rate"]) * 100, 2)
            if baseline["engagement_rate"] else 0.0,
            "quality_score_pct": round(_safe_div((current["quality_score"] - baseline["quality_score"]), baseline["quality_score"]) * 100, 2)
            if baseline["quality_score"] else 0.0,
            "generation_latency_pct": round(_safe_div((current["generation_latency_ms"] - baseline["generation_latency_ms"]), baseline["generation_latency_ms"]) * 100, 2)
            if baseline["generation_latency_ms"] else 0.0,
        },
    }
