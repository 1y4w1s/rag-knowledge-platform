"""ORG-1.7：Citation resolve / Messages API 撤销 grant 后行为测试。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.models.enums import GranteeType, GrantPermission
from app.models.kb_unit_grant import KbUnitGrant
from app.models.user import User
from app.services.rag.persistence import save_chat_turn
from tests.fixtures.org_isolation import (
    OrgIsolationFixture,
    _login_user,
    _seed_kb_document_with_ids,
)

pytestmark = pytest.mark.asyncio


async def test_citation_resolve_after_grant_revoked_returns_inaccessible(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """ORG-1.7 / PRD E10：撤 grant 后 citation resolve 返回不可见文案，非 403/500。"""
    doc_id: object
    chunk_id: object
    async with SessionLocal() as db:
        db.add(
            KbUnitGrant(
                kb_id=org_iso.mkt_kb_id,
                grantee_type=GranteeType.org_unit,
                grantee_id=org_iso.rd_id,
                permission=GrantPermission.read,
            )
        )
        doc_id, chunk_id = await _seed_kb_document_with_ids(
            db,
            kb_id=org_iso.mkt_kb_id,
            uploaded_by=org_iso.mkt_member.id,
            filename="grant-handbook.txt",
            content="市场部 grant 引用内容",
        )
        await save_chat_turn(
            db,
            kb_id=org_iso.mkt_kb_id,
            user_id=org_iso.rd_member.id,
            user_content="grant 可见时的问题",
            assistant_content="引用市场部文档",
            citations=[
                {
                    "chunk_id": str(chunk_id),
                    "document_id": str(doc_id),
                    "doc_name": "grant-handbook.txt",
                    "page": None,
                    "section_title": None,
                    "excerpt": "市场部 grant 引用内容",
                }
            ],
        )
        await db.commit()

        rd_user = await db.get(User, org_iso.rd_member.id)
        assert rd_user is not None
        headers, _ = await _login_user(client, rd_user.email, "password123")

        await db.execute(delete(KbUnitGrant).where(KbUnitGrant.kb_id == org_iso.mkt_kb_id))
        await db.commit()

    resolve_resp = await client.get(
        f"/api/v1/knowledge-bases/{org_iso.mkt_kb_id}/citations/resolve",
        headers=headers,
        params={
            "document_id": str(doc_id),
            "chunk_id": str(chunk_id),
        },
    )
    assert resolve_resp.status_code == 200
    body = resolve_resp.json()
    assert body["source_status"] == "source_inaccessible"
    assert body["doc_name"] is None


async def test_get_messages_after_grant_revoked_marks_citations_inaccessible(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """ORG-1.7：撤 grant 后仍可读自己的历史消息，citation 带 source_inaccessible。"""
    async with SessionLocal() as db:
        db.add(
            KbUnitGrant(
                kb_id=org_iso.mkt_kb_id,
                grantee_type=GranteeType.org_unit,
                grantee_id=org_iso.rd_id,
                permission=GrantPermission.read,
            )
        )
        doc_id, chunk_id = await _seed_kb_document_with_ids(
            db,
            kb_id=org_iso.mkt_kb_id,
            uploaded_by=org_iso.mkt_member.id,
            filename="history-grant.txt",
            content="历史消息 grant 引用",
        )
        await save_chat_turn(
            db,
            kb_id=org_iso.mkt_kb_id,
            user_id=org_iso.rd_member.id,
            user_content="历史问题",
            assistant_content="历史回答",
            citations=[
                {
                    "chunk_id": str(chunk_id),
                    "document_id": str(doc_id),
                    "doc_name": "history-grant.txt",
                    "page": None,
                    "section_title": None,
                    "excerpt": "历史消息 grant 引用",
                }
            ],
        )
        await db.commit()

        rd_user = await db.get(User, org_iso.rd_member.id)
        assert rd_user is not None
        headers, _ = await _login_user(client, rd_user.email, "password123")

        await db.execute(delete(KbUnitGrant).where(KbUnitGrant.kb_id == org_iso.mkt_kb_id))
        await db.commit()

    messages_resp = await client.get(
        f"/api/v1/knowledge-bases/{org_iso.mkt_kb_id}/messages",
        headers=headers,
    )
    assert messages_resp.status_code == 200
    messages = messages_resp.json()["messages"]
    assert len(messages) == 2
    assistant = next(m for m in messages if m["role"] == "assistant")
    assert assistant["citations"]
    assert assistant["citations"][0]["source_status"] == "source_inaccessible"


async def test_get_messages_invisible_kb_without_history_returns_403(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """ORG-1.7：不可见库且无个人历史时 GET messages 仍 403（非 500）。"""
    async with SessionLocal() as db:
        rd_user = await db.get(User, org_iso.rd_member.id)
        assert rd_user is not None
        headers, _ = await _login_user(client, rd_user.email, "password123")

    resp = await client.get(
        f"/api/v1/knowledge-bases/{org_iso.mkt_kb_id}/messages",
        headers=headers,
    )
    assert resp.status_code == 403
