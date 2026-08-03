"""M10（P1-27）· submit/clarify 服务层 thread 归属校验测试。

T4-M10：submit/clarify 的 thread_id/run_id 由客户端任意传入且无归属校验，
可在**他人会话 thread** 上注入审批卡（需猜 UUID），跨用户数据污染。

修复：服务层按 current_user 校验 thread 归属（thread.user_id == current_user.id），
thread 不存在与越权统一 403（fail-closed，不泄露存在性）。

覆盖：
- 他人 thread（攻击者持有 kb 写权限）submit → 403 且不建审批；
- 本人 thread 但引用他人 run_id submit → 403 且不建审批；
- thread 不存在 submit → 403 且不建审批；
- member 硬闯他人 thread submit → 403 且不建审批；
- 本人 thread submit → 200 建 pending（thread_id/user_id 归属正确）；
- clarify 他人 thread → 403；本人 thread → 200 返回提案。
"""

from __future__ import annotations

import uuid
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models.agent_approval import AgentApproval
from app.models.agent_run import AgentRun
from app.models.chat_thread import ChatThread
from app.models.document import Document
from app.models.enums import (
    AgentRunMode,
    AgentRunStatus,
    ApprovalKind,
    DocumentStatus,
    ThreadKind,
    ThreadStatus,
)

SUBMIT_URL = "/api/v1/agent/document-write/submit"
CLARIFY_URL = "/api/v1/agent/document-write/clarify"


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


async def _insert_doc(kb_id: UUID, user_id: UUID) -> UUID:
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
                deleted_at=None,
            )
        )
        await db.commit()
    return doc_id


async def _approvals_on_thread(thread_id: UUID) -> int:
    async with SessionLocal() as db:
        count = await db.scalar(
            select(func.count())
            .select_from(AgentApproval)
            .where(AgentApproval.thread_id == thread_id)
        )
        return int(count or 0)


# --------------------------------------------------------------------------- #
# submit · 他人 thread / 不存在 thread → 403 且不建审批
# --------------------------------------------------------------------------- #


async def test_submit_other_user_thread_forbidden_no_approval(
    client: AsyncClient, org_iso
) -> None:
    """拥有 kb 写权限的用户在他人会话 thread 上 submit → 403 且不建审批。"""
    doc_id = await _insert_doc(org_iso.public_kb_id, org_iso.owner.id)
    victim_thread_id, _ = await _insert_thread_run(
        org_iso.rd_member.id, org_iso.public_kb_id
    )
    run_id = uuid.uuid4()
    headers = await _login(client, org_iso.owner)

    resp = await client.post(
        SUBMIT_URL,
        headers=headers,
        json={
            "thread_id": str(victim_thread_id),
            "kb_id": str(org_iso.public_kb_id),
            "document_id": str(doc_id),
            "operation": "delete",
            "run_id": str(run_id),
        },
    )
    assert resp.status_code == 403, resp.text
    assert await _approvals_on_thread(victim_thread_id) == 0


async def test_submit_nonexistent_thread_forbidden_no_approval(
    client: AsyncClient, org_iso
) -> None:
    """thread 不存在 → 403（fail-closed，不泄露存在性）且不建审批。"""
    doc_id = await _insert_doc(org_iso.public_kb_id, org_iso.owner.id)
    run_id = uuid.uuid4()
    headers = await _login(client, org_iso.owner)

    resp = await client.post(
        SUBMIT_URL,
        headers=headers,
        json={
            "thread_id": str(uuid.uuid4()),
            "kb_id": str(org_iso.public_kb_id),
            "document_id": str(doc_id),
            "operation": "delete",
            "run_id": str(run_id),
        },
    )
    assert resp.status_code == 403, resp.text
    async with SessionLocal() as db:
        count = await db.scalar(
            select(func.count())
            .select_from(AgentApproval)
            .where(AgentApproval.run_id == run_id)
        )
        assert int(count or 0) == 0


async def test_submit_other_user_run_forbidden_no_approval(
    client: AsyncClient, org_iso
) -> None:
    """本人 thread 但引用他人 run_id submit → 403 且不建审批。"""
    doc_id = await _insert_doc(org_iso.public_kb_id, org_iso.owner.id)
    owner_thread_id, _ = await _insert_thread_run(
        org_iso.owner.id, org_iso.public_kb_id
    )
    _, victim_run_id = await _insert_thread_run(
        org_iso.rd_member.id, org_iso.public_kb_id
    )
    headers = await _login(client, org_iso.owner)

    resp = await client.post(
        SUBMIT_URL,
        headers=headers,
        json={
            "thread_id": str(owner_thread_id),
            "kb_id": str(org_iso.public_kb_id),
            "document_id": str(doc_id),
            "operation": "delete",
            "run_id": str(victim_run_id),
        },
    )
    assert resp.status_code == 403, resp.text
    assert await _approvals_on_thread(owner_thread_id) == 0


async def test_submit_member_other_user_thread_forbidden_no_approval(
    client: AsyncClient, org_iso
) -> None:
    """member 对他人 thread submit → 403（写权限 + 归属双闸）且不建审批。"""
    doc_id = await _insert_doc(org_iso.public_kb_id, org_iso.owner.id)
    owner_thread_id, _ = await _insert_thread_run(
        org_iso.owner.id, org_iso.public_kb_id
    )
    run_id = uuid.uuid4()
    headers = await _login(client, org_iso.rd_member)

    resp = await client.post(
        SUBMIT_URL,
        headers=headers,
        json={
            "thread_id": str(owner_thread_id),
            "kb_id": str(org_iso.public_kb_id),
            "document_id": str(doc_id),
            "operation": "delete",
            "run_id": str(run_id),
        },
    )
    assert resp.status_code == 403, resp.text
    assert await _approvals_on_thread(owner_thread_id) == 0


# --------------------------------------------------------------------------- #
# submit · 本人 thread 正常建 pending
# --------------------------------------------------------------------------- #


async def test_submit_own_thread_creates_pending(
    client: AsyncClient, org_iso
) -> None:
    """本人 thread submit → 200 建 pending，审批归属（thread/user/run）正确。"""
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

    async with SessionLocal() as db:
        approval = await db.get(AgentApproval, approval_id)
        assert approval is not None
        assert approval.thread_id == thread_id
        assert approval.user_id == org_iso.owner.id
        assert approval.run_id == run_id
        assert approval.kind == ApprovalKind.delete_document


# --------------------------------------------------------------------------- #
# clarify · 他人 thread → 403；本人 thread → 200
# --------------------------------------------------------------------------- #


async def test_clarify_other_user_thread_forbidden(
    client: AsyncClient, org_iso
) -> None:
    """拥有 kb 写权限的用户在他人会话 thread 上 clarify → 403。"""
    doc_id = await _insert_doc(org_iso.public_kb_id, org_iso.owner.id)
    victim_thread_id, _ = await _insert_thread_run(
        org_iso.rd_member.id, org_iso.public_kb_id
    )
    headers = await _login(client, org_iso.owner)

    resp = await client.post(
        CLARIFY_URL,
        headers=headers,
        json={
            "thread_id": str(victim_thread_id),
            "document_id": str(doc_id),
            "operation": "delete",
        },
    )
    assert resp.status_code == 403, resp.text


async def test_clarify_own_thread_ok(client: AsyncClient, org_iso) -> None:
    """本人 thread clarify → 200 返回结构化提案（不误伤正常路径）。"""
    doc_id = await _insert_doc(org_iso.public_kb_id, org_iso.owner.id)
    thread_id, _ = await _insert_thread_run(
        org_iso.owner.id, org_iso.public_kb_id
    )
    headers = await _login(client, org_iso.owner)

    resp = await client.post(
        CLARIFY_URL,
        headers=headers,
        json={
            "thread_id": str(thread_id),
            "document_id": str(doc_id),
            "operation": "delete",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["operation"] == "delete"
    assert data["document_id"] == str(doc_id)
    assert data["double_confirm"] is True
    assert "run_id" in data
