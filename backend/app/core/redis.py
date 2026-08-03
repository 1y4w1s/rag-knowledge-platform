"""统一 Redis 连接池（限流 + 缓存共用）。"""
from __future__ import annotations

import logging
import os
from typing import Any

from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_REDIS_URL: str | None = None
_pool: ConnectionPool | None = None


def get_redis_url() -> str:
    global _REDIS_URL
    if _REDIS_URL is None:
        # C1 收口：settings.redis_url（pydantic 读 REDIS_URL env）→ CELERY_BROKER_URL env → 默认
        _REDIS_URL = (
            settings.redis_url
            or os.environ.get("CELERY_BROKER_URL")
            or "redis://localhost:6379/1"
        )
    return _REDIS_URL


async def get_redis() -> Redis:
    """获取 Redis 连接（懒加载连接池）。"""
    global _pool
    if _pool is None:
        url = get_redis_url()
        # P0-11 连接超时守卫：显式 socket/connect timeout，失败快速抛出而非挂死；
        # retry_on_timeout=False（redis-py 默认）保持 fail-fast 语义，由调用方降级/拒答。
        _pool = ConnectionPool.from_url(
            url,
            max_connections=20,
            socket_timeout=settings.redis_socket_timeout_seconds,
            socket_connect_timeout=settings.redis_connect_timeout_seconds,
            retry_on_timeout=False,
        )
        logger.info("Redis 连接池已创建: %s", url)
    return Redis(connection_pool=_pool)


async def close_redis() -> None:
    """关闭 Redis 连接池。"""
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None
        logger.info("Redis 连接池已关闭")
