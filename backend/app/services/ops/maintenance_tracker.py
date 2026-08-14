"""运维维护状态追踪（物尽其用 Phase 4）。

记录每项维护任务的最近执行时间，通过 /health/detailed 暴露。
"""

from __future__ import annotations

from datetime import datetime, timezone

_MAINTENANCE_HISTORY: dict[str, datetime] = {}

MAINTENANCE_TASKS = [
    "orphan_scan",
    "trash_purge",
    "stale_scan",
    "chat_retention",
    "dedup_documents",
    "reindex_pgvector",
]


def record_maintenance(kind: str) -> None:
    """记录某项维护任务的执行时间（幂等）。"""
    if kind in MAINTENANCE_TASKS:
        _MAINTENANCE_HISTORY[kind] = datetime.now(timezone.utc)


def get_maintenance_status() -> dict[str, dict]:
    """返回每项维护任务的状态和距上次执行天数。"""
    now = datetime.now(timezone.utc)
    result: dict[str, dict] = {}
    for task in MAINTENANCE_TASKS:
        last = _MAINTENANCE_HISTORY.get(task)
        if last is None:
            result[task] = {"days_since": None, "status": "never"}
        else:
            days = (now - last).days
            result[task] = {
                "days_since": days,
                "status": "overdue" if days > 35 else "ok",
            }
    return result
