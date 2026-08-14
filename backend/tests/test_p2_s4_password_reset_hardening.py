"""P2-S4：密码重置并发竞态 + SMTP 故障统一口径（防邮箱枚举）。"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.services.auth import password_reset as pwd_reset
from app.services.auth.password_reset import _generate_reset_token

pytestmark = pytest.mark.asyncio

GENERIC_MESSAGE = "如果该邮箱已注册，您将收到密码重置邮件"


async def test_smtp_failure_same_message_as_unknown_email(
    client,
    register_and_login,
    monkeypatch,
) -> None:
    """SMTP 故障与邮箱不存在返回完全相同的文案（防枚举）。"""
    _headers, user = await register_and_login(prefix="p2s4-smtp-fail")

    async def _raise(*_args, **_kwargs) -> None:
        raise RuntimeError("smtp down")

    monkeypatch.setattr(pwd_reset, "send_email_smtp", _raise)
    monkeypatch.setattr(pwd_reset.settings, "smtp_host", "smtp.test.local")

    known = await client.post(
        "/api/v1/auth/forgot-password",
        json={"identifier": user["email"]},
    )
    unknown = await client.post(
        "/api/v1/auth/forgot-password",
        json={"identifier": "no-such-user@example.com"},
    )

    assert known.status_code == 200, known.text
    assert unknown.status_code == 200, unknown.text
    assert known.json()["message"] == GENERIC_MESSAGE
    assert unknown.json()["message"] == GENERIC_MESSAGE


async def test_concurrent_reset_same_token_only_once(
    client,
    register_and_login,
    monkeypatch,
) -> None:
    """并发使用同一重置令牌：仅一次成功，败方 422 且败方密码不可登录。"""
    _headers, user = await register_and_login(prefix="p2s4-race")
    token = _generate_reset_token(uuid.UUID(user["id"]))

    original_check = pwd_reset._is_token_consumed_db

    async def _slow_check(db, value: str) -> bool:
        # 人为拉开“已用检查”窗口，让两个请求同时越过初检再进入行锁
        await asyncio.sleep(0.1)
        return await original_check(db, value)

    monkeypatch.setattr(pwd_reset, "_is_token_consumed_db", _slow_check)

    win_password = "NewPass123!@"
    lose_password = "AnotherPass1!@"
    resp_a, resp_b = await asyncio.gather(
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": win_password},
        ),
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": lose_password},
        ),
    )

    statuses = sorted([resp_a.status_code, resp_b.status_code])
    assert statuses == [200, 422], (
        f"预期一成一败，实际 {resp_a.status_code}/{resp_b.status_code}: "
        f"{resp_a.text} | {resp_b.text}"
    )
    failed = resp_a if resp_a.status_code == 422 else resp_b
    assert "已使用" in failed.json()["detail"]

    ok_login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": user["email"], "password": win_password},
    )
    bad_login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": user["email"], "password": lose_password},
    )
    assert ok_login.status_code == 200, ok_login.text
    assert bad_login.status_code == 401, bad_login.text
