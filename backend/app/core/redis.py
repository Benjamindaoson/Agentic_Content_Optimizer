import redis.asyncio as redis
from typing import Optional, Any
import json
from app.core.config import get_settings

settings = get_settings()

TOKEN_BLACKLIST_PREFIX = "token_blacklist:"


class RedisClient:
    """Redis 客户端封装"""

    def __init__(self):
        self.client: Optional[redis.Redis] = None

    async def connect(self):
        """连接 Redis"""
        self.client = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )

    async def close(self):
        """关闭连接"""
        if self.client:
            await self.client.close()

    async def get(self, key: str) -> Optional[Any]:
        """获取值"""
        if not self.client:
            return None
        value = await self.client.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None

    async def set(
        self, key: str, value: Any, expire: Optional[int] = None
    ) -> bool:
        """设置值"""
        if not self.client:
            return False
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        return await self.client.set(key, value, ex=expire or settings.REDIS_CACHE_TTL)

    async def delete(self, key: str) -> bool:
        """删除键"""
        if not self.client:
            return False
        return await self.client.delete(key) > 0

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        if not self.client:
            return False
        return await self.client.exists(key) > 0

    async def publish(self, channel: str, message: str) -> int:
        """发布消息"""
        if not self.client:
            return 0
        return await self.client.publish(channel, message)

    async def ping(self) -> bool:
        """Redis 就绪探针。"""
        if not self.client:
            return False
        try:
            pong = await self.client.ping()
            return bool(pong)
        except Exception:
            return False

    async def blacklist_token(self, jti: str, ttl: int) -> bool:
        """将 JWT token 加入黑名单"""
        if not self.client:
            return False
        key = f"{TOKEN_BLACKLIST_PREFIX}{jti}"
        return await self.client.set(key, "1", ex=ttl)

    async def is_token_blacklisted(self, jti: str) -> bool:
        """检查 token 是否在黑名单中"""
        if not self.client:
            return False
        key = f"{TOKEN_BLACKLIST_PREFIX}{jti}"
        return await self.client.exists(key) > 0


# 全局 Redis 客户端
redis_client = RedisClient()


async def get_redis() -> RedisClient:
    """获取 Redis 客户端"""
    return redis_client
