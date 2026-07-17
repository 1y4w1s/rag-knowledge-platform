"""Wave 1.1+ 认证 API 测试（需 Postgres + alembic upgrade head）。"""

import jwt
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.services.auth.jwt import JWT_ALGORITHM
from tests.conftest import unique_email, unique_username


@pytest.mark.asyncio
async def test_register_personal(client: AsyncClient) -> None:
    email = unique_email("personal")
    username = unique_username("personal")
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "Test123!@",
            "account_type": "personal",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["user"]["email"] == email
    assert data["user"]["username"] == username
    assert data["user"]["nickname"] is None
    assert data["user"]["account_type"] == "personal"
    assert data["user"]["org_id"] is None
    assert data["user"]["org_role"] is None


@pytest.mark.asyncio
async def test_register_with_optional_nickname(client: AsyncClient) -> None:
    email = unique_email("nick")
    username = unique_username("nick")
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "nickname": "小知",
            "password": "Test123!@",
            "account_type": "personal",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["user"]["nickname"] == "小知"


@pytest.mark.asyncio
async def test_register_enterprise(client: AsyncClient) -> None:
    email = unique_email("enterprise")
    username = unique_username("enterprise")
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "Test123!@",
            "account_type": "enterprise",
            "org_name": "测试科技有限公司",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["user"]["account_type"] == "enterprise"
    assert data["user"]["org_id"] is not None
    assert data["user"]["org_role"] == "admin"


@pytest.mark.asyncio
async def test_register_enterprise_requires_org_name(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email("no-org"),
            "username": unique_username("no-org"),
            "password": "Test123!@",
            "account_type": "enterprise",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient) -> None:
    email = unique_email("dup")
    username_a = unique_username("dup-a")
    username_b = unique_username("dup-b")
    payload = {
        "email": email,
        "username": username_a,
        "password": "Test123!@",
        "account_type": "personal",
    }
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201
    second = await client.post(
        "/api/v1/auth/register",
        json={**payload, "username": username_b},
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient) -> None:
    username = unique_username("dupuser")
    first = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email("dupuser-a"),
            "username": username,
            "password": "Test123!@",
            "account_type": "personal",
        },
    )
    assert first.status_code == 201
    second = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email("dupuser-b"),
            "username": username,
            "password": "Test123!@",
            "account_type": "personal",
        },
    )
    assert second.status_code == 409
    assert "用户名" in second.json()["detail"]


@pytest.mark.asyncio
async def test_login_returns_jwt(client: AsyncClient) -> None:
    email = unique_email("login")
    username = unique_username("login")
    password = "Test123!@"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": password,
            "account_type": "personal",
        },
    )
    assert reg.status_code == 201

    resp = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": password},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["user"]["email"] == email
    assert data["user"]["username"] == username

    payload = jwt.decode(data["access_token"], settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    assert payload["sub"] == data["user"]["id"]
    assert payload["account_type"] == "personal"


@pytest.mark.asyncio
async def test_login_with_username(client: AsyncClient) -> None:
    email = unique_email("login-user")
    username = unique_username("loginuser")
    password = "Test123!@"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": password,
            "account_type": "personal",
        },
    )
    assert reg.status_code == 201

    resp = await client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": password},
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["username"] == username


@pytest.mark.asyncio
async def test_login_enterprise_jwt_has_org_claims(client: AsyncClient) -> None:
    email = unique_email("ent-login")
    username = unique_username("entlogin")
    password = "Test123!@"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": password,
            "account_type": "enterprise",
            "org_name": "答辩演示公司",
        },
    )
    assert reg.status_code == 201
    user = reg.json()["user"]

    resp = await client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": password},
    )
    assert resp.status_code == 200
    data = resp.json()
    payload = jwt.decode(data["access_token"], settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    assert payload["account_type"] == "enterprise"
    assert payload["org_id"] == user["org_id"]
    assert payload["org_role"] == "admin"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient) -> None:
    email = unique_email("wrong-pw")
    username = unique_username("wrongpw")
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "Test123!@",
            "account_type": "personal",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": "wrongpassword"},
    )
    assert resp.status_code == 401
