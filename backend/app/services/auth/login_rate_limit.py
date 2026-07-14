"""登录失败限流（EW-A4 · TECH-SEC P1）。

双维度限流：
- identifier 维度：5 次失败 / 15 分钟滑动窗口
- IP 维度：20 次失败 / 5 分钟滑动窗口（防止同一 IP 换账号爆破）

单实例内存滑动窗口；多副本部署须换 Redis（Wave 2+）。
"""

from __future__ import annotations

from collections import defaultdict
from time import monotonic

# identifier 维度
MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60

# IP 维度
MAX_IP_FAILURES = 20
IP_WINDOW_SECONDS = 5 * 60

_failures: dict[str, list[float]] = defaultdict(list)
_ip_failures: dict[str, list[float]] = defaultdict(list)


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

    # IP 维度计数
    ip_key = ip or "unknown"
    ip_ts = _ip_prune(ip_key, now=ts)
    ip_ts.append(ts)
    _ip_failures[ip_key] = ip_ts


def _ip_prune(ip_key: str, *, now: float) -> list[float]:
    """裁剪 IP 维度过期记录。"""
    window_start = now - IP_WINDOW_SECONDS
    kept = [t for t in _ip_failures.get(ip_key, []) if t > window_start]
    if kept:
        _ip_failures[ip_key] = kept
    else:
        _ip_failures.pop(ip_key, None)
    return kept


def is_ip_login_rate_limited(
    ip: str | None,
    *,
    now: float | None = None,
) -> bool:
    """同 IP 是否已达失败上限（MAX_IP_FAILURES 次 / IP_WINDOW_SECONDS）。"""
    ts = now if now is not None else monotonic()
    ip_key = ip or "unknown"
    return len(_ip_prune(ip_key, now=ts)) >= MAX_IP_FAILURES


def clear_login_failures(ip: str | None, identifier: str) -> None:
    """成功登录后清除该 key 的失败计数。"""
    _failures.pop(_rate_limit_key(ip, identifier), None)


def reset_all_login_rate_limits() -> None:
    """测试隔离：清空内存计数器。"""
    _failures.clear()
    _ip_failures.clear()
