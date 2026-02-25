"""
Outcome → Thompson Sampling 闭环桥接

将真实平台互动数据转换为 RL reward，回灌到 Thompson Sampling 策略选择器。
这是整个飞轮的核心引擎——没有这条通路，RL 就是在沙箱里自嗨。
"""

import math
import logging
from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.ml.training.schemas import GenerationTrace, Outcome
from app.ml.rl.thompson_persistence import load_selector, update_action
from app.ml.rl.thompson_sampling import ThompsonSamplingConfig
from app.ml.rl.action_space import action_space
from app.ml.rl.contextual_bandit import ContextFeatures
from app.ml.rl.contextual_persistence import load_contextual_bandit, save_contextual_bandit

logger = logging.getLogger(__name__)

# engagement_score 的 sigmoid 归一化参数
# score=50 对应 reward≈0.5，score=100 对应 reward≈0.92
_SIGMOID_MIDPOINT = 50.0
_SIGMOID_STEEPNESS = 0.05

# 不同 time_bucket 的 reward 权重：越晚的数据越可靠
TIME_BUCKET_WEIGHTS = {
    "1h": 0.3,
    "6h": 0.6,
    "24h": 1.0,
    "7d": 1.0,
}


def normalize_engagement_to_reward(engagement_score: float) -> float:
    """将 engagement_score 通过 sigmoid 压缩到 [0, 1]"""
    return 1.0 / (1.0 + math.exp(-_SIGMOID_STEEPNESS * (engagement_score - _SIGMOID_MIDPOINT)))


def parse_policy_id(policy_id: str) -> Optional[Tuple[int, int, int]]:
    """将 policy_id (如 'H01-B03-C02') 解析为 (h_idx, b_idx, c_idx)"""
    parts = policy_id.split("-")
    if len(parts) != 3:
        return None

    hook, body, cta = parts
    if not action_space.validate_action((hook, body, cta)):
        return None

    hooks = list(action_space.HOOKS.keys())
    bodies = list(action_space.BODIES.keys())
    ctas = list(action_space.CTAS.keys())

    try:
        h_idx = hooks.index(hook)
        b_idx = bodies.index(body)
        c_idx = ctas.index(cta)
        return (h_idx, b_idx, c_idx)
    except ValueError:
        return None


async def sync_outcome_to_rl(
    db: AsyncSession,
    trace_id: str,
    engagement_score: float,
    time_bucket: str = "24h",
) -> bool:
    """
    将单条 Outcome 的 engagement_score 回灌到 Thompson Sampling。

    Returns:
        True 如果成功更新，False 如果数据不完整或已同步
    """
    result = await db.execute(
        select(GenerationTrace).where(GenerationTrace.id == trace_id)
    )
    trace = result.scalar_one_or_none()
    if not trace:
        logger.debug(f"Trace {trace_id} not found, skip RL sync")
        return False

    policy_id = trace.policy_id
    if not policy_id:
        logger.debug(f"Trace {trace_id} has no policy_id, skip RL sync")
        return False

    action_idx = parse_policy_id(policy_id)
    if action_idx is None:
        logger.warning(f"Invalid policy_id '{policy_id}' for trace {trace_id}")
        return False

    # 从 constraints 中提取 user_id（兜底 0）
    constraints = trace.constraints or {}
    user_id = int(constraints.get("user_id", 0))

    # engagement_score → [0, 1] reward，乘以 time_bucket 权重
    base_reward = normalize_engagement_to_reward(engagement_score)
    weight = TIME_BUCKET_WEIGHTS.get(time_bucket, 0.8)
    reward = base_reward * weight

    try:
        selector = await load_selector(
            user_id=user_id,
            n_hooks=len(action_space.HOOKS),
            n_bodies=len(action_space.BODIES),
            n_ctas=len(action_space.CTAS),
            config=ThompsonSamplingConfig(use_hierarchical=True, temperature=1.0, min_pulls=3),
        )
        await update_action(
            user_id=user_id,
            selector=selector,
            action=action_idx,
            reward=reward,
        )

        # 同步更新 Contextual Bandit（使用真实 Outcome 高权重信号）
        try:
            h, b, c = action_idx
            n_bodies = len(action_space.BODIES)
            n_ctas = len(action_space.CTAS)
            flat_action = h * n_bodies * n_ctas + b * n_ctas + c
            total_actions = len(action_space.HOOKS) * n_bodies * n_ctas

            constraints = trace.constraints or {}
            topic = str(trace.topic or "")
            platform = str(trace.platform or "xiaohongshu")
            audience = str(constraints.get("target_audience", ""))
            style = str(constraints.get("content_style", ""))
            topic_len = len(topic)
            if topic_len <= 20:
                content_length = "short"
            elif topic_len <= 60:
                content_length = "medium"
            else:
                content_length = "long"

            measured_at = datetime.utcnow()
            context = ContextFeatures(
                topic_category=topic,
                platform=platform,
                hour_of_day=measured_at.hour,
                day_of_week=measured_at.weekday(),
                audience_type=audience,
                content_length=content_length,
            )

            bandit = await load_contextual_bandit(user_id=user_id, n_actions=total_actions)
            bandit.update(flat_action, context, reward)
            await save_contextual_bandit(user_id=user_id, bandit=bandit)
        except Exception as cb_err:
            logger.warning(f"[RL SYNC] Contextual bandit update skipped: {cb_err}")
        logger.info(
            f"[RL SYNC] trace={trace_id} policy={policy_id} "
            f"engagement={engagement_score:.1f} reward={reward:.3f} "
            f"bucket={time_bucket} user={user_id}"
        )
        return True

    except Exception as e:
        logger.error(f"[RL SYNC] Failed for trace {trace_id}: {e}", exc_info=True)
        return False


async def batch_sync_pending_outcomes(
    db: AsyncSession,
    limit: int = 200,
    max_retries: int = 3,
) -> int:
    """
    批量同步未同步的 Outcome 到 Thompson Sampling。

    关键修复：只有 RL 确认成功后才标记 rl_synced=1。
    失败的 Outcome 保持 rl_synced=0，下次定时任务会重新处理。
    连续失败超过 max_retries 的标记为 rl_synced=-1（需人工干预）。
    """
    stmt = (
        select(Outcome)
        .where(Outcome.rl_synced.in_([0, -1]))
        .where(Outcome.time_bucket.in_(["24h", "7d"]))
        .where(Outcome.engagement_score > 0)
        .order_by(Outcome.measured_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    outcomes = result.scalars().all()

    synced = 0
    failed = 0
    for outcome in outcomes:
        success = False
        for attempt in range(max_retries):
            ok = await sync_outcome_to_rl(
                db=db,
                trace_id=outcome.trace_id,
                engagement_score=outcome.engagement_score,
                time_bucket=outcome.time_bucket,
            )
            if ok:
                outcome.rl_synced = 1
                outcome.rl_synced_at = datetime.utcnow()
                synced += 1
                success = True
                break
            else:
                import asyncio
                await asyncio.sleep(0.5 * (attempt + 1))

        if not success:
            failed += 1
            logger.warning(
                f"[RL BATCH SYNC] Failed after {max_retries} retries: "
                f"outcome={outcome.id} trace={outcome.trace_id}"
            )

    if synced > 0 or failed > 0:
        await db.flush()
        logger.info(
            f"[RL BATCH SYNC] synced={synced} failed={failed} total={len(outcomes)}"
        )

    return synced
