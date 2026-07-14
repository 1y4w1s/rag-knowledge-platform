"""登录失败限流（EW-A4 · TECH-SEC P1）。

单实例内存滑动窗口；多副本部署须换 Redis（Wave 2+）。
"""

from __future__ import annotations

from collections import defaultdict
from time import monotonic

# 5 次失败 / 15 分钟滑动窗口（按 IP + identifier）
MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60

_failures: dict[str, list[float]] = defaultdict(list)


def _rate_limit_key(ip: str | None, identifier: str) -> str:
    return f"{ip or 'unknown'}:{identifier.strip().lower()}"


def _prune(key: str, *, now: float) -> list[float]:
    window_start = now - WINDOW_SECONDS
    kept = [t for t in _failures.get(key, []) if t > window_start]
    if kept:
        _failures[key] = kept
    else:
        _failures.pop(key, None)
    return kept


def is_login_rate_limited(
    ip: str | None,
    identifier: str,
    *,
    now: float | None = None,
) -> bool:
    """当前 key 在窗口内是否已达失败上限（第 6 次起应 429）。"""
    ts = now if now is not None else monotonic()
    return len(_prune(_rate_limit_key(ip, identifier), now=ts)) >= MAX_FAILURES


def record_login_failure(
    ip: str | None,
    identifier: str,
    *,
    now: float | None = None,
) -> None:
    ts = now if now is not None else monotonic()
    key = _rate_limit_key(ip, identifier)
    timestamps = _prune(key, now=ts)
    timestamps.append(ts)
    _failures[key] = timestamps


def clear_login_failures(ip: str | None, identifier: str) -> None:
    """成功登录后清除该 key 的失败计数。"""
    _failures.pop(_rate_limit_key(ip, identifier), None)


def reset_all_login_rate_limits() -> None:
    """测试隔离：清空内存计数器。"""
    _failures.clear()
