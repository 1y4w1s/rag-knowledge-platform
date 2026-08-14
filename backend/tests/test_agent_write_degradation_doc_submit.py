"""G4/G5 写类链路降级 W2 · G5 文档操作降级边界固化（submit / 采纳 / Member 权限）。

契约：docs/tasks/audit-g4g5-write-degradation-plan.md §5 W2。
- LLM_DOWN 下 submit 建 pending、resolve adopt 执行软删 / 恢复全流程零 LLM；
- Member submit / clarify / resolve adopt → 403，L10 commit 分支
  run_delete_document(commit=True) → write_forbidden 不建审批；
- 不预埋未消费开关 / 守卫 / 指标；未来写类链路接入 LLM 须同窗消费
  degradation_requires_llm() 并扩展本文件测试。

A/B 提案 SSE 与 clarify 另见 test_agent_write_degradation_doc_write.py。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from uuid import UUID

import pytest
from httpx import AsyncClient

import app.services.rag.chat_llm as chat_llm_mod
from app.core.database import SessionLocal
from app.core.degradation import DegradationLevel
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
from app.services.agent.tools.document_write import (
    DocumentWriteFailure,
    run_delete_document,
)
from app.services.agent.tools.scope import AgentToolScope

SUBMIT_URL = "/api/v1/agent/document-write/submit"
CLARIFY_URL = "/api/v1/agent/document-write/clarify"
RESOLVE_URL = "/api/v1/agent/approvals/{approval_id}/resolve"

DOC_NAME = "员工手册 v3.pdf"


def _patch_llm_down(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """权威判定钉在 LLM_DOWN，三条 LLM 生成入口换成计数桩。"""
    calls = {"stream": 0, "engine": 0, "chat_llm": 0}

    async def _never_stream(_messages: list) -> None:
        calls["stream"] += 1
        yield "不应到达"

    async def _never_engine(_messages: list) -> None:
        calls["engine"] += 1
        yield "不应到达"

    async def _never_chat_llm(_messages: list) -> tuple[str, None]:
        calls["chat_llm"] += 1
        return "", None

    for target in (
        "app.core.degradation.assess_degradation",
        "app.services.agent.stream.assess_degradation",
        "app.services.rag.engine.assess_degradation",
    ):
        monkeypatch.setattr(target, lambda: DegradationLevel.LLM_DOWN)
    monkeypatch.setattr(
        "app.services.agent.stream.stream_deepseek_tokens", _never_stream
    )
    monkeypatch.setattr(
        "app.services.rag.engine.stream_deepseek_tokens", _never_engine
    )
    monkeypatch.setattr(
        chat_llm_mod, "complete_chat_with_usage", _never_chat_llm
    )
    return calls


async def _login(client: AsyncClient, user) -> dict[str, str]:
    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": user.email, "password": "Test123!@"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _insert_doc(kb_id: UUID, user_id: UUID, *, deleted: bool = False) -> UUID:
    doc_id = uuid.uuid4()
    async with SessionLocal() as db:
        db.add(
            Document(
                id=doc_id,
                kb_id=kb_id,
                filename=DOC_NAME,
                file_type="pdf",
                file_size=10,
                storage_path=f"/tmp/{doc_id}.pdf",
                status=DocumentStatus.completed,
                uploaded_by=user_id,
                deleted_at=datetime.now(timezone.utc) if deleted else None,
            )
        )
        await db.commit()
    return doc_id


async def _insert_thread_run(user_id: UUID, kb_id: UUID) -> tuple[UUID, UUID]:
    thread_id = uuid.uuid4()
    run_id = uuid.uuid4()
    async with SessionLocal() as db:
        db.add(
            ChatThread(
                id=thread_id,
                thread_kind=ThreadKind.knowledge_base,
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


async def _insert_approval(
    *,
    kb_id: UUID,
    user_id: UUID,
    kind: ApprovalKind,
    document_id: UUID,
    thread_id: UUID,
    run_id: UUID,
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
                status=ApprovalStatus.pending,
                kb_id=kb_id,
                filename=DOC_NAME,
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
# submit → resolve adopt 全流程
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_doc_write_submit_adopt_delete_no_llm_on_llm_down(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, org_iso
) -> None:
    """submit 建 pending → 采纳软删：LLM_DOWN 下全流程零 LLM。"""
    kb_id = org_iso.public_kb_id
    doc_id = await _insert_doc(kb_id, org_iso.owner.id)
    thread_id, run_id = await _insert_thread_run(org_iso.owner.id, kb_id)
    headers = await _login(client, org_iso.owner)
    calls = _patch_llm_down(monkeypatch)

    resp = await client.post(
        SUBMIT_URL,
        headers=headers,
        json={
            "thread_id": str(thread_id),
            "kb_id": str(kb_id),
            "document_id": str(doc_id),
            "operation": "delete",
            "run_id": str(run_id),
        },
    )
    assert resp.status_code == 200, resp.text
    approval_id = UUID(resp.json()["approval_id"])
    assert resp.json()["status"] == "pending"

    resp2 = await client.post(
        RESOLVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "adopt"},
    )
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["status"] == "deleted"

    assert await _doc_deleted_at(doc_id) is not None
    assert await _approval_status(approval_id) == ApprovalStatus.adopted
    assert calls == {"stream": 0, "engine": 0, "chat_llm": 0}


@pytest.mark.asyncio
async def test_doc_write_submit_adopt_restore_no_llm_on_llm_down(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, org_iso
) -> None:
    """submit 建 pending → 采纳恢复：LLM_DOWN 下全流程零 LLM。"""
    kb_id = org_iso.public_kb_id
    doc_id = await _insert_doc(kb_id, org_iso.owner.id, deleted=True)
    thread_id, run_id = await _insert_thread_run(org_iso.owner.id, kb_id)
    headers = await _login(client, org_iso.owner)
    calls = _patch_llm_down(monkeypatch)

    resp = await client.post(
        SUBMIT_URL,
        headers=headers,
        json={
            "thread_id": str(thread_id),
            "kb_id": str(kb_id),
            "document_id": str(doc_id),
            "operation": "restore",
            "run_id": str(run_id),
        },
    )
    assert resp.status_code == 200, resp.text
    approval_id = UUID(resp.json()["approval_id"])
    assert resp.json()["status"] == "pending"

    resp2 = await client.post(
        RESOLVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "adopt"},
    )
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["status"] == "restored"

    assert await _doc_deleted_at(doc_id) is None
    assert await _approval_status(approval_id) == ApprovalStatus.adopted
    assert calls == {"stream": 0, "engine": 0, "chat_llm": 0}


# --------------------------------------------------------------------------- #
# Member 权限 + L10 纵深防御
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_doc_write_member_permissions_and_l10_no_regress_on_llm_down(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, org_iso
) -> None:
    """LLM_DOWN 下 Member 写操作全拒、L10 commit 分支不建审批，权限不回退。"""
    kb_id = org_iso.public_kb_id
    doc_id = await _insert_doc(kb_id, org_iso.owner.id)
    thread_id, run_id = await _insert_thread_run(org_iso.owner.id, kb_id)
    approval_id = await _insert_approval(
        kb_id=kb_id,
        user_id=org_iso.owner.id,
        kind=ApprovalKind.delete_document,
        document_id=doc_id,
        thread_id=thread_id,
        run_id=run_id,
    )
    headers = await _login(client, org_iso.rd_member)
    calls = _patch_llm_down(monkeypatch)

    # L10：commit 分支纵深防御
    async with SessionLocal() as db:
        result = await run_delete_document(
            db,
            AgentToolScope(
                visible_kb_ids=frozenset({kb_id}),
                default_kb_id=kb_id,
                member=True,
            ),
            kb_id=kb_id,
            document_id=doc_id,
            run_id=run_id,
            thread_id=thread_id,
            current_user=org_iso.rd_member,
            commit=True,
        )
    assert result.ok is False
    assert result.reason == DocumentWriteFailure.write_forbidden
    assert result.approval_id is None

    resp = await client.post(
        SUBMIT_URL,
        headers=headers,
        json={
            "thread_id": str(thread_id),
            "kb_id": str(kb_id),
            "document_id": str(doc_id),
            "operation": "delete",
            "run_id": str(run_id),
        },
    )
    assert resp.status_code == 403, resp.text

    resp = await client.post(
        CLARIFY_URL,
        headers=headers,
        json={
            "thread_id": str(thread_id),
            "document_id": str(doc_id),
            "operation": "delete",
        },
    )
    assert resp.status_code == 403, resp.text

    resp = await client.post(
        RESOLVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "adopt"},
    )
    assert resp.status_code == 403, resp.text

    assert await _doc_deleted_at(doc_id) is None
    assert await _approval_status(approval_id) == ApprovalStatus.pending
    assert calls == {"stream": 0, "engine": 0, "chat_llm": 0}
