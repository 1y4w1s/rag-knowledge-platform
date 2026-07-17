"""ORG-1.6：Chat/Retrieval API 部门隔离测试。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.user import User
from app.services.org.scope import resolve_org_scope
from app.services.rag.retrieval import retrieve_chunks
from tests.fixtures.org_isolation import (
    OrgIsolationFixture,
    _login_user,
    _seed_kb_document_with_chunk,
)

pytestmark = pytest.mark.asyncio


async def test_api_chat_sibling_department_kb_returns_403(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    async with SessionLocal() as db:
        rd_user = await db.get(User, org_iso.rd_member.id)
        assert rd_user is not None
        headers, _ = await _login_user(client, rd_user.email, "Test123!@")

    resp = await client.post(
        f"/api/v1/knowledge-bases/{org_iso.mkt_kb_id}/chat",
        headers=headers,
        json={"message": "市场机密内容是什么"},
    )
    assert resp.status_code == 403


async def test_chat_retrieval_rd_member_excludes_sibling_dept_chunks(
    org_iso: OrgIsolationFixture,
) -> None:
    """ORG-1.6 / PRD E2：兄弟部门 chunk 不得出现在对话检索结果。"""
    async with SessionLocal() as db:
        await _seed_kb_document_with_chunk(
            db,
            kb_id=org_iso.mkt_kb_id,
            uploaded_by=org_iso.mkt_member.id,
            filename="mkt-secret.txt",
            content="市场部专属对话关键词 alpha 机密",
        )
        await _seed_kb_document_with_chunk(
            db,
            kb_id=org_iso.rd_kb_id,
            uploaded_by=org_iso.rd_member.id,
            filename="rd-body.txt",
            content="研发部专属对话关键词 beta",
        )
        await db.commit()

        scope = await resolve_org_scope(db, org_iso.rd_member)

        mkt_leak = await retrieve_chunks(
            db,
            kb_id=org_iso.mkt_kb_id,
            query="市场部专属对话关键词 alpha",
            visible_kb_ids=scope.visible_kb_ids,
        )
        assert mkt_leak == []

        rd_hits = await retrieve_chunks(
            db,
            kb_id=org_iso.rd_kb_id,
            query="研发部专属对话关键词 beta",
            visible_kb_ids=scope.visible_kb_ids,
        )
        assert rd_hits
        assert all(chunk.kb_id == org_iso.rd_kb_id for chunk in rd_hits)
        assert all("市场部专属" not in chunk.content for chunk in rd_hits)

        cross_query = await retrieve_chunks(
            db,
            kb_id=org_iso.rd_kb_id,
            query="市场部专属对话关键词 alpha",
            visible_kb_ids=scope.visible_kb_ids,
        )
        assert all("市场部专属" not in chunk.content for chunk in cross_query)
