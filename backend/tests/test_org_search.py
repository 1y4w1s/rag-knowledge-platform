"""ORG-1.6：搜索 API 文档隔离测试。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.user import User
from tests.fixtures.org_isolation import (
    OrgIsolationFixture,
    _login_user,
    _seed_kb_documents,
    _seed_kb_document_with_chunk,
)

pytestmark = pytest.mark.asyncio


async def test_api_search_filename_rd_member_excludes_sibling_dept_docs(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    async with SessionLocal() as db:
        await _seed_kb_documents(
            db,
            kb_id=org_iso.mkt_kb_id,
            count=3,
            uploaded_by=org_iso.mkt_member.id,
        )
        await _seed_kb_documents(
            db,
            kb_id=org_iso.rd_kb_id,
            count=2,
            uploaded_by=org_iso.rd_member.id,
        )
        await db.commit()
        rd_user = await db.get(User, org_iso.rd_member.id)
        assert rd_user is not None
        headers, _ = await _login_user(client, rd_user.email, "Test123!@")

    search_resp = await client.get(
        "/api/v1/search/documents",
        headers=headers,
        params={"q": "doc", "workspace": str(org_iso.org_id)},
    )
    assert search_resp.status_code == 200
    body = search_resp.json()
    kb_ids = {item["kb_id"] for item in body["items"]}

    assert str(org_iso.mkt_kb_id) not in kb_ids
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert all(item["kb_id"] != str(org_iso.mkt_kb_id) for item in body["items"])


async def test_api_search_content_rd_member_excludes_sibling_dept_docs(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    async with SessionLocal() as db:
        await _seed_kb_document_with_chunk(
            db,
            kb_id=org_iso.mkt_kb_id,
            uploaded_by=org_iso.mkt_member.id,
            filename="mkt-body.txt",
            content="市场部专属正文关键词 alpha",
        )
        await _seed_kb_document_with_chunk(
            db,
            kb_id=org_iso.rd_kb_id,
            uploaded_by=org_iso.rd_member.id,
            filename="rd-body.txt",
            content="研发部专属正文关键词 beta",
        )
        await db.commit()
        rd_user = await db.get(User, org_iso.rd_member.id)
        assert rd_user is not None
        headers, _ = await _login_user(client, rd_user.email, "Test123!@")

    alpha_resp = await client.get(
        "/api/v1/search/documents",
        headers=headers,
        params={
            "q": "alpha",
            "workspace": str(org_iso.org_id),
            "mode": "content",
        },
    )
    assert alpha_resp.status_code == 200
    assert alpha_resp.json()["total"] == 0
    assert alpha_resp.json()["items"] == []

    beta_resp = await client.get(
        "/api/v1/search/documents",
        headers=headers,
        params={
            "q": "beta",
            "workspace": str(org_iso.org_id),
            "mode": "content",
        },
    )
    assert beta_resp.status_code == 200
    beta_body = beta_resp.json()
    assert beta_body["total"] == 1
    assert len(beta_body["items"]) == 1
    assert beta_body["items"][0]["kb_id"] == str(org_iso.rd_kb_id)
    assert str(org_iso.mkt_kb_id) not in {item["kb_id"] for item in beta_body["items"]}
