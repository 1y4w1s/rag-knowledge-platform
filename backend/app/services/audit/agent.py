"""Agent 精准模式审计钩子（G3-2.6 · plan §7 · G3-E10）。

G4-3.5 扩展：approval 4 事件（created / adopted / cancelled / denied）。
红线：metadata **绝不**含草稿全文（payload_json.markdown）；仅放 draft_chars 字符数。
"""

from __future__ import annotations

from collections.abc import Awaitable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.audit.log import write_audit_log

AGENT_MODE_THOROUGH = "thorough"


async def safe_audit(coro: Awaitable[None]) -> None:
    """审计异常容忍：绝不冒泡为 500 / 阻塞主流程（G4-3.5 红线）。

    审计写入失败（DB 抖动等）只会被吞掉，不影响主业务提交。
    """
    try:
        await coro
    except Exception:
        return


async def audit_agent_run_started(
    db: AsyncSession,
    *,
    actor_user_id: UUID,
    run_id: UUID,
    thread_id: UUID,
    max_steps: int,
    mode: str = AGENT_MODE_THOROUGH,
) -> None:
    """精准 run 开始 → agent.run_started（不含用户问题全文）。"""
    await write_audit_log(
        db,
        action="agent.run_started",
        actor_user_id=actor_user_id,
        resource_type="agent_run",
        resource_id=run_id,
        metadata={
            "run_id": str(run_id),
            "thread_id": str(thread_id),
            "mode": mode,
            "max_steps": max_steps,
        },
    )


async def audit_agent_tool_executed(
    db: AsyncSession,
    *,
    actor_user_id: UUID,
    run_id: UUID,
    step: int,
    tool: str,
    ok: bool,
    latency_ms: int,
) -> None:
    """单步 tool 执行 → agent.tool_executed（metadata 无 query 全文）。"""
    await write_audit_log(
        db,
        action="agent.tool_executed",
        actor_user_id=actor_user_id,
        resource_type="agent_run",
        resource_id=run_id,
        metadata={
            "run_id": str(run_id),
            "step": step,
            "tool": tool,
            "ok": ok,
            "latency_ms": latency_ms,
        },
    )


async def audit_agent_tool_denied(
    db: AsyncSession,
    *,
    actor_user_id: UUID,
    run_id: UUID,
    tool: str,
    reason: str = "forbidden_kb",
) -> None:
    """越权 kb → agent.tool_denied。"""
    await write_audit_log(
        db,
        action="agent.tool_denied",
        actor_user_id=actor_user_id,
        resource_type="agent_run",
        resource_id=run_id,
        metadata={
            "run_id": str(run_id),
            "tool": tool,
            "reason": reason,
        },
    )


async def audit_agent_run_completed(
    db: AsyncSession,
    *,
    actor_user_id: UUID,
    run_id: UUID,
    steps_used: int,
    capped: bool,
    citation_count: int,
) -> None:
    """精准 run 结束 → agent.run_completed。"""
    await write_audit_log(
        db,
        action="agent.run_completed",
        actor_user_id=actor_user_id,
        resource_type="agent_run",
        resource_id=run_id,
        metadata={
            "run_id": str(run_id),
            "steps_used": steps_used,
            "capped": capped,
            "citation_count": citation_count,
        },
    )


async def audit_agent_approval_created(
    db: AsyncSession,
    *,
    actor_user_id: UUID,
    approval_id: UUID,
    kb_id: UUID,
    filename: str,
    draft_chars: int,
) -> None:
    """草稿生成 → agent.approval_created。

    metadata **仅**放 draft_chars 字符数，**绝不**含草稿全文（payload_json.markdown）。
    """
    await write_audit_log(
        db,
        action="agent.approval_created",
        actor_user_id=actor_user_id,
        resource_type="agent_approval",
        resource_id=approval_id,
        kb_id=kb_id,
        metadata={
            "approval_id": str(approval_id),
            "kb_id": str(kb_id),
            "filename": filename,
            "draft_chars": draft_chars,
        },
    )


async def audit_agent_approval_adopted(
    db: AsyncSession,
    *,
    resolver_user_id: UUID,
    approval_id: UUID,
    document_id: UUID,
    kb_id: UUID,
    filename: str,
) -> None:
    """用户采纳 → agent.approval_adopted（含 document_id / resolver_user_id）。"""
    await write_audit_log(
        db,
        action="agent.approval_adopted",
        actor_user_id=resolver_user_id,
        resource_type="agent_approval",
        resource_id=approval_id,
        kb_id=kb_id,
        metadata={
            "approval_id": str(approval_id),
            "document_id": str(document_id),
            "kb_id": str(kb_id),
            "filename": filename,
            "resolver_user_id": str(resolver_user_id),
        },
    )


async def audit_agent_approval_cancelled(
    db: AsyncSession,
    *,
    resolver_user_id: UUID,
    approval_id: UUID,
) -> None:
    """用户取消 → agent.approval_cancelled（含 resolver_user_id）。"""
    await write_audit_log(
        db,
        action="agent.approval_cancelled",
        actor_user_id=resolver_user_id,
        resource_type="agent_approval",
        resource_id=approval_id,
        metadata={
            "approval_id": str(approval_id),
            "resolver_user_id": str(resolver_user_id),
        },
    )


async def audit_agent_approval_denied(
    db: AsyncSession,
    *,
    approval_id: UUID,
    reason: str,
) -> None:
    """采纳/取消被拒 → agent.approval_denied。

    reason ∈ {member_forbidden, grant_revoked, not_pending}。
    metadata **仅**含 approval_id + reason，无草稿全文。actor 由路由决定是否在
    独立会话中记录；本函数严格按 plan §7 只写 {approval_id, reason}。
    """
    await write_audit_log(
        db,
        action="agent.approval_denied",
        resource_type="agent_approval",
        resource_id=approval_id,
        metadata={
            "approval_id": str(approval_id),
            "reason": reason,
        },
    )
