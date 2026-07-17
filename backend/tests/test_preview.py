"""Wave 2.4 文档预览 API 测试。"""

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

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
    password: str = "Test123!@",
) -> tuple[dict[str, str], dict]:
    email = unique_email("preview-member")
    username = unique_username("previewmember")
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


async def _upload_txt(
    client: AsyncClient,
    headers: dict[str, str],
    kb_id: str,
    *,
    filename: str = "notes.txt",
    content: bytes = b"hello preview",
) -> dict:
    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        headers=headers,
        files=[("files", (filename, content, "text/plain"))],
    )
    assert resp.status_code == 201
    return resp.json()["documents"][0]


def _make_pdf(path: Path) -> None:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(72, 720, "Preview PDF sample with enough extractable text for parser.")
    c.drawString(72, 690, "Chapter 1 Attendance policy details.")
    c.save()


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_preview_txt_returns_200_with_text_plain(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="preview-txt")
    kb = await _create_kb(client, headers, user)
    doc = await _upload_txt(client, headers, kb["id"])

    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc['id']}/preview",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert resp.content == b"hello preview"


@pytest.mark.asyncio
async def test_preview_pdf_returns_200_with_application_pdf(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    tmp_path: Path,
) -> None:
    pytest.importorskip("reportlab")
    pdf_path = tmp_path / "sample.pdf"
    _make_pdf(pdf_path)
    pdf_bytes = pdf_path.read_bytes()

    headers, user = await register_and_login(prefix="preview-pdf")
    kb = await _create_kb(client, headers, user)

    upload_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("sample.pdf", pdf_bytes, "application/pdf"))],
    )
    assert upload_resp.status_code == 201
    doc = upload_resp.json()["documents"][0]

    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc['id']}/preview",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_org_member_can_preview_document(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    admin_headers, admin_user = await register_and_login(
        prefix="preview-admin",
        account_type="enterprise",
        org_name="预览可读公司",
    )
    kb = await _create_kb(client, admin_headers, admin_user)
    doc = await _upload_txt(
        client,
        admin_headers,
        kb["id"],
        content=b"member can read",
    )

    member_headers, _member = await _create_org_member_and_login(
        client,
        org_id=admin_user["org_id"],
    )

    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc['id']}/preview",
        headers=member_headers,
    )
    assert resp.status_code == 200
    assert resp.content == b"member can read"


@pytest.mark.asyncio
async def test_sa1_cannot_preview_other_users_document(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers_a, user_a = await register_and_login(prefix="preview-user-a")
    headers_b, _user_b = await register_and_login(prefix="preview-user-b")
    kb = await _create_kb(client, headers_a, user_a)
    doc = await _upload_txt(client, headers_a, kb["id"])

    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc['id']}/preview",
        headers=headers_b,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "无权访问该知识库"


@pytest.mark.asyncio
async def test_preview_non_completed_document_returns_409(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="preview-queued")
    kb = await _create_kb(client, headers, user)

    doc_id = uuid.uuid4()
    storage_dir = upload_dir / kb["id"] / str(doc_id)
    storage_dir.mkdir(parents=True)
    storage_path = storage_dir / f"{uuid.uuid4()}.txt"
    storage_path.write_bytes(b"not ready")

    async with SessionLocal() as db:
        db.add(
            Document(
                id=doc_id,
                kb_id=uuid.UUID(kb["id"]),
                filename="queued.txt",
                file_type="txt",
                file_size=9,
                storage_path=str(storage_path),
                status=DocumentStatus.queued,
                uploaded_by=uuid.UUID(user["id"]),
            )
        )
        await db.commit()

    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc_id}/preview",
        headers=headers,
    )
    assert resp.status_code == 409
    assert "尚未入库完成" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_preview_unknown_document_returns_404(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="preview-missing")
    kb = await _create_kb(client, headers, user)

    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{uuid.uuid4()}/preview",
        headers=headers,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "文档不存在"
