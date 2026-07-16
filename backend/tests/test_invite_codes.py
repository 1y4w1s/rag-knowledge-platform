"""W5+-2 · 邀请码 validate / register member / admin 发码。"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.user import User
from app.services.organization.invites import INVITE_INVALID_MSG, revoke_organization_invite_code
from tests.conftest import unique_email, unique_username


async def _create_invite(client: AsyncClient, headers: dict[str, str]) -> str:
    resp = await client.post(
        "/api/v1/organization/invites",
        headers=headers,
        json={},
    )
    assert resp.status_code == 201
    return resp.json()["code"]


@pytest.mark.asyncio
async def test_validate_invite_invalid_code(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/invites/validate",
        json={"code": "BAD-CODE"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == INVITE_INVALID_MSG


@pytest.mark.asyncio
async def test_validate_invite_success(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, admin = await register_and_login(
        prefix="invite-admin",
        account_type="enterprise",
        org_name="睿阁科技",
    )
    code = await _create_invite(client, headers)

    resp = await client.post(
        "/api/v1/auth/invites/validate",
        json={"code": code},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["org_id"] == admin["org_id"]
    assert data["org_name"] == "睿阁科技"


@pytest.mark.asyncio
async def test_register_member_with_invite(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, admin = await register_and_login(
        prefix="member-org",
        account_type="enterprise",
        org_name="成员测试团队",
    )
    code = await _create_invite(client, headers)

    email = unique_email("member")
    username = unique_username("member")
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "password123",
            "account_type": "enterprise",
            "invite_code": code,
        },
    )
    assert resp.status_code == 201
    user = resp.json()["user"]
    assert user["account_type"] == "enterprise"
    assert user["org_id"] == admin["org_id"]
    assert user["org_role"] == "member"


@pytest.mark.asyncio
async def test_same_invite_code_two_members(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, admin = await register_and_login(
        prefix="multi-invite",
        account_type="enterprise",
        org_name="多人码团队",
    )
    code = await _create_invite(client, headers)

    for idx in range(2):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": unique_email(f"multi-{idx}"),
                "username": unique_username(f"multi{idx}"),
                "password": "password123",
                "account_type": "enterprise",
                "invite_code": code,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["user"]["org_id"] == admin["org_id"]
        assert resp.json()["user"]["org_role"] == "member"


@pytest.mark.asyncio
async def test_register_member_rejects_revoked_invite(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _admin = await register_and_login(
        prefix="revoke-org",
        account_type="enterprise",
        org_name="撤销码团队",
    )
    code = await _create_invite(client, headers)

    async with SessionLocal() as db:
        await revoke_organization_invite_code(db, code=code)

    email = unique_email("revoked")
    username = unique_username("revoked")
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "password123",
            "account_type": "enterprise",
            "invite_code": code,
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == INVITE_INVALID_MSG

    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        assert user is None


@pytest.mark.asyncio
async def test_admin_create_invite_requires_admin(
    client: AsyncClient,
    register_and_login,
) -> None:
    personal_headers, _personal = await register_and_login(prefix="personal-no-invite")
    resp = await client.post(
        "/api/v1/organization/invites",
        headers=personal_headers,
        json={},
    )
    assert resp.status_code == 403
