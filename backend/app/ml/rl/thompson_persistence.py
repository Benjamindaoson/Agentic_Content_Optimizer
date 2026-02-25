from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Tuple

from app.core.redis import get_redis
from app.ml.rl.thompson_sampling import ThompsonSamplingSelector, ThompsonSamplingConfig, BanditArm


_REDIS_KEY_PREFIX = "rl:thompson:v1:user:"


def _triplet_key(action: Tuple[int, int, int]) -> str:
    h, b, c = action
    return f"{h},{b},{c}"


def _arm_to_payload(arm: BanditArm) -> Dict[str, float]:
    return {
        "n_pulls": int(arm.n_pulls),
        "sum_reward": float(arm.sum_reward),
        "sum_reward_sq": float(arm.sum_reward_sq),
    }


def _apply_arm(arm: BanditArm, payload: Dict[str, Any]) -> None:
    arm.n_pulls = int(payload.get("n_pulls", 0) or 0)
    arm.sum_reward = float(payload.get("sum_reward", 0.0) or 0.0)
    arm.sum_reward_sq = float(payload.get("sum_reward_sq", 0.0) or 0.0)


def _rebuild_hierarchical_stats(selector: ThompsonSamplingSelector) -> None:
    # 由 triplet_stats 聚合得到 hook/body/cta 条件统计，保证可持久化且一致
    selector.hook_stats.clear()
    selector.body_given_hook_stats.clear()
    selector.cta_given_hook_body_stats.clear()

    for (h, b, c), t_arm in selector.triplet_stats.items():
        if t_arm.n_pulls <= 0:
            continue

        h_arm = selector.hook_stats[h]
        hb_arm = selector.body_given_hook_stats[(h, b)]
        hbc_arm = selector.cta_given_hook_body_stats[(h, b, c)]

        for arm in (h_arm, hb_arm, hbc_arm):
            arm.n_pulls += t_arm.n_pulls
            arm.sum_reward += t_arm.sum_reward
            arm.sum_reward_sq += t_arm.sum_reward_sq


async def load_selector(
    *,
    user_id: int,
    n_hooks: int,
    n_bodies: int,
    n_ctas: int,
    config: ThompsonSamplingConfig,
) -> ThompsonSamplingSelector:
    """
    从 Redis 加载 ThompsonSamplingSelector（仅持久化 triplet_stats，再重建层级统计）。
    若 Redis 无数据，则返回冷启动 selector。
    """
    selector = ThompsonSamplingSelector(n_hooks=n_hooks, n_bodies=n_bodies, n_ctas=n_ctas, config=config)

    redis = await get_redis()
    key = f"{_REDIS_KEY_PREFIX}{user_id}"
    payload = await redis.get(key)
    if not payload or not isinstance(payload, dict):
        return selector

    triplets: Dict[str, Any] = payload.get("triplets") or {}
    if not isinstance(triplets, dict):
        return selector

    for k, v in triplets.items():
        try:
            h_s, b_s, c_s = k.split(",")
            action = (int(h_s), int(b_s), int(c_s))
        except Exception:
            continue

        if not isinstance(v, dict):
            continue

        arm = selector.triplet_stats[action]
        _apply_arm(arm, v)

    _rebuild_hierarchical_stats(selector)
    return selector


async def save_selector(*, user_id: int, selector: ThompsonSamplingSelector) -> None:
    redis = await get_redis()
    key = f"{_REDIS_KEY_PREFIX}{user_id}"

    triplets: Dict[str, Any] = {}
    for action, arm in selector.triplet_stats.items():
        if arm.n_pulls <= 0:
            continue
        triplets[_triplet_key(action)] = _arm_to_payload(arm)

    payload: Dict[str, Any] = {
        "version": 1,
        "config": asdict(selector.config) if hasattr(selector.config, "__dict__") else {},
        "triplets": triplets,
    }
    await redis.set(key, payload)


async def update_action(
    *,
    user_id: int,
    selector: ThompsonSamplingSelector,
    action: Tuple[int, int, int],
    reward: float,
) -> None:
    selector.update(action, reward)
    # 简单策略：每次更新都持久化（400 arms 规模下可接受；需要更高吞吐可改为批量/节流）
    await save_selector(user_id=user_id, selector=selector)

