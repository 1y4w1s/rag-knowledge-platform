"""G3-2.5 · 同 thread 生成锁（H3-4-A · G3-E7：并行 POST → 409）。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import Request

THREAD_GENERATION_BUSY_DETAIL = "上一条仍在生成"

_active_thread_ids: set[UUID] = set()
_registry_lock = asyncio.Lock()


async def try_acquire_thread_generation_lock(thread_id: UUID) -> bool:
    """非阻塞占用 thread 生成槽；已占用则返回 False。"""
    async with _registry_lock:
        if thread_id in _active_thread_ids:
            return False
        _active_thread_ids.add(thread_id)
        return True


async def release_thread_generation_lock(thread_id: UUID) -> None:
    """释放 thread 生成槽（幂等）。"""
    async with _registry_lock:
        _active_thread_ids.discard(thread_id)


async def wrap_stream_with_thread_generation_lock(
    thread_id: UUID,
    stream: AsyncIterator[str],
    request: Request | None = None,
) -> AsyncIterator[str]:
    """SSE 流结束时释放锁（含客户端断开 / 异常）。

    可选传入 request 以检测客户端断开并提前终止，避免 LLM 算力浪费。
    """
    try:
        async for frame in stream:
            if request and await request.is_disconnected():
                break
            yield frame
    finally:
        await release_thread_generation_lock(thread_id)


def reset_thread_generation_locks() -> None:
    """测试隔离：清空进程内占用表。"""
    _active_thread_ids.clear()
