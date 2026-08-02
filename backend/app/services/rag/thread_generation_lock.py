"""G3-2.5 · 同 thread 生成锁（H3-4-A · G3-E7：并行 POST → 409）。"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import Request

from app.core.config import settings
from app.services.rag.distributed_lock import acquire_lock, release_lock

THREAD_GENERATION_BUSY_DETAIL = "上一条仍在生成"

_thread_tokens: dict[UUID, str] = {}


async def try_acquire_thread_generation_lock(thread_id: UUID) -> bool:
    """非阻塞占用 thread 生成槽；已占用则返回 False（B3：分布式锁 + TTL 兜底）。"""
    token = uuid.uuid4().hex
    key = f"thread_gen:{thread_id}"
    ok = await acquire_lock(
        key,
        ttl_seconds=settings.agent_run_lock_ttl_seconds,
        token=token,
    )
    if ok:
        _thread_tokens[thread_id] = token
    return ok


async def release_thread_generation_lock(thread_id: UUID) -> None:
    """释放 thread 生成槽（幂等）。"""
    token = _thread_tokens.pop(thread_id, None)
    await release_lock(f"thread_gen:{thread_id}", token)


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
    _thread_tokens.clear()
    from app.services.rag.distributed_lock import reset_lock_registry

    reset_lock_registry()
