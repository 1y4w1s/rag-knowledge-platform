"""Wave 5.3 账号设置 API 测试 + WS-2-7 填码加入 / 离开团队。"""

import pytest
from httpx import AsyncClient

from app.services.organization.invites import INVITE_INVALID_MSG
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
async def test_get_account_settings_personal(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="acct-personal")
    resp = await client.get("/api/v1/settings/account", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == user["email"]
    assert data["username"] == user["username"]
    assert data["account_type"] == "personal"
    assert data["org_name"] is None


@pytest.mark.asyncio
async def test_get_account_settings_enterprise_includes_org_name(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(
        prefix="acct-ent",
        account_type="enterprise",
        org_name="答辩演示公司",
    )
    resp = await client.get("/api/v1/settings/account", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["account_type"] == "enterprise"
    assert data["org_id"] == user["org_id"]
    assert data["org_name"] == "答辩演示公司"


@pytest.mark.asyncio
async def test_change_password_success_then_relogin(
    client: AsyncClient,
    register_and_login,
) -> None:
    old_password = "password123"
    new_password = "newpass456"
    headers, user = await register_and_login(prefix="acct-pw", password=old_password)

    patch = await client.patch(
        "/api/v1/settings/account",
        headers=headers,
        json={"current_password": old_password, "new_password": new_password},
    )
    assert patch.status_code == 200
    assert "重新登录" in patch.json()["message"]

    old_login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": user["email"], "password": old_password},
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": user["email"], "password": new_password},
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _ = await register_and_login(prefix="acct-wrong")
    resp = await client.patch(
        "/api/v1/settings/account",
        headers=headers,
        json={"current_password": "wrongpass", "new_password": "newpass456"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "当前密码不正确"


@pytest.mark.asyncio
async def test_change_password_too_short(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _ = await register_and_login(prefix="acct-short")
    resp = await client.patch(
        "/api/v1/settings/account",
        headers=headers,
        json={"current_password": "password123", "new_password": "short"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_account_settings_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/settings/account")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_join_team_with_invite_success(
    client: AsyncClient,
    register_and_login,
) -> None:
    admin_headers, admin = await register_and_login(
        prefix="join-admin",
        account_type="enterprise",
        org_name="填码测试团队",
    )
    code = await _create_invite(client, admin_headers)

    personal_headers, personal = await register_and_login(prefix="join-personal")
    assert personal["org_id"] is None

    resp = await client.post(
        "/api/v1/settings/account/join-team",
        headers=personal_headers,
        json={"invite_code": code},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "填码测试团队" in data["message"]
    assert data["account"]["org_id"] == admin["org_id"]
    assert data["account"]["org_role"] == "member"
    assert data["account"]["org_name"] == "填码测试团队"
    assert data["account"]["account_type"] == "enterprise"

    me = await client.get("/api/v1/auth/me", headers=personal_headers)
    assert me.status_code == 200
    assert me.json()["org_id"] == admin["org_id"]
    assert me.json()["org_role"] == "member"


@pytest.mark.asyncio
async def test_join_team_invalid_invite(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _ = await register_and_login(prefix="join-bad-code")
    resp = await client.post(
        "/api/v1/settings/account/join-team",
        headers=headers,
        json={"invite_code": "BAD-CODE"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == INVITE_INVALID_MSG


@pytest.mark.asyncio
async def test_join_team_already_in_team(
    client: AsyncClient,
    register_and_login,
) -> None:
    admin_headers, admin = await register_and_login(
        prefix="join-dup-admin",
        account_type="enterprise",
        org_name="已在团队",
    )
    code = await _create_invite(client, admin_headers)

    member_email = unique_email("join-dup-member")
    member_username = unique_username("joindup")
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": member_email,
            "username": member_username,
            "password": "password123",
            "account_type": "enterprise",
            "invite_code": code,
        },
    )
    assert reg.status_code == 201

    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": member_email, "password": "password123"},
    )
    assert login.status_code == 200
    member_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.post(
        "/api/v1/settings/account/join-team",
        headers=member_headers,
        json={"invite_code": code},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "您已在团队中"


@pytest.mark.asyncio
async def test_leave_team_member_success(
    client: AsyncClient,
    register_and_login,
) -> None:
    admin_headers, admin = await register_and_login(
        prefix="leave-admin",
        account_type="enterprise",
        org_name="离开测试团队",
    )
    code = await _create_invite(client, admin_headers)

    member_email = unique_email("leave-member")
    member_username = unique_username("leavemem")
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": member_email,
            "username": member_username,
            "password": "password123",
            "account_type": "enterprise",
            "invite_code": code,
        },
    )
    assert reg.status_code == 201

    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": member_email, "password": "password123"},
    )
    assert login.status_code == 200
    member_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.post(
        "/api/v1/settings/account/leave-team",
        headers=member_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "离开测试团队" in data["message"]
    assert data["account"]["org_id"] is None
    assert data["account"]["account_type"] == "personal"
    assert data["account"]["org_name"] is None

    me = await client.get("/api/v1/auth/me", headers=member_headers)
    assert me.status_code == 200
    assert me.json()["org_id"] is None
    assert me.json()["account_type"] == "personal"


@pytest.mark.asyncio
async def test_leave_team_loses_team_kb_access(
    client: AsyncClient,
    register_and_login,
) -> None:
    """R2 E3/Bookmark：Member 自退团队后不能再读团队资料库（403）。"""
    from tests.conftest import create_test_kb

    admin_headers, admin = await register_and_login(
        prefix="leave-kb-admin",
        account_type="enterprise",
        org_name="离开失权团队",
    )
    kb = await create_test_kb(client, admin_headers, admin, name="团队共享库")
    code = await _create_invite(client, admin_headers)

    member_email = unique_email("leave-kb-member")
    member_username = unique_username("leavekbmem")
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": member_email,
            "username": member_username,
            "password": "password123",
            "account_type": "enterprise",
            "invite_code": code,
        },
    )
    assert reg.status_code == 201

    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": member_email, "password": "password123"},
    )
    assert login.status_code == 200
    member_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    before = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}",
        headers=member_headers,
    )
    assert before.status_code == 200

    leave = await client.post(
        "/api/v1/settings/account/leave-team",
        headers=member_headers,
    )
    assert leave.status_code == 200

    after = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}",
        headers=member_headers,
    )
    assert after.status_code == 403
    assert after.json()["detail"] == "无权访问该知识库"


@pytest.mark.asyncio
async def test_leave_team_owner_forbidden(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _ = await register_and_login(
        prefix="leave-owner",
        account_type="enterprise",
        org_name="Owner 不能自退",
    )
    resp = await client.post(
        "/api/v1/settings/account/leave-team",
        headers=headers,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "离开前请先转让团队所有权"


@pytest.mark.asyncio
async def test_leave_team_not_in_team(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _ = await register_and_login(prefix="leave-personal")
    resp = await client.post(
        "/api/v1/settings/account/leave-team",
        headers=headers,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "您未加入任何团队"
