"""G5 · 自然语言文档写操作（delete/restore）后端测试。

覆盖 plan 锁定的关键路径：
- resolve 执行：delete_document → 软删（deleted_at 置位）+ 落终态 adopted + status "deleted"
- resolve 执行：restore_document → 恢复（deleted_at 清除）+ status "restored"
- G5-E1：Member 硬闯 resolve/submit → 403，文档状态不变
- submit：Admin/Owner 确认提案 → 建 pending（kind=delete_document/restore_document）
- 提案工具（commit=False）：返回结构化提案，不建 pending
- 预检：processing 文档删除 → proposal.conflict 标记

复用 org_iso 隔离 fixture（owner 可写 / rd_member 只读）。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.agent_approval import AgentApproval
from app.models.agent_run import AgentRun
from app.models.chat_thread import ChatThread
from app.models.document import Document
from app.models.enums import (
    AgentRunMode,
    AgentRunStatus,
    ApprovalKind,
    ApprovalStatus,
    DocumentStatus,
    ThreadKind,
    ThreadStatus,
)

RESOLVE_URL = "/api/v1/agent/approvals/{approval_id}/resolve"
SUBMIT_URL = "/api/v1/agent/document-write/submit"


async def _login(client: AsyncClient, user) -> dict[str, str]:
    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": user.email, "password": "Test123!@"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _insert_thread_run(user_id: UUID, kb_id: UUID) -> tuple[UUID, UUID]:
    """直插 chat_threads + agent_runs（AgentApproval 的 FK 父表）。"""
    thread_id = uuid.uuid4()
    run_id = uuid.uuid4()
    async with SessionLocal() as db:
        db.add(
            ChatThread(
                id=thread_id,
                thread_kind=ThreadKind.workspace,
                user_id=user_id,
                kb_id=kb_id,
                status=ThreadStatus.active,
            )
        )
        await db.flush()
        db.add(
            AgentRun(
                id=run_id,
                thread_id=thread_id,
                user_id=user_id,
                mode=AgentRunMode.document_write,
                status=AgentRunStatus.completed,
            )
        )
        await db.commit()
    return thread_id, run_id


async def _insert_doc(
    kb_id: UUID, user_id: UUID, *, deleted: bool = False
) -> UUID:
    """直插 documents 行（active 或回收站），满足删除/恢复目标。"""
    doc_id = uuid.uuid4()
    async with SessionLocal() as db:
        db.add(
            Document(
                id=doc_id,
                kb_id=kb_id,
                filename="ops-doc.txt",
                file_type="txt",
                file_size=10,
                storage_path=f"/tmp/{doc_id}.txt",
                status=DocumentStatus.completed,
                uploaded_by=user_id,
                deleted_at=datetime.now(timezone.utc) if deleted else None,
            )
        )
        await db.commit()
    return doc_id


async def _insert_approval(
    *,
    kb_id: UUID,
    user_id: UUID,
    kind: ApprovalKind,
    document_id: UUID,
    thread_id: UUID,
    run_id: UUID,
    status: ApprovalStatus = ApprovalStatus.pending,
) -> UUID:
    approval_id = uuid.uuid4()
    async with SessionLocal() as db:
        db.add(
            AgentApproval(
                id=approval_id,
                run_id=run_id,
                thread_id=thread_id,
                user_id=user_id,
                kind=kind,
                status=status,
                kb_id=kb_id,
                filename="ops-doc.txt",
                document_id=document_id,
                payload_json={"proposal": {}},
            )
        )
        await db.commit()
    return approval_id


async def _doc_deleted_at(doc_id: UUID):
    async with SessionLocal() as db:
        doc = await db.get(Document, doc_id)
        return doc.deleted_at if doc is not None else "missing"


async def _approval_status(approval_id: UUID) -> ApprovalStatus | None:
    async with SessionLocal() as db:
        approval = await db.get(AgentApproval, approval_id)
        return approval.status if approval is not None else None


# --------------------------------------------------------------------------- #
# resolve 执行 · delete / restore
# --------------------------------------------------------------------------- #


async def test_resolve_delete_soft_deletes(
    client: AsyncClient, org_iso
) -> None:
    """采纳 delete_document 审批 → 文档软删（deleted_at 置位）+ 终态 adopted。"""
    doc_id = await _insert_doc(org_iso.public_kb_id, org_iso.owner.id)
    thread_id, run_id = await _insert_thread_run(
        org_iso.owner.id, org_iso.public_kb_id
    )
    approval_id = await _insert_approval(
        kb_id=org_iso.public_kb_id,
        user_id=org_iso.owner.id,
        kind=ApprovalKind.delete_document,
        document_id=doc_id,
        thread_id=thread_id,
        run_id=run_id,
    )
    headers = await _login(client, org_iso.owner)

    resp = await client.post(
        RESOLVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "adopt"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "deleted"

    assert await _doc_deleted_at(doc_id) is not None
    assert await _approval_status(approval_id) == ApprovalStatus.adopted


async def test_resolve_restore_undeletes(
    client: AsyncClient, org_iso
) -> None:
    """采纳 restore_document 审批 → 文档恢复（deleted_at 清除）+ status "restored"。"""
    doc_id = await _insert_doc(
        org_iso.public_kb_id, org_iso.owner.id, deleted=True
    )
    thread_id, run_id = await _insert_thread_run(
        org_iso.owner.id, org_iso.public_kb_id
    )
    approval_id = await _insert_approval(
        kb_id=org_iso.public_kb_id,
        user_id=org_iso.owner.id,
        kind=ApprovalKind.restore_document,
        document_id=doc_id,
        thread_id=thread_id,
        run_id=run_id,
    )
    headers = await _login(client, org_iso.owner)

    resp = await client.post(
        RESOLVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "adopt"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "restored"

    assert await _doc_deleted_at(doc_id) is None
    assert await _approval_status(approval_id) == ApprovalStatus.adopted


# --------------------------------------------------------------------------- #
# G5-E1 · Member 硬闯 → 403
# --------------------------------------------------------------------------- #


async def test_resolve_delete_member_forbidden(
    client: AsyncClient, org_iso
) -> None:
    """Member 无采纳权限 → 403；文档状态与审批状态均不变。"""
    doc_id = await _insert_doc(org_iso.public_kb_id, org_iso.owner.id)
    thread_id, run_id = await _insert_thread_run(
        org_iso.owner.id, org_iso.public_kb_id
    )
    approval_id = await _insert_approval(
        kb_id=org_iso.public_kb_id,
        user_id=org_iso.owner.id,
        kind=ApprovalKind.delete_document,
        document_id=doc_id,
        thread_id=thread_id,
        run_id=run_id,
    )
    headers = await _login(client, org_iso.rd_member)

    resp = await client.post(
        RESOLVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "adopt"},
    )
    assert resp.status_code == 403, resp.text
    assert await _doc_deleted_at(doc_id) is None
    assert await _approval_status(approval_id) == ApprovalStatus.pending


async def test_submit_member_forbidden(
    client: AsyncClient, org_iso
) -> None:
    """Member 提交删除提案 → 403（写权限门禁）。"""
    doc_id = await _insert_doc(org_iso.public_kb_id, org_iso.owner.id)
    thread_id, run_id = await _insert_thread_run(
        org_iso.owner.id, org_iso.public_kb_id
    )
    headers = await _login(client, org_iso.rd_member)

    resp = await client.post(
        SUBMIT_URL,
        headers=headers,
        json={
            "thread_id": str(thread_id),
            "kb_id": str(org_iso.public_kb_id),
            "document_id": str(doc_id),
            "operation": "delete",
            "run_id": str(run_id),
        },
    )
    assert resp.status_code == 403, resp.text


async def test_submit_double_click_returns_same_pending_approval(
    client: AsyncClient, org_iso
) -> None:
    """P2-A5：同一确认连点两次 → 复用同一 pending 审批卡，只落一行。"""
    doc_id = await _insert_doc(org_iso.public_kb_id, org_iso.owner.id)
    thread_id, run_id = await _insert_thread_run(
        org_iso.owner.id, org_iso.public_kb_id
    )
    headers = await _login(client, org_iso.owner)
    payload = {
        "thread_id": str(thread_id),
        "kb_id": str(org_iso.public_kb_id),
        "document_id": str(doc_id),
        "operation": "delete",
        "run_id": str(run_id),
    }

    first = await client.post(SUBMIT_URL, headers=headers, json=payload)
    assert first.status_code == 200, first.text
    second = await client.post(SUBMIT_URL, headers=headers, json=payload)
    assert second.status_code == 200, second.text
    assert first.json()["approval_id"] == second.json()["approval_id"]

    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(AgentApproval).where(
                    AgentApproval.run_id == run_id,
                    AgentApproval.document_id == doc_id,
                    AgentApproval.kind == ApprovalKind.delete_document,
                    AgentApproval.status == ApprovalStatus.pending,
                )
            )
        ).scalars().all()
        assert len(rows) == 1


async def test_submit_concurrent_double_click_keeps_single_pending_approval(
    client: AsyncClient,
    org_iso,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P2-A5：并发双击同时越过初查 → advisory lock 兜底仍只生成一个 pending。"""
    import asyncio

    from app.services.agent.tools import document_write as document_write_mod

    doc_id = await _insert_doc(org_iso.public_kb_id, org_iso.owner.id)
    thread_id, run_id = await _insert_thread_run(
        org_iso.owner.id, org_iso.public_kb_id
    )
    headers = await _login(client, org_iso.owner)
    payload = {
        "thread_id": str(thread_id),
        "kb_id": str(org_iso.public_kb_id),
        "document_id": str(doc_id),
        "operation": "delete",
        "run_id": str(run_id),
    }

    barrier = asyncio.Barrier(2)
    original_lock = document_write_mod._lock_approval_idempotency

    async def _gated_lock(*args, **kwargs) -> None:
        await barrier.wait()
        await original_lock(*args, **kwargs)

    monkeypatch.setattr(
        document_write_mod, "_lock_approval_idempotency", _gated_lock
    )

    async def _submit() -> dict:
        resp = await client.post(SUBMIT_URL, headers=headers, json=payload)
        assert resp.status_code == 200, resp.text
        return resp.json()

    first, second = await asyncio.gather(_submit(), _submit())
    assert first["approval_id"] == second["approval_id"]

    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(AgentApproval).where(
                    AgentApproval.run_id == run_id,
                    AgentApproval.document_id == doc_id,
                    AgentApproval.kind == ApprovalKind.delete_document,
                    AgentApproval.status == ApprovalStatus.pending,
                )
            )
        ).scalars().all()
        assert len(rows) == 1


# --------------------------------------------------------------------------- #
# submit 建 pending → resolve 执行
# --------------------------------------------------------------------------- #


async def test_submit_creates_pending_then_resolve_deletes(
    client: AsyncClient, org_iso
) -> None:
    """Admin 确认提案 → 建 pending；采纳 → 文档软删（全链路）。"""
    doc_id = await _insert_doc(org_iso.public_kb_id, org_iso.owner.id)
    thread_id, run_id = await _insert_thread_run(
        org_iso.owner.id, org_iso.public_kb_id
    )
    headers = await _login(client, org_iso.owner)

    resp = await client.post(
        SUBMIT_URL,
        headers=headers,
        json={
            "thread_id": str(thread_id),
            "kb_id": str(org_iso.public_kb_id),
            "document_id": str(doc_id),
            "operation": "delete",
            "run_id": str(run_id),
        },
    )
    assert resp.status_code == 200, resp.text
    approval_id = UUID(resp.json()["approval_id"])
    assert resp.json()["status"] == "pending"

    async with SessionLocal() as db:
        approval = await db.get(AgentApproval, approval_id)
        assert approval.kind == ApprovalKind.delete_document
        assert approval.status == ApprovalStatus.pending
        assert approval.document_id == doc_id

    # 采纳 → 执行
    resp2 = await client.post(
        RESOLVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "adopt"},
    )
    assert resp2.status_code == 200, resp2.text
    assert await _doc_deleted_at(doc_id) is not None


# --------------------------------------------------------------------------- #
# 提案工具（commit=False）· 结构化提案 + 预检
# --------------------------------------------------------------------------- #


async def test_proposal_tool_delete_dry(client: AsyncClient, org_iso) -> None:
    """run_delete_document(commit=False) → 返回结构化提案，不建 pending。"""
    from app.services.agent.tools.document_write import run_delete_document
    from app.services.agent.tools.scope import AgentToolScope

    doc_id = await _insert_doc(org_iso.public_kb_id, org_iso.owner.id)
    async with SessionLocal() as db:
        tool_scope = AgentToolScope(
            visible_kb_ids=frozenset({org_iso.public_kb_id})
        )
        result = await run_delete_document(
            db,
            tool_scope,
            kb_id=org_iso.public_kb_id,
            document_id=doc_id,
            run_id=uuid.uuid4(),
            thread_id=uuid.uuid4(),
            current_user=org_iso.owner,
            commit=False,
        )
    assert result.ok
    assert result.proposal is not None
    assert result.proposal.operation == "delete"
    assert result.approval_id is None


async def test_proposal_tool_delete_processing_conflict(
    client: AsyncClient, org_iso
) -> None:
    """processing 文档删除 → 提案 conflict 预检标记（不静默执行）。"""
    from app.services.agent.tools.document_write import run_delete_document
    from app.services.agent.tools.scope import AgentToolScope

    doc_id = await _insert_doc(org_iso.public_kb_id, org_iso.owner.id)
    # 置为 processing
    async with SessionLocal() as db:
        doc = await db.get(Document, doc_id)
        doc.status = DocumentStatus.processing
        await db.commit()

    async with SessionLocal() as db:
        tool_scope = AgentToolScope(
            visible_kb_ids=frozenset({org_iso.public_kb_id})
        )
        result = await run_delete_document(
            db,
            tool_scope,
            kb_id=org_iso.public_kb_id,
            document_id=doc_id,
            run_id=uuid.uuid4(),
            thread_id=uuid.uuid4(),
            current_user=org_iso.owner,
            commit=False,
        )
    assert result.ok
    assert result.proposal is not None
    assert result.proposal.conflict is not None
