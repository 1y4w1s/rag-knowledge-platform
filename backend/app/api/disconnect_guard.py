"""SSE 流式断开检测工具。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TypeVar

from fastapi import Request

T = TypeVar("T")


async def with_disconnect_guard(
    request: Request,
    stream: AsyncIterator[T],
) -> AsyncIterator[T]:
    """包装 SSE 生成器：客户端断开时主动终止，避免 LLM 算力浪费。"""
    try:
        async for item in stream:
            if await request.is_disconnected():
                break
            yield item
    finally:
        # 确保底层生成器被关闭
        await stream.aclose()
