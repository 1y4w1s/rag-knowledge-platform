"""API 限流（EW-A5 · TECH-SEC P1）：对话与上传按 user_id 滑动窗口。

双后端：memory（默认，单实例）/ redis（多副本）。
环境变量 RATE_LIMIT_BACKEND=redis 启用 Redis 后端。
"""

from __future__ import annotations

import asyncio
import os
from collections import defaultdict
from enum import Enum
import logging
import threading
from time import monotonic
from uuid import UUID

from fastapi import status
from app.core.degradation import DegradationLevel, assess_degradation
from app.core.exceptions import RateLimitError

logger = logging.getLogger(__name__)

_BYPASS = os.environ.get("RAG_RATE_LIMIT_MODE", "") == "bypass"
_BACKEND = os.environ.get("RATE_LIMIT_BACKEND", "memory")

# 生产阈值（plan：30 chat / 20 upload 每用户每小时）
CHAT_MAX_REQUESTS = 10000 if _BYPASS else 30
CHAT_WINDOW_SECONDS = 60 * 60
UPLOAD_MAX_REQUESTS = 10000 if _BYPASS else 20
UPLOAD_WINDOW_SECONDS = 60 * 60
SEARCH_MAX_REQUESTS = 10000 if _BYPASS else 60
SEARCH_WINDOW_SECONDS = 60 * 60

# IP 限流（防止多账号绕过用户级限流）
IP_CHAT_MAX_REQUESTS = 60
IP_CHAT_WINDOW_SECONDS = 60 * 60
IP_UPLOAD_MAX_REQUESTS = 40
IP_UPLOAD_WINDOW_SECONDS = 60 * 60
IP_SEARCH_MAX_REQUESTS = 120
IP_SEARCH_WINDOW_SECONDS = 60 * 60

_counters: dict[str, list[float]] = defaultdict(list)
_rate_limit_lock = threading.Lock()

# 内存守卫：最多保留 key 数，超出时触发清理最旧条目
_MAX_COUNTER_KEYS = 10_000
_cleanup_counter = 0


class ApiRateLimitKind(str, Enum):
    chat = "chat"
    upload = "upload"
    search = "search"


def _limits(kind: ApiRateLimitKind) -> tuple[int, int]:
    if kind == ApiRateLimitKind.chat:
        return CHAT_MAX_REQUESTS, CHAT_WINDOW_SECONDS
    if kind == ApiRateLimitKind.search:
        return SEARCH_MAX_REQUESTS, SEARCH_WINDOW_SECONDS
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
    # 每 100 次 prune 触发一次全局清理，防止单次触发时延抖动
    global _cleanup_counter
    _cleanup_counter += 1
    if _cleanup_counter % 100 == 0 and len(_counters) > _MAX_COUNTER_KEYS:
        _evict_oldest_keys()
    return kept


def _evict_oldest_keys() -> None:
    """淘汰最旧的 10% key，防止内存无限增长。"""
    now = monotonic()
    # 先 prune 所有 key
    for k in list(_counters.keys()):
        window_start = now - (60 * 60)  # 用 1h 窗口 prune
        _counters[k] = [t for t in _counters[k] if t > window_start]
        if not _counters[k]:
            _counters.pop(k, None)
    # 如果仍然超限，按最后活跃时间淘汰
    while len(_counters) > _MAX_COUNTER_KEYS:
        oldest_key = min(_counters.keys(), key=lambda k: max(_counters[k]) if _counters[k] else 0)
        _counters.pop(oldest_key, None)


def _degradation_multiplier() -> float:
    """根据当前降级等级收紧限流配额。

    降级后用户可能反复重试，但系统资源（DB FTS）反而更脆弱，
    需要主动收紧入口流量以保护后端。
    """
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
    return f"上传过于频繁，请 {minutes} 分钟后再试"


def _redis_key(kind: ApiRateLimitKind, uid: str) -> str:
    return f"ratelimit:{kind.value}:{uid}"


async def _redis_check(
    key: str,
    max_requests: int,
    window_seconds: int,
    now: float,
) -> None:
    """Redis 滑动窗口：ZREMRANGEBYSCORE + ZCARD + ZADD 原子操作。"""
    from app.core.redis import get_redis

    r = await get_redis()
    window_start = now - window_seconds
    # 清理过期 + 计数
    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)
    pipe.zcard(key)
    pipe.zadd(key, {str(now): now})
    pipe.expire(key, window_seconds)
    _, count, _, _ = await pipe.execute()
    if count >= max_requests:
        raise RateLimitError(detail=f"请求过于频繁，请稍后再试（{window_seconds//60} 分钟内限制 {max_requests} 次）")


def enforce_api_rate_limit(
    kind: ApiRateLimitKind,
    user_id: UUID,
    *,
    ip: str | None = None,
    now: float | None = None,
) -> None:
    """未超限则记录本次请求；已达上限则 429。

    双后端：_BACKEND == "redis" 用 Redis ZSET，否则用内存。
    """
    ts = now if now is not None else monotonic()
    multiplier = _degradation_multiplier()
    max_requests, window_seconds = _limits(kind)
    effective_max = max(1, int(max_requests * multiplier))

    if _BACKEND == "redis":
        try:
            import asyncio
            key = _redis_key(kind, str(user_id))
            asyncio.run(_redis_check(key, effective_max, window_seconds, ts))
            if ip is not None:
                ip_key = _redis_key(kind, f"ip:{ip}")
                ip_max, _ = _ip_limits(kind)
                asyncio.run(_redis_check(ip_key, ip_max, window_seconds, ts))
            return
        except RateLimitError:
            raise
        except Exception as e:
            logger.warning("Redis 限流失败，回退 memory: %s", e)

    # Memory 后端 (原有逻辑)
    key = _rate_limit_key(kind, user_id)
    with _rate_limit_lock:
        timestamps = _prune(key, window_seconds, now=ts)
        if len(timestamps) >= effective_max:
            raise RateLimitError(detail=_detail_message(kind, window_seconds))
        timestamps.append(ts)
        _counters[key] = timestamps

        if ip is not None:
            ip_key = _ip_rate_limit_key(kind, ip)
            ip_max, ip_window = _ip_limits(kind)
            ip_effective = max(1, int(ip_max * multiplier))
            ip_timestamps = _prune(ip_key, ip_window, now=ts)
            if len(ip_timestamps) >= ip_effective:
                raise RateLimitError(detail=_detail_message(kind, ip_window))
            ip_timestamps.append(ts)
            _counters[ip_key] = ip_timestamps


def reset_all_api_rate_limits() -> None:
    """测试隔离：清空内存计数器。"""
    _counters.clear()
