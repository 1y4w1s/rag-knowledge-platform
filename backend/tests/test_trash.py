"""回收站测试：软删/列表/恢复/永久删除。"""

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_kb


@pytest.mark.asyncio
async def test_delete_moves_to_trash(
    client: AsyncClient,
    register_and_login,
) -> None:
    """删除文档后从列表消失，在回收站可见。"""
    headers, user = await register_and_login(prefix="trash-1")
    kb = await create_test_kb(client, headers, user, name="TrashTest1")
    kb_id = kb["id"]

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        files={"files": ("delete_me.txt", b"Goodbye unique trash1")},
        headers=headers,
    )
    doc_id = resp.json()["documents"][0]["id"]

    resp = await client.delete(
        f"/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}",
        headers=headers,
    )
    assert resp.status_code == 204

    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        headers=headers,
    )
    doc_ids = [d["id"] for d in resp.json()["items"]]
    assert doc_id not in doc_ids

    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb_id}/documents/trash",
        headers=headers,
    )
    trash_ids = [d["id"] for d in resp.json()]
    assert doc_id in trash_ids


@pytest.mark.asyncio
async def test_restore_from_trash(
    client: AsyncClient,
    register_and_login,
) -> None:
    """从回收站恢复文档后，重新出现在列表中。"""
    headers, user = await register_and_login(prefix="trash-2")
    kb = await create_test_kb(client, headers, user, name="TrashTest2")
    kb_id = kb["id"]

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        files={"files": ("restore_me.txt", b"Restore unique trash2")},
        headers=headers,
    )
    doc_id = resp.json()["documents"][0]["id"]

    await client.delete(
        f"/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}",
        headers=headers,
    )

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}/restore",
        headers=headers,
    )
    assert resp.status_code == 200

    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        headers=headers,
    )
    doc_ids = [d["id"] for d in resp.json()["items"]]
    assert doc_id in doc_ids


@pytest.mark.asyncio
async def test_permanent_delete_removes_from_trash(
    client: AsyncClient,
    register_and_login,
) -> None:
    """永久删除后从回收站消失。"""
    headers, user = await register_and_login(prefix="trash-3")
    kb = await create_test_kb(client, headers, user, name="TrashTest3")
    kb_id = kb["id"]

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        files={"files": ("perma_delete.txt", b"Bye unique trash3")},
        headers=headers,
    )
    doc_id = resp.json()["documents"][0]["id"]

    await client.delete(
        f"/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}",
        headers=headers,
    )

    resp = await client.delete(
        f"/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}/permanent",
        headers=headers,
    )
    assert resp.status_code == 204

    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb_id}/documents/trash",
        headers=headers,
    )
    trash_ids = [d["id"] for d in resp.json()]
    assert doc_id not in trash_ids
