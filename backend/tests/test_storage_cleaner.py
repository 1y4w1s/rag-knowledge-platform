"""Plan-3E-6c：磁盘清盘失败 mock · audit · dashboard 端到端。"""

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
async def test_delete_document_cleanup_failure_writes_audit_and_dashboard(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DELETE 仍 204；磁盘清盘 mock 失败 → storage.cleanup_failed audit + dashboard +1。"""
    headers, user = await register_and_login(prefix="cleaner-doc-fail")
    kb = await create_test_kb(client, headers, user, name="清盘失败库")

    upload_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("disk-fail.txt", b"cleanup should fail", "text/plain"))],
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["documents"][0]["id"]

    stats_before = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers,
        params=workspace_query(user),
    )
    assert stats_before.status_code == 200
    assert stats_before.json()["storage_cleanup_failure_count"] == 0

    audit_before = await _count_audit_logs(action="storage.cleanup_failed")
    _patch_cleanup_oserror(monkeypatch)

    delete_resp = await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc_id}",
        headers=headers,
    )
    assert delete_resp.status_code == 204

    async with SessionLocal() as db:
        assert await db.get(Document, uuid.UUID(doc_id)) is None

    audit_after = await _count_audit_logs(action="storage.cleanup_failed")
    assert audit_after - audit_before == 1

    latest = await _latest_audit_log(action="storage.cleanup_failed")
    assert latest is not None
    assert str(latest.actor_user_id) == user["id"]
    assert str(latest.kb_id) == kb["id"]
    assert str(latest.resource_id) == doc_id
    assert latest.resource_type == "document"
    assert latest.details is not None
    assert latest.details["filename"] == "disk-fail.txt"
    assert latest.details["file_errors"] >= 1 or latest.details["tree_errors"] >= 1

    stats_after = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers,
        params=workspace_query(user),
    )
    assert stats_after.status_code == 200
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
