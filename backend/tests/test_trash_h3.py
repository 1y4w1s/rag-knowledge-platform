"""H3 回收站：软删留盘 / restore / permanent / purge。"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.services.documents.trash import purge_expired_trash
from tests.conftest import create_test_kb
from tests.fixtures.audit_events import _count_audit_logs


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


async def _upload_txt(
    client: AsyncClient,
    headers: dict,
    kb_id: str,
    name: str,
    body: bytes = b"hello trash",
) -> dict:
    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        headers=headers,
        files=[("files", (name, body, "text/plain"))],
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["documents"][0]


@pytest.mark.asyncio
async def test_soft_delete_keeps_disk_file(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="h3-keep")
    kb = await create_test_kb(client, headers, user, name="H3留盘")
    doc = await _upload_txt(client, headers, kb["id"], "keep_me.txt")

    async with SessionLocal() as db:
        row = await db.get(Document, uuid.UUID(doc["id"]))
        assert row is not None
        path = Path(row.storage_path)
        assert path.is_file()

    resp = await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc['id']}",
        headers=headers,
    )
    assert resp.status_code == 204
    assert path.is_file(), "软删后磁盘文件应保留"


@pytest.mark.asyncio
async def test_restore_commits_and_preview_works(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="h3-restore")
    kb = await create_test_kb(client, headers, user, name="H3恢复")
    doc = await _upload_txt(client, headers, kb["id"], "restore_me.txt", b"preview ok")

    await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc['id']}",
        headers=headers,
    )

    audit_before = await _count_audit_logs(action="document.restore")
    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc['id']}/restore",
        headers=headers,
    )
    assert resp.status_code == 200
    assert await _count_audit_logs(action="document.restore") == audit_before + 1

    # 跨请求仍在列表（证明 commit）
    listing = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
    )
    assert doc["id"] in [d["id"] for d in listing.json()["items"]]

    async with SessionLocal() as db:
        row = await db.get(Document, uuid.UUID(doc["id"]))
        assert row is not None and row.deleted_at is None
        assert Path(row.storage_path).is_file()

    preview = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc['id']}/preview",
        headers=headers,
    )
    # queued 未完成时可能 409；文件可读即可作为兜底
    if preview.status_code == 200:
        assert b"preview ok" in preview.content
    else:
        assert preview.status_code in (409, 404)


@pytest.mark.asyncio
async def test_batch_delete_keeps_disk(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="h3-batch")
    kb = await create_test_kb(client, headers, user, name="H3批量")
    doc = await _upload_txt(client, headers, kb["id"], "batch_me.txt")

    async with SessionLocal() as db:
        row = await db.get(Document, uuid.UUID(doc["id"]))
        path = Path(row.storage_path)

    resp = await client.post(
        "/api/v1/batch/delete",
        headers=headers,
        json={"kb_id": kb["id"], "doc_ids": [doc["id"]]},
    )
    assert resp.status_code == 204
    assert path.is_file()

    trash = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/trash",
        headers=headers,
    )
    assert doc["id"] in [d["id"] for d in trash.json()]


@pytest.mark.asyncio
async def test_restore_same_name_conflict_409(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="h3-clash")
    kb = await create_test_kb(client, headers, user, name="H3同名")
    doc = await _upload_txt(client, headers, kb["id"], "same.txt", b"v1")

    await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc['id']}",
        headers=headers,
    )
    # 回收站同名不算冲突 → 可再上传
    again = await _upload_txt(client, headers, kb["id"], "same.txt", b"v2")
    assert again["id"] != doc["id"]

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc['id']}/restore",
        headers=headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_permanent_delete_removes_disk(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="h3-perm")
    kb = await create_test_kb(client, headers, user, name="H3永久")
    doc = await _upload_txt(client, headers, kb["id"], "gone.txt")

    async with SessionLocal() as db:
        row = await db.get(Document, uuid.UUID(doc["id"]))
        path = Path(row.storage_path)
        doc_dir = path.parent

    await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc['id']}",
        headers=headers,
    )
    assert path.is_file()

    resp = await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc['id']}/permanent",
        headers=headers,
    )
    assert resp.status_code == 204
    assert not path.is_file()
    assert not doc_dir.exists()

    trash = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/trash",
        headers=headers,
    )
    assert doc["id"] not in [d["id"] for d in trash.json()]


@pytest.mark.asyncio
async def test_purge_dry_run_and_apply(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "trash_retention_days", 30)
    monkeypatch.setattr(settings, "trash_purge_max_delete", 100)

    headers, user = await register_and_login(prefix="h3-purge")
    kb = await create_test_kb(client, headers, user, name="H3过期")
    old_doc = await _upload_txt(client, headers, kb["id"], "old.txt", b"old content unique")
    new_doc = await _upload_txt(client, headers, kb["id"], "new.txt", b"new content unique")

    await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{old_doc['id']}",
        headers=headers,
    )
    await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{new_doc['id']}",
        headers=headers,
    )

    old_cutoff = datetime.now(timezone.utc) - timedelta(days=40)
    async with SessionLocal() as db:
        row = await db.get(Document, uuid.UUID(old_doc["id"]))
        assert row is not None
        row.deleted_at = old_cutoff
        path = Path(row.storage_path)
        await db.commit()

    async with SessionLocal() as db:
        dry = await purge_expired_trash(db, dry_run=True)
    assert dry.found >= 1
    assert dry.deleted == 0
    assert any(i["id"] == old_doc["id"] for i in dry.items)
    assert path.is_file()

    async with SessionLocal() as db:
        applied = await purge_expired_trash(db, dry_run=False)
    assert applied.deleted >= 1
    assert applied.errors == 0
    assert not path.is_file()

    async with SessionLocal() as db:
        gone = await db.get(Document, uuid.UUID(old_doc["id"]))
        assert gone is None
        still = await db.get(Document, uuid.UUID(new_doc["id"]))
        assert still is not None and still.deleted_at is not None
