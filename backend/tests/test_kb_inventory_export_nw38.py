"""NW-38：GET /admin/kb-inventory/export 文档清单 CSV/JSON 导出。"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import AccountType, DocumentStatus, DocumentVisibility, OrgRole
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.auth.password import hash_password
from app.services.documents.inventory_export import CSV_COLUMNS, EXPORT_MAX_ROWS
from tests.conftest import create_test_kb, unique_email, unique_username

FORBIDDEN_COLUMNS = frozenset(
    {
        "content",
        "body",
        "storage_path",
        "question",
        "answer",
        "chunk_content",
        "embeddings",
    }
)


async def _register_org_admin(
    client: AsyncClient,
    *,
    prefix: str = "inv-export-admin",
    org_name: str = "清单导出公司",
) -> tuple[dict[str, str], dict]:
    email = unique_email(prefix)
    username = unique_username(prefix)
    password = "Test123!@"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": password,
            "account_type": "enterprise",
            "org_name": org_name,
        },
    )
    assert reg.status_code == 201
    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": password},
    )
    assert login.status_code == 200
    data = login.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]


async def _create_org_member_and_login(
    client: AsyncClient,
    *,
    org_id: str,
) -> dict[str, str]:
    email = unique_email("inv-export-member")
    username = unique_username("invexportmember")
    password = "Test123!@"
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
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _seed_document(
    *,
    kb_id: uuid.UUID,
    filename: str = "handbook.md",
    uploaded_by: uuid.UUID | None = None,
    deleted_at: datetime | None = None,
    created_at: datetime | None = None,
    status: DocumentStatus = DocumentStatus.completed,
) -> Document:
    async with SessionLocal() as db:
        doc_id = uuid.uuid4()
        doc = Document(
            id=doc_id,
            kb_id=kb_id,
            filename=filename,
            file_type="md",
            file_size=128,
            content_sha256=doc_id.hex,
            storage_path=f"/tmp/nw38/{doc_id}.md",
            status=status,
            chunk_count=3,
            uploaded_by=uploaded_by,
            visibility=DocumentVisibility.everyone,
            current_version=1,
            deleted_at=deleted_at,
        )
        if created_at is not None:
            doc.created_at = created_at
            doc.updated_at = created_at
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        return doc


@pytest.mark.asyncio
async def test_org_admin_export_csv_200(client: AsyncClient) -> None:
    headers, admin_user = await _register_org_admin(client)
    kb = await create_test_kb(client, headers, admin_user, name="清单导出库")
    await _seed_document(
        kb_id=uuid.UUID(kb["id"]),
        filename="acme_手册.md",
        uploaded_by=uuid.UUID(admin_user["id"]),
    )

    resp = await client.get(
        "/api/v1/admin/kb-inventory/export",
        headers=headers,
        params={"format": "csv", "kb_id": kb["id"]},
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.headers["x-export-truncated"] == "0"
    assert resp.headers["x-export-include-trash"] == "0"

    reader = csv.DictReader(io.StringIO(resp.text))
    assert reader.fieldnames == list(CSV_COLUMNS)
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["filename"] == "acme_手册.md"
    assert rows[0]["kb_name"] == "清单导出库"
    assert rows[0]["in_trash"] == "false"
    assert rows[0]["deleted_at"] == ""
    assert FORBIDDEN_COLUMNS.isdisjoint(set(CSV_COLUMNS))
    assert "storage_path" not in resp.text


@pytest.mark.asyncio
async def test_org_admin_export_json_kind_and_columns(client: AsyncClient) -> None:
    headers, admin_user = await _register_org_admin(client, prefix="inv-json")
    kb = await create_test_kb(client, headers, admin_user, name="JSON清单库")
    await _seed_document(
        kb_id=uuid.UUID(kb["id"]),
        filename="spec.md",
        uploaded_by=uuid.UUID(admin_user["id"]),
    )

    resp = await client.get(
        "/api/v1/admin/kb-inventory/export",
        headers=headers,
        params={"format": "json", "kb_id": kb["id"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "kb_inventory_export"
    assert body["kind"] != "audit_logs_export"
    assert body["include_trash"] is False
    assert body["truncated"] is False
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["filename"] == "spec.md"
    assert item["kb_name"] == "JSON清单库"
    assert item["in_trash"] is False
    assert item["deleted_at"] is None
    for key in FORBIDDEN_COLUMNS:
        assert key not in item


@pytest.mark.asyncio
async def test_default_excludes_trash(client: AsyncClient) -> None:
    headers, admin_user = await _register_org_admin(client, prefix="inv-notrash")
    kb = await create_test_kb(client, headers, admin_user, name="无Trash默认库")
    kb_id = uuid.UUID(kb["id"])
    await _seed_document(kb_id=kb_id, filename="active.md")
    await _seed_document(
        kb_id=kb_id,
        filename="trashed.md",
        deleted_at=datetime.now(UTC) - timedelta(days=1),
    )

    resp = await client.get(
        "/api/v1/admin/kb-inventory/export",
        headers=headers,
        params={"format": "json", "kb_id": kb["id"]},
    )
    assert resp.status_code == 200
    names = {item["filename"] for item in resp.json()["items"]}
    assert names == {"active.md"}


@pytest.mark.asyncio
async def test_include_trash_shows_deleted(client: AsyncClient) -> None:
    headers, admin_user = await _register_org_admin(client, prefix="inv-trash")
    kb = await create_test_kb(client, headers, admin_user, name="含Trash库")
    kb_id = uuid.UUID(kb["id"])
    deleted_at = datetime.now(UTC) - timedelta(hours=2)
    await _seed_document(kb_id=kb_id, filename="alive.md")
    await _seed_document(
        kb_id=kb_id,
        filename="gone.md",
        deleted_at=deleted_at,
    )

    resp = await client.get(
        "/api/v1/admin/kb-inventory/export",
        headers=headers,
        params={
            "format": "json",
            "kb_id": kb["id"],
            "include_trash": "true",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["x-export-include-trash"] == "1"
    body = resp.json()
    assert body["include_trash"] is True
    by_name = {item["filename"]: item for item in body["items"]}
    assert set(by_name) == {"alive.md", "gone.md"}
    assert by_name["alive.md"]["in_trash"] is False
    assert by_name["gone.md"]["in_trash"] is True
    assert by_name["gone.md"]["deleted_at"] is not None


@pytest.mark.asyncio
async def test_org_member_export_403(client: AsyncClient) -> None:
    _admin_headers, admin_user = await _register_org_admin(
        client, prefix="inv-m403"
    )
    member_headers = await _create_org_member_and_login(
        client, org_id=admin_user["org_id"]
    )
    resp = await client.get(
        "/api/v1/admin/kb-inventory/export",
        headers=member_headers,
        params={"format": "json"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_personal_user_export_403(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _ = await register_and_login(prefix="inv-personal")
    resp = await client.get(
        "/api/v1/admin/kb-inventory/export",
        headers=headers,
        params={"format": "csv"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_export_truncated_when_over_cap(client: AsyncClient) -> None:
    headers, admin_user = await _register_org_admin(client, prefix="inv-cap")
    kb = await create_test_kb(client, headers, admin_user, name="截断清单库")
    kb_id = uuid.UUID(kb["id"])
    now = datetime.now(UTC)
    for idx in range(3):
        await _seed_document(
            kb_id=kb_id,
            filename=f"doc-{idx}.md",
            created_at=now - timedelta(minutes=idx),
        )

    with patch("app.api.kb_inventory.EXPORT_MAX_ROWS", 2):
        resp = await client.get(
            "/api/v1/admin/kb-inventory/export",
            headers=headers,
            params={"format": "json", "kb_id": kb["id"]},
        )
    assert resp.status_code == 200
    assert resp.headers["x-export-truncated"] == "1"
    assert resp.headers["x-export-limit"] == "2"
    body = resp.json()
    assert body["truncated"] is True
    assert body["exported"] == 2
    assert body["total_matched"] >= 3
    assert body["export_limit"] == 2


@pytest.mark.asyncio
async def test_audit_export_route_isolated(client: AsyncClient) -> None:
    """清单路由 ≠ 审计导出；审计 kind 仍为 audit_logs_export。"""
    headers, admin_user = await _register_org_admin(client, prefix="inv-isol")
    kb = await create_test_kb(client, headers, admin_user, name="隔离库")
    await _seed_document(kb_id=uuid.UUID(kb["id"]), filename="only.md")

    inv = await client.get(
        "/api/v1/admin/kb-inventory/export",
        headers=headers,
        params={"format": "json", "kb_id": kb["id"]},
    )
    assert inv.status_code == 200
    assert inv.json()["kind"] == "kb_inventory_export"

    audit = await client.get(
        "/api/v1/admin/audit-logs/export",
        headers=headers,
        params={"format": "json", "kb_id": kb["id"]},
    )
    assert audit.status_code == 200
    assert audit.json()["kind"] == "audit_logs_export"


@pytest.mark.asyncio
async def test_foreign_kb_id_forbidden(client: AsyncClient) -> None:
    headers_a, _ = await _register_org_admin(client, prefix="inv-fora", org_name="甲公司")
    headers_b, admin_b = await _register_org_admin(
        client, prefix="inv-forb", org_name="乙公司"
    )
    kb_b = await create_test_kb(client, headers_b, admin_b, name="乙库")

    resp = await client.get(
        "/api/v1/admin/kb-inventory/export",
        headers=headers_a,
        params={"format": "json", "kb_id": kb_b["id"]},
    )
    assert resp.status_code == 403


def test_export_max_rows_constant() -> None:
    assert EXPORT_MAX_ROWS == 5000
