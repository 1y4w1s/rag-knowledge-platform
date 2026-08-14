"""用户级 SSE 并发限制（防止超时放大：用户反复刷新叠请求）。

同一 user_id 最多 ACTIVE_LIMIT 个并发 SSE 流。
超过返回 HTTP 429。

B3（P1-09/H8）：计数后端收敛到统一锁抽象——memory（显式单 worker）或
redis（INCR+EXPIRE，多 worker）；内存槽位带 TTL 兜底，防 release 遗漏后永久占位。
"""

from __future__ import annotations

import asyncio
import logging
import time
from uuid import UUID

from app.core.config import settings
from app.services.rag.distributed_lock import _use_redis_backend

logger = logging.getLogger(__name__)

ACTIVE_LIMIT = 3

_active_streams: dict[UUID, int] = {}
_slots_expires: dict[UUID, float] = {}
_lock = asyncio.Lock()


def _slot_key(user_id: UUID) -> str:
    return f"sse_slots:{user_id}"


def _slot_ttl_seconds() -> int:
    return settings.agent_run_lock_ttl_seconds


async def _acquire_memory_slot(user_id: UUID) -> bool:
    async with _lock:
        now = time.monotonic()
        # 清理过期槽位（release 遗漏兜底）
        if _slots_expires.get(user_id, 0) <= now:
            _active_streams.pop(user_id, None)
        current = _active_streams.get(user_id, 0)
        if current >= ACTIVE_LIMIT:
            logger.warning("SSE 并发超限: user=%s count=%d", user_id, current)
            return False
        _active_streams[user_id] = current + 1
        _slots_expires[user_id] = now + _slot_ttl_seconds()
        return True


async def _decrement_redis_slot(redis, key: str) -> None:
    count = await redis.decr(key)
    if count <= 0:
        await redis.delete(key)


async def _acquire_redis_slot(user_id: UUID) -> bool:
    from app.core.redis import get_redis

    redis = await get_redis()
    key = _slot_key(user_id)
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, _slot_ttl_seconds())
    if count > ACTIVE_LIMIT:
        logger.warning("SSE 并发超限(redis): user=%s count=%d", user_id, count)
        await _decrement_redis_slot(redis, key)  # 拒绝路径补偿，计数回到真实占用
        return False
    return True


async def try_acquire_sse_slot(user_id: UUID) -> bool:
    """尝试占用一个 SSE 槽位。返回 False 表示已达上限。"""
    if _use_redis_backend():
        try:
            return await _acquire_redis_slot(user_id)
        except Exception:
            logger.exception("Redis SSE 槽位获取失败，按未持有处理: user=%s", user_id)
            return False
    return await _acquire_memory_slot(user_id)


async def _release_redis_slot(user_id: UUID) -> None:
    from app.core.redis import get_redis

    redis = await get_redis()
    await _decrement_redis_slot(redis, _slot_key(user_id))


async def release_sse_slot(user_id: UUID) -> None:
    """释放 SSE 槽位（幂等）。"""
    if _use_redis_backend():
        try:
            await _release_redis_slot(user_id)
        except Exception:
            logger.exception("Redis SSE 槽位释放失败（TTL 兜底）: user=%s", user_id)
        return
    async with _lock:
        current = _active_streams.get(user_id, 0)
        if current <= 1:
            _active_streams.pop(user_id, None)
            _slots_expires.pop(user_id, None)
        else:
            _active_streams[user_id] = current - 1
            _slots_expires[user_id] = time.monotonic() + _slot_ttl_seconds()
