"""文档可见性过滤测试：member 看不到 admin_only 文档。"""

from uuid import UUID

import pytest
from httpx import AsyncClient, Response


@pytest.mark.asyncio
async def test_document_visibility_default_is_everyone(
    client: AsyncClient,
    register_and_login,
) -> None:
    """上传的文档默认可见性为 everyone。"""
    headers, user = await register_and_login(prefix="doc-vis-1")

    # 创建 KB
    resp = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "VisTest1"},
        headers=headers,
    )
    kb_id = resp.json()["id"]

    # 上传文档
    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        files={"files": ("hello.txt", b"Hello World")},
        headers=headers,
    )
    assert resp.status_code == 201
    doc = resp.json()["documents"][0]
    assert doc["visibility"] == "everyone"


@pytest.mark.asyncio
async def test_admin_can_set_admin_only_visibility(
    client: AsyncClient,
    register_and_login,
) -> None:
    """Admin/Owner 可改文档可见性为 admin_only。"""
    headers, user = await register_and_login(prefix="doc-vis-2")

    resp = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "VisTest2"},
        headers=headers,
    )
    kb_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        files={"files": ("secret.txt", b"Secret Content")},
        headers=headers,
    )
    doc_id = resp.json()["documents"][0]["id"]

    # 改为 admin_only
    resp = await client.patch(
        f"/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}/visibility",
        json={"visibility": "admin_only"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["visibility"] == "admin_only"


@pytest.mark.asyncio
async def test_member_cannot_see_admin_only_docs(
    client: AsyncClient,
    org_iso,
) -> None:
    """Member 在文档列表中看不到 admin_only 文档。"""
    # org_iso 提供了 admin 和 member 两个用户
    admin_headers, member_headers, org_data = org_iso
    admin_kb_id = org_data["admin_kb_id"]

    # Admin 上传一个文档并设为 admin_only
    resp = await client.post(
        f"/api/v1/knowledge-bases/{admin_kb_id}/documents",
        files={"files": ("admin_only.txt", b"Admin Secret")},
        headers=admin_headers,
    )
    doc_id = resp.json()["documents"][0]["id"]

    await client.patch(
        f"/api/v1/knowledge-bases/{admin_kb_id}/documents/{doc_id}/visibility",
        json={"visibility": "admin_only"},
        headers=admin_headers,
    )

    # Admin 能看到
    resp = await client.get(
        f"/api/v1/knowledge-bases/{admin_kb_id}/documents",
        headers=admin_headers,
    )
    doc_ids = [d["id"] for d in resp.json()["items"]]
    assert doc_id in doc_ids

    # Member 看不到
    resp = await client.get(
        f"/api/v1/knowledge-bases/{admin_kb_id}/documents",
        headers=member_headers,
    )
    doc_ids = [d["id"] for d in resp.json()["items"]]
    assert doc_id not in doc_ids
