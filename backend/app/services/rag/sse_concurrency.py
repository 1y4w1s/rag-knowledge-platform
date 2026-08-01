"""用户级 SSE 并发限制（防止超时放大：用户反复刷新叠请求）。

同一 user_id 最多 ACTIVE_LIMIT 个并发 SSE 流。
超过返回 HTTP 429。
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

logger = logging.getLogger(__name__)

ACTIVE_LIMIT = 3

_active_streams: dict[UUID, int] = {}
_lock = asyncio.Lock()


async def try_acquire_sse_slot(user_id: UUID) -> bool:
    """尝试占用一个 SSE 槽位。返回 False 表示已达上限。"""
    async with _lock:
        current = _active_streams.get(user_id, 0)
        if current >= ACTIVE_LIMIT:
            logger.warning("SSE 并发超限: user=%s count=%d", user_id, current)
            return False
        _active_streams[user_id] = current + 1
        return True


async def release_sse_slot(user_id: UUID) -> None:
    """释放 SSE 槽位（幂等）。"""
    async with _lock:
        current = _active_streams.get(user_id, 0)
        if current <= 1:
            _active_streams.pop(user_id, None)
        else:
            _active_streams[user_id] = current - 1
