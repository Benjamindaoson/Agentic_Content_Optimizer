"""Contextual Bandit 持久化（Redis）。"""

from __future__ import annotations

import logging

from app.core.redis import redis_client
from app.ml.rl.contextual_bandit import ContextualBandit

logger = logging.getLogger(__name__)


def _key(user_id: int) -> str:
    return f"ctx_bandit:{user_id}"


async def load_contextual_bandit(user_id: int, n_actions: int, alpha: float = 1.0) -> ContextualBandit:
    """加载 ContextualBandit，不存在则创建。"""
    try:
        data = await redis_client.get(_key(user_id))
        if data:
            return ContextualBandit.from_dict(data)
    except Exception as e:
        logger.warning(f"Load contextual bandit failed: {e}")
    return ContextualBandit(n_actions=n_actions, alpha=alpha)


async def save_contextual_bandit(user_id: int, bandit: ContextualBandit, ttl_seconds: int = 86400 * 30):
    """保存 ContextualBandit 到 Redis。"""
    try:
        await redis_client.set(_key(user_id), bandit.to_dict(), expire=ttl_seconds)
    except Exception as e:
        logger.warning(f"Save contextual bandit failed: {e}")

