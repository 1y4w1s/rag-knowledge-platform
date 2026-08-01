"""Plan-3E-6c：磁盘清盘失败 mock · audit · dashboard 端到端（H3：软删不再清盘）。"""

import shutil
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from tests.conftest import create_test_kb, workspace_query
from tests.fixtures.audit_events import _count_audit_logs, _latest_audit_log


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


def _patch_cleanup_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock unlink + rmtree 均 OSError，触发 cleaner 失败计数。"""

    def failing_unlink(self: Path, missing_ok: bool = False) -> None:
        raise OSError("mock unlink failure")

    def failing_rmtree(*_args: object, **_kwargs: object) -> None:
        raise OSError("mock rmtree failure")

    monkeypatch.setattr(Path, "unlink", failing_unlink)
    monkeypatch.setattr(shutil, "rmtree", failing_rmtree)


@pytest.mark.asyncio
async def test_soft_delete_keeps_file_no_cleanup_audit(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """H3：软删保留磁盘；即使 mock cleaner 失败也不写 cleanup audit。"""
    headers, user = await register_and_login(prefix="cleaner-soft")
    kb = await create_test_kb(client, headers, user, name="软删留盘库")

    upload_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("keep.txt", b"keep on soft delete", "text/plain"))],
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["documents"][0]["id"]

    async with SessionLocal() as db:
        doc = await db.get(Document, uuid.UUID(doc_id))
        assert doc is not None
        path = Path(doc.storage_path)
        assert path.is_file()

    audit_before = await _count_audit_logs(action="storage.cleanup_failed")
    _patch_cleanup_oserror(monkeypatch)

    delete_resp = await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc_id}",
        headers=headers,
    )
    assert delete_resp.status_code == 204
    assert path.is_file(), "软删不应清盘"

    async with SessionLocal() as db:
        doc = await db.get(Document, uuid.UUID(doc_id))
        assert doc is not None
        assert doc.deleted_at is not None

    assert await _count_audit_logs(action="storage.cleanup_failed") == audit_before


@pytest.mark.asyncio
async def test_permanent_delete_cleanup_failure_writes_audit_and_dashboard(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """永久删：清盘 mock 失败 → storage.cleanup_failed + dashboard +1。"""
    headers, user = await register_and_login(prefix="cleaner-perm-fail")
    kb = await create_test_kb(client, headers, user, name="永久清盘失败库")

    upload_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("disk-fail.txt", b"cleanup should fail", "text/plain"))],
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["documents"][0]["id"]

    await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc_id}",
        headers=headers,
    )

    stats_before = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers,
        params=workspace_query(user),
    )
    assert stats_before.json()["storage_cleanup_failure_count"] == 0

    audit_before = await _count_audit_logs(action="storage.cleanup_failed")
    _patch_cleanup_oserror(monkeypatch)

    perm = await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc_id}/permanent",
        headers=headers,
    )
    assert perm.status_code == 204

    assert await _count_audit_logs(action="storage.cleanup_failed") == audit_before + 1

    stats_after = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers,
        params=workspace_query(user),
    )
    assert stats_after.json()["storage_cleanup_failure_count"] == 1


@pytest.mark.asyncio
async def test_delete_kb_cleanup_failure_writes_audit_and_dashboard(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """删库路径对称：rmtree 失败 → audit + dashboard 计数 +1，删库仍 204。"""
    headers, user = await register_and_login(prefix="cleaner-kb-fail")
    kb = await create_test_kb(client, headers, user, name="删库清盘失败")

    upload_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("kb-fail.txt", b"kb cleanup fail", "text/plain"))],
    )
    assert upload_resp.status_code == 201

    stats_before = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers,
        params=workspace_query(user),
    )
    assert stats_before.json()["storage_cleanup_failure_count"] == 0

    audit_before = await _count_audit_logs(action="storage.cleanup_failed")

    def failing_rmtree(*_args: object, **_kwargs: object) -> None:
        raise OSError("mock kb rmtree failure")

    monkeypatch.setattr(shutil, "rmtree", failing_rmtree)

    del_resp = await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}",
        headers=headers,
    )
    assert del_resp.status_code == 204

    audit_after = await _count_audit_logs(action="storage.cleanup_failed")
    assert audit_after - audit_before == 1

    latest = await _latest_audit_log(action="storage.cleanup_failed")
    assert latest is not None
    assert latest.resource_type == "knowledge_base"
    assert str(latest.kb_id) == kb["id"]
    assert latest.details is not None
    assert latest.details["tree_errors"] >= 1

    stats_after = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers,
        params=workspace_query(user),
    )
    assert stats_after.json()["storage_cleanup_failure_count"] == 1
