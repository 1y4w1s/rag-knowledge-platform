"""Wave 1.2 权限测试：JWT 中间件 + SA-1 占位路由。"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.services.auth.jwt import JWT_ALGORITHM


@pytest.mark.asyncio
async def test_protected_route_without_token_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "未提供认证凭据"


@pytest.mark.asyncio
async def test_protected_route_with_invalid_token_returns_401(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "无效的认证凭据"


@pytest.mark.asyncio
async def test_protected_route_with_expired_token_returns_401(client: AsyncClient) -> None:
    expired = jwt.encode(
        {
            "sub": str(uuid4()),
            "account_type": "personal",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        },
        settings.jwt_secret,
        algorithm=JWT_ALGORITHM,
    )
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "认证已过期"


@pytest.mark.asyncio
async def test_auth_me_with_valid_token(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="me")
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == user["id"]
    assert data["email"] == user["email"]
    assert data["account_type"] == "personal"


@pytest.mark.asyncio
async def test_sa1_owner_can_access_own_placeholder_resource(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="owner")
    resp = await client.get(
        f"/api/v1/placeholder/resources/{user['id']}",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["owner_user_id"] == user["id"]


@pytest.mark.asyncio
async def test_sa1_user_cannot_access_other_users_resource(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers_a, _user_a = await register_and_login(prefix="user-a")
    _headers_b, user_b = await register_and_login(prefix="user-b")

    resp = await client.get(
        f"/api/v1/placeholder/resources/{user_b['id']}",
        headers=headers_a,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "无权访问该资源"


@pytest.mark.asyncio
async def test_register_and_login_still_public_without_token(client: AsyncClient) -> None:
    email = f"public-{uuid4().hex[:8]}@example.com"
    username = f"public{uuid4().hex[:8]}"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "password123",
            "account_type": "personal",
        },
    )
    assert reg.status_code == 201

    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": "password123"},
    )
    assert login.status_code == 200
