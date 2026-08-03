"""G4-3.1 · Agent approval resolve API（adopt 落库 + G4-3.3 cancel 翻转状态）。

``POST /api/v1/agent/approvals/{approval_id}/resolve``
- Body：``{ "action": "adopt" | "cancel" }``
- adopt 出参：``{ document_id, kb_id, filename, status: "processing" }``
- cancel 出参：``{ ok: true }``（仅翻转 ``agent_approvals.status``）

JWT 校验复用现网 ``get_current_user`` 依赖（与 ``ask_threads.py`` 同构）。
红线：resolve 是独立 HTTP 端点，**不在 SSE 层写库**；adopt 异步返回 processing；
cancel **绝不**写库 / 落 md / ``_v2`` / ingestion / 改源 PDF（G4-3.3 红线）。
"""

from __future__ import annotations

import uuid
from typing import Annotated, Union
from uuid import UUID

from app.core.exceptions import ServiceError, ValidationError
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal, get_db
from app.core.deps import (
    CurrentUser,
    KbAction,
    get_current_user,
    require_kb_access,
)
from app.models.agent_approval import AgentApproval
from app.models.document import Document
from app.models.enums import ApprovalKind
from app.services.agent.approvals import (
    resolve_adopt_approval,
    resolve_cancel_approval,
)
from app.services.agent.dispatch import build_kb_tool_scope
from app.services.agent.tools.document_write import (
    _proposal_to_dict,
    require_thread_owner,
    run_delete_document,
    run_restore_document,
    submit_document_write,
)
from app.services.audit.agent import audit_agent_approval_denied


class ResolveApprovalRequest(BaseModel):
    action: str  # "adopt" | "cancel"


class AdoptApprovalResponse(BaseModel):
    document_id: UUID
    kb_id: UUID
    filename: str
    status: str = "processing"


class CancelApprovalResponse(BaseModel):
    ok: bool = True


class SubmitDocumentWriteRequest(BaseModel):
    """前端确认提案后建 pending（G5：删除/恢复二次校验入口）。"""

    thread_id: UUID
    kb_id: UUID
    document_id: UUID
    operation: str  # "delete" | "restore"
    run_id: UUID


class SubmitDocumentWriteResponse(BaseModel):
    approval_id: UUID
    status: str = "pending"


class ClarifyDocumentWriteRequest(BaseModel):
    """B 路径歧义澄清：用户点选目标文档后重新生成提案（dry）。"""

    thread_id: UUID
    document_id: UUID
    operation: str  # "delete" | "restore"


router = APIRouter(prefix="/agent", tags=["agent"])


@router.post(
    "/approvals/{approval_id}/resolve",
    status_code=status.HTTP_200_OK,
)
async def resolve_approval(
    approval_id: UUID,
    body: ResolveApprovalRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
) -> Union[AdoptApprovalResponse, CancelApprovalResponse]:
    """采纳/取消写库审批（G4-3.1 adopt · G4-3.3 cancel）。

    - ``action=adopt``  → 写库 + 异步 ingestion（H4-4-A），返回 document_id + processing。
    - ``action=cancel`` → 仅翻转 ``agent_approvals.status=cancelled``（G4-3.3 红线：不写库）。
    - 其余 action       → 422（未知动作）。
    """
    try:
        if body.action == "adopt":
            approval = await resolve_adopt_approval(
                db,
                approval_id=approval_id,
                current_user=current_user,
                background_tasks=background_tasks,
            )
            await db.commit()
            # 返回实际落库文件名（可能因 H4-6-A 同名而自动 _v2），而非请求时的文件名。
            doc = await db.get(Document, approval.document_id)
            stored_filename = doc.filename if doc is not None else approval.filename
            # 状态随 kind：adopt_faq 异步 ingestion → processing；
            # delete/restore 同步执行 → deleted / restored。
            if approval.kind == ApprovalKind.adopt_faq:
                status_value = "processing"
            elif approval.kind == ApprovalKind.delete_document:
                status_value = "deleted"
            else:
                status_value = "restored"
            return AdoptApprovalResponse(
                document_id=approval.document_id,
                kb_id=approval.kb_id,
                filename=stored_filename,
                status=status_value,
            )

        if body.action == "cancel":
            # G4-3.3：仅翻转状态，绝不写库 / _v2 / ingestion。
            approval = await resolve_cancel_approval(
                db,
                approval_id=approval_id,
                current_user=current_user,
            )
            await db.commit()
            return CancelApprovalResponse(ok=True)

        # 未知 action → 422（G4-3.3：422 守卫降级为「未知 action 才 422」）。
        raise ValidationError(
            detail="action 仅支持 adopt 或 cancel",
        )
    except (HTTPException, ServiceError) as exc:
        # G4-3.5：denied 审计（撤销/采纳被拒）。主事务即将回滚，必须用**独立会话**
        # 立即 commit，避免被主请求的回滚吞掉；写完后原样 re-raise 原异常。
        await _audit_approval_denied(approval_id, exc)
        if getattr(exc, "audit_reason", None) == "expired":
            # B2（P1-03）：惰性过期在主事务内判定并置 expired——行锁内不能用独立会话
            # 更新同行使锁自死，故在回滚前显式提交该状态转换（审计随主事务落库）。
            await db.commit()
        raise


@router.post(
    "/document-write/submit",
    status_code=status.HTTP_200_OK,
    response_model=SubmitDocumentWriteResponse,
)
async def submit_document_write_approval(
    body: SubmitDocumentWriteRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubmitDocumentWriteResponse:
    """确认文档操作提案 → 建 AgentApproval(pending)（G5）。

    - 强制 kb 写权限（仅 Admin/Owner）；
    - 据 operation 取目标文档正确状态（delete 需 active / restore 需回收站）；
    - 建 pending + 审计；返回 approval_id 供前端渲染审批卡。
    """
    result = await submit_document_write(
        db,
        current_user=current_user,
        kb_id=body.kb_id,
        document_id=body.document_id,
        operation=body.operation,
        thread_id=body.thread_id,
        run_id=body.run_id,
    )
    if not result.ok or result.approval_id is None:
        raise ValidationError(detail=result.summary or "无法生成待审批")
    await db.commit()
    return SubmitDocumentWriteResponse(approval_id=result.approval_id)


@router.post(
    "/document-write/clarify",
    status_code=status.HTTP_200_OK,
)
async def clarify_document_write(
    body: ClarifyDocumentWriteRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """B 路径歧义澄清（情景 5）：用户点选目标文档后重新生成提案（dry，不建 pending）。

    - 强制 kb 写权限（仅 Admin/Owner · Member → 403）；
    - 复用 run_*_document(commit=False) 取结构化提案；
    - 返回与 proposal_preview 同构 dict（含 run_id / can_adopt / double_confirm=True）。
    """
    if body.operation not in ("delete", "restore"):
        raise ValidationError(detail="不支持的操作")
    # M10（P1-27）：thread 归属校验——thread 必须属于当前用户，否则 403
    # （防在他人会话 thread 上注入/污染审批上下文；thread 不存在统一 403）。
    await require_thread_owner(
        db, thread_id=body.thread_id, current_user=current_user
    )
    doc = await db.get(Document, body.document_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在"
        )
    # 写权限二次校验（与 submit / resolve 同守卫）
    await require_kb_access(
        kb_id=doc.kb_id, action=KbAction.write, current_user=current_user, db=db
    )
    tool_scope = build_kb_tool_scope(
        doc.kb_id,
        None,
        member=(
            current_user.account_type.value == "enterprise"
            and current_user.org_role == "member"
        ),
    )
    run_id = uuid.uuid4()
    if body.operation == "delete":
        res = await run_delete_document(
            db,
            tool_scope,
            kb_id=doc.kb_id,
            document_id=doc.id,
            run_id=run_id,
            thread_id=body.thread_id,
            current_user=current_user,
            commit=False,
        )
    else:
        res = await run_restore_document(
            db,
            tool_scope,
            kb_id=doc.kb_id,
            document_id=doc.id,
            run_id=run_id,
            thread_id=body.thread_id,
            current_user=current_user,
            commit=False,
        )
    if not res.ok or res.proposal is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=res.summary or "无法生成提案",
        )
    data = _proposal_to_dict(res.proposal)
    data["run_id"] = str(run_id)
    data["can_adopt"] = True
    data["double_confirm"] = True
    return data


async def _audit_approval_denied(approval_id: UUID, exc: Union[HTTPException, ServiceError]) -> None:
    """denied 审计（G4-3.5）：独立会话、立即 commit，避免被主事务回滚吞掉。

    - 仅对 403 / 404 / 409 记录；422（未知 action）不记。
    - approval 不存在（404 G4-E8）跳过（无 approval_id 可关联）。
    - reason 优先取服务层标注的 ``exc.audit_reason``，否则按 status_code 兜底映射：
      409 → not_pending；404 → grant_revoked；403 → member_forbidden。
    - 审计写入异常被容忍，绝不阻塞主流程。
    """
    if exc.status_code not in (403, 404, 409):
        return
    reason = getattr(exc, "audit_reason", None)
    if reason is None:
        reason = {409: "not_pending", 404: "grant_revoked"}.get(
            exc.status_code, "member_forbidden"
        )

    # 404：approval 不存在则跳过；kb 不可见（approval 存在）→ grant_revoked。
    if exc.status_code == 404:
        try:
            async with SessionLocal() as audit_db:
                existing = await audit_db.get(AgentApproval, approval_id)
                if existing is None:
                    return
                await audit_agent_approval_denied(
                    audit_db, approval_id=approval_id, reason=reason
                )
                await audit_db.commit()
        except Exception:
            return
        return

    # 403 / 409：独立会话写入并立即 commit（不随主事务回滚）。
    try:
        async with SessionLocal() as audit_db:
            await audit_agent_approval_denied(
                audit_db, approval_id=approval_id, reason=reason
            )
            await audit_db.commit()
    except Exception:
        # 审计失败绝不阻塞主流程，原异常仍由调用方 re-raise。
        pass


# ═══════════════════════════════════════════════════════════════
# E3 长期记忆 API
# ═══════════════════════════════════════════════════════════════


class MemoryResponse(BaseModel):
    id: UUID
    key: str
    memory_type: str
    value: dict
    confidence: float
    last_accessed_at: str


class MemoryListResponse(BaseModel):
    memories: list[MemoryResponse]


@router.get("/memories", response_model=MemoryListResponse)
async def list_memories(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MemoryListResponse:
    """列出当前用户的活跃记忆。"""
    from app.services.agent.memory import load_active_memories

    memories = await load_active_memories(db, current_user.id)
    return MemoryListResponse(
        memories=[
            MemoryResponse(
                id=m.id,
                key=m.key,
                memory_type=m.memory_type,
                value=m.value if isinstance(m.value, dict) else {},
                confidence=m.confidence,
                last_accessed_at=m.last_accessed_at.isoformat() if m.last_accessed_at else "",
            )
            for m in memories
        ]
    )


@router.delete("/memories/{memory_id}", status_code=status.HTTP_200_OK)
async def delete_memory(
    memory_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """删除一条记忆（仅限自己的）。

    404 也返回 ``{"ok": true}`` 防止内存 ID 枚举。
    """
    from app.services.agent.memory import delete_memory as service_delete_memory

    # 只删除属于当前用户的记忆
    from app.models.agent_memory import AgentMemory

    memory = await db.get(AgentMemory, memory_id)
    if memory is None or memory.user_id != current_user.id:
        return {"ok": True}

    await service_delete_memory(db, memory_id)
    return {"ok": True}
