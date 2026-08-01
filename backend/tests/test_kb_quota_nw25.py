"""NW-25 · 单库容量硬闸：超限 / trash / 版本 / 关闭 / adopt。"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.exceptions import ValidationError
from app.models.agent_approval import AgentApproval
from app.models.agent_run import AgentRun
from app.models.chat_thread import ChatThread
from app.models.document_version import DocumentVersion
from app.models.enums import (
    AgentRunMode,
    AgentRunStatus,
    ApprovalKind,
    ApprovalStatus,
    ThreadKind,
    ThreadStatus,
)
from app.models.knowledge_base import KnowledgeBase
from app.services.agent.adopt import adopt_draft_to_kb
from app.services.documents.quota import used_bytes_for_kb
from tests.conftest import create_test_kb, workspace_query
from tests.fixtures.audit_events import _count_audit_logs


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


async def _upload(
    client: AsyncClient,
    headers: dict,
    kb_id: str,
    name: str,
    body: bytes,
) -> tuple[int, dict | None]:
    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        headers=headers,
        files=[("files", (name, body, "text/plain"))],
    )
    if resp.status_code == 201:
        return resp.status_code, resp.json()["documents"][0]
    return resp.status_code, {"detail": resp.json().get("detail")}


@pytest.mark.asyncio
async def test_upload_rejected_when_over_quota(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "kb_quota_max_bytes", 50)
    headers, user = await register_and_login(prefix="nw25-over")
    kb = await create_test_kb(client, headers, user, name="配额超限")

    ok, doc = await _upload(client, headers, kb["id"], "a.txt", b"x" * 40)
    assert ok == 201 and doc is not None

    before_audit = await _count_audit_logs(action="document.quota_rejected")
    status, err = await _upload(client, headers, kb["id"], "b.txt", b"y" * 20)
    assert status == 422
    assert err is not None
    assert "容量已达上限" in str(err["detail"])
    assert await _count_audit_logs(action="document.quota_rejected") == before_audit + 1


@pytest.mark.asyncio
async def test_trash_still_counts_toward_quota(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "kb_quota_max_bytes", 50)
    headers, user = await register_and_login(prefix="nw25-trash")
    kb = await create_test_kb(client, headers, user, name="配额回收站")

    ok, doc = await _upload(client, headers, kb["id"], "keep.txt", b"x" * 40)
    assert ok == 201 and doc is not None

    deleted = await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc['id']}",
        headers=headers,
    )
    assert deleted.status_code == 204

    async with SessionLocal() as db:
        used = await used_bytes_for_kb(db, uuid.UUID(kb["id"]))
    assert used == 40

    status, err = await _upload(client, headers, kb["id"], "again.txt", b"y" * 20)
    assert status == 422
    assert err is not None
    assert "容量已达上限" in str(err["detail"])


@pytest.mark.asyncio
async def test_versions_count_toward_quota_on_overwrite(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "kb_quota_max_bytes", 100)
    headers, user = await register_and_login(prefix="nw25-ver")
    kb = await create_test_kb(client, headers, user, name="配额版本")

    ok, _ = await _upload(client, headers, kb["id"], "same.txt", b"a" * 40)
    assert ok == 201

    # 覆盖：旧 40 进 versions，新 40 落盘 → used≈80；再传 30 应拒
    ok2, _ = await _upload(client, headers, kb["id"], "same.txt", b"b" * 40)
    assert ok2 == 201

    async with SessionLocal() as db:
        used = await used_bytes_for_kb(db, uuid.UUID(kb["id"]))
        assert used == 80
        ver_count = await db.scalar(select(func.count()).select_from(DocumentVersion))
    assert ver_count is not None and int(ver_count) >= 1

    status, err = await _upload(client, headers, kb["id"], "extra.txt", b"c" * 30)
    assert status == 422
    assert err is not None
    assert "容量已达上限" in str(err["detail"])


@pytest.mark.asyncio
async def test_quota_zero_disables_gate(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "kb_quota_max_bytes", 0)
    headers, user = await register_and_login(prefix="nw25-off")
    kb = await create_test_kb(client, headers, user, name="配额关闭")

    status, doc = await _upload(client, headers, kb["id"], "big.txt", b"z" * 5000)
    assert status == 201 and doc is not None


@pytest.mark.asyncio
async def test_single_file_20mb_unchanged(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "kb_quota_max_bytes", 0)
    headers, user = await register_and_login(prefix="nw25-20mb")
    kb = await create_test_kb(client, headers, user, name="单文件闸")

    too_big = b"x" * (settings.upload_max_bytes + 1)
    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("huge.txt", too_big, "text/plain"))],
    )
    assert resp.status_code == 422
    assert "单文件不能超过" in str(resp.json().get("detail", ""))


@pytest.mark.asyncio
async def test_enterprise_upload_same_quota_gate(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "kb_quota_max_bytes", 30)
    headers, user = await register_and_login(
        prefix="nw25-ent",
        account_type="enterprise",
        org_name="配额企业",
    )
    kb = await create_test_kb(client, headers, user, name="企业库配额")
    ok, _ = await _upload(client, headers, kb["id"], "e1.txt", b"a" * 25)
    assert ok == 201
    status, err = await _upload(client, headers, kb["id"], "e2.txt", b"b" * 10)
    assert status == 422
    assert err is not None
    assert "容量已达上限" in str(err["detail"])


@pytest.mark.asyncio
async def test_batch_fails_entirely_when_second_would_exceed(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "kb_quota_max_bytes", 50)
    headers, user = await register_and_login(prefix="nw25-batch")
    kb = await create_test_kb(client, headers, user, name="配额批量")

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[
            ("files", ("one.txt", b"a" * 40, "text/plain")),
            ("files", ("two.txt", b"b" * 20, "text/plain")),
        ],
    )
    assert resp.status_code == 422
    assert "容量已达上限" in str(resp.json().get("detail", ""))

    listing = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
    )
    assert listing.status_code == 200
    assert listing.json()["items"] == []


@pytest.mark.asyncio
async def test_adopt_respects_kb_quota(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "kb_quota_max_bytes", 40)
    headers, user = await register_and_login(prefix="nw25-adopt")
    kb_row = await create_test_kb(client, headers, user, name="采纳配额")
    kb_id = uuid.UUID(kb_row["id"])
    user_id = uuid.UUID(user["id"])

    ok, _ = await _upload(client, headers, kb_row["id"], "fill.txt", b"x" * 35)
    assert ok == 201

    markdown = "# draft\n" + ("y" * 50)
    thread_id = uuid.uuid4()
    run_id = uuid.uuid4()
    approval_id = uuid.uuid4()

    async with SessionLocal() as db:
        db.add(
            ChatThread(
                id=thread_id,
                thread_kind=ThreadKind.workspace,
                user_id=user_id,
                kb_id=kb_id,
                status=ThreadStatus.active,
            )
        )
        await db.flush()
        db.add(
            AgentRun(
                id=run_id,
                thread_id=thread_id,
                user_id=user_id,
                mode=AgentRunMode.edit,
                status=AgentRunStatus.completed,
            )
        )
        await db.flush()
        db.add(
            AgentApproval(
                id=approval_id,
                run_id=run_id,
                thread_id=thread_id,
                user_id=user_id,
                kind=ApprovalKind.adopt_faq,
                status=ApprovalStatus.pending,
                kb_id=kb_id,
                filename="faq-draft.md",
                payload_json={
                    "title": "quota",
                    "filename": "faq-draft.md",
                    "markdown": markdown,
                    "source_chunk_ids": [],
                },
            )
        )
        await db.commit()

    async with SessionLocal() as db:
        kb = await db.get(KnowledgeBase, kb_id)
        approval = await db.get(AgentApproval, approval_id)
        assert kb is not None and approval is not None
        with pytest.raises(ValidationError) as exc:
            await adopt_draft_to_kb(db, approval, kb)
        assert "容量已达上限" in exc.value.detail


@pytest.mark.asyncio
async def test_kb_detail_includes_quota_fields(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "kb_quota_max_bytes", 10 * 1024**3)
    headers, user = await register_and_login(prefix="nw25-i2-det")
    kb = await create_test_kb(client, headers, user, name="详情配额")
    ok, _ = await _upload(client, headers, kb["id"], "a.txt", b"hello")
    assert ok == 201

    detail = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}",
        headers=headers,
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["quota_max_bytes"] == 10 * 1024**3
    assert body["quota_used_bytes"] == 5

    listed = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=workspace_query(user),
    )
    assert listed.status_code == 200
    item = next(i for i in listed.json()["items"] if i["id"] == kb["id"])
    assert item.get("quota_used_bytes") is None
    assert item.get("quota_max_bytes") is None


@pytest.mark.asyncio
async def test_kb_detail_quota_null_when_disabled(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "kb_quota_max_bytes", 0)
    headers, user = await register_and_login(prefix="nw25-i2-off")
    kb = await create_test_kb(client, headers, user, name="关闸无配额")

    detail = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}",
        headers=headers,
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body.get("quota_used_bytes") is None
    assert body.get("quota_max_bytes") is None
