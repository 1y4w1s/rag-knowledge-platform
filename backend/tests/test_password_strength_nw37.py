"""NW-37：密码强度策略（中文 422 · 注册/改密）。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services.auth.password import validate_password_strength
from app.core.exceptions import ValidationError
from tests.conftest import unique_email, unique_username

STRONG = "Test123!@"


def test_validate_password_strength_unit_messages() -> None:
    with pytest.raises(ValidationError, match="至少 8 位"):
        validate_password_strength("Ab1!")
    with pytest.raises(ValidationError, match="大写字母"):
        validate_password_strength("test123!@")
    with pytest.raises(ValidationError, match="小写字母"):
        validate_password_strength("TEST123!@")
    with pytest.raises(ValidationError, match="数字"):
        validate_password_strength("TestTest!@")
    with pytest.raises(ValidationError, match="特殊字符"):
        validate_password_strength("Test1234")
    validate_password_strength(STRONG)
    validate_password_strength("GoodPass#1")  # # is special under [^A-Za-z0-9]


@pytest.mark.asyncio
async def test_register_rejects_weak_password_chinese(
    client: AsyncClient,
) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email("nw37-weak"),
            "username": unique_username("nw37weak"),
            "password": "password123",
            "account_type": "personal",
        },
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "大写" in detail or "特殊" in detail


@pytest.mark.asyncio
async def test_register_accepts_strong_password(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email("nw37-ok"),
            "username": unique_username("nw37ok"),
            "password": STRONG,
            "account_type": "personal",
        },
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_change_password_rejects_weak_chinese(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _ = await register_and_login(prefix="nw37-chg", password=STRONG)
    resp = await client.patch(
        "/api/v1/settings/account",
        headers=headers,
        json={"current_password": STRONG, "new_password": "newpass456"},
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert isinstance(detail, str)
    assert any(k in detail for k in ("大写", "特殊", "至少"))
