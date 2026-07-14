"""Plan-3E-1 后半：GET /admin/audit-logs 查询 API 测试。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.audit_log import AuditLog
from app.models.enums import AccountType, OrgRole
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.auth.password import hash_password
from tests.conftest import create_test_kb, unique_email, unique_username, workspace_query


async def _register_org_admin(
    client: AsyncClient,
    *,
    prefix: str = "audit-query-admin",
    org_name: str = "审计查询公司",
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
) -> tuple[dict[str, str], dict]:
    email = unique_email("audit-query-member")
    username = unique_username("auditquerymember")
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
    data = login.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]


async def _seed_audit_log(
    *,
    action: str,
    actor_user_id: uuid.UUID | None = None,
    kb_id: uuid.UUID | None = None,
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
            details={"seed": True},
            ip="127.0.0.1",
        )
        if created_at is not None:
            entry.created_at = created_at
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry


@pytest.mark.asyncio
async def test_org_admin_list_audit_logs_200(
    client: AsyncClient,
) -> None:
    admin_headers, admin_user = await _register_org_admin(client)
    kb = await create_test_kb(client, admin_headers, admin_user, name="审计库")
    await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=admin_headers,
        files=[("files", ("audit-query.txt", b"audit query test", "text/plain"))],
    )

    resp = await client.get("/api/v1/admin/audit-logs", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert body["total"] >= 1
    actions = {item["action"] for item in body["items"]}
    assert "document.upload" in actions
    assert all(item["actor_user_id"] == admin_user["id"] for item in body["items"] if item["action"] == "document.upload")


@pytest.mark.asyncio
async def test_org_member_list_audit_logs_403(
    client: AsyncClient,
) -> None:
    admin_headers, admin_user = await _register_org_admin(client, prefix="audit-query-m403")
    member_headers, _ = await _create_org_member_and_login(
        client,
        org_id=admin_user["org_id"],
    )

    resp = await client.get("/api/v1/admin/audit-logs", headers=member_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_personal_user_list_audit_logs_403(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _user = await register_and_login(prefix="audit-query-personal")

    resp = await client.get("/api/v1/admin/audit-logs", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_audit_logs_pagination(
    client: AsyncClient,
) -> None:
    admin_headers, admin_user = await _register_org_admin(client, prefix="audit-query-page")
    kb = await create_test_kb(
        client,
        admin_headers,
        admin_user,
        name="分页审计库",
        workspace_kind="organization",
    )
    actor_id = uuid.UUID(admin_user["id"])
    kb_id = uuid.UUID(kb["id"])

    for idx in range(3):
        await _seed_audit_log(
            action=f"document.delete",
            actor_user_id=actor_id,
            kb_id=kb_id,
            created_at=datetime.now(UTC) - timedelta(minutes=idx),
        )

    page1 = await client.get(
        "/api/v1/admin/audit-logs",
        headers=admin_headers,
        params={"limit": 2, "offset": 0, "action": "document.delete", "kb_id": kb["id"]},
    )
    assert page1.status_code == 200
    body1 = page1.json()
    assert body1["total"] == 3
    assert body1["limit"] == 2
    assert body1["offset"] == 0
    assert len(body1["items"]) == 2

    page2 = await client.get(
        "/api/v1/admin/audit-logs",
        headers=admin_headers,
        params={"limit": 2, "offset": 2, "action": "document.delete", "kb_id": kb["id"]},
    )
    assert page2.status_code == 200
    body2 = page2.json()
    assert body2["total"] == 3
    assert len(body2["items"]) == 1

    page1_ids = {item["id"] for item in body1["items"]}
    page2_ids = {item["id"] for item in body2["items"]}
    assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.asyncio
async def test_list_audit_logs_filter_action(
    client: AsyncClient,
) -> None:
    admin_headers, admin_user = await _register_org_admin(client, prefix="audit-query-action")
    kb = await create_test_kb(client, admin_headers, admin_user, name="筛选审计库")
    actor_id = uuid.UUID(admin_user["id"])
    kb_id = uuid.UUID(kb["id"])

    await _seed_audit_log(action="document.delete", actor_user_id=actor_id, kb_id=kb_id)
    await _seed_audit_log(action="document.retry", actor_user_id=actor_id, kb_id=kb_id)

    resp = await client.get(
        "/api/v1/admin/audit-logs",
        headers=admin_headers,
        params={"action": "document.retry", "kb_id": kb["id"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert all(item["action"] == "document.retry" for item in body["items"])


@pytest.mark.asyncio
async def test_list_audit_logs_filter_time_range(
    client: AsyncClient,
) -> None:
    admin_headers, admin_user = await _register_org_admin(client, prefix="audit-query-time")
    kb = await create_test_kb(client, admin_headers, admin_user, name="时间筛选库")
    actor_id = uuid.UUID(admin_user["id"])
    kb_id = uuid.UUID(kb["id"])
    now = datetime.now(UTC)

    old = await _seed_audit_log(
        action="document.delete",
        actor_user_id=actor_id,
        kb_id=kb_id,
        created_at=now - timedelta(days=10),
    )
    recent = await _seed_audit_log(
        action="document.delete",
        actor_user_id=actor_id,
        kb_id=kb_id,
        created_at=now - timedelta(hours=1),
    )

    resp = await client.get(
        "/api/v1/admin/audit-logs",
        headers=admin_headers,
        params={
            "action": "document.delete",
            "kb_id": kb["id"],
            "created_from": (now - timedelta(days=2)).isoformat(),
            "created_to": now.isoformat(),
        },
    )
    assert resp.status_code == 200
    ids = {item["id"] for item in resp.json()["items"]}
    assert str(recent.id) in ids
    assert str(old.id) not in ids


@pytest.mark.asyncio
async def test_list_audit_logs_foreign_kb_id_403(
    client: AsyncClient,
    register_and_login,
) -> None:
    admin_headers, admin_user = await _register_org_admin(client, prefix="audit-query-kb403")
    other_headers, other_user = await register_and_login(
        prefix="audit-query-other",
        account_type="enterprise",
        org_name="另一家公司",
    )
    foreign_kb = await create_test_kb(
        client,
        other_headers,
        other_user,
        name="外公司库",
        workspace_kind="organization",
    )

    resp = await client.get(
        "/api/v1/admin/audit-logs",
        headers=admin_headers,
        params={"kb_id": foreign_kb["id"]},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_audit_logs_scoped_to_org(
    client: AsyncClient,
    register_and_login,
) -> None:
    admin_headers, admin_user = await _register_org_admin(client, prefix="audit-query-scope")
    other_headers, other_user = await register_and_login(
        prefix="audit-query-scope-other",
        account_type="enterprise",
        org_name="隔离审计公司",
    )
    other_kb = await create_test_kb(
        client,
        other_headers,
        other_user,
        name="隔离库",
        workspace_kind="organization",
    )

    await _seed_audit_log(
        action="document.delete",
        actor_user_id=uuid.UUID(other_user["id"]),
        kb_id=uuid.UUID(other_kb["id"]),
    )

    resp = await client.get(
        "/api/v1/admin/audit-logs",
        headers=admin_headers,
        params={"action": "document.delete", "kb_id": other_kb["id"]},
    )
    assert resp.status_code == 403

    list_resp = await client.get("/api/v1/admin/audit-logs", headers=admin_headers)
    assert list_resp.status_code == 200
    visible_kb_ids = {item["kb_id"] for item in list_resp.json()["items"] if item["kb_id"]}
    assert str(other_kb["id"]) not in visible_kb_ids

    async with SessionLocal() as db:
        foreign_rows = await db.scalars(
            select(AuditLog.id).where(AuditLog.kb_id == uuid.UUID(other_kb["id"]))
        )
        foreign_ids = {str(row) for row in foreign_rows.all()}
    returned_ids = {item["id"] for item in list_resp.json()["items"]}
    assert returned_ids.isdisjoint(foreign_ids)
