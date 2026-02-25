"""
API 速率限制中间件
Rate Limiting Middleware using Redis
"""

import time
import logging
from typing import Callable, Optional
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.redis import redis_client

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    速率限制中间件

    使用 Redis 实现分布式速率限制
    支持按 IP、用户、端点的多维度限制
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_size: int = 10,
        enabled: bool = True
    ):
        """
        初始化速率限制器

        Args:
            app: FastAPI 应用
            requests_per_minute: 每分钟请求限制
            requests_per_hour: 每小时请求限制
            burst_size: 突发请求容量
            enabled: 是否启用速率限制
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_size = burst_size
        self.enabled = enabled

        logger.info(
            f"Rate limiter initialized: "
            f"{requests_per_minute} req/min, "
            f"{requests_per_hour} req/hour, "
            f"burst={burst_size}, "
            f"enabled={enabled}"
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""

        # 如果未启用，直接放行
        if not self.enabled:
            return await call_next(request)

        # 健康检查端点不限流
        if request.url.path in ["/health", "/", "/docs", "/openapi.json"]:
            return await call_next(request)

        # 获取客户端标识
        client_id = self._get_client_id(request)

        # 检查速率限制
        try:
            is_allowed, retry_after = await self._check_rate_limit(client_id, request.url.path)

            if not is_allowed:
                logger.warning(
                    f"Rate limit exceeded for {client_id} on {request.url.path}, "
                    f"retry after {retry_after}s"
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Rate limit exceeded",
                        "retry_after": retry_after,
                        "limit": {
                            "per_minute": self.requests_per_minute,
                            "per_hour": self.requests_per_hour
                        }
                    },
                    headers={"Retry-After": str(retry_after)}
                )

            # 执行请求
            response = await call_next(request)

            # 添加速率限制头
            response.headers["X-RateLimit-Limit-Minute"] = str(self.requests_per_minute)
            response.headers["X-RateLimit-Limit-Hour"] = str(self.requests_per_hour)

            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Rate limiter error: {e}")
            # 速率限制器故障时不阻塞请求
            return await call_next(request)

    def _get_client_id(self, request: Request) -> str:
        """获取客户端标识"""

        # 优先使用认证用户 ID
        if hasattr(request.state, "user_id"):
            return f"user:{request.state.user_id}"

        # 使用 IP 地址
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"

        return f"ip:{ip}"

    async def _check_rate_limit(self, client_id: str, path: str) -> tuple[bool, int]:
        """
        检查速率限制

        使用滑动窗口算法

        Returns:
            (is_allowed, retry_after_seconds)
        """

        current_time = int(time.time())

        # 分钟级限制
        minute_key = f"rate_limit:minute:{client_id}:{current_time // 60}"
        minute_count = await redis_client.incr(minute_key)

        if minute_count == 1:
            await redis_client.expire(minute_key, 60)

        if minute_count > self.requests_per_minute:
            retry_after = 60 - (current_time % 60)
            return False, retry_after

        # 小时级限制
        hour_key = f"rate_limit:hour:{client_id}:{current_time // 3600}"
        hour_count = await redis_client.incr(hour_key)

        if hour_count == 1:
            await redis_client.expire(hour_key, 3600)

        if hour_count > self.requests_per_hour:
            retry_after = 3600 - (current_time % 3600)
            return False, retry_after

        return True, 0


class EndpointRateLimiter:
    """
    端点级速率限制器

    用于装饰器模式，对特定端点应用不同的限制
    """

    def __init__(
        self,
        requests_per_minute: int = 10,
        requests_per_hour: int = 100
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour

    async def __call__(self, request: Request):
        """检查端点速率限制"""

        client_id = self._get_client_id(request)
        current_time = int(time.time())

        # 分钟级限制
        minute_key = f"rate_limit:endpoint:minute:{client_id}:{request.url.path}:{current_time // 60}"
        minute_count = await redis_client.incr(minute_key)

        if minute_count == 1:
            await redis_client.expire(minute_key, 60)

        if minute_count > self.requests_per_minute:
            retry_after = 60 - (current_time % 60)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Endpoint rate limit exceeded",
                    "retry_after": retry_after,
                    "limit": self.requests_per_minute
                },
                headers={"Retry-After": str(retry_after)}
            )

        return True

    def _get_client_id(self, request: Request) -> str:
        """获取客户端标识"""
        if hasattr(request.state, "user_id"):
            return f"user:{request.state.user_id}"

        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"

        return f"ip:{ip}"


# 预定义的速率限制器
rate_limit_strict = EndpointRateLimiter(requests_per_minute=5, requests_per_hour=50)
rate_limit_moderate = EndpointRateLimiter(requests_per_minute=20, requests_per_hour=200)
rate_limit_relaxed = EndpointRateLimiter(requests_per_minute=60, requests_per_hour=1000)
