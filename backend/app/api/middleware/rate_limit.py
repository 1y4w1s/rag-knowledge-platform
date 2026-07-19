"""API 全局限流 middleware（TECH-SEC P1）。

校验每个请求的 IP 是否超限；超限时返回 429。
跳过健康检查端点。
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from app.core.config import settings
from app.services.rate_limit import (
    is_rate_limited,
    record_request,
    remaining,
    window_reset_seconds,
)

logger = logging.getLogger(__name__)

# 不限流的路径前缀
_SKIP_PREFIXES = frozenset({
    "/health",
})


class RateLimitMiddleware(BaseHTTPMiddleware):
    """全局限流：100 req/min / IP，返回 429 + Retry-After。"""

    async def dispatch(self, request: Request, call_next):
        # 跳过健康检查
        path = request.url.path
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        # 跳过禁用的场景
        if not settings.rate_limit_enabled:
            return await call_next(request)

        # 获取客户端 IP
        ip = request.client.host if request.client else "unknown"
        # 如果有 X-Forwarded-For，取第一个
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()

        # 检查是否超限
        if is_rate_limited(ip):
            retry_after = window_reset_seconds(ip)
            logger.warning("Rate limit exceeded: ip=%s path=%s", ip, path)
            return JSONResponse(
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "请求过于频繁，请稍后再试",
                    "retry_after_seconds": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # 记录请求
        record_request(ip)
        response = await call_next(request)

        # 添加限流头
        rem = remaining(ip)
        response.headers["X-RateLimit-Remaining"] = str(rem)
        response.headers["X-RateLimit-Limit"] = str(settings.rate_limit_max_requests)

        return response
