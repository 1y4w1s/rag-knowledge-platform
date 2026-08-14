"""B2 · agent_run_sweeper：running 超时强制 failed + pending 审批过期清理。

覆盖 masterplan 主题 B 步骤 3/4（T4 H1/H2 · P0-01/P1-03）：
- running run 超过 ``AGENT_RUN_STALE_MINUTES``（默认 15min）→ 强制 failed
  （running steps 置 error；条件更新幂等，重复清扫不覆盖终态）；
- pending 审批按 ``AGENT_APPROVAL_TTL_HOURS``（默认 24h）TTL 过期 → 置 expired
  （与 approvals.py 惰性判定同口径，sweeper 负责批量清理）；
- 消费方式：Celery beat 周期任务（``agent.sweep_agent_runs``）+ **启动时一次性扫描**
  （crash 残留兜底，main.py startup 调用）；干跑默认，单测/运维可直调函数。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.agent_approval import AgentApproval
from app.models.agent_run import AgentRun
from app.models.agent_step import AgentStep
from app.models.enums import AgentRunStatus, AgentStepStatus, ApprovalStatus
from app.services.audit.agent import audit_agent_approval_expired
from app.services.audit.log import write_audit_log

logger = logging.getLogger(__name__)


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class SweepReport:
    """单次清扫报告（dry_run 同构，便于运维预览）。"""

    scanned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    dry_run: bool = True
    stale_runs_found: int = 0
    runs_marked_failed: int = 0
    expired_approvals_found: int = 0
    approvals_marked_expired: int = 0

    def to_dict(self) -> dict:
        return {
            "scanned_at": self.scanned_at.isoformat(),
            "dry_run": self.dry_run,
            "stale_runs_found": self.stale_runs_found,
            "runs_marked_failed": self.runs_marked_failed,
            "expired_approvals_found": self.expired_approvals_found,
            "approvals_marked_expired": self.approvals_marked_expired,
        }


def _run_cutoff(now: datetime, stale_minutes: float | None) -> datetime:
    minutes = stale_minutes or settings.agent_run_stale_minutes
    return now - timedelta(minutes=minutes)


def _approval_cutoff(now: datetime, ttl_hours: float | None) -> datetime:
    hours = ttl_hours or settings.agent_approval_ttl_hours
    return now - timedelta(hours=hours)


async def scan_stale_agent_runs(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    stale_minutes: float | None = None,
) -> list[AgentRun]:
    """查出 running 且超过 deadline 的 run（crash/断线残留）。

    P2-A7：按「最后活动时间」判超时而非创建时间——最后 step 的开始时间即最后
    活动信号；无 step 时回退到 run 创建时间，避免合法长对话被误杀。
    """
    now = _ensure_aware(now or datetime.now(timezone.utc))
    last_step_at = (
        select(func.max(AgentStep.created_at))
        .where(AgentStep.run_id == AgentRun.id)
        .correlate(AgentRun)
        .scalar_subquery()
    )
    result = await db.execute(
        select(AgentRun).where(
            AgentRun.status == AgentRunStatus.running,
            func.coalesce(last_step_at, AgentRun.created_at)
            < _run_cutoff(now, stale_minutes),
        )
    )
    return list(result.scalars().all())


async def apply_stale_agent_runs(
    db: AsyncSession,
    *,
    dry_run: bool = True,
    now: datetime | None = None,
    stale_minutes: float | None = None,
) -> int:
    """超时 running → failed（running steps → error）+ 审计。返回标记数；幂等。"""
    now = _ensure_aware(now or datetime.now(timezone.utc))
    runs = await scan_stale_agent_runs(db, now=now, stale_minutes=stale_minutes)
    marked = 0
    for run in runs:
        if dry_run:
            continue
        age_seconds = (now - _ensure_aware(run.created_at)).total_seconds()
        # 条件更新幂等：仅 running 可写终态（重复清扫/与 in-flight finish 竞态安全）
        await db.execute(
            update(AgentRun)
            .where(
                AgentRun.id == run.id,
                AgentRun.status == AgentRunStatus.running,
            )
            .values(status=AgentRunStatus.failed, finished_at=now)
        )
        await db.execute(
            update(AgentStep)
            .where(
                AgentStep.run_id == run.id,
                AgentStep.status == AgentStepStatus.running,
            )
            .values(status=AgentStepStatus.error)
        )
        await write_audit_log(
            db,
            action="agent_run.sweep_marked_failed",
            resource_type="agent_run",
            resource_id=run.id,
            metadata={
                "run_id": str(run.id),
                "thread_id": str(run.thread_id),
                "age_seconds": round(age_seconds, 1),
                "stale_minutes": stale_minutes or settings.agent_run_stale_minutes,
            },
        )
        marked += 1

    await write_audit_log(
        db,
        action="agent_run.sweep",
        metadata={
            "dry_run": dry_run,
            "found": len(runs),
            "marked_failed": marked,
        },
    )
    await db.commit()
    return marked


async def scan_expired_approvals(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    ttl_hours: float | None = None,
) -> list[AgentApproval]:
    """查出 pending 且超 TTL 的审批（P1-03）。"""
    now = _ensure_aware(now or datetime.now(timezone.utc))
    result = await db.execute(
        select(AgentApproval).where(
            AgentApproval.status == ApprovalStatus.pending,
            AgentApproval.created_at < _approval_cutoff(now, ttl_hours),
        )
    )
    return list(result.scalars().all())


async def apply_expired_approvals(
    db: AsyncSession,
    *,
    dry_run: bool = True,
    now: datetime | None = None,
    ttl_hours: float | None = None,
) -> int:
    """过期 pending → expired + 审计。返回标记数；幂等。"""
    now = _ensure_aware(now or datetime.now(timezone.utc))
    approvals = await scan_expired_approvals(db, now=now, ttl_hours=ttl_hours)
    marked = 0
    for approval in approvals:
        if dry_run:
            continue
        if approval.status != ApprovalStatus.pending:
            continue
        approval.status = ApprovalStatus.expired
        approval.resolved_at = now
        await db.flush()
        await audit_agent_approval_expired(
            db,
            approval_id=approval.id,
            kb_id=approval.kb_id,
            filename=approval.filename,
        )
        marked += 1

    await write_audit_log(
        db,
        action="agent_approval.sweep",
        metadata={
            "dry_run": dry_run,
            "found": len(approvals),
            "marked_expired": marked,
        },
    )
    await db.commit()
    return marked


async def run_agent_sweep(
    db: AsyncSession,
    *,
    dry_run: bool = True,
    now: datetime | None = None,
) -> SweepReport:
    """合并清扫：stale runs + expired approvals（干跑默认）。"""
    now = _ensure_aware(now or datetime.now(timezone.utc))
    stale_runs = await scan_stale_agent_runs(db, now=now)
    expired_approvals = await scan_expired_approvals(db, now=now)
    report = SweepReport(
        scanned_at=now,
        dry_run=dry_run,
        stale_runs_found=len(stale_runs),
        expired_approvals_found=len(expired_approvals),
    )
    if not dry_run:
        report.runs_marked_failed = await apply_stale_agent_runs(
            db, dry_run=False, now=now
        )
        report.approvals_marked_expired = await apply_expired_approvals(
            db, dry_run=False, now=now
        )
    return report


async def run_agent_sweep_startup() -> SweepReport | None:
    """启动时一次性扫描：处理 crash 残留 running run / 过期审批（不阻断启动）。"""
    from app.core.database import SessionLocal

    try:
        async with SessionLocal() as db:
            report = await run_agent_sweep(db, dry_run=False)
        logger.info(
            "启动清扫完成: runs_marked_failed=%d approvals_marked_expired=%d",
            report.runs_marked_failed,
            report.approvals_marked_expired,
        )
        return report
    except Exception:
        logger.exception("启动清扫失败（不阻断启动）")
        return None


__all__ = [
    "SweepReport",
    "run_agent_sweep",
    "run_agent_sweep_startup",
    "scan_expired_approvals",
    "scan_stale_agent_runs",
    "apply_expired_approvals",
    "apply_stale_agent_runs",
]
