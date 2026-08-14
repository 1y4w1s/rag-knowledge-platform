"""P0-04 / P1-S3 令牌吊销接线测试：改密后旧 token 401，吊销持久化到 Redis。

- 单测：吊销比较量纲为 epoch；memory / Redis 双后端；
- Redis 语义：进程重启 / 多副本共享后旧 token 仍被拒绝；
- 集成：改密后旧 token 401（memory 与 Redis 各一条）。
"""

from __future__ import annotations

import asyncio
import time
import uuid

import pytest
from httpx import AsyncClient

from app.services.auth import token_revocation
from app.services.auth.token_revocation import is_token_revoked, revoke_user_tokens


class _FakeSyncRedis:
    """进程内同步假 Redis：实现令牌吊销用到的 get/set（含 TTL 语义）。"""

    def __init__(self) -> None:
        self.kv: dict[str, str] = {}
        self.expirations: dict[str, float] = {}

    def get(self, key: str) -> str | None:
        self._drop_expired()
        return self.kv.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._drop_expired()
        self.kv[key] = value
        if ex is not None:
            self.expirations[key] = time.time() + ex

    def _drop_expired(self) -> None:
        now = time.time()
        expired = [k for k, t in self.expirations.items() if t <= now]
        for k in expired:
            self.kv.pop(k, None)
            self.expirations.pop(k, None)


@pytest.fixture(autouse=True)
def _clean_revocation_store() -> None:
    token_revocation.reset_token_revocation_state()
    yield
    token_revocation.reset_token_revocation_state()


@pytest.fixture
def fake_sync_redis(monkeypatch: pytest.MonkeyPatch) -> _FakeSyncRedis:
    """Redis 后端 + 共享假 Redis：模拟多副本共用同一存储。"""
    from app.services.auth.rate_limit_store import reset_rate_limit_backend_cache

    fake = _FakeSyncRedis()
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    reset_rate_limit_backend_cache()
    monkeypatch.setattr("app.core.redis.get_sync_redis", lambda: fake)
    token_revocation.reset_token_revocation_state()
    yield fake
    token_revocation.reset_token_revocation_state()
    monkeypatch.delenv("RATE_LIMIT_BACKEND", raising=False)
    reset_rate_limit_backend_cache()


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


# ── Redis 双后端：重启 / 多副本 / 回退 ─────────────────────────────


def test_redis_revocation_survives_restart(fake_sync_redis: _FakeSyncRedis) -> None:
    """P1-S3：吊销写入 Redis；清空内存缓存模拟重启后旧 token 仍被拒绝。"""
    uid = uuid.uuid4()
    revoke_user_tokens(uid)
    assert fake_sync_redis.get(token_revocation._revocation_key(uid)) is not None

    token_revocation._revoked_before.clear()  # 模拟进程重启
    epoch_now = time.time()
    assert is_token_revoked(uid, epoch_now - 10) is True
    assert is_token_revoked(uid, epoch_now + 100) is False


def test_redis_revocation_shared_across_copies(fake_sync_redis: _FakeSyncRedis) -> None:
    """多副本：另一副本写入的吊销可被本副本读到并回填进程内缓存。"""
    uid = uuid.uuid4()
    token_revocation._revoked_before.clear()
    fake_sync_redis.set(
        token_revocation._revocation_key(uid),
        str(time.time() - 1),
        ex=token_revocation._TTL,
    )
    assert uid not in token_revocation._revoked_before
    assert is_token_revoked(uid, time.time() - 10) is True
    assert uid in token_revocation._revoked_before  # 读后回填本地缓存


def test_redis_revocation_writes_local_and_redis(fake_sync_redis: _FakeSyncRedis) -> None:
    """本进程吊销同时写入 Redis 与本地缓存，两侧时间一致。"""
    uid = uuid.uuid4()
    revoke_user_tokens(uid)
    assert uid in token_revocation._revoked_before
    raw = fake_sync_redis.get(token_revocation._revocation_key(uid))
    assert raw is not None
    assert abs(float(raw) - token_revocation._revoked_before[uid]) < 0.001


def test_redis_revocation_falls_back_to_memory_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redis 不可达：写/读回退内存，当前进程吊销仍生效，不抛错。"""
    from app.services.auth.rate_limit_store import reset_rate_limit_backend_cache

    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    reset_rate_limit_backend_cache()
    token_revocation.reset_token_revocation_state()

    def _boom() -> None:
        raise ConnectionError("redis down")

    monkeypatch.setattr("app.core.redis.get_sync_redis", _boom)
    uid = uuid.uuid4()
    revoke_user_tokens(uid)
    assert is_token_revoked(uid, time.time() - 10) is True
    assert is_token_revoked(uuid.uuid4(), time.time()) is False

    token_revocation.reset_token_revocation_state()
    monkeypatch.delenv("RATE_LIMIT_BACKEND", raising=False)
    reset_rate_limit_backend_cache()


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


@pytest.mark.asyncio
async def test_old_token_rejected_after_password_change_redis(
    client: AsyncClient,
    register_and_login,
    fake_sync_redis: _FakeSyncRedis,
) -> None:
    """Redis 后端集成：改密吊销写入 Redis，模拟重启后旧 token 仍 401。"""
    old_password = "Test123!@"
    new_password = "Newpass456!"
    headers, user = await register_and_login(prefix="tokrev-redis")

    me_before = await client.get("/api/v1/auth/me", headers=headers)
    assert me_before.status_code == 200

    patch = await client.patch(
        "/api/v1/settings/account",
        headers=headers,
        json={"current_password": old_password, "new_password": new_password},
    )
    assert patch.status_code == 200

    # 清空本地缓存，强制走 Redis 恢复吊销（等价进程重启后首次请求）
    token_revocation._revoked_before.clear()
    me_after = await client.get("/api/v1/auth/me", headers=headers)
    assert me_after.status_code == 401
    assert "重新登录" in me_after.json()["detail"]

    await asyncio.sleep(1.1)
    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": user["email"], "password": new_password},
    )
    assert login.status_code == 200
    new_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me_new = await client.get("/api/v1/auth/me", headers=new_headers)
    assert me_new.status_code == 200
