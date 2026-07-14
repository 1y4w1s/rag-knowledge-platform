"""Wave 2.2 文档上传 + BackgroundTasks 入库管道测试。"""

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import AccountType, DocumentStatus, OrgRole
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.auth.password import hash_password
from tests.conftest import create_test_kb as _create_kb, unique_email, unique_username


async def _create_org_member_and_login(
    client: AsyncClient,
    *,
    org_id: str,
    password: str = "password123",
) -> tuple[dict[str, str], dict]:
    email = unique_email("upload-member")
    username = unique_username("uploadmember")
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
async def test_personal_user_can_upload_document(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="upload-personal")
    kb = await _create_kb(client, headers, user)

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("notes.txt", b"hello zhiku", "text/plain"))],
    )
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["documents"]) == 1

    doc = body["documents"][0]
    assert doc["filename"] == "notes.txt"
    assert doc["file_type"] == "txt"
    assert doc["file_size"] == len(b"hello zhiku")
    assert doc["status"] == DocumentStatus.queued.value
    assert doc["uploaded_by"] == user["id"]
    assert doc["kb_id"] == kb["id"]

    stored = Path(doc["storage_path"] if "storage_path" in doc else "")
    # response 不含 storage_path；查磁盘
    disk_files = list(upload_dir.rglob("*"))
    assert any(f.is_file() for f in disk_files)

    async with SessionLocal() as db:
        row = await db.get(Document, uuid.UUID(doc["id"]))
        assert row is not None
        assert row.status == DocumentStatus.completed
        assert row.chunk_count is not None and row.chunk_count > 0
        assert row.processing_started_at is not None
        assert row.processing_completed_at is not None


@pytest.mark.asyncio
async def test_enterprise_admin_can_upload_document(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(
        prefix="upload-admin",
        account_type="enterprise",
        org_name="上传测试公司",
    )
    kb = await _create_kb(client, headers, user)

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("manual.md", b"# Title\n\nBody", "text/markdown"))],
    )
    assert resp.status_code == 201
    assert resp.json()["documents"][0]["status"] == DocumentStatus.queued.value


@pytest.mark.asyncio
async def test_org_member_cannot_upload_document(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    admin_headers, admin_user = await register_and_login(
        prefix="upload-admin-for-member",
        account_type="enterprise",
        org_name="成员禁上传公司",
    )
    kb = await _create_kb(client, admin_headers, admin_user)

    member_headers, _member = await _create_org_member_and_login(
        client,
        org_id=admin_user["org_id"],
    )

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=member_headers,
        files=[("files", ("secret.txt", b"nope", "text/plain"))],
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "权限不足"


@pytest.mark.asyncio
async def test_org_member_can_list_documents(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    admin_headers, admin_user = await register_and_login(
        prefix="upload-list-admin",
        account_type="enterprise",
        org_name="成员可读文档公司",
    )
    kb = await _create_kb(client, admin_headers, admin_user)

    upload_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=admin_headers,
        files=[("files", ("shared.txt", b"shared content", "text/plain"))],
    )
    assert upload_resp.status_code == 201

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


@pytest.mark.asyncio
async def test_sa1_cannot_upload_to_other_users_knowledge_base(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers_a, user_a = await register_and_login(prefix="upload-user-a")
    headers_b, _user_b = await register_and_login(prefix="upload-user-b")
    kb = await _create_kb(client, headers_a, user_a)

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers_b,
        files=[("files", ("intrude.txt", b"bad", "text/plain"))],
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "无权访问该知识库"


@pytest.mark.asyncio
async def test_upload_multiple_files(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="upload-multi")
    kb = await _create_kb(client, headers, user)

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[
            ("files", ("a.txt", b"aaa", "text/plain")),
            ("files", ("b.txt", b"bbb", "text/plain")),
        ],
    )
    assert resp.status_code == 201
    assert len(resp.json()["documents"]) == 2
    assert all(d["status"] == DocumentStatus.queued.value for d in resp.json()["documents"])


@pytest.mark.asyncio
async def test_upload_duplicate_filename_in_kb_returns_409(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="upload-dup-file")
    kb = await _create_kb(client, headers, user)

    first = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("handbook.txt", b"v1", "text/plain"))],
    )
    assert first.status_code == 201

    dup = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("handbook.txt", b"v2", "text/plain"))],
    )
    assert dup.status_code == 409
    assert "同名" in dup.json()["detail"]

    case_dup = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("Handbook.TXT", b"v3", "text/plain"))],
    )
    assert case_dup.status_code == 409


@pytest.mark.asyncio
async def test_upload_duplicate_content_different_filename_returns_409(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="upload-dup-content")
    kb = await _create_kb(client, headers, user)
    content = b"same bytes, different names should still dedupe"

    first = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("handbook.txt", content, "text/plain"))],
    )
    assert first.status_code == 201

    dup = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("copy.md", content, "text/markdown"))],
    )
    assert dup.status_code == 409
    detail = dup.json()["detail"]
    assert "文件内容已存在" in detail
    assert "handbook.txt" in detail

    async with SessionLocal() as db:
        result = await db.scalars(
            select(Document).where(Document.kb_id == uuid.UUID(kb["id"]))
        )
        assert len(result.all()) == 1


@pytest.mark.asyncio
async def test_upload_same_content_allowed_in_different_knowledge_bases(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="upload-cross-kb")
    kb_a = await _create_kb(client, headers, user, name="库 A")
    kb_b = await _create_kb(client, headers, user, name="库 B")
    content = b"shared content across knowledge bases is ok"

    first = await client.post(
        f"/api/v1/knowledge-bases/{kb_a['id']}/documents",
        headers=headers,
        files=[("files", ("a.txt", content, "text/plain"))],
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/v1/knowledge-bases/{kb_b['id']}/documents",
        headers=headers,
        files=[("files", ("b.txt", content, "text/plain"))],
    )
    assert second.status_code == 201


@pytest.mark.asyncio
async def test_upload_duplicate_content_in_same_batch_returns_400(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="upload-dup-content-batch")
    kb = await _create_kb(client, headers, user)
    content = b"batch duplicate content"

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[
            ("files", ("a.txt", content, "text/plain")),
            ("files", ("b.txt", content, "text/plain")),
        ],
    )
    assert resp.status_code == 422
    assert "内容相同" in resp.json()["detail"]

    async with SessionLocal() as db:
        result = await db.scalars(
            select(Document).where(Document.kb_id == uuid.UUID(kb["id"]))
        )
        assert result.all() == []


@pytest.mark.asyncio
async def test_upload_empty_file_returns_400(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="upload-empty")
    kb = await _create_kb(client, headers, user)

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("empty.txt", b"", "text/plain"))],
    )
    assert resp.status_code == 422
    assert "0 字节" in resp.json()["detail"]

    async with SessionLocal() as db:
        result = await db.scalars(
            select(Document).where(Document.kb_id == uuid.UUID(kb["id"]))
        )
        assert result.all() == []


@pytest.mark.asyncio
async def test_upload_duplicate_filename_in_same_batch_returns_400(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="upload-dup-batch")
    kb = await _create_kb(client, headers, user)

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[
            ("files", ("same.txt", b"first", "text/plain")),
            ("files", ("same.txt", b"second", "text/plain")),
        ],
    )
    assert resp.status_code == 422
    assert "重复" in resp.json()["detail"]

    async with SessionLocal() as db:
        result = await db.scalars(
            select(Document).where(Document.kb_id == uuid.UUID(kb["id"]))
        )
        assert result.all() == []
