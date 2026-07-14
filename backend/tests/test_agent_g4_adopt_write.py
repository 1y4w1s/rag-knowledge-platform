"""G4-3.2 · adopt 真实写库（文件落盘 + _v2 冲突 + ingestion 入队）。

本文件覆盖 plan §9 **G4-3.2**，刻意**不** monkeypatch ``adopt_draft_to_kb``，
走真实实现：

- 真实 ``adopt_draft_to_kb``：读 ``payload_json["markdown"]`` → 落 ``.md`` 文件 →
  创建 ``documents(queued)`` → 复用现网 upload 文本路径入队 ``process_document_ingestion``。
- G4-E16：同名文件 → 自动 ``_v2``（不 409）。
- happy path：200 + ``{document_id, kb_id, filename, status:"processing"}``，ingestion 已
  入队（spy ``process_document_ingestion`` 确认被调用）。

复用 ``org_iso`` fixture（owner/admin/member）。避免污染宿主：``settings.upload_dir``
指向 pytest 的 ``tmp_path``。

注意：本窗不写 G4-3.3 cancel / G4-3.5 审计 / 前端；cancel 仍 422（继承自 G4-3.1）。
"""

from __future__ import annotations

import uuid
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import BackgroundTasks
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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
from app.models.knowledge_base import KnowledgeBase
from app.services.agent.adopt import (
    adopt_draft_to_kb,
    bind_adopt_background_tasks,
    unbind_adopt_background_tasks,
)

APPROVE_URL = "/api/v1/agent/approvals/{approval_id}/resolve"

DRAFT_MARKDOWN = "# FAQ\n\n内容"


async def _login(client: AsyncClient, user) -> dict[str, str]:
    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": user.email, "password": "password123"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _insert_approval(
    *,
    kb_id: UUID,
    user_id: UUID,
    status: ApprovalStatus = ApprovalStatus.pending,
    filename: str = "faq-draft.md",
    markdown: str = DRAFT_MARKDOWN,
) -> UUID:
    """直插 agent_approvals 行（commit 使路由所在会话可见 · READ COMMITTED）。

    同时插入父表 chat_threads / agent_runs（FK 约束）。
    """
    approval_id = uuid.uuid4()
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
                mode=AgentRunMode.edit,
                status=AgentRunStatus.completed,
            )
        )
        await db.flush()
        db.add(
            AgentApproval(
                id=approval_id,
                run_id=run_id,
                thread_id=thread_id,
                user_id=user_id,
                kind=ApprovalKind.adopt_faq,
                status=status,
                kb_id=kb_id,
                filename=filename,
                payload_json={
                    "title": "年假制度 FAQ",
                    "filename": filename,
                    "markdown": markdown,
                    "source_chunk_ids": [],
                },
            )
        )
        await db.commit()
    return approval_id


async def _insert_existing_doc(
    *, kb_id: UUID, filename: str, user_id: UUID
) -> UUID:
    """在目标库预置一个同名 Document（用于验证 _v2 冲突策略）。"""
    doc_id = uuid.uuid4()
    async with SessionLocal() as db:
        db.add(
            Document(
                id=doc_id,
                kb_id=kb_id,
                filename=filename,
                file_type="md",
                file_size=1,
                storage_path="/tmp/existing.md",
                status=DocumentStatus.completed,
                uploaded_by=user_id,
            )
        )
        await db.commit()
    return doc_id


# --------------------------------------------------------------------------- #
# G4-3.2 · 真实写库：文件落盘 + documents(queued) + ingestion 入队
# --------------------------------------------------------------------------- #


async def test_g4_adopt_unit_writes_file_and_enqueues(
    client: AsyncClient,
    org_iso,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """真实 adopt_draft_to_kb：落 .md 文件 + 创建 queued 文档 + 入队 ingestion。"""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    recorded: list[UUID] = []

    async def _spy(doc_id: UUID) -> None:
        recorded.append(doc_id)

    monkeypatch.setattr(
        "app.services.agent.adopt.process_document_ingestion", _spy
    )

    approval_id = await _insert_approval(
        kb_id=org_iso.public_kb_id,
        user_id=org_iso.owner.id,
        filename="unit-faq.md",
    )
    bt = BackgroundTasks()
    token = bind_adopt_background_tasks(bt)
    try:
        async with SessionLocal() as db:
            approval = await db.get(AgentApproval, approval_id)
            kb = await db.get(KnowledgeBase, org_iso.public_kb_id)
            doc_id = await adopt_draft_to_kb(db, approval, kb)
            await db.commit()
    finally:
        unbind_adopt_background_tasks(token)

    # 触发（等价于 FastAPI 在响应后跑 BackgroundTasks）
    await bt()

    # ingestion 已入队且传入正确 document_id
    assert recorded == [doc_id]

    # documents 落 queued + 文件落盘内容一致
    async with SessionLocal() as db:
        doc = await db.get(Document, doc_id)
        assert doc is not None
        assert doc.status == DocumentStatus.queued
        assert doc.filename == "unit-faq.md"
        assert doc.kb_id == org_iso.public_kb_id
        assert doc.uploaded_by == org_iso.owner.id
        p = Path(doc.storage_path)
        assert p.is_file()
        assert p.read_text(encoding="utf-8") == DRAFT_MARKDOWN


async def test_g4_e16_unit_same_name_auto_v2(
    client: AsyncClient,
    org_iso,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """G4-E16：同名文件已存在 → 自动 _v2（不 409）。"""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(
        "app.services.agent.adopt.process_document_ingestion",
        (lambda doc_id: None),
    )

    await _insert_existing_doc(
        kb_id=org_iso.public_kb_id,
        filename="unit-faq.md",
        user_id=org_iso.owner.id,
    )
    approval_id = await _insert_approval(
        kb_id=org_iso.public_kb_id,
        user_id=org_iso.owner.id,
        filename="unit-faq.md",
    )
    bt = BackgroundTasks()
    token = bind_adopt_background_tasks(bt)
    try:
        async with SessionLocal() as db:
            approval = await db.get(AgentApproval, approval_id)
            kb = await db.get(KnowledgeBase, org_iso.public_kb_id)
            doc_id = await adopt_draft_to_kb(db, approval, kb)
            await db.commit()
    finally:
        unbind_adopt_background_tasks(token)

    async with SessionLocal() as db:
        doc = await db.get(Document, doc_id)
        assert doc.filename == "unit-faq_v2.md"
        # 原文件仍在，新文件以 _v2 落盘
        assert Path(doc.storage_path).is_file()


# --------------------------------------------------------------------------- #
# G4-3.2 · HTTP 端到端：路由集成 + 上下文注入 BackgroundTasks
# --------------------------------------------------------------------------- #


async def test_g4_adopt_http_writes_file_and_enqueues(
    client: AsyncClient,
    org_iso,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """HTTP happy path：owner 采纳 → 200 + processing + 文件落盘 + ingestion 入队。"""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    recorded: list[UUID] = []

    async def _spy(doc_id: UUID) -> None:
        recorded.append(doc_id)

    monkeypatch.setattr(
        "app.services.agent.adopt.process_document_ingestion", _spy
    )

    approval_id = await _insert_approval(
        kb_id=org_iso.public_kb_id, user_id=org_iso.owner.id
    )
    headers = await _login(client, org_iso.owner)

    resp = await client.post(
        APPROVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "adopt"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["kb_id"] == str(org_iso.public_kb_id)
    assert body["filename"] == "faq-draft.md"
    assert body["status"] == "processing"
    did = UUID(body["document_id"])

    # ingestion 入队（BackgroundTasks 在响应后由框架执行 spy）
    assert recorded == [did]

    # documents 落 queued + 文件落盘
    async with SessionLocal() as db:
        doc = await db.get(Document, did)
        assert doc is not None
        assert doc.status == DocumentStatus.queued
        p = Path(doc.storage_path)
        assert p.is_file()
        assert DRAFT_MARKDOWN in p.read_text(encoding="utf-8")


async def test_g4_e16_http_same_name_auto_v2(
    client: AsyncClient,
    org_iso,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """G4-E16 · HTTP：同名文件 → 响应 filename 自动 _v2，文档以 _v2 落库。"""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(
        "app.services.agent.adopt.process_document_ingestion",
        (lambda doc_id: None),
    )

    await _insert_existing_doc(
        kb_id=org_iso.public_kb_id,
        filename="faq-draft.md",
        user_id=org_iso.owner.id,
    )
    approval_id = await _insert_approval(
        kb_id=org_iso.public_kb_id, user_id=org_iso.owner.id
    )
    headers = await _login(client, org_iso.owner)

    resp = await client.post(
        APPROVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "adopt"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["filename"] == "faq-draft_v2.md"
    did = UUID(resp.json()["document_id"])

    async with SessionLocal() as db:
        doc = await db.get(Document, did)
        assert doc.filename == "faq-draft_v2.md"
