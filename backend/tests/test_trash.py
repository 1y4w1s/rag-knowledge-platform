"""回收站测试：软删/列表/恢复/永久删除。"""

import pytest
from httpx import AsyncClient, Response


@pytest.mark.asyncio
async def test_delete_moves_to_trash(
    client: AsyncClient,
    register_and_login,
) -> None:
    """删除文档后从列表消失，在回收站可见。"""
    headers, user = await register_and_login(prefix="trash-1")

    resp = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "TrashTest1"},
        headers=headers,
    )
    kb_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        files={"files": ("delete_me.txt", b"Goodbye")},
        headers=headers,
    )
    doc_id = resp.json()["documents"][0]["id"]

    # 删除（软删）
    resp = await client.delete(
        f"/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}",
        headers=headers,
    )
    assert resp.status_code == 204

    # 文档列表不可见
    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        headers=headers,
    )
    doc_ids = [d["id"] for d in resp.json()["items"]]
    assert doc_id not in doc_ids

    # 回收站可见
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

    resp = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "TrashTest2"},
        headers=headers,
    )
    kb_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        files={"files": ("restore_me.txt", b"Restore")},
        headers=headers,
    )
    doc_id = resp.json()["documents"][0]["id"]

    # 软删
    await client.delete(
        f"/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}",
        headers=headers,
    )

    # 恢复
    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}/restore",
        headers=headers,
    )
    assert resp.status_code == 200

    # 文档列表恢复可见
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

    resp = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "TrashTest3"},
        headers=headers,
    )
    kb_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        files={"files": ("perma_delete.txt", b"Bye")},
        headers=headers,
    )
    doc_id = resp.json()["documents"][0]["id"]

    # 软删
    await client.delete(
        f"/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}",
        headers=headers,
    )

    # 永久删除
    resp = await client.delete(
        f"/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}/permanent",
        headers=headers,
    )
    assert resp.status_code == 204

    # 回收站不再有
    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb_id}/documents/trash",
        headers=headers,
    )
    trash_ids = [d["id"] for d in resp.json()]
    assert doc_id not in trash_ids
