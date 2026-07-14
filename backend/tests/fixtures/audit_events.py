"""共享 helper：审计事件测试用的辅助函数。"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models.audit_log import AuditLog
from app.models.enums import AccountType, OrgRole
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.auth.password import hash_password
from tests.conftest import unique_email, unique_username


async def _count_audit_logs(*, action: str | None = None) -> int:
    async with SessionLocal() as db:
        stmt = select(func.count()).select_from(AuditLog)
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        count = await db.scalar(stmt)
        return int(count or 0)


async def _latest_audit_log(*, action: str) -> AuditLog | None:
    async with SessionLocal() as db:
        stmt = (
            select(AuditLog)
            .where(AuditLog.action == action)
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
        return await db.scalar(stmt)


async def _register_org_admin(
    client: AsyncClient,
    *,
    prefix: str = "audit-org-unit",
    org_name: str = "审计部门公司",
) -> tuple[dict[str, str], dict]:
    email = unique_email(prefix)
    username = unique_username(prefix)
    password = "password123"
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


async def _create_org_roster_member(
    *,
    org_id: uuid.UUID,
    prefix: str = "roster",
) -> User:
    async with SessionLocal() as db:
        user = User(
            id=uuid.uuid4(),
            email=unique_email(prefix),
            username=unique_username(prefix),
            password_hash=hash_password("password123"),
            account_type=AccountType.enterprise,
        )
        db.add(user)
        db.add(
            OrganizationMember(
                id=uuid.uuid4(),
                org_id=org_id,
                user_id=user.id,
                role=OrgRole.member,
            )
        )
        await db.commit()
        await db.refresh(user)
        return user
