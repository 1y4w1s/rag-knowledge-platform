"""检索查询缓存（双后端：memory / redis）。

2026-07-18 重构：全 async-native（移除 asyncio.run anti-pattern）。

用法：
    CACHE_BACKEND=memory   # 默认，进程内 LRU
    CACHE_BACKEND=redis    # Redis，多副本共享

    await set_query_cache(kb_id, user_message, chunks)
    chunks = await get_query_cache(kb_id, user_message)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from collections import OrderedDict
from uuid import UUID

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── 后端选择 ──

_CACHE_BACKEND: str | None = None


def _get_backend() -> str:
    global _CACHE_BACKEND
    if _CACHE_BACKEND is None:
        _CACHE_BACKEND = os.environ.get("CACHE_BACKEND", "memory")
    return _CACHE_BACKEND


# ── Memory 后端 ──

_cache: OrderedDict[str, tuple[float, list]] = OrderedDict()
_MAX_SIZE: int = 5000
_TTL_SECONDS: int = 300


def _cache_key(kb_id: UUID, query: str) -> str:
    raw = f"{kb_id}|{query.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def get_query_cache(kb_id: UUID, query: str) -> list | None:
    """返回缓存的检索结果，过期或未命中返回 None。"""
    key = _cache_key(kb_id, query)

    if _get_backend() == "redis":
        try:
            from app.core.redis import get_redis
            r = await get_redis()
            data = await r.get(key)
            if data:
                cached_at, chunks = json.loads(data)
                if time.monotonic() - cached_at < _TTL_SECONDS:
                    return chunks
        except Exception as e:
            logger.warning("Redis 读取失败，回退 memory: %s", e)

    entry = _cache.get(key)
    if entry is None:
        return None
    ts, chunks = entry
    if time.monotonic() - ts > _TTL_SECONDS:
        del _cache[key]
        return None
    return chunks


async def set_query_cache(kb_id: UUID, query: str, chunks: list) -> None:
    """写入查询缓存。"""
    key = _cache_key(kb_id, query)

    if _get_backend() == "redis":
        try:
            from app.core.redis import get_redis
            r = await get_redis()
            data = json.dumps([time.monotonic(), chunks])
            await r.setex(key, _TTL_SECONDS, data)
            return
        except Exception as e:
            logger.warning("Redis 写入失败，回退 memory: %s", e)

    _cache[key] = (time.monotonic(), chunks)
    if len(_cache) > _MAX_SIZE:
        _cache.popitem(last=False)


async def clear_query_cache(kb_id: UUID | None = None) -> int:
    """清空缓存（可选按 kb_id 维度）。返回清除条目数。"""
    cleared = 0

    if _get_backend() == "redis":
        try:
            from app.core.redis import get_redis
            r = await get_redis()
            if kb_id:
                pattern = hashlib.sha256(f"{kb_id}|".encode("utf-8")).hexdigest()[:10]
                keys = await r.keys(f"*{pattern}*")
            else:
                keys = await r.keys("*")
            if keys:
                await r.delete(*keys)
                cleared = len(keys)
            logger.info("Redis 缓存清空: %d 条", cleared)
            return cleared
        except Exception as e:
            logger.warning("Redis 清空失败: %s", e)

    if kb_id:
        prefix = str(kb_id)[:8]
        keys = [k for k in _cache if prefix in k]
        for k in keys:
            del _cache[k]
        cleared = len(keys)
    else:
        cleared = len(_cache)
        _cache.clear()
    logger.info("Memory 缓存清空: %d 条", cleared)
    return cleared


# ── 开关 ──

_QUERY_CACHE_ENABLED: bool = True


def query_cache_enabled() -> bool:
    return _QUERY_CACHE_ENABLED


def set_query_cache_enabled(enabled: bool) -> None:
    global _QUERY_CACHE_ENABLED
    _QUERY_CACHE_ENABLED = enabled
    if not enabled:
        import asyncio
        asyncio.create_task(clear_query_cache())
