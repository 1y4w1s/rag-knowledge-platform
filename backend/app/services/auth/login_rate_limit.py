"""登录失败限流（EW-A4 · TECH-SEC P1 · G2 Redis 跨副本）。

双维度：
- identifier：5 次失败 / 15 分钟滑动窗口
- IP：20 次失败 / 5 分钟滑动窗口

双后端：memory（默认）/ redis（RATE_LIMIT_BACKEND=redis）。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from time import monotonic

from app.core.exceptions import RateLimitError
from app.services.auth.rate_limit_store import (
    get_rate_limit_backend,
    redis_delete_keys,
    redis_get_json,
    redis_set_json,
    redis_sliding_allow,
    redis_sliding_record,
    redis_zcard_in_window,
    wall_now,
)
from app.services.observability.metrics_registry import (
    inc_rate_limit_backend_fallback,
    inc_rate_limit_rejected,
)

logger = logging.getLogger(__name__)

MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60

MAX_IP_FAILURES = 20
IP_WINDOW_SECONDS = 5 * 60

STRIKE_DURATIONS = (60, 300, 900, 3600)  # 1min, 5min, 15min, 1h

# 忘记密码 IP 桶（G2 N6 · 防枚举）；阈值与历史 api/auth 一致
FORGOT_PASSWORD_MAX = 3
FORGOT_PASSWORD_WINDOW = 300  # 5 分钟
_FORGOT_PASSWORD_DETAIL = "请求过于频繁，请 5 分钟后再试"

_failures: dict[str, list[float]] = defaultdict(list)
_ip_failures: dict[str, list[float]] = defaultdict(list)
_strikes: dict[str, int] = defaultdict(int)
_strike_times: dict[str, float] = {}
_forgot_password_calls: dict[str, list[float]] = defaultdict(list)


def _log_redis_fallback(*, operation: str, error: Exception) -> None:
    """Redis 降级统一入口：结构化 warning + login 降级计数。"""
    logger.warning("Redis 登录限流降级，回退 memory: module=login operation=%s error=%s", operation, error)
    inc_rate_limit_backend_fallback("login")


def _rate_limit_key(ip: str | None, identifier: str) -> str:
    return f"{ip or 'unknown'}:{identifier.strip().lower()}"


def _redis_fail_key(ip: str | None, identifier: str) -> str:
    return f"rl:login:fail:{_rate_limit_key(ip, identifier)}"


def _redis_ip_key(ip: str | None) -> str:
    return f"rl:login:ip:{ip or 'unknown'}"


def _redis_strike_key(key: str) -> str:
    return f"rl:login:strike:{key}"


def _redis_forgot_key(ip: str) -> str:
    return f"rl:forgot:{ip or 'unknown'}"


def _prune(key: str, *, now: float) -> list[float]:
    window_start = now - WINDOW_SECONDS
    kept = [t for t in _failures.get(key, []) if t > window_start]
    if kept:
        _failures[key] = kept
    else:
        _failures.pop(key, None)
    return kept


def _ip_prune(ip_key: str, *, now: float) -> list[float]:
    window_start = now - IP_WINDOW_SECONDS
    kept = [t for t in _ip_failures.get(ip_key, []) if t > window_start]
    if kept:
        _ip_failures[ip_key] = kept
    else:
        _ip_failures.pop(ip_key, None)
    return kept


def _lockout_remaining_memory(key: str, *, now: float) -> int:
    strike_count = _strikes.get(key, 0)
    if strike_count == 0:
        return 0
    started = _strike_times.get(key, 0)
    duration = STRIKE_DURATIONS[min(strike_count - 1, len(STRIKE_DURATIONS) - 1)]
    remaining = duration - (now - started)
    if remaining <= 0:
        _strikes.pop(key, None)
        _strike_times.pop(key, None)
        return 0
    return int(remaining)


async def is_login_rate_limited(
    ip: str | None,
    identifier: str,
    *,
    now: float | None = None,
) -> bool:
    """当前 key 在窗口内是否已达失败上限（第 6 次起应 429）。"""
    if get_rate_limit_backend() == "redis":
        try:
            n = await redis_zcard_in_window(
                _redis_fail_key(ip, identifier),
                window_seconds=WINDOW_SECONDS,
                now=wall_now(now),
            )
            return n >= MAX_FAILURES
        except Exception as e:
            _log_redis_fallback(operation="read_failures", error=e)

    ts = now if now is not None else monotonic()
    return len(_prune(_rate_limit_key(ip, identifier), now=ts)) >= MAX_FAILURES


async def is_ip_login_rate_limited(
    ip: str | None,
    *,
    now: float | None = None,
) -> bool:
    """同 IP 是否已达失败上限。"""
    if get_rate_limit_backend() == "redis":
        try:
            n = await redis_zcard_in_window(
                _redis_ip_key(ip),
                window_seconds=IP_WINDOW_SECONDS,
                now=wall_now(now),
            )
            return n >= MAX_IP_FAILURES
        except Exception as e:
            _log_redis_fallback(operation="read_ip_failures", error=e)

    ts = now if now is not None else monotonic()
    return len(_ip_prune(ip or "unknown", now=ts)) >= MAX_IP_FAILURES


async def record_login_failure(
    ip: str | None,
    identifier: str,
    *,
    now: float | None = None,
) -> None:
    if get_rate_limit_backend() == "redis":
        try:
            ts = wall_now(now)
            await redis_sliding_record(
                _redis_fail_key(ip, identifier),
                window_seconds=WINDOW_SECONDS,
                now=ts,
            )
            await redis_sliding_record(
                _redis_ip_key(ip),
                window_seconds=IP_WINDOW_SECONDS,
                now=ts,
            )
            return
        except Exception as e:
            _log_redis_fallback(operation="write_failures", error=e)

    ts = now if now is not None else monotonic()
    key = _rate_limit_key(ip, identifier)
    timestamps = _prune(key, now=ts)
    timestamps.append(ts)
    _failures[key] = timestamps

    ip_key = ip or "unknown"
    ip_ts = _ip_prune(ip_key, now=ts)
    ip_ts.append(ts)
    _ip_failures[ip_key] = ip_ts


async def lockout_remaining(key: str, *, now: float | None = None) -> int:
    """距可再试还剩秒数；0 = 未锁。"""
    if get_rate_limit_backend() == "redis":
        try:
            ts = wall_now(now)
            data = await redis_get_json(_redis_strike_key(key))
            if not data:
                return 0
            strike_count = int(data.get("count", 0))
            if strike_count <= 0:
                return 0
            started = float(data.get("started", 0))
            duration = STRIKE_DURATIONS[min(strike_count - 1, len(STRIKE_DURATIONS) - 1)]
            remaining = duration - (ts - started)
            if remaining <= 0:
                await redis_delete_keys(_redis_strike_key(key))
                return 0
            return int(remaining)
        except Exception as e:
            _log_redis_fallback(operation="read_strike", error=e)

    ts = now if now is not None else monotonic()
    return _lockout_remaining_memory(key, now=ts)


async def record_lockout_strike(key: str, *, now: float | None = None) -> None:
    if get_rate_limit_backend() == "redis":
        try:
            ts = wall_now(now)
            sk = _redis_strike_key(key)
            data = await redis_get_json(sk) or {}
            count = int(data.get("count", 0)) + 1
            await redis_set_json(
                sk,
                {"count": count, "started": ts},
                ttl_seconds=STRIKE_DURATIONS[-1] + WINDOW_SECONDS,
            )
            return
        except Exception as e:
            _log_redis_fallback(operation="write_strike", error=e)

    ts = now if now is not None else monotonic()
    _strikes[key] += 1
    _strike_times[key] = ts


async def enforce_forgot_password_rate_limit(
    ip: str,
    *,
    now: float | None = None,
) -> None:
    """忘记密码 IP 限流：3 次 / 5 分钟；超限 raise RateLimitError(429)。

    redis 后端失败时 fail-open 回退 memory。
    """
    if get_rate_limit_backend() == "redis":
        try:
            allowed = await redis_sliding_allow(
                _redis_forgot_key(ip),
                max_requests=FORGOT_PASSWORD_MAX,
                window_seconds=FORGOT_PASSWORD_WINDOW,
                now=wall_now(now),
            )
            if not allowed:
                inc_rate_limit_rejected("forgot")
                raise RateLimitError(_FORGOT_PASSWORD_DETAIL)
            return
        except RateLimitError:
            raise
        except Exception as e:
            _log_redis_fallback(operation="forgot_password", error=e)

    ts = now if now is not None else monotonic()
    window_start = ts - FORGOT_PASSWORD_WINDOW
    key = ip or "unknown"
    timestamps = [t for t in _forgot_password_calls.get(key, []) if t > window_start]
    if len(timestamps) >= FORGOT_PASSWORD_MAX:
        inc_rate_limit_rejected("forgot")
        raise RateLimitError(_FORGOT_PASSWORD_DETAIL)
    timestamps.append(ts)
    _forgot_password_calls[key] = timestamps


async def clear_login_failures(ip: str | None, identifier: str) -> None:
    key = _rate_limit_key(ip, identifier)
    if get_rate_limit_backend() == "redis":
        try:
            await redis_delete_keys(
                _redis_fail_key(ip, identifier),
                _redis_strike_key(key),
            )
            # IP 桶故意不清：防换号爆破仍受 IP 窗约束
        except Exception as e:
            _log_redis_fallback(operation="clear_failures", error=e)

    _failures.pop(key, None)
    _strikes.pop(key, None)
    _strike_times.pop(key, None)


def reset_all_login_rate_limits() -> None:
    """测试隔离：清空内存计数器。"""
    _failures.clear()
    _ip_failures.clear()
    _strikes.clear()
    _strike_times.clear()
    _forgot_password_calls.clear()
