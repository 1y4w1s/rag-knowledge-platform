"""G2：Redis 跨副本限流（mock Redis · 无真 Redis 依赖）。"""

from __future__ import annotations

import time
from collections import defaultdict
from uuid import uuid4

import pytest

from app.core.exceptions import RateLimitError
from app.services.auth import api_rate_limit as api_rl
from app.services.auth import login_rate_limit as login_rl
from app.services.auth.api_rate_limit import ApiRateLimitKind
from app.services.auth.rate_limit_store import (
    redis_sliding_allow,
    reset_rate_limit_backend_cache,
)


class _FakePipeline:
    def __init__(self, fake: "_FakeRedis") -> None:
        self._fake = fake
        self._ops: list[tuple] = []

    def zremrangebyscore(self, key: str, min_s: str | float, max_s: float) -> "_FakePipeline":
        lo = float("-inf") if min_s == "-inf" else float(min_s)
        self._ops.append(("zrem", key, lo, float(max_s)))
        return self

    def zadd(self, key: str, mapping: dict) -> "_FakePipeline":
        self._ops.append(("zadd", key, mapping))
        return self

    def expire(self, key: str, ttl: int) -> "_FakePipeline":
        self._ops.append(("expire", key, ttl))
        return self

    def zcard(self, key: str) -> "_FakePipeline":
        self._ops.append(("zcard", key))
        return self

    async def execute(self) -> list:
        out: list = []
        for op in self._ops:
            if op[0] == "zrem":
                _, key, lo, hi = op
                self._fake._zremrangebyscore(key, lo, hi)
                out.append(0)
            elif op[0] == "zadd":
                _, key, mapping = op
                self._fake._zadd(key, mapping)
                out.append(1)
            elif op[0] == "expire":
                out.append(True)
            elif op[0] == "zcard":
                out.append(self._fake._zcard(op[1]))
        self._ops.clear()
        return out


class _FakeRedis:
    """进程内共享假 Redis：模拟多 api 副本共用同一存储。"""

    def __init__(self) -> None:
        self.zsets: dict[str, dict[str, float]] = defaultdict(dict)
        self.kv: dict[str, str] = {}

    def pipeline(self, transaction: bool = False) -> _FakePipeline:
        return _FakePipeline(self)

    def _zremrangebyscore(self, key: str, lo: float, hi: float) -> None:
        z = self.zsets.get(key, {})
        self.zsets[key] = {m: s for m, s in z.items() if not (lo <= s <= hi)}

    def _zadd(self, key: str, mapping: dict) -> None:
        self.zsets[key].update({str(m): float(s) for m, s in mapping.items()})

    def _zcard(self, key: str) -> int:
        return len(self.zsets.get(key, {}))

    async def eval(self, script: str, numkeys: int, *keys_and_args: str) -> int:
        key = keys_and_args[0]
        now = float(keys_and_args[1])
        window_start = float(keys_and_args[2])
        max_req = int(keys_and_args[3])
        member = keys_and_args[5]
        self._zremrangebyscore(key, float("-inf"), window_start)
        if self._zcard(key) >= max_req:
            return 0
        self._zadd(key, {member: now})
        return 1

    async def get(self, key: str) -> str | None:
        return self.kv.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.kv[key] = value

    async def delete(self, *keys: str) -> int:
        n = 0
        for k in keys:
            if k in self.kv:
                del self.kv[k]
                n += 1
            if k in self.zsets:
                del self.zsets[k]
                n += 1
        return n


# 恢复真实限流实现：直接调用 enforce_api_rate_limit 的用例需真实 429
pytestmark = pytest.mark.usefixtures("real_api_rate_limit")


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> _FakeRedis:
    fake = _FakeRedis()
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    reset_rate_limit_backend_cache()

    async def _get() -> _FakeRedis:
        return fake

    monkeypatch.setattr("app.core.redis.get_redis", _get)
    yield fake
    monkeypatch.delenv("RATE_LIMIT_BACKEND", raising=False)
    reset_rate_limit_backend_cache()
    api_rl.reset_all_api_rate_limits()
    login_rl.reset_all_login_rate_limits()


@pytest.mark.asyncio
async def test_redis_api_exceeds_limit(
    fake_redis: _FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_rl, "CHAT_MAX_REQUESTS", 3)
    uid = uuid4()
    for _ in range(3):
        await api_rl.enforce_api_rate_limit(ApiRateLimitKind.chat, uid)
    with pytest.raises(RateLimitError):
        await api_rl.enforce_api_rate_limit(ApiRateLimitKind.chat, uid)


@pytest.mark.asyncio
async def test_redis_api_fallback_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    reset_rate_limit_backend_cache()
    monkeypatch.setattr(api_rl, "CHAT_MAX_REQUESTS", 2)

    async def _boom():
        raise ConnectionError("redis down")

    monkeypatch.setattr("app.core.redis.get_redis", _boom)
    api_rl.reset_all_api_rate_limits()
    uid = uuid4()
    await api_rl.enforce_api_rate_limit(ApiRateLimitKind.chat, uid)
    await api_rl.enforce_api_rate_limit(ApiRateLimitKind.chat, uid)
    with pytest.raises(RateLimitError):
        await api_rl.enforce_api_rate_limit(ApiRateLimitKind.chat, uid)
    monkeypatch.delenv("RATE_LIMIT_BACKEND", raising=False)
    reset_rate_limit_backend_cache()
    api_rl.reset_all_api_rate_limits()


@pytest.mark.asyncio
async def test_redis_login_failures_shared(fake_redis: _FakeRedis) -> None:
    ip = "203.0.113.9"
    ident = "user-g2"
    for _ in range(login_rl.MAX_FAILURES):
        await login_rl.record_login_failure(ip, ident)
    assert await login_rl.is_login_rate_limited(ip, ident) is True


@pytest.mark.asyncio
async def test_redis_sliding_allow_unit(fake_redis: _FakeRedis) -> None:
    key = "rl:test:unit"
    now = time.time()
    assert await redis_sliding_allow(key, max_requests=2, window_seconds=60, now=now) is True
    assert await redis_sliding_allow(key, max_requests=2, window_seconds=60, now=now + 1) is True
    assert await redis_sliding_allow(key, max_requests=2, window_seconds=60, now=now + 2) is False


@pytest.mark.asyncio
async def test_redis_forgot_password_shared_across_logical_instances(
    fake_redis: _FakeRedis,
) -> None:
    """同 IP 跨逻辑实例共用 rl:forgot 桶（G2 N6）。"""
    ip = "198.51.100.7"
    for _ in range(login_rl.FORGOT_PASSWORD_MAX):
        await login_rl.enforce_forgot_password_rate_limit(ip)
    with pytest.raises(RateLimitError, match="5 分钟"):
        await login_rl.enforce_forgot_password_rate_limit(ip)
    assert f"rl:forgot:{ip}" in fake_redis.zsets


@pytest.mark.asyncio
async def test_redis_forgot_password_fallback_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    reset_rate_limit_backend_cache()
    login_rl.reset_all_login_rate_limits()

    async def _boom():
        raise ConnectionError("redis down")

    monkeypatch.setattr("app.core.redis.get_redis", _boom)
    ip = "198.51.100.8"
    for _ in range(login_rl.FORGOT_PASSWORD_MAX):
        await login_rl.enforce_forgot_password_rate_limit(ip)
    with pytest.raises(RateLimitError):
        await login_rl.enforce_forgot_password_rate_limit(ip)
    monkeypatch.delenv("RATE_LIMIT_BACKEND", raising=False)
    reset_rate_limit_backend_cache()
    login_rl.reset_all_login_rate_limits()


@pytest.mark.asyncio
async def test_memory_forgot_password_exceeds_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RATE_LIMIT_BACKEND", raising=False)
    reset_rate_limit_backend_cache()
    login_rl.reset_all_login_rate_limits()
    ip = "203.0.113.40"
    for _ in range(login_rl.FORGOT_PASSWORD_MAX):
        await login_rl.enforce_forgot_password_rate_limit(ip)
    with pytest.raises(RateLimitError, match="5 分钟"):
        await login_rl.enforce_forgot_password_rate_limit(ip)
    login_rl.reset_all_login_rate_limits()
