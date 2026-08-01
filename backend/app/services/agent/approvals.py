"""G4-3.1 · Approval 服务层（adopt 路径）。

``resolve_adopt_approval``：校验 ``pending`` + kb write 权限 + Admin/Owner 角色 →
调 ``adopt_draft_to_kb`` → 落 ``agent_approvals.status=adopted`` + ``document_id``
+ ``resolved_at``。

权限/归属二次校验（G4-3.1 红线）：
- 真实写库权限须在 resolve 二次校验（kb write + 角色 + pending）；前端
  ``can_user_adopt_kb`` / ``can_user_adopt_in_workspace`` 仅为「是否显示采纳钮」信号。
- Member 永不可采纳（HA-2-A · H4-1-B）；adopt **绝不**暴露给模型（G4-2.1 红线）。
- adopt 异步（H4-4-A）：返回 ``document_id`` + processing，不阻塞 ingestion。

cancel 路径（G4-E5/E6/E9）属 G4-3.3，见 ``resolve_cancel_approval``。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import BackgroundTasks, HTTPException, status
from app.core.exceptions import NotFoundError, ConflictError, ServiceError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, KbAction, require_kb_access
from app.models.agent_approval import AgentApproval
from app.models.document import Document
from app.models.enums import AccountType, ApprovalKind, ApprovalStatus, OrgRole
from app.services.agent.adopt import (
    adopt_draft_to_kb,
    bind_adopt_background_tasks,
    unbind_adopt_background_tasks,
)
from app.services.documents.lifecycle import _soft_delete_no_commit
from app.services.documents.trash import _restore_no_commit
from sqlalchemy import select
from app.services.audit.agent import (
    audit_agent_approval_adopted,
    audit_agent_approval_cancelled,
    safe_audit,
)


async def resolve_adopt_approval(
    db: AsyncSession,
    *,
    approval_id: UUID,
    current_user: CurrentUser,
    background_tasks: Optional[BackgroundTasks] = None,
) -> AgentApproval:
    """采纳一个 pending 审批：二次校验权限 + 状态 → 写库 → 落终态。

    返回已更新（flush 未 commit）的 ``AgentApproval``；调用方负责 commit。

    校验顺序（影响 E 语义）：
      1. approval 存在性 → 404（G4-E8/E15 归属校验失败兜底）
      2. kb 可见/可写 + 角色 → 404（kb 不存在）/ 403（跨库·不可写·Member 硬闯）
         （G4-E1 Member 403 / 归属校验失败 403/404）
      3. 状态必须为 pending → 否则 409（G4-E3 重复采纳 / 非 pending G4-E15）
    """
    approval = await db.get(AgentApproval, approval_id)
    if approval is None:
        raise NotFoundError("审批不存在")

    # 归属 + 权限二次校验：approval 目标 kb 必须在当前用户可见/可写范围，且角色可写。
    # 跨组织库 / 不可见库 → 403/404；Member 写动作 → 403（G4-E1）。
    # G4-3.5：在异常上标注 audit_reason，供路由 denied 审计精确归因（不改变出参）。
    try:
        kb = await require_kb_access(
            kb_id=approval.kb_id,
            action=KbAction.write,
            current_user=current_user,
            db=db,
        )
    except (HTTPException, ServiceError) as e:
        if e.status_code == status.HTTP_404_NOT_FOUND:
            e.audit_reason = "grant_revoked"  # kb 不存在
        elif e.status_code == status.HTTP_403_FORBIDDEN:
            # Member 角色写动作 → member_forbidden；其余（跨库/不可见）→ grant_revoked
            e.audit_reason = (
                "member_forbidden"
                if (
                    current_user.account_type == AccountType.enterprise
                    and current_user.org_role == OrgRole.member
                )
                else "grant_revoked"
            )
        raise

    # 状态校验：仅 pending 可采纳；已 adopted/cancelled/expired → 409。
    if approval.status != ApprovalStatus.pending:
        exc = ConflictError("该审批已处理，不可重复采纳")
        exc.audit_reason = "not_pending"  # G4-3.5 denied 归因
        raise exc

    # 写库（按 kind 分发 · 同事务 · 不提交；caller 统一 commit）。
    if approval.kind == ApprovalKind.adopt_faq:
        document_id = await _resolve_adopt_faq(
            db, approval=approval, kb=kb, background_tasks=background_tasks
        )
    else:
        # delete_document / restore_document：二次校验 + 执行（H3 软删 / 回收站恢复）
        document_id = await _resolve_document_write(
            db, approval=approval, current_user=current_user
        )

    approval.status = ApprovalStatus.adopted
    approval.document_id = document_id
    approval.resolved_at = datetime.now(timezone.utc)
    await db.flush()

    # G4-3.5 审计钩子：采纳（异常容忍，不冒泡为 500；同 db 会话，caller 统一 commit）。
    await safe_audit(
        audit_agent_approval_adopted(
            db,
            resolver_user_id=current_user.id,
            approval_id=approval.id,
            document_id=document_id,
            kb_id=approval.kb_id,
            filename=approval.filename,
        )
    )
    return approval


async def _resolve_adopt_faq(
    db: AsyncSession,
    *,
    approval: AgentApproval,
    kb,
    background_tasks: Optional[BackgroundTasks] = None,
) -> UUID:
    """adopt_faq 采纳：adopt_draft_to_kb 落库 + 异步 ingestion（H4-4-A）。"""
    bind_token = (
        bind_adopt_background_tasks(background_tasks)
        if background_tasks is not None
        else None
    )
    try:
        document_id = await adopt_draft_to_kb(db, approval, kb)
    finally:
        if bind_token is not None:
            unbind_adopt_background_tasks(bind_token)
    return document_id


async def _resolve_document_write(
    db: AsyncSession,
    *,
    approval: AgentApproval,
    current_user: CurrentUser,
) -> UUID:
    """delete_document / restore_document 采纳：二次校验 + 执行（同事务，不提交）。

    权限/归属已由 resolve_adopt_approval 顶部 require_kb_access(write) 校验；
    此处仅按状态取目标文档并复用底层 no_commit 变体（保留 processing / 同名冲突检查）。
    """
    document_id = approval.document_id
    if approval.kind == ApprovalKind.delete_document:
        doc = await db.scalar(
            select(Document).where(
                Document.id == document_id,
                Document.kb_id == approval.kb_id,
                Document.deleted_at.is_(None),
            )
        )
        if doc is None:
            raise NotFoundError("目标文档不存在或非 active 状态")
        await _soft_delete_no_commit(
            db, doc, actor_user_id=current_user.id, kb_id=approval.kb_id, ip=None
        )
    elif approval.kind == ApprovalKind.restore_document:
        doc = await db.scalar(
            select(Document).where(
                Document.id == document_id,
                Document.kb_id == approval.kb_id,
                Document.deleted_at.is_not(None),
            )
        )
        if doc is None:
            raise NotFoundError("目标文档不在回收站中")
        await _restore_no_commit(
            db, doc, actor_user_id=current_user.id, kb_id=approval.kb_id, ip=None
        )
    else:
        raise ValidationError(detail="未知审批类型")
    return document_id


async def resolve_cancel_approval(
    db: AsyncSession,
    *,
    approval_id: UUID,
    current_user: CurrentUser,
) -> AgentApproval:
    """取消一个 pending 审批（G4-3.3 · H4-5-B）。

    **仅翻转** ``agent_approvals.status = cancelled`` + ``resolved_at``；
    **绝不**写库 / 落 md / ``_v2`` / ingestion / 改源 PDF（G4-3.3 红线）。

    校验顺序（影响 E 语义）：
      1. approval 存在性 → 404（G4-E8）
      2. 权限：创建者本人 → 放行；否则 ``require_kb_access(KbAction.write)``
         → 403（Member 硬闯他人 pending = G4-E9）/ 404（kb 不存在）
      3. 状态须 ``pending`` → 否则 409（G4-E5 · 已 adopted / 已 cancelled）
    """
    approval = await db.get(AgentApproval, approval_id)
    if approval is None:
        raise NotFoundError("审批不存在")

    # H4-5-B：创建者本人可取消自己的卡；否则需为 kb Admin/Owner（写权限）。
    # 创建者路径跳过 require_kb_access（Member 也能撤自己创建的卡）。
    is_creator = approval.user_id == current_user.id
    if not is_creator:
        # require_kb_access 内部：kb 不存在 → 404；跨库 / Member 写动作 → 403。
        # G4-3.5：在异常上标注 audit_reason，供路由 denied 审计精确归因。
        try:
            await require_kb_access(
                kb_id=approval.kb_id,
                action=KbAction.write,
                current_user=current_user,
                db=db,
            )
        except (HTTPException, ServiceError) as e:
            if e.status_code == status.HTTP_404_NOT_FOUND:
                e.audit_reason = "grant_revoked"  # kb 不存在
            elif e.status_code == status.HTTP_403_FORBIDDEN:
                e.audit_reason = (
                    "member_forbidden"
                    if (
                        current_user.account_type == AccountType.enterprise
                        and current_user.org_role == OrgRole.member
                    )
                    else "grant_revoked"
                )
            raise

    # 状态校验：仅 pending 可取消；已 adopted/cancelled/expired → 409（G4-E5）。
    if approval.status != ApprovalStatus.pending:
        exc = ConflictError("该审批已处理，不可重复取消")
        exc.audit_reason = "not_pending"  # G4-3.5 denied 归因
        raise exc

    approval.status = ApprovalStatus.cancelled
    approval.resolved_at = datetime.now(timezone.utc)
    await db.flush()

    # G4-3.5 审计钩子：取消（异常容忍，不冒泡为 500；同 db 会话，caller 统一 commit）。
    await safe_audit(
        audit_agent_approval_cancelled(
            db,
            resolver_user_id=current_user.id,
            approval_id=approval.id,
        )
    )
    return approval


__all__ = ["resolve_adopt_approval", "resolve_cancel_approval"]
