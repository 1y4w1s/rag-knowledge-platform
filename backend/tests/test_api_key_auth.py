"""API Key 认证测试：创建/使用/吊销（P1-17：API Key = 账号级全权凭证）。"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from httpx import AsyncClient, Response

from app.core.database import SessionLocal
from app.models.api_key import ApiKey
from tests.conftest import unique_email, unique_username, workspace_query
from tests.fixtures.audit_events import _count_audit_logs, _latest_audit_log
from tests.fixtures.org_members import _promote_member_to_admin_in_db


def _iso_dt(value: str) -> datetime:
    """归一化 ISO 时间串（容忍 ``Z`` 与 ``+00:00`` 两种表达）。"""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def _register_enterprise_owner(
    client: AsyncClient,
    register_and_login,
    *,
    prefix: str,
) -> tuple[dict[str, str], dict]:
    """注册企业 owner（注册即 org_role=admin + is_owner=True）。"""
    return await register_and_login(
        prefix=prefix,
        account_type="enterprise",
        org_name="API Key 测试团队",
    )


async def _register_enterprise_member(
    client: AsyncClient,
    admin_headers: dict[str, str],
    *,
    prefix: str,
) -> tuple[dict[str, str], dict]:
    """复用邀请注册路径构造 enterprise member。"""
    resp = await client.post(
        "/api/v1/organization/invites",
        headers=admin_headers,
        json={},
    )
    assert resp.status_code == 201, resp.text
    code = resp.json()["code"]

    email = unique_email(prefix)
    username = unique_username(prefix)
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "Test123!@",
            "account_type": "enterprise",
            "invite_code": code,
        },
    )
    assert reg.status_code == 201, reg.text

    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": "Test123!@"},
    )
    assert login.status_code == 200
    data = login.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]


@pytest.mark.asyncio
async def test_api_key_create_and_list(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await _register_enterprise_owner(
        client, register_and_login, prefix="api-key-1"
    )
    # 创建 Key
    resp: Response = await client.post(
        "/api/v1/api-keys",
        json={"name": "test-key"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "test-key"
    assert data["raw_key"].startswith("zkan_")
    assert data["scopes"] == ""
    assert data["expires_at"] is None
    raw_key = data["raw_key"]

    # 列出 Key
    resp = await client.get("/api/v1/api-keys", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    # raw_key 不在列表中
    assert all("raw_key" not in item for item in items)


@pytest.mark.asyncio
async def test_api_key_auth_via_bearer(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await _register_enterprise_owner(
        client, register_and_login, prefix="api-key-2"
    )

    # 创建 Key
    resp = await client.post(
        "/api/v1/api-keys",
        json={"name": "ci-key"},
        headers=headers,
    )
    raw_key = resp.json()["raw_key"]

    # 用 Key 调 API（免登录）
    key_headers = {"Authorization": f"Bearer {raw_key}"}
    resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=key_headers,
        params=workspace_query(user, kind="organization"),
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_api_key_revoke_returns_401(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _user = await _register_enterprise_owner(
        client, register_and_login, prefix="api-key-3"
    )

    # 创建 Key
    resp = await client.post(
        "/api/v1/api-keys",
        json={"name": "revoke-me"},
        headers=headers,
    )
    raw_key = resp.json()["raw_key"]
    key_id = resp.json()["id"]

    # 撤销
    resp = await client.delete(f"/api/v1/api-keys/{key_id}", headers=headers)
    assert resp.status_code == 204

    # 用已撤销 Key 调 API → 401
    key_headers = {"Authorization": f"Bearer {raw_key}"}
    resp = await client.get("/api/v1/knowledge-bases", headers=key_headers)
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_api_key_create_personal_forbidden(
    client: AsyncClient,
    register_and_login,
) -> None:
    """P1-17：personal 账号创建 → 403，且不产生 api_key.create 审计。"""
    headers, _user = await register_and_login(prefix="api-key-personal")
    before = await _count_audit_logs(action="api_key.create")

    resp = await client.post(
        "/api/v1/api-keys",
        json={"name": "forbidden"},
        headers=headers,
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == "仅团队账号可创建 API Key"

    after = await _count_audit_logs(action="api_key.create")
    assert after == before


@pytest.mark.asyncio
async def test_api_key_create_enterprise_member_forbidden(
    client: AsyncClient,
    register_and_login,
) -> None:
    """P1-17：enterprise member 创建 → 403（无审批流，默认禁）。"""
    admin_headers, _admin = await _register_enterprise_owner(
        client, register_and_login, prefix="api-key-org"
    )
    member_headers, member = await _register_enterprise_member(
        client, admin_headers, prefix="api-key-member"
    )
    assert member["org_role"] == "member"

    resp = await client.post(
        "/api/v1/api-keys",
        json={"name": "member-key"},
        headers=member_headers,
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == "仅团队管理员或所有者可创建 API Key"


@pytest.mark.asyncio
async def test_api_key_create_owner_and_admin_201(
    client: AsyncClient,
    register_and_login,
) -> None:
    """P1-17：enterprise owner 与 admin（非 owner）创建 → 201。"""
    owner_headers, _owner = await _register_enterprise_owner(
        client, register_and_login, prefix="api-key-owner"
    )
    resp = await client.post(
        "/api/v1/api-keys",
        json={"name": "owner-key"},
        headers=owner_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["expires_at"] is None

    # admin（非 owner）：member 提升为 admin 后即可创建
    admin_headers, admin = await _register_enterprise_owner(
        client, register_and_login, prefix="api-key-promoter"
    )
    member_headers, member = await _register_enterprise_member(
        client, admin_headers, prefix="api-key-admin"
    )
    await _promote_member_to_admin_in_db(
        org_id=admin["org_id"],
        user_id=member["id"],
    )
    resp = await client.post(
        "/api/v1/api-keys",
        json={"name": "admin-key"},
        headers=member_headers,
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_api_key_expires_at_past_422_future_201(
    client: AsyncClient,
    register_and_login,
) -> None:
    """P1-17：expires_at 过去时间 → 422；未来时间（含 naive）→ 201。"""
    headers, _user = await _register_enterprise_owner(
        client, register_and_login, prefix="api-key-expiry"
    )

    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    resp = await client.post(
        "/api/v1/api-keys",
        json={"name": "past-key", "expires_at": past},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"] == "有效期必须晚于当前时间"

    future = (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()
    resp = await client.post(
        "/api/v1/api-keys",
        json={"name": "future-key", "expires_at": future},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["expires_at"] is not None

    # 不带时区的 naive 未来时间也接受（按 UTC 处理）
    naive_future = (datetime.now(timezone.utc) + timedelta(days=30)).replace(
        tzinfo=None
    ).isoformat()
    resp = await client.post(
        "/api/v1/api-keys",
        json={"name": "naive-key", "expires_at": naive_future},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["expires_at"] is not None


@pytest.mark.asyncio
async def test_api_key_expired_returns_401_and_auto_deactivates(
    client: AsyncClient,
    register_and_login,
) -> None:
    """过期 key 调 API → 401，且 is_active 自动置 False（落库）。"""
    headers, _user = await _register_enterprise_owner(
        client, register_and_login, prefix="api-key-expired"
    )
    resp = await client.post(
        "/api/v1/api-keys",
        json={"name": "expire-me"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    raw_key = resp.json()["raw_key"]
    key_id = UUID(resp.json()["id"])

    # 直接改 DB 把 expires_at 置为过去
    async with SessionLocal() as db:
        row = await db.get(ApiKey, key_id)
        assert row is not None
        row.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        await db.commit()

    key_headers = {"Authorization": f"Bearer {raw_key}"}
    resp = await client.get("/api/v1/knowledge-bases", headers=key_headers)
    assert resp.status_code == 401, resp.text

    async with SessionLocal() as db:
        row = await db.get(ApiKey, key_id)
        assert row is not None
        assert row.is_active is False


@pytest.mark.asyncio
async def test_api_key_scopes_input_ignored(
    client: AsyncClient,
    register_and_login,
) -> None:
    """P1-17：scopes 入参忽略 → 落库/响应均为 ""，认证行为仍全权。"""
    headers, user = await _register_enterprise_owner(
        client, register_and_login, prefix="api-key-scopes"
    )
    resp = await client.post(
        "/api/v1/api-keys",
        json={"name": "scope-key", "scopes": "read"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["scopes"] == ""
    raw_key = data["raw_key"]

    async with SessionLocal() as db:
        row = await db.get(ApiKey, UUID(data["id"]))
        assert row is not None
        assert row.scopes == ""

    # 全权：该 key 可直接访问组织知识库
    key_headers = {"Authorization": f"Bearer {raw_key}"}
    resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=key_headers,
        params=workspace_query(user, kind="organization"),
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_api_key_create_audit_contains_expires_at(
    client: AsyncClient,
    register_and_login,
) -> None:
    """api_key.create 审计事件含 name/prefix/expires_at 与创建人。"""
    headers, user = await _register_enterprise_owner(
        client, register_and_login, prefix="api-key-audit"
    )
    future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    resp = await client.post(
        "/api/v1/api-keys",
        json={"name": "audit-key", "expires_at": future},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text

    log = await _latest_audit_log(action="api_key.create")
    assert log is not None
    assert log.actor_user_id == UUID(user["id"])
    assert log.resource_type == "api_key"
    meta = log.details or {}
    assert meta["name"] == "audit-key"
    assert meta["prefix"] == resp.json()["prefix"]
    assert _iso_dt(meta["expires_at"]) == _iso_dt(resp.json()["expires_at"])
