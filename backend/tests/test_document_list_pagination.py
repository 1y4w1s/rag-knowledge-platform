"""EW-E2：单库文档列表 limit/offset 分页。"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus
from tests.conftest import create_test_kb as _create_kb


async def _seed_document(
    *,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str,
) -> None:
    doc_id = uuid.uuid4()
    async with SessionLocal() as db:
        db.add(
            Document(
                id=doc_id,
                kb_id=kb_id,
                filename=filename,
                file_type="txt",
                file_size=12,
                storage_path=f"/tmp/{doc_id}.txt",
                status=DocumentStatus.completed,
                uploaded_by=user_id,
            )
        )
        await db.commit()


async def _upload_named_txt(
    client: AsyncClient,
    headers: dict[str, str],
    kb_id: str,
    name: str,
    content: bytes = b"page test",
) -> None:
    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        headers=headers,
        files=[("files", (name, content, "text/plain"))],
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_list_documents_default_page_size(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="doc-page-default")
    kb = await _create_kb(client, headers, user)
    await _upload_named_txt(client, headers, kb["id"], "one.txt")

    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["filename"] == "one.txt"


@pytest.mark.asyncio
async def test_list_documents_pagination_over_fifty(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="doc-page-fifty")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    for i in range(55):
        await _seed_document(
            kb_id=kb_id,
            user_id=user_id,
            filename=f"doc-{i:02d}.txt",
        )

    page1 = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        params={"limit": 50, "offset": 0},
    )
    assert page1.status_code == 200
    body1 = page1.json()
    assert body1["total"] == 55
    assert body1["limit"] == 50
    assert body1["offset"] == 0
    assert len(body1["items"]) == 50

    page2 = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        params={"limit": 50, "offset": 50},
    )
    assert page2.status_code == 200
    body2 = page2.json()
    assert body2["total"] == 55
    assert body2["offset"] == 50
    assert len(body2["items"]) == 5

    names = {item["filename"] for item in body1["items"] + body2["items"]}
    assert len(names) == 55


@pytest.mark.asyncio
async def test_list_documents_offset_beyond_total_returns_empty(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="doc-page-empty")
    kb = await _create_kb(client, headers, user)
    await _upload_named_txt(client, headers, kb["id"], "only.txt")

    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        params={"limit": 10, "offset": 100},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"] == []


@pytest.mark.asyncio
async def test_get_document_by_id(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="doc-get-one")
    kb = await _create_kb(client, headers, user)
    upload = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("target.txt", b"hello", "text/plain"))],
    )
    doc_id = upload.json()["documents"][0]["id"]

    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc_id}",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["filename"] == "target.txt"


@pytest.mark.asyncio
async def test_org_member_can_list_documents_paginated(
    client: AsyncClient,
    register_and_login,
) -> None:
    from tests.test_upload import _create_org_member_and_login

    admin_headers, admin_user = await register_and_login(
        prefix="doc-page-member-admin",
        account_type="enterprise",
        org_name="分页可读公司",
    )
    kb = await _create_kb(client, admin_headers, admin_user)
    await _upload_named_txt(client, admin_headers, kb["id"], "shared.txt")

    member_headers, _member = await _create_org_member_and_login(
        client,
        org_id=admin_user["org_id"],
    )

    list_resp = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=member_headers,
    )
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["total"] == 1
    assert body["items"][0]["filename"] == "shared.txt"
