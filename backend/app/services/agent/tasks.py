"""B2 · agent 清扫 Celery 周期任务（beat 驱动；eager 本地由启动扫描兜底）。"""

from __future__ import annotations

import anyio

from app.core.database import SessionLocal
from app.services.agent.sweeper import run_agent_sweep
from app.services.ingestion.celery_app import celery_app


@celery_app.task(name="agent.sweep_agent_runs")
def sweep_agent_runs_task() -> dict:
    """running 超时强制 failed + pending 审批过期清理（非干跑）。"""

    async def _run() -> dict:
        async with SessionLocal() as db:
            report = await run_agent_sweep(db, dry_run=False)
            return report.to_dict()

    return anyio.run(_run)


__all__ = ["sweep_agent_runs_task"]
