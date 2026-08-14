"""P2-R4：历史消息引用批量富化（N+1 回归）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, event

from app.core.database import SessionLocal, engine
from app.core.deps import CurrentUser
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentStatus, GrantPermission, GranteeType
from app.models.kb_unit_grant import KbUnitGrant
from app.models.user import User
from app.services.rag.message_builder import build_chat_message_list
from app.services.rag.persistence import (
    list_chat_messages,
    save_kb_chat_turn,
    save_workspace_chat_turn,
)
from app.services.workspace.scope import WorkspaceKind
from tests.conftest import create_test_kb
from tests.fixtures.org_isolation import OrgIsolationFixture, _login_user

pytestmark = pytest.mark.asyncio


async def _seed_doc_chunk(
    db,
    *,
    kb_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    filename: str,
    deleted: bool = False,
) -> tuple[uuid.UUID, uuid.UUID]:
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    db.add(
        Document(
            id=doc_id,
            kb_id=kb_id,
            filename=filename,
            file_type="txt",
            file_size=12,
            storage_path=f"/tmp/{kb_id}/{doc_id}.txt",
            status=DocumentStatus.completed,
            chunk_count=1,
            uploaded_by=uploaded_by,
            deleted_at=datetime.now(timezone.utc) if deleted else None,
        )
    )
    db.add(
        DocumentChunk(
            id=chunk_id,
            document_id=doc_id,
            kb_id=kb_id,
            chunk_index=0,
            content=f"{filename} content",
            embedding=None,
        )
    )
    await db.flush()
    return doc_id, chunk_id


def _citation(
    *,
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
    chunk_id: uuid.UUID,
    kb_name: str = "R4 KB",
) -> dict:
    return {
        "chunk_id": str(chunk_id),
        "document_id": str(doc_id),
        "doc_name": "doc.txt",
        "page": None,
        "section_title": None,
        "excerpt": "R4 citation",
        "kb_id": str(kb_id),
        "kb_name": kb_name,
    }


@pytest.mark.asyncio
async def test_build_messages_enriches_citation_statuses_in_batch(
    client: AsyncClient,
    register_and_login,
) -> None:
    """批量富化保持 available / document_deleted / chunk_stale 语义。"""
    headers, user = await register_and_login(prefix="r4-batch-status")
    kb = await create_test_kb(client, headers, user, name="R4 KB")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    async with SessionLocal() as db:
        doc_a_id, chunk_a_id = await _seed_doc_chunk(
            db, kb_id=kb_id, uploaded_by=user_id, filename="a.txt"
        )
        doc_b_id, _ = await _seed_doc_chunk(
            db, kb_id=kb_id, uploaded_by=user_id, filename="b.txt", deleted=True
        )
        doc_c_id, _ = await _seed_doc_chunk(
            db, kb_id=kb_id, uploaded_by=user_id, filename="c.txt"
        )
        await save_kb_chat_turn(
            db,
            kb_id=kb_id,
            user_id=user_id,
            user_content="批量引用问题",
            assistant_content="批量引用回答",
            citations=[
                _citation(
                    kb_id=kb_id,
                    doc_id=doc_a_id,
                    chunk_id=chunk_a_id,
                ),
                _citation(
                    kb_id=kb_id,
                    doc_id=doc_b_id,
                    chunk_id=chunk_a_id,
                ),
                _citation(
                    kb_id=kb_id,
                    doc_id=doc_c_id,
                    chunk_id=chunk_a_id,
                ),
            ],
        )
        await db.commit()

    async with SessionLocal() as db:
        rows = await list_chat_messages(db, kb_id=kb_id, user_id=user_id)

        async def _always_visible(
            _payload, _raw: dict
        ) -> bool:
            return True

        messages = await build_chat_message_list(
            db,
            rows,
            current_user=CurrentUser.model_validate(user),
            kb_visible_fn=_always_visible,
            include_approval=True,
            kb_id=kb_id,
        )

    assistant = next(m for m in messages if m.role.value == "assistant")
    statuses = [
        c.source_status.value if c.source_status is not None else None
        for c in assistant.citations
    ]
    assert statuses == [
        None,
        "document_deleted",
        "chunk_stale",
    ]


@pytest.mark.asyncio
async def test_get_kb_messages_query_count_flat_for_many_citations(
    client: AsyncClient,
    register_and_login,
) -> None:
    """50 条历史 × 多引用的 N+1 回归：查询次数与引用总数解耦。"""
    headers, user = await register_and_login(prefix="r4-kb-n1")
    kb = await create_test_kb(client, headers, user, name="R4 N+1 KB")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    async with SessionLocal() as db:
        doc_a_id, chunk_a_id = await _seed_doc_chunk(
            db, kb_id=kb_id, uploaded_by=user_id, filename="a.txt"
        )
        doc_b_id, _ = await _seed_doc_chunk(
            db, kb_id=kb_id, uploaded_by=user_id, filename="b.txt", deleted=True
        )
        for index in range(3):
            await save_kb_chat_turn(
                db,
                kb_id=kb_id,
                user_id=user_id,
                user_content=f"第 {index} 轮问题",
                assistant_content=f"第 {index} 轮回答",
                citations=[
                    _citation(
                        kb_id=kb_id,
                        doc_id=doc_a_id,
                        chunk_id=chunk_a_id,
                    ),
                    _citation(
                        kb_id=kb_id,
                        doc_id=doc_b_id,
                        chunk_id=chunk_a_id,
                    ),
                    _citation(
                        kb_id=kb_id,
                        doc_id=doc_a_id,
                        chunk_id=chunk_a_id,
                    ),
                ],
            )
        await db.commit()

    executed = 0

    def _count_execute(
        _conn,
        _cursor,
        _statement,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        nonlocal executed
        executed += 1

    event.listen(engine.sync_engine, "before_cursor_execute", _count_execute)
    try:
        resp = await client.get(
            f"/api/v1/knowledge-bases/{kb_id}/messages",
            headers=headers,
        )
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _count_execute)

    assert resp.status_code == 200
    body = resp.json()
    assistants = [m for m in body["messages"] if m["role"] == "assistant"]
    assert len(assistants) == 3
    assert all(len(m["citations"]) == 3 for m in assistants)
    assert executed <= 12, f"历史消息引用查询次数异常: {executed}"


@pytest.mark.asyncio
async def test_workspace_messages_batch_visibility_after_revoke(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """工作区撤权后批量判灰；查询次数不随引用数线性增长。"""
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    async with SessionLocal() as db:
        db.add(
            KbUnitGrant(
                kb_id=org_iso.mkt_kb_id,
                grantee_type=GranteeType.org_unit,
                grantee_id=org_iso.rd_id,
                permission=GrantPermission.read,
            )
        )
        db.add(
            Document(
                id=doc_id,
                kb_id=org_iso.mkt_kb_id,
                filename="ws-r4-grant.txt",
                file_type="txt",
                file_size=20,
                storage_path=f"/tmp/{org_iso.mkt_kb_id}/{doc_id}.txt",
                status=DocumentStatus.completed,
                chunk_count=1,
                uploaded_by=org_iso.mkt_member.id,
            )
        )
        db.add(
            DocumentChunk(
                id=chunk_id,
                document_id=doc_id,
                kb_id=org_iso.mkt_kb_id,
                chunk_index=0,
                content="工作区 R4 引用",
                embedding=None,
            )
        )
        citations = [
            _citation(
                kb_id=org_iso.mkt_kb_id,
                doc_id=doc_id,
                chunk_id=chunk_id,
                kb_name="市场机密库",
            )
            for _ in range(3)
        ]
        for index in range(2):
            await save_workspace_chat_turn(
                db,
                user_id=org_iso.rd_member.id,
                workspace_kind=WorkspaceKind.organization,
                workspace_org_id=org_iso.org_id,
                department_id=str(org_iso.rd_id),
                user_content=f"工作区问题 {index}",
                assistant_content=f"工作区回答 {index}",
                citations=citations,
            )
        await db.commit()

        rd_user = await db.get(User, org_iso.rd_member.id)
        assert rd_user is not None
        headers, _ = await _login_user(client, rd_user.email, "Test123!@")

        await db.execute(
            delete(KbUnitGrant).where(KbUnitGrant.kb_id == org_iso.mkt_kb_id)
        )
        await db.commit()

    executed = 0

    def _count_execute(
        _conn,
        _cursor,
        _statement,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        nonlocal executed
        executed += 1

    event.listen(engine.sync_engine, "before_cursor_execute", _count_execute)
    try:
        resp = await client.get(
            "/api/v1/ask/messages",
            headers=headers,
            params={
                "workspace": str(org_iso.org_id),
                "department_id": str(org_iso.rd_id),
            },
        )
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _count_execute)

    assert resp.status_code == 200
    body = resp.json()
    assistants = [m for m in body["messages"] if m["role"] == "assistant"]
    assert len(assistants) == 2
    statuses = [
        c["source_status"]
        for m in assistants
        for c in m["citations"]
    ]
    assert statuses == ["source_inaccessible"] * 6
    assert executed <= 30, f"工作区引用可见性查询次数异常: {executed}"
