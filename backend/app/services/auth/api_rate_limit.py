"""API 限流（EW-A5 · TECH-SEC P1 · G2 Redis 跨副本）。

对话 / 上传 / 搜索按 user_id 滑动窗口。
双后端：memory（默认，单实例）/ redis（多副本，RATE_LIMIT_BACKEND=redis）。
"""

from __future__ import annotations

from collections import defaultdict
from enum import Enum
import logging
import os
import threading
from time import monotonic
from uuid import UUID

from app.core.degradation import DegradationLevel, assess_degradation
from app.core.exceptions import RateLimitError
from app.services.auth.rate_limit_store import (
    get_rate_limit_backend,
    redis_sliding_allow,
    wall_now,
)
from app.services.observability.metrics_registry import inc_rate_limit_rejected

logger = logging.getLogger(__name__)

_BYPASS = os.environ.get("RAG_RATE_LIMIT_MODE", "") == "bypass"

# 生产阈值（plan：30 chat / 20 upload 每用户每小时）
CHAT_MAX_REQUESTS = 10000 if _BYPASS else 30
CHAT_WINDOW_SECONDS = 60 * 60
UPLOAD_MAX_REQUESTS = 10000 if _BYPASS else 20
UPLOAD_WINDOW_SECONDS = 60 * 60
SEARCH_MAX_REQUESTS = 10000 if _BYPASS else 60
SEARCH_WINDOW_SECONDS = 60 * 60
# M1：注册限流，同 IP 10 次/小时
REGISTER_MAX_REQUESTS = 10000 if _BYPASS else 10
REGISTER_WINDOW_SECONDS = 60 * 60

# IP 限流（防止多账号绕过用户级限流；调用方传 ip= 才生效）
IP_CHAT_MAX_REQUESTS = 10000 if _BYPASS else 60
IP_CHAT_WINDOW_SECONDS = 60 * 60
IP_UPLOAD_MAX_REQUESTS = 10000 if _BYPASS else 40
IP_UPLOAD_WINDOW_SECONDS = 60 * 60
IP_SEARCH_MAX_REQUESTS = 10000 if _BYPASS else 120
IP_SEARCH_WINDOW_SECONDS = 60 * 60

_counters: dict[str, list[float]] = defaultdict(list)
_rate_limit_lock = threading.Lock()

_MAX_COUNTER_KEYS = 10_000
_cleanup_counter = 0


class ApiRateLimitKind(str, Enum):
    chat = "chat"
    upload = "upload"
    search = "search"
    register = "register"


def _limits(kind: ApiRateLimitKind) -> tuple[int, int]:
    if kind == ApiRateLimitKind.chat:
        return CHAT_MAX_REQUESTS, CHAT_WINDOW_SECONDS
    if kind == ApiRateLimitKind.search:
        return SEARCH_MAX_REQUESTS, SEARCH_WINDOW_SECONDS
    if kind == ApiRateLimitKind.register:
        return REGISTER_MAX_REQUESTS, REGISTER_WINDOW_SECONDS
    return UPLOAD_MAX_REQUESTS, UPLOAD_WINDOW_SECONDS


def _rate_limit_key(kind: ApiRateLimitKind, user_id: UUID) -> str:
    return f"{kind.value}:{user_id}"


def _ip_rate_limit_key(kind: ApiRateLimitKind, ip: str) -> str:
    return f"ip:{kind.value}:{ip}"


def _ip_limits(kind: ApiRateLimitKind) -> tuple[int, int]:
    if kind == ApiRateLimitKind.chat:
        return IP_CHAT_MAX_REQUESTS, IP_CHAT_WINDOW_SECONDS
    if kind == ApiRateLimitKind.search:
        return IP_SEARCH_MAX_REQUESTS, IP_SEARCH_WINDOW_SECONDS
    return IP_UPLOAD_MAX_REQUESTS, IP_UPLOAD_WINDOW_SECONDS


def _prune(key: str, window_seconds: int, *, now: float) -> list[float]:
    window_start = now - window_seconds
    kept = [t for t in _counters.get(key, []) if t > window_start]
    if kept:
        _counters[key] = kept
    else:
        _counters.pop(key, None)
    global _cleanup_counter
    _cleanup_counter += 1
    if _cleanup_counter % 100 == 0 and len(_counters) > _MAX_COUNTER_KEYS:
        _evict_oldest_keys()
    return kept


def _evict_oldest_keys() -> None:
    """淘汰最旧的 key，防止内存无限增长。"""
    now = monotonic()
    for k in list(_counters.keys()):
        window_start = now - (60 * 60)
        _counters[k] = [t for t in _counters[k] if t > window_start]
        if not _counters[k]:
            _counters.pop(k, None)
    while len(_counters) > _MAX_COUNTER_KEYS:
        oldest_key = min(_counters.keys(), key=lambda k: max(_counters[k]) if _counters[k] else 0)
        _counters.pop(oldest_key, None)


def _degradation_multiplier() -> float:
    level = assess_degradation()
    factors = {
        DegradationLevel.NORMAL: 1.0,
        DegradationLevel.LLM_DOWN: 0.5,
        DegradationLevel.RERANK_DOWN: 0.5,
        DegradationLevel.EMBED_DOWN: 0.3,
        DegradationLevel.ALL_DOWN: 0.3,
    }
    return factors.get(level, 0.3)


def _detail_message(kind: ApiRateLimitKind, window_seconds: int) -> str:
    minutes = max(1, window_seconds // 60)
    if kind == ApiRateLimitKind.chat:
        return f"对话请求过于频繁，请 {minutes} 分钟后再试"
    if kind == ApiRateLimitKind.search:
        return f"搜索过于频繁，请 {minutes} 分钟后再试"
    if kind == ApiRateLimitKind.register:
        return f"注册过于频繁，请 {minutes} 分钟后再试"
    return f"上传过于频繁，请 {minutes} 分钟后再试"


def _redis_key(kind: ApiRateLimitKind, uid: str) -> str:
    return f"rl:api:{kind.value}:{uid}"


def _raise_limited(kind: ApiRateLimitKind, window_seconds: int) -> None:
    inc_rate_limit_rejected(kind.value)
    raise RateLimitError(_detail_message(kind, window_seconds))


def _enforce_memory(
    kind: ApiRateLimitKind,
    user_id: UUID,
    *,
    ip: str | None,
    now: float,
    effective_max: int,
    window_seconds: int,
) -> None:
    key = _rate_limit_key(kind, user_id)
    with _rate_limit_lock:
        timestamps = _prune(key, window_seconds, now=now)
        if len(timestamps) >= effective_max:
            _raise_limited(kind, window_seconds)
        timestamps.append(now)
        _counters[key] = timestamps

        if ip is not None:
            ip_key = _ip_rate_limit_key(kind, ip)
            ip_max, ip_window = _ip_limits(kind)
            ip_effective = max(1, int(ip_max * _degradation_multiplier()))
            ip_timestamps = _prune(ip_key, ip_window, now=now)
            if len(ip_timestamps) >= ip_effective:
                _raise_limited(kind, ip_window)
            ip_timestamps.append(now)
            _counters[ip_key] = ip_timestamps


async def enforce_api_rate_limit(
    kind: ApiRateLimitKind,
    user_id: UUID | None = None,
    *,
    ip: str | None = None,
    now: float | None = None,
) -> None:
    """未超限则记录本次请求；已达上限则 429。可仅传 ip（如注册等无 user 场景）。

    redis 后端失败时 fail-open 回退 memory。
    """
    multiplier = _degradation_multiplier()
    max_requests, window_seconds = _limits(kind)
    effective_max = max(1, int(max_requests * multiplier))

    if get_rate_limit_backend() == "redis":
        try:
            ts = wall_now(now)
            uid = str(user_id) if user_id is not None else f"ip:{ip or 'unknown'}"
            key = _redis_key(kind, uid)
            allowed = await redis_sliding_allow(
                key,
                max_requests=effective_max,
                window_seconds=window_seconds,
                now=ts,
            )
            if not allowed:
                _raise_limited(kind, window_seconds)
            if ip is not None:
                ip_key = _redis_key(kind, f"ip:{ip}")
                ip_max, ip_window = _ip_limits(kind)
                ip_effective = max(1, int(ip_max * multiplier))
                ip_ok = await redis_sliding_allow(
                    ip_key,
                    max_requests=ip_effective,
                    window_seconds=ip_window,
                    now=ts,
                )
                if not ip_ok:
                    _raise_limited(kind, ip_window)
            return
        except RateLimitError:
            raise
        except Exception as e:
            logger.warning("Redis 限流失败，回退 memory: %s", e)

    # Memory：沿用 monotonic，单进程内自洽
    ts_mem = now if now is not None else monotonic()
    _enforce_memory(
        kind,
        user_id or ip or "unknown",
        ip=ip,
        now=ts_mem,
        effective_max=effective_max,
        window_seconds=window_seconds,
    )


def reset_all_api_rate_limits() -> None:
    """测试隔离：清空内存计数器。"""
    _counters.clear()
