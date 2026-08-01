"""M4：密码重置 token 持久化 — 服务重启不可重放。

测试场景：
- 同一 token 二次使用 → 422
- 模拟重启后同一 token 仍被拒
- 篡改 token → 422
"""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.services.auth.password_reset import (
    _consumed_tokens,
    _generate_reset_token,
    reset_password,
)
from app.core.database import SessionLocal
from app.core.exceptions import ValidationError

pytestmark = pytest.mark.asyncio


async def test_reset_token_cannot_be_reused_db(
    client: AsyncClient,
    register_and_login,
) -> None:
    """同一 token 调两次 reset-password → 第二次 422。"""
    headers, user = await register_and_login(prefix="replay-reuse")

    # 生成一个有效的重置 token
    token = _generate_reset_token(uuid.UUID(user["id"]))

    # 第一次调用 — 应成功
    resp1 = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "NewPass123!@"},
    )
    assert resp1.status_code == 200, f"第一次重置失败: {resp1.text}"

    # 第二次调用同一 token — 应 422
    resp2 = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "AnotherPass1!@"},
    )
    assert resp2.status_code == 422, f"预期 422, 得到 {resp2.status_code}: {resp2.text}"
    detail = resp2.json()["detail"]
    assert "已使用" in detail, f"预期包含'已使用', 得到: {detail}"


async def test_reset_token_db_survives_restart(
    client: AsyncClient,
    register_and_login,
) -> None:
    """模拟服务重启后（清空内存缓存），同一 token 仍被拒。"""
    headers, user = await register_and_login(prefix="replay-restart")

    token = _generate_reset_token(uuid.UUID(user["id"]))

    # 第一次调用
    resp1 = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "NewPass123!@"},
    )
    assert resp1.status_code == 200, f"第一次重置失败: {resp1.text}"

    # 模拟重启：清空内存消耗集合
    _consumed_tokens.clear()

    # 同一 token 再次调用 — 应从 DB 查到已消耗
    resp2 = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "AnotherPass1!@"},
    )
    assert resp2.status_code == 422, f"预期 422, 得到 {resp2.status_code}: {resp2.text}"
    detail = resp2.json()["detail"]
    assert "已使用" in detail, f"预期包含'已使用', 得到: {detail}"


async def test_reset_token_invalid(
    client: AsyncClient,
) -> None:
    """篡改 token → 422。"""
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "invalid-token-123", "new_password": "NewPass123!@"},
    )
    assert resp.status_code == 422, f"预期 422, 得到 {resp.status_code}: {resp.text}"
    detail = resp.json()["detail"]
    assert "无效" in detail or "过期" in detail, f"预期包含'无效'或'过期', 得到: [{detail}]"


async def test_reset_token_db_persistence_direct(
    client: AsyncClient,
    register_and_login,
) -> None:
    """直接测试 DB 层持久化：通过服务函数验证重启不可重放。"""
    headers, user = await register_and_login(prefix="replay-db")

    user_id = uuid.UUID(user["id"])
    token = _generate_reset_token(user_id)

    # 通过服务函数重置
    async with SessionLocal() as db:
        await reset_password(
            db,
            token=token,
            new_password="NewPass123!@",
        )

    # 清空内存缓存
    _consumed_tokens.clear()

    # 再次通过服务函数调用同一 token — 应从 DB 拒绝
    async with SessionLocal() as db:
        with pytest.raises(ValidationError, match="已使用"):
            await reset_password(
                db,
                token=token,
                new_password="AnotherPass1!@",
            )
