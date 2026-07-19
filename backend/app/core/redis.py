"""统一 Redis 连接池（限流 + 缓存共用）。"""
from __future__ import annotations

import logging
import os
from typing import Any

from redis.asyncio import ConnectionPool, Redis

logger = logging.getLogger(__name__)

_REDIS_URL: str | None = None
_pool: ConnectionPool | None = None


def get_redis_url() -> str:
    global _REDIS_URL
    if _REDIS_URL is None:
        _REDIS_URL = os.environ.get(
            "REDIS_URL",
            os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1"),
        )
    return _REDIS_URL


async def get_redis() -> Redis:
    """获取 Redis 连接（懒加载连接池）。"""
    global _pool
    if _pool is None:
        url = get_redis_url()
        _pool = ConnectionPool.from_url(url, max_connections=20)
        logger.info("Redis 连接池已创建: %s", url)
    return Redis(connection_pool=_pool)


async def close_redis() -> None:
    """关闭 Redis 连接池。"""
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None
        logger.info("Redis 连接池已关闭")
