"""进程级延迟追踪（P50/P99 百分位统计）。

线程安全：使用 threading.Lock 保护 observations 列表。
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Sequence


class LatencyTracker:
    """轻量级延迟追踪器：记录观测值，计算 P50/P95/P99。

    用法：
        tracker = LatencyTracker(name="retrieval.vector_recall")
        tracker.record(42.5)  # 42.5ms
        stats = tracker.stats()  # {"p50": 42.5, "p95": ..., "p99": ..., "count": 1}
    """

    def __init__(self, name: str, max_samples: int = 10000):
        self.name = name
        self._max_samples = max_samples
        self._lock = threading.Lock()
        self._observations: list[float] = []

    def record(self, milliseconds: float) -> None:
        with self._lock:
            self._observations.append(milliseconds)
            if len(self._observations) > self._max_samples:
                self._observations.pop(0)

    def _percentile(self, sorted_values: Sequence[float], p: float) -> float:
        if not sorted_values:
            return 0.0
        idx = math.ceil(p / 100.0 * len(sorted_values)) - 1
        return sorted_values[max(0, min(idx, len(sorted_values) - 1))]

    def stats(self, min_count: int = 1) -> dict:
        with self._lock:
            obs = list(self._observations)
        count = len(obs)
        if count < min_count:
            return {"count": count}
        obs.sort()
        return {
            "count": count,
            "p50": round(self._percentile(obs, 50), 1),
            "p95": round(self._percentile(obs, 95), 1),
            "p99": round(self._percentile(obs, 99), 1),
            "max": round(obs[-1], 1) if obs else 0.0,
        }

    def clear(self) -> None:
        with self._lock:
            self._observations.clear()


# ── 全局追踪器注册表 ──

_trackers: dict[str, LatencyTracker] = {}
_tracker_lock = threading.Lock()


def get_tracker(name: str, max_samples: int = 10000) -> LatencyTracker:
    global _trackers
    with _tracker_lock:
        if name not in _trackers:
            _trackers[name] = LatencyTracker(name=name, max_samples=max_samples)
        return _trackers[name]


def all_tracker_stats(min_count: int = 10) -> dict[str, dict]:
    global _trackers
    with _tracker_lock:
        return {
            name: tracker.stats(min_count=min_count)
            for name, tracker in sorted(_trackers.items())
        }
