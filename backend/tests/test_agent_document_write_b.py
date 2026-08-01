"""G5-B · 文档名歧义澄清 + planner 歧义检测（情景 5）。

覆盖：
- DocumentWritePlanner：search 命中 2 篇 → ambiguous=True + candidates 含 2 篇；
  命中 0 篇 → ambiguous=False + candidates 空（交上层发 refusal）。
- POST /agent/document-write/clarify：Owner 取回提案（double_confirm=True）；
  Member → 403；非法 operation → 422。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from uuid import UUID

import pytest
from httpx import AsyncClient

from app.core.database import SessionLocal
from app.models.agent_run import AgentRun
from app.models.chat_thread import ChatThread
from app.models.document import Document
from app.models.enums import (
    AgentRunMode,
    AgentRunStatus,
    DocumentStatus,
    ThreadKind,
    ThreadStatus,
)
from app.services.agent.planners import create_document_write_planner
from app.services.agent.tools.search_documents import (
    SearchDocumentsItem,
    SearchDocumentsOutput,
)
from app.services.agent.types import AgentStepRecord

CLARIFY_URL = "/api/v1/agent/document-write/clarify"


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


async def _insert_thread_run(user_id: UUID, kb_id: UUID) -> UUID:
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
    return thread_id


def _search_record(items: tuple[SearchDocumentsItem, ...]) -> AgentStepRecord:
    return AgentStepRecord(
        step_index=0,
        tool_name="search_documents",
        args={},
        ok=True,
        summary="",
        latency_ms=0,
        data=SearchDocumentsOutput(items=items, total=len(items)),
    )


# --------------------------------------------------------------------------- #
# planner 歧义检测
# --------------------------------------------------------------------------- #


async def test_planner_ambiguous_on_two_candidates(
    client: AsyncClient, org_iso
) -> None:
    """search 命中 2 篇同名 → ambiguous=True + candidates 含 2 篇（发 clarify）。"""
    kb_id = org_iso.public_kb_id
    item1 = SearchDocumentsItem(
        document_id=uuid.uuid4(), kb_id=kb_id, kb_name="kb", filename="年假制度 v1.docx"
    )
    item2 = SearchDocumentsItem(
        document_id=uuid.uuid4(), kb_id=kb_id, kb_name="kb", filename="年假制度 v2.docx"
    )
    planner = create_document_write_planner("删除 年假制度.docx")
    plan1 = await planner.next_tool_call(
        query="删除 年假制度.docx",
        step_index=0,
        steps_used=0,
        max_steps=4,
        prior_steps=(),
    )
    assert plan1 is not None and plan1.tool_name == "search_documents"
    plan2 = await planner.next_tool_call(
        query="删除 年假制度.docx",
        step_index=1,
        steps_used=1,
        max_steps=4,
        prior_steps=(_search_record((item1, item2)),),
    )
    # 歧义 → 不返回写工具，置 ambiguous
    assert plan2 is None
    assert planner.ambiguous is True
    assert len(planner.candidates) == 2


async def test_planner_no_candidates_not_ambiguous(
    client: AsyncClient, org_iso
) -> None:
    """search 命中 0 篇 → ambiguous=False + candidates 空（上层发 refusal）。"""
    planner = create_document_write_planner("删除 不存在的文档.docx")
    await planner.next_tool_call(
        query="删除 不存在的文档.docx",
        step_index=0,
        steps_used=0,
        max_steps=4,
        prior_steps=(),
    )
    plan2 = await planner.next_tool_call(
        query="删除 不存在的文档.docx",
        step_index=1,
        steps_used=1,
        max_steps=4,
        prior_steps=(_search_record(()),),
    )
    assert plan2 is None
    assert planner.ambiguous is False
    assert planner.candidates == []


# --------------------------------------------------------------------------- #
# clarify 端点
# --------------------------------------------------------------------------- #


async def test_clarify_returns_proposal(client: AsyncClient, org_iso) -> None:
    """Owner 点选目标文档 → 取回结构化提案（double_confirm=True）。"""
    doc_id = await _insert_doc(org_iso.public_kb_id, org_iso.owner.id)
    thread_id = await _insert_thread_run(org_iso.owner.id, org_iso.public_kb_id)
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
    assert data["kb_id"] == str(org_iso.public_kb_id)
    assert data["double_confirm"] is True
    assert data["can_adopt"] is True
    assert "run_id" in data


async def test_clarify_member_forbidden(client: AsyncClient, org_iso) -> None:
    """Member 无写权限 → 403。"""
    doc_id = await _insert_doc(org_iso.public_kb_id, org_iso.owner.id)
    thread_id = await _insert_thread_run(org_iso.owner.id, org_iso.public_kb_id)
    headers = await _login(client, org_iso.rd_member)

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


async def test_clarify_bad_operation(client: AsyncClient, org_iso) -> None:
    """非法 operation → 422（ValidationError）。"""
    headers = await _login(client, org_iso.owner)
    resp = await client.post(
        CLARIFY_URL,
        headers=headers,
        json={
            "thread_id": str(uuid.uuid4()),
            "document_id": str(uuid.uuid4()),
            "operation": "pwn",
        },
    )
    assert resp.status_code == 422, resp.text
