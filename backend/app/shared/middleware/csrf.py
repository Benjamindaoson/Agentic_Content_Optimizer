"""
CSRF 保护中间件
使用自定义头部验证（X-Requested-With）防止跨站请求伪造
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


STATE_CHANGING_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
EXEMPT_PATHS = {"/api/v1/auth/login", "/api/v1/auth/register", "/health", "/", "/docs", "/openapi.json"}


class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF 防护中间件 — 验证状态变更请求包含自定义头部"""

    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.enabled:
            return await call_next(request)

        if request.method in STATE_CHANGING_METHODS:
            path = request.url.path
            # 跳过豁免路径
            if not any(path.startswith(p) for p in EXEMPT_PATHS):
                xhr_header = request.headers.get("X-Requested-With")
                if xhr_header != "XMLHttpRequest":
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "缺少 CSRF 保护头部"},
                    )

        return await call_next(request)
