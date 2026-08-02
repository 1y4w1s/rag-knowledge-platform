"""P0-04 令牌吊销接线测试：改密后旧 token 401，吊销比较量纲为 epoch。"""

from __future__ import annotations

import asyncio
import time
import uuid

import pytest
from httpx import AsyncClient

from app.services.auth import token_revocation
from app.services.auth.token_revocation import is_token_revoked, revoke_user_tokens


@pytest.fixture(autouse=True)
def _clean_revocation_store() -> None:
    token_revocation._revoked_before.clear()
    yield
    token_revocation._revoked_before.clear()


# ── 单元：吊销比较量纲（epoch）──────────────────────────────────────


def test_revocation_uses_epoch_not_monotonic() -> None:
    """吊销时间必须与 JWT iat（epoch）同量纲；monotonic 会让吊销永失效。"""
    uid = uuid.uuid4()
    revoke_user_tokens(uid)

    # iat 是 epoch 时间戳（约 1.7e9）；若实现误用 monotonic（约 1e4），
    # epoch_iat < monotonic_revoked 恒为 False → 吊销失效（P0-04 原缺陷）。
    epoch_now = time.time()
    assert epoch_now > 1_000_000_000  # 确保量纲是 epoch
    assert is_token_revoked(uid, epoch_now - 10) is True   # 旧 token → 吊销
    assert is_token_revoked(uid, epoch_now + 100) is False  # 未来签发 → 有效


def test_unknown_user_and_none_iat_not_revoked() -> None:
    uid = uuid.uuid4()
    revoke_user_tokens(uid)
    assert is_token_revoked(uuid.uuid4(), time.time()) is False  # 未吊销用户
    assert is_token_revoked(uid, None) is False                  # 无 iat 不误杀


def test_expired_entries_are_pruned(monkeypatch: pytest.MonkeyPatch) -> None:
    """超过 TTL 的吊销记录自动清理。"""
    monkeypatch.setattr(token_revocation, "_TTL", 0.01)
    uid = uuid.uuid4()
    revoke_user_tokens(uid)
    time.sleep(0.02)
    # 触发 _prune_expired
    assert is_token_revoked(uid, time.time() - 100) is False
    assert uid not in token_revocation._revoked_before


# ── 集成：改密后旧 token 401，新 token 可用 ──────────────────────────


@pytest.mark.asyncio
async def test_old_token_rejected_after_password_change(
    client: AsyncClient,
    register_and_login,
) -> None:
    old_password = "Test123!@"
    new_password = "Newpass456!"
    headers, user = await register_and_login(prefix="tokrev")

    # 改密前旧 token 正常
    me_before = await client.get("/api/v1/auth/me", headers=headers)
    assert me_before.status_code == 200

    # 改密 → 吊销该用户全部旧 token
    patch = await client.patch(
        "/api/v1/settings/account",
        headers=headers,
        json={"current_password": old_password, "new_password": new_password},
    )
    assert patch.status_code == 200

    # 同一旧 token 访问受保护端点 → 401（吊销生效）
    me_after = await client.get("/api/v1/auth/me", headers=headers)
    assert me_after.status_code == 401
    assert "重新登录" in me_after.json()["detail"]

    # 新密码重新登录 → 新 token 可用
    # 注意：JWT iat 是整秒（PyJWT 截断），吊销时间带小数；改密后须跨过下一整秒，
    # 否则同一秒内签发的新 token 也会被 `iat < revoked_at` 判定为已吊销。
    await asyncio.sleep(1.1)
    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": user["email"], "password": new_password},
    )
    assert login.status_code == 200
    new_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me_new = await client.get("/api/v1/auth/me", headers=new_headers)
    assert me_new.status_code == 200
