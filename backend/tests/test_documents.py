"""Plan-3A 文档 DELETE + retry API 测试。"""

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import AccountType, DocumentStatus, OrgRole
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.auth.password import hash_password
from app.services.ingestion.pipeline import process_document_ingestion
from tests.conftest import create_test_kb as _create_kb, unique_email, unique_username


async def _create_org_member_and_login(
    client: AsyncClient,
    *,
    org_id: str,
    password: str = "password123",
) -> tuple[dict[str, str], dict]:
    email = unique_email("doc-member")
    username = unique_username("docmember")
    async with SessionLocal() as db:
        user = User(
            id=uuid.uuid4(),
            email=email,
            username=username,
            password_hash=hash_password(password),
            account_type=AccountType.enterprise,
        )
        db.add(user)
        db.add(
            OrganizationMember(
                id=uuid.uuid4(),
                org_id=uuid.UUID(org_id),
                user_id=user.id,
                role=OrgRole.member,
            )
        )
        await db.commit()

    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": password},
    )
    assert login.status_code == 200
    data = login.json()
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    return headers, data["user"]


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_delete_document_cascades_chunks_and_storage(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="doc-delete")
    kb = await _create_kb(client, headers, user)

    upload_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("remove-me.txt", b"delete cascade test", "text/plain"))],
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["documents"][0]["id"]

    async with SessionLocal() as db:
        chunk_count = await db.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == uuid.UUID(doc_id))
        )
        assert chunk_count and chunk_count > 0

    delete_resp = await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc_id}",
        headers=headers,
    )
    assert delete_resp.status_code == 204

    async with SessionLocal() as db:
        assert await db.get(Document, uuid.UUID(doc_id)) is None
        remaining_chunks = await db.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == uuid.UUID(doc_id))
        )
        assert remaining_chunks == 0

    doc_dir = upload_dir / kb["id"] / doc_id
    assert not doc_dir.exists()
    assert not any(p.is_file() for p in upload_dir.rglob("*") if doc_id in str(p))


@pytest.mark.asyncio
async def test_org_member_cannot_delete_document(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    admin_headers, admin_user = await register_and_login(
        prefix="doc-del-admin",
        account_type="enterprise",
        org_name="删文档权限公司",
    )
    kb = await _create_kb(client, admin_headers, admin_user)

    upload_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=admin_headers,
        files=[("files", ("protected.txt", b"no delete", "text/plain"))],
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["documents"][0]["id"]

    member_headers, _member = await _create_org_member_and_login(
        client,
        org_id=admin_user["org_id"],
    )

    resp = await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc_id}",
        headers=member_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "权限不足"


@pytest.mark.asyncio
async def test_sa1_cannot_delete_other_users_document(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers_a, user_a = await register_and_login(prefix="doc-del-a")
    headers_b, _user_b = await register_and_login(prefix="doc-del-b")
    kb = await _create_kb(client, headers_a, user_a)

    upload_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers_a,
        files=[("files", ("mine.txt", b"mine", "text/plain"))],
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["documents"][0]["id"]

    resp = await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc_id}",
        headers=headers_b,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "无权访问该知识库"


@pytest.mark.asyncio
async def test_delete_processing_document_returns_409(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="doc-del-proc")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])
    doc_id = uuid.uuid4()
    storage_dir = upload_dir / str(kb_id) / str(doc_id)
    storage_dir.mkdir(parents=True)
    storage_path = storage_dir / f"{uuid.uuid4()}.txt"
    storage_path.write_bytes(b"still processing")

    async with SessionLocal() as db:
        db.add(
            Document(
                id=doc_id,
                kb_id=kb_id,
                filename="processing.txt",
                file_type="txt",
                file_size=storage_path.stat().st_size,
                storage_path=str(storage_path),
                status=DocumentStatus.processing,
                uploaded_by=uuid.UUID(user["id"]),
            )
        )
        await db.commit()

    resp = await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc_id}",
        headers=headers,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "整理中请稍后再删"

    async with SessionLocal() as db:
        doc = await db.get(Document, doc_id)
        assert doc is not None
        assert doc.status == DocumentStatus.processing


@pytest.mark.asyncio
async def test_delete_queued_document_still_allowed(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="doc-del-queued")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])
    doc_id = uuid.uuid4()
    storage_dir = upload_dir / str(kb_id) / str(doc_id)
    storage_dir.mkdir(parents=True)
    storage_path = storage_dir / f"{uuid.uuid4()}.txt"
    storage_path.write_bytes(b"waiting in queue")

    async with SessionLocal() as db:
        db.add(
            Document(
                id=doc_id,
                kb_id=kb_id,
                filename="queued.txt",
                file_type="txt",
                file_size=storage_path.stat().st_size,
                storage_path=str(storage_path),
                status=DocumentStatus.queued,
                uploaded_by=uuid.UUID(user["id"]),
            )
        )
        await db.commit()

    resp = await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc_id}",
        headers=headers,
    )
    assert resp.status_code == 204

    async with SessionLocal() as db:
        assert await db.get(Document, doc_id) is None


@pytest.mark.asyncio
async def test_delete_nonexistent_document_returns_404(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="doc-del-404")
    kb = await _create_kb(client, headers, user)

    resp = await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{uuid.uuid4()}",
        headers=headers,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "文档不存在"


@pytest.mark.asyncio
async def test_retry_failed_document_reprocesses(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="doc-retry")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])
    doc_id = uuid.uuid4()
    storage_dir = upload_dir / str(kb_id) / str(doc_id)
    storage_dir.mkdir(parents=True)
    storage_path = storage_dir / f"{uuid.uuid4()}.txt"
    storage_path.write_bytes(b"retry me please")

    async with SessionLocal() as db:
        db.add(
            Document(
                id=doc_id,
                kb_id=kb_id,
                filename="retry-me.txt",
                file_type="txt",
                file_size=storage_path.stat().st_size,
                storage_path=str(storage_path),
                status=DocumentStatus.failed,
                error_message="simulated failure",
                uploaded_by=uuid.UUID(user["id"]),
            )
        )
        await db.commit()

    retry_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc_id}/retry",
        headers=headers,
    )
    assert retry_resp.status_code == 200
    body = retry_resp.json()
    assert body["status"] == DocumentStatus.queued.value
    assert body["error_message"] is None

    async with SessionLocal() as db:
        doc = await db.get(Document, doc_id)
        assert doc is not None
        assert doc.status == DocumentStatus.completed
        assert doc.chunk_count is not None and doc.chunk_count > 0


@pytest.mark.asyncio
async def test_retry_non_failed_document_returns_400(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="doc-retry-400")
    kb = await _create_kb(client, headers, user)

    upload_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("ok.txt", b"completed doc", "text/plain"))],
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["documents"][0]["id"]

    retry_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc_id}/retry",
        headers=headers,
    )
    assert retry_resp.status_code == 422
    assert retry_resp.json()["detail"] == "仅失败文档可重试"


@pytest.mark.asyncio
async def test_org_member_cannot_retry_document(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    admin_headers, admin_user = await register_and_login(
        prefix="doc-retry-admin",
        account_type="enterprise",
        org_name="重试权限公司",
    )
    kb = await _create_kb(client, admin_headers, admin_user)
    kb_id = uuid.UUID(kb["id"])
    doc_id = uuid.uuid4()

    async with SessionLocal() as db:
        db.add(
            Document(
                id=doc_id,
                kb_id=kb_id,
                filename="failed.txt",
                file_type="txt",
                file_size=1,
                storage_path=str(upload_dir / "missing-for-failed.txt"),
                status=DocumentStatus.failed,
                error_message="failed",
                uploaded_by=uuid.UUID(admin_user["id"]),
            )
        )
        await db.commit()

    member_headers, _member = await _create_org_member_and_login(
        client,
        org_id=admin_user["org_id"],
    )

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc_id}/retry",
        headers=member_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "权限不足"


@pytest.mark.asyncio
async def test_failed_ingestion_then_retry_via_api(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """端到端：缺文件入库失败 → 补文件 → API retry 成功。"""
    headers, user = await register_and_login(prefix="doc-retry-e2e")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])
    doc_id = uuid.uuid4()
    storage_dir = upload_dir / str(kb_id) / str(doc_id)
    storage_dir.mkdir(parents=True)
    storage_path = storage_dir / f"{uuid.uuid4()}.txt"

    async with SessionLocal() as db:
        db.add(
            Document(
                id=doc_id,
                kb_id=kb_id,
                filename="e2e-retry.txt",
                file_type="txt",
                file_size=1,
                storage_path=str(storage_path),
                status=DocumentStatus.queued,
                uploaded_by=uuid.UUID(user["id"]),
            )
        )
        await db.commit()

    await process_document_ingestion(doc_id)

    async with SessionLocal() as db:
        doc = await db.get(Document, doc_id)
        assert doc is not None
        assert doc.status == DocumentStatus.failed

    storage_path.write_bytes(b"now the file exists for retry")

    retry_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc_id}/retry",
        headers=headers,
    )
    assert retry_resp.status_code == 200
    assert retry_resp.json()["status"] == DocumentStatus.queued.value

    async with SessionLocal() as db:
        doc = await db.get(Document, doc_id)
        assert doc is not None
        assert doc.status == DocumentStatus.completed
