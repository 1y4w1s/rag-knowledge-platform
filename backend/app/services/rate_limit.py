"""全局限流（TECH-SEC P1 · API rate limit）。

基于 IP 的滑动窗口限流，复用 login_rate_limit.py 的内存模式。
单实例内存实现；多副本部署须换 Redis（Wave 2+）。

配置项（Settings）：
- rate_limit_enabled: bool (默认 True)
- rate_limit_max_requests: int (默认 100)
- rate_limit_window_seconds: int (默认 60)
"""

from __future__ import annotations

from collections import defaultdict
from time import monotonic

MAX_REQUESTS = 100
WINDOW_SECONDS = 60

_requests: dict[str, list[float]] = defaultdict(list)


def _prune(ip: str, *, now: float) -> list[float]:
    """裁剪过期的请求记录，返回当前窗口内的记录。"""
    window_start = now - WINDOW_SECONDS
    kept = [t for t in _requests.get(ip, []) if t > window_start]
    if kept:
        _requests[ip] = kept
    else:
        _requests.pop(ip, None)
    return kept


def is_rate_limited(ip: str, *, now: float | None = None) -> bool:
    """当前 IP 在窗口内是否已达请求上限。"""
    ts = now if now is not None else monotonic()
    timestamps = _prune(ip, now=ts)
    return len(timestamps) >= MAX_REQUESTS


def record_request(ip: str, *, now: float | None = None) -> None:
    """记录一次请求。"""
    ts = now if now is not None else monotonic()
    timestamps = _prune(ip, now=ts)
    timestamps.append(ts)
    _requests[ip] = timestamps


def remaining(ip: str, *, now: float | None = None) -> int:
    """当前 IP 在窗口内还剩多少请求配额。"""
    ts = now if now is not None else monotonic()
    used = len(_prune(ip, now=ts))
    return max(0, MAX_REQUESTS - used)


def window_reset_seconds(ip: str, *, now: float | None = None) -> int:
    """当前窗口还剩多少秒重置。"""
    ts = now if now is not None else monotonic()
    timestamps = _prune(ip, now=ts)
    if not timestamps:
        return 0
    # 窗口从最早记录开始算
    elapsed = ts - timestamps[0]
    remaining_sec = WINDOW_SECONDS - elapsed
    return max(0, int(remaining_sec))


def reset_all_rate_limits() -> None:
    """测试隔离：清空内存计数器。"""
    _requests.clear()
