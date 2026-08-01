"""NW-32：GET /admin/audit-logs/export 筛选同源 CSV/JSON 导出。"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.core.database import SessionLocal
from app.models.audit_log import AuditLog
from app.models.enums import AccountType, OrgRole
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.audit.export import CSV_COLUMNS, EXPORT_MAX_ROWS
from app.services.auth.password import hash_password
from tests.conftest import create_test_kb, unique_email, unique_username


async def _register_org_admin(
    client: AsyncClient,
    *,
    prefix: str = "audit-export-admin",
    org_name: str = "审计导出公司",
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
    email = unique_email("audit-export-member")
    username = unique_username("auditexportmember")
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


async def _seed_audit_log(
    *,
    action: str,
    actor_user_id: uuid.UUID | None = None,
    kb_id: uuid.UUID | None = None,
    details: dict | None = None,
    created_at: datetime | None = None,
) -> AuditLog:
    async with SessionLocal() as db:
        entry = AuditLog(
            id=uuid.uuid4(),
            action=action,
            actor_user_id=actor_user_id,
            resource_type="document" if kb_id else None,
            resource_id=uuid.uuid4() if kb_id else None,
            kb_id=kb_id,
            details=details if details is not None else {"seed": True},
            ip="127.0.0.1",
        )
        if created_at is not None:
            entry.created_at = created_at
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry


@pytest.mark.asyncio
async def test_org_admin_export_csv_200(client: AsyncClient) -> None:
    headers, admin_user = await _register_org_admin(client)
    kb = await create_test_kb(client, headers, admin_user, name="导出审计库")
    await _seed_audit_log(
        action="document.delete",
        actor_user_id=uuid.UUID(admin_user["id"]),
        kb_id=uuid.UUID(kb["id"]),
        details={"filename": "a.pdf"},
    )

    resp = await client.get(
        "/api/v1/admin/audit-logs/export",
        headers=headers,
        params={"format": "csv", "action": "document.delete", "kb_id": kb["id"]},
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.headers["x-export-truncated"] == "0"

    reader = csv.DictReader(io.StringIO(resp.text))
    assert reader.fieldnames == list(CSV_COLUMNS)
    rows = list(reader)
    assert len(rows) >= 1
    assert all(r["action"] == "document.delete" for r in rows)
    assert "content" not in CSV_COLUMNS
    assert "question" not in CSV_COLUMNS
    assert "answer" not in CSV_COLUMNS
    assert "body" not in CSV_COLUMNS


@pytest.mark.asyncio
async def test_org_admin_export_json_filter_matches_list(
    client: AsyncClient,
) -> None:
    headers, admin_user = await _register_org_admin(client, prefix="audit-export-json")
    kb = await create_test_kb(client, headers, admin_user, name="JSON导出库")
    actor_id = uuid.UUID(admin_user["id"])
    kb_id = uuid.UUID(kb["id"])
    await _seed_audit_log(action="document.delete", actor_user_id=actor_id, kb_id=kb_id)
    await _seed_audit_log(action="document.retry", actor_user_id=actor_id, kb_id=kb_id)

    params = {"action": "document.retry", "kb_id": kb["id"]}
    listed = await client.get(
        "/api/v1/admin/audit-logs",
        headers=headers,
        params={**params, "limit": 100},
    )
    assert listed.status_code == 200
    list_ids = {item["id"] for item in listed.json()["items"]}

    exported = await client.get(
        "/api/v1/admin/audit-logs/export",
        headers=headers,
        params={**params, "format": "json"},
    )
    assert exported.status_code == 200
    body = exported.json()
    assert body["kind"] == "audit_logs_export"
    assert body["truncated"] is False
    export_ids = {item["id"] for item in body["items"]}
    assert export_ids == list_ids
    assert all(item["action"] == "document.retry" for item in body["items"])
    for item in body["items"]:
        assert "content" not in item
        assert "question" not in item
        assert "answer" not in item


@pytest.mark.asyncio
async def test_org_member_export_403(client: AsyncClient) -> None:
    _admin_headers, admin_user = await _register_org_admin(
        client, prefix="audit-export-m403"
    )
    member_headers = await _create_org_member_and_login(
        client, org_id=admin_user["org_id"]
    )
    resp = await client.get(
        "/api/v1/admin/audit-logs/export",
        headers=member_headers,
        params={"format": "json"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_personal_user_export_403(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _ = await register_and_login(prefix="audit-export-personal")
    resp = await client.get(
        "/api/v1/admin/audit-logs/export",
        headers=headers,
        params={"format": "csv"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_export_no_chat_body_in_details_passthrough(
    client: AsyncClient,
) -> None:
    """落库本就无正文；导出 details 不含对话字段键。"""
    headers, admin_user = await _register_org_admin(client, prefix="audit-export-body")
    kb = await create_test_kb(client, headers, admin_user, name="无正文库")
    await _seed_audit_log(
        action="chat.message_sent",
        actor_user_id=uuid.UUID(admin_user["id"]),
        kb_id=uuid.UUID(kb["id"]),
        details={
            "message_id": str(uuid.uuid4()),
            "citation_count": 2,
            "retrieval_ms": 40,
        },
    )

    resp = await client.get(
        "/api/v1/admin/audit-logs/export",
        headers=headers,
        params={
            "format": "json",
            "action": "chat.message_sent",
            "kb_id": kb["id"],
        },
    )
    assert resp.status_code == 200
    text = resp.text
    assert "citation_count" in text
    assert "user_question" not in text
    assert "assistant_answer" not in text
    assert "对话正文" not in text


@pytest.mark.asyncio
async def test_export_truncated_header_when_over_cap(
    client: AsyncClient,
) -> None:
    headers, admin_user = await _register_org_admin(client, prefix="audit-export-cap")
    kb = await create_test_kb(client, headers, admin_user, name="截断库")
    actor_id = uuid.UUID(admin_user["id"])
    kb_id = uuid.UUID(kb["id"])
    now = datetime.now(UTC)
    for idx in range(3):
        await _seed_audit_log(
            action="document.delete",
            actor_user_id=actor_id,
            kb_id=kb_id,
            created_at=now - timedelta(minutes=idx),
        )

    with patch("app.api.audit.EXPORT_MAX_ROWS", 2):
        resp = await client.get(
            "/api/v1/admin/audit-logs/export",
            headers=headers,
            params={
                "format": "json",
                "action": "document.delete",
                "kb_id": kb["id"],
            },
        )
    assert resp.status_code == 200
    assert resp.headers["x-export-truncated"] == "1"
    assert resp.headers["x-export-limit"] == "2"
    body = resp.json()
    assert body["truncated"] is True
    assert body["exported"] == 2
    assert body["total_matched"] >= 3
    assert body["export_limit"] == 2


def test_export_max_rows_constant() -> None:
    assert EXPORT_MAX_ROWS == 5000
