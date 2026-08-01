"""G5 文档写·待审 tool：delete_document / restore_document（G5-1）。

统一链路（A/B 同构）：
  解析意图 → 结构化提案(dry, commit=False) → 用户确认 →
  submit(commit=True 建 pending) → 管理员审批 → 采纳执行
  （由 approvals.py 调底层 _soft_delete_no_commit / _restore_no_commit）。

- dry：解析 kb + 文档，做预检（processing / 同名冲突），返回结构化提案；
  不建 approval、不改动文档状态。
- commit=True：经 scope 校验后建 AgentApproval(pending) + 审计，返回 approval_id；
  不执行删除/恢复（执行在采纳 resolve_document_write_approval 时）。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_approval import AgentApproval
from app.models.document import Document
from app.models.enums import ApprovalKind, ApprovalStatus, DocumentStatus
from app.models.knowledge_base import KnowledgeBase
from app.core.deps import CurrentUser, KbAction, require_kb_access
from app.services.agent.tools.scope import AgentToolScope, ToolDenial
from app.services.audit.agent import audit_agent_approval_created, safe_audit


class DocumentWriteFailure(str, Enum):
    """失败原因码（G5-1.3）。"""

    kb_not_visible = "kb_not_visible"  # 目标库越权 / 不可见
    doc_not_found = "doc_not_found"  # 文档不存在 / 非目标状态
    bad_request = "bad_request"


@dataclass(frozen=True, slots=True)
class DocumentWriteProposal:
    """结构化提案（A/B 通用；前端 proposal_preview 渲染 + confirm_token 绑定）。"""

    operation: str  # "delete" / "restore"
    document_id: uuid.UUID
    filename: str
    kb_id: uuid.UUID
    kb_name: str
    impact: str
    conflict: str | None = None  # 预检冲突提示（processing / 同名冲突）


@dataclass(frozen=True, slots=True)
class DocumentWriteToolResult:
    ok: bool
    summary: str
    reason: DocumentWriteFailure | None = None
    proposal: DocumentWriteProposal | None = None  # dry 阶段非空
    approval_id: uuid.UUID | None = None  # commit 阶段非空


def _proposal_to_dict(p: DocumentWriteProposal) -> dict[str, Any]:
    return {
        "operation": p.operation,
        "document_id": str(p.document_id),
        "filename": p.filename,
        "kb_id": str(p.kb_id),
        "kb_name": p.kb_name,
        "impact": p.impact,
        "conflict": p.conflict,
    }


async def _create_document_write_approval(
    db: AsyncSession,
    *,
    kind: ApprovalKind,
    resolved_kb_id: uuid.UUID,
    doc: Document,
    thread_id: uuid.UUID,
    run_id: uuid.UUID,
    user_id: uuid.UUID,
    proposal: DocumentWriteProposal,
) -> DocumentWriteToolResult:
    """建 AgentApproval(pending) + 审计（不执行删除/恢复）。幂等。"""
    existing = await db.scalar(
        select(AgentApproval).where(
            AgentApproval.run_id == run_id,
            AgentApproval.document_id == doc.id,
            AgentApproval.kind == kind,
            AgentApproval.status == ApprovalStatus.pending,
        )
    )
    if existing is not None:
        return DocumentWriteToolResult(
            ok=True, summary="待审已存在（幂等）", approval_id=existing.id
        )

    approval = AgentApproval(
        id=uuid.uuid4(),
        run_id=run_id,
        thread_id=thread_id,
        user_id=user_id,
        kind=kind,
        status=ApprovalStatus.pending,
        kb_id=resolved_kb_id,
        filename=doc.filename,
        document_id=doc.id,
        payload_json={"proposal": _proposal_to_dict(proposal)},
    )
    db.add(approval)
    await db.flush()
    await safe_audit(
        audit_agent_approval_created(
            db,
            actor_user_id=user_id,
            approval_id=approval.id,
            kb_id=resolved_kb_id,
            filename=doc.filename,
            draft_chars=0,
        )
    )
    return DocumentWriteToolResult(
        ok=True, summary=f"已生成待审批：{kind.value}", approval_id=approval.id
    )


async def run_delete_document(
    db: AsyncSession,
    tool_scope: AgentToolScope,
    *,
    kb_id: uuid.UUID,
    document_id: uuid.UUID,
    run_id: uuid.UUID,
    thread_id: uuid.UUID,
    user_id: uuid.UUID,
    commit: bool = False,
) -> DocumentWriteToolResult:
    resolved = tool_scope.resolve_target_kb_for_edit(kb_id)
    if isinstance(resolved, ToolDenial):
        return DocumentWriteToolResult(
            ok=False,
            summary=resolved.summary,
            reason=DocumentWriteFailure.kb_not_visible,
        )

    doc = await db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.kb_id == resolved,
            Document.deleted_at.is_(None),
        )
    )
    if doc is None:
        return DocumentWriteToolResult(
            ok=False,
            summary="文档不存在或非 active 状态",
            reason=DocumentWriteFailure.doc_not_found,
        )

    conflict = None
    if doc.status == DocumentStatus.processing:
        conflict = "文档正在整理中，暂不可删除（请稍后再试）"

    kb = await db.get(KnowledgeBase, resolved)
    kb_name = kb.name if kb is not None else ""
    impact = (
        "将移入回收站，保留 30 天可恢复；引用该文档的历史对话保留，"
        "但检索不再返回其内容。"
    )
    proposal = DocumentWriteProposal(
        operation="delete",
        document_id=doc.id,
        filename=doc.filename,
        kb_id=resolved,
        kb_name=kb_name,
        impact=impact,
        conflict=conflict,
    )
    if not commit:
        return DocumentWriteToolResult(
            ok=True, summary=f"提案：删除《{doc.filename}》", proposal=proposal
        )
    return await _create_document_write_approval(
        db,
        kind=ApprovalKind.delete_document,
        resolved_kb_id=resolved,
        doc=doc,
        thread_id=thread_id,
        run_id=run_id,
        user_id=user_id,
        proposal=proposal,
    )


async def run_restore_document(
    db: AsyncSession,
    tool_scope: AgentToolScope,
    *,
    kb_id: uuid.UUID,
    document_id: uuid.UUID,
    run_id: uuid.UUID,
    thread_id: uuid.UUID,
    user_id: uuid.UUID,
    commit: bool = False,
) -> DocumentWriteToolResult:
    resolved = tool_scope.resolve_target_kb_for_edit(kb_id)
    if isinstance(resolved, ToolDenial):
        return DocumentWriteToolResult(
            ok=False,
            summary=resolved.summary,
            reason=DocumentWriteFailure.kb_not_visible,
        )

    doc = await db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.kb_id == resolved,
            Document.deleted_at.is_not(None),
        )
    )
    if doc is None:
        return DocumentWriteToolResult(
            ok=False,
            summary="文档不在回收站中",
            reason=DocumentWriteFailure.doc_not_found,
        )

    clash = await db.scalar(
        select(Document.id)
        .where(
            Document.kb_id == resolved,
            Document.id != doc.id,
            Document.deleted_at.is_(None),
            func.lower(Document.filename) == doc.filename.lower(),
        )
        .limit(1)
    )
    conflict = (
        "库内已有同名 active 文档，恢复将冲突（需先处理同名文档）"
        if clash is not None
        else None
    )

    kb = await db.get(KnowledgeBase, resolved)
    kb_name = kb.name if kb is not None else ""
    impact = "将从回收站恢复为 active，检索可重新返回其内容。"
    proposal = DocumentWriteProposal(
        operation="restore",
        document_id=doc.id,
        filename=doc.filename,
        kb_id=resolved,
        kb_name=kb_name,
        impact=impact,
        conflict=conflict,
    )
    if not commit:
        return DocumentWriteToolResult(
            ok=True, summary=f"提案：恢复《{doc.filename}》", proposal=proposal
        )
    return await _create_document_write_approval(
        db,
        kind=ApprovalKind.restore_document,
        resolved_kb_id=resolved,
        doc=doc,
        thread_id=thread_id,
        run_id=run_id,
        user_id=user_id,
        proposal=proposal,
    )


async def submit_document_write(
    db: AsyncSession,
    *,
    current_user: CurrentUser,
    kb_id: uuid.UUID,
    document_id: uuid.UUID,
    operation: str,
    thread_id: uuid.UUID,
    run_id: uuid.UUID,
) -> DocumentWriteToolResult:
    """前端确认后建 AgentApproval(pending)（G5：二次校验 + 审计，不执行删除/恢复）。

    与 run_*_document(commit=True) 同路径，但额外强制 kb 写权限
    （require_kb_access(write) → 仅 Admin/Owner），并据 operation 取目标文档
    的正确状态（delete 需 active / restore 需回收站）。
    """
    if operation not in ("delete", "restore"):
        return DocumentWriteToolResult(
            ok=False, summary="不支持的操作", reason=DocumentWriteFailure.bad_request
        )

    # 写权限二次校验（Member 硬闯 → 403）：与 resolve 同守卫。
    await require_kb_access(
        kb_id=kb_id, action=KbAction.write, current_user=current_user, db=db
    )

    kind = (
        ApprovalKind.delete_document
        if operation == "delete"
        else ApprovalKind.restore_document
    )

    if operation == "delete":
        doc = await db.scalar(
            select(Document).where(
                Document.id == document_id,
                Document.kb_id == kb_id,
                Document.deleted_at.is_(None),
            )
        )
        if doc is None:
            return DocumentWriteToolResult(
                ok=False,
                summary="文档不存在或非 active 状态",
                reason=DocumentWriteFailure.doc_not_found,
            )
        conflict = (
            "文档正在整理中，暂不可删除（请稍后再试）"
            if doc.status == DocumentStatus.processing
            else None
        )
        impact = (
            "将移入回收站，保留 30 天可恢复；引用该文档的历史对话保留，"
            "但检索不再返回其内容。"
        )
    else:
        doc = await db.scalar(
            select(Document).where(
                Document.id == document_id,
                Document.kb_id == kb_id,
                Document.deleted_at.is_not(None),
            )
        )
        if doc is None:
            return DocumentWriteToolResult(
                ok=False,
                summary="文档不在回收站中",
                reason=DocumentWriteFailure.doc_not_found,
            )
        clash = await db.scalar(
            select(Document.id)
            .where(
                Document.kb_id == kb_id,
                Document.id != doc.id,
                Document.deleted_at.is_(None),
                func.lower(Document.filename) == doc.filename.lower(),
            )
            .limit(1)
        )
        conflict = (
            "库内已有同名 active 文档，恢复将冲突（需先处理同名文档）"
            if clash is not None
            else None
        )
        impact = "将从回收站恢复为 active，检索可重新返回其内容。"

    kb = await db.get(KnowledgeBase, kb_id)
    kb_name = kb.name if kb is not None else ""
    proposal = DocumentWriteProposal(
        operation=operation,
        document_id=doc.id,
        filename=doc.filename,
        kb_id=kb_id,
        kb_name=kb_name,
        impact=impact,
        conflict=conflict,
    )
    return await _create_document_write_approval(
        db,
        kind=kind,
        resolved_kb_id=kb_id,
        doc=doc,
        thread_id=thread_id,
        run_id=run_id,
        user_id=current_user.id,
        proposal=proposal,
    )


__all__ = [
    "DocumentWriteFailure",
    "DocumentWriteProposal",
    "DocumentWriteToolResult",
    "run_delete_document",
    "run_restore_document",
    "submit_document_write",
]
