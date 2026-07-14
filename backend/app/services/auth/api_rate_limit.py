"""API 限流（EW-A5 · TECH-SEC P1）：对话与上传按 user_id 滑动窗口。

单实例内存计数；多副本部署须换 Redis（Wave 2+）。
"""

from __future__ import annotations

from collections import defaultdict
from enum import Enum
from time import monotonic
from uuid import UUID

from fastapi import status
from app.core.exceptions import RateLimitError

# 生产阈值（plan：30 chat / 20 upload 每用户每小时）
CHAT_MAX_REQUESTS = 30
CHAT_WINDOW_SECONDS = 60 * 60
UPLOAD_MAX_REQUESTS = 20
UPLOAD_WINDOW_SECONDS = 60 * 60

_counters: dict[str, list[float]] = defaultdict(list)


class ApiRateLimitKind(str, Enum):
    chat = "chat"
    upload = "upload"


def _limits(kind: ApiRateLimitKind) -> tuple[int, int]:
    if kind == ApiRateLimitKind.chat:
        return CHAT_MAX_REQUESTS, CHAT_WINDOW_SECONDS
    return UPLOAD_MAX_REQUESTS, UPLOAD_WINDOW_SECONDS


def _rate_limit_key(kind: ApiRateLimitKind, user_id: UUID) -> str:
    return f"{kind.value}:{user_id}"


def _prune(key: str, window_seconds: int, *, now: float) -> list[float]:
    window_start = now - window_seconds
    kept = [t for t in _counters.get(key, []) if t > window_start]
    if kept:
        _counters[key] = kept
    else:
        _counters.pop(key, None)
    return kept


def _detail_message(kind: ApiRateLimitKind, window_seconds: int) -> str:
    minutes = max(1, window_seconds // 60)
    if kind == ApiRateLimitKind.chat:
        return f"对话请求过于频繁，请 {minutes} 分钟后再试"
    return f"上传过于频繁，请 {minutes} 分钟后再试"


def enforce_api_rate_limit(
    kind: ApiRateLimitKind,
    user_id: UUID,
    *,
    now: float | None = None,
) -> None:
    """未超限则记录本次请求；已达上限则 429。"""
    ts = now if now is not None else monotonic()
    max_requests, window_seconds = _limits(kind)
    key = _rate_limit_key(kind, user_id)
    timestamps = _prune(key, window_seconds, now=ts)
    if len(timestamps) >= max_requests:
        raise RateLimitError(detail=_detail_message(kind, window_seconds))
    timestamps.append(ts)
    _counters[key] = timestamps


def reset_all_api_rate_limits() -> None:
    """测试隔离：清空内存计数器。"""
    _counters.clear()
