"""Wave 1.3 组织设置 API 测试。"""

import uuid

import pytest
from httpx import AsyncClient

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
    password: str = "password123",
) -> tuple[dict[str, str], dict]:
    """在已有组织下创建 member 用户并登录（成员管理 API 在后续 Wave）。"""
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


@pytest.mark.asyncio
async def test_org_admin_can_get_settings(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(
        prefix="org-admin",
        account_type="enterprise",
        org_name="原始公司名",
    )
    resp = await client.get("/api/v1/organization/settings", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == user["org_id"]
    assert data["name"] == "原始公司名"
    assert "created_at" in data


@pytest.mark.asyncio
async def test_org_admin_can_patch_settings_name(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(
        prefix="org-patch",
        account_type="enterprise",
        org_name="旧名称",
    )
    resp = await client.patch(
        "/api/v1/organization/settings",
        headers=headers,
        json={"name": "新名称科技有限公司"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "新名称科技有限公司"
    assert resp.json()["id"] == user["org_id"]

    get_resp = await client.get("/api/v1/organization/settings", headers=headers)
    assert get_resp.json()["name"] == "新名称科技有限公司"


@pytest.mark.asyncio
async def test_personal_user_cannot_access_org_settings(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _user = await register_and_login(prefix="personal-deny")
    get_resp = await client.get("/api/v1/organization/settings", headers=headers)
    assert get_resp.status_code == 403
    assert get_resp.json()["detail"] == "需要团队账号"

    patch_resp = await client.patch(
        "/api/v1/organization/settings",
        headers=headers,
        json={"name": "非法改名"},
    )
    assert patch_resp.status_code == 403


@pytest.mark.asyncio
async def test_org_member_cannot_access_org_settings(
    client: AsyncClient,
    register_and_login,
) -> None:
    admin_headers, admin_user = await register_and_login(
        prefix="admin-for-member",
        account_type="enterprise",
        org_name="成员测试公司",
    )
    assert admin_user["org_id"] is not None

    member_headers, _member = await _create_org_member_and_login(
        client,
        org_id=admin_user["org_id"],
    )

    get_resp = await client.get("/api/v1/organization/settings", headers=member_headers)
    assert get_resp.status_code == 403
    assert get_resp.json()["detail"] == "权限不足"

    patch_resp = await client.patch(
        "/api/v1/organization/settings",
        headers=member_headers,
        json={"name": "成员试图改名"},
    )
    assert patch_resp.status_code == 403


@pytest.mark.asyncio
async def test_org_settings_requires_token(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/organization/settings")
    assert resp.status_code == 401
