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

from typing import Annotated, Union
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal, get_db
from app.core.deps import CurrentUser, get_current_user
from app.models.agent_approval import AgentApproval
from app.models.document import Document
from app.services.agent.approvals import (
    resolve_adopt_approval,
    resolve_cancel_approval,
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
            return AdoptApprovalResponse(
                document_id=approval.document_id,
                kb_id=approval.kb_id,
                filename=stored_filename,
                status="processing",
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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="action 仅支持 adopt 或 cancel",
        )
    except HTTPException as exc:
        # G4-3.5：denied 审计（撤销/采纳被拒）。主事务即将回滚，必须用**独立会话**
        # 立即 commit，避免被主请求的回滚吞掉；写完后原样 re-raise 原异常。
        await _audit_approval_denied(approval_id, exc)
        raise


async def _audit_approval_denied(approval_id: UUID, exc: HTTPException) -> None:
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
