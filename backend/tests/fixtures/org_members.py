"""共享 helper：组织成员管理测试用的辅助函数。"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.enums import AccountType, OrgRole
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.auth.password import hash_password
from tests.conftest import unique_email, unique_username


async def _create_org_member_and_login(
    client: AsyncClient,
    *,
    org_id: str,
    password: str = "Test123!@",
) -> tuple[dict[str, str], dict]:
    email = unique_email("member")
    username = unique_username("member")
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


async def _register_personal_user(client: AsyncClient, *, prefix: str = "invite") -> dict:
    email = unique_email(prefix)
    username = unique_username(prefix)
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "Test123!@",
            "account_type": "personal",
        },
    )
    assert reg.status_code == 201
    return reg.json()["user"]


async def _promote_member_to_admin_in_db(
    *,
    org_id: str,
    user_id: str,
) -> None:
    async with SessionLocal() as db:
        membership = await db.scalar(
            select(OrganizationMember).where(
                OrganizationMember.org_id == uuid.UUID(org_id),
                OrganizationMember.user_id == uuid.UUID(user_id),
            )
        )
        assert membership is not None
        membership.role = OrgRole.admin
        membership.is_owner = False
        await db.commit()
