"""M8-R2 · SSE 并发超限拒绝路径 Redis 计数补偿（P1-R2）。

回归：Redis 后端并发超限拒绝时只 INCR 不补 DECR，被拒请求仍占计数，
用户会被持续 429 直到 TTL 过期。本文件锁定拒绝路径即时补偿回真实占用，
并覆盖内存/Redis 双后端 × 峰值/释放/拒绝三态 + 幂等 + TTL 兜底。
"""

from __future__ import annotations

import inspect
import time
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from app.core import redis as redis_mod
from app.services.rag import sse_concurrency
from app.services.rag.sse_concurrency import (
    ACTIVE_LIMIT,
    _active_streams,
    _slots_expires,
    release_sse_slot,
    try_acquire_sse_slot,
)


class _FakeRedis:
    """记录调用序列的最小 Redis 替身（incr/decr/expire/delete 计数语义）。"""

    def __init__(self) -> None:
        self._store: dict[str, int] = {}
        self.ops: list[tuple[str, ...]] = []

    async def incr(self, key: str) -> int:
        self.ops.append(("incr", key))
        value = self._store.get(key, 0) + 1
        self._store[key] = value
        return value

    async def decr(self, key: str) -> int:
        self.ops.append(("decr", key))
        value = self._store.get(key, 0) - 1
        self._store[key] = value
        return value

    async def expire(self, key: str, ttl: int) -> int:
        self.ops.append(("expire", key, ttl))
        return 1 if key in self._store else 0

    async def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            self.ops.append(("delete", key))
            if key in self._store:
                del self._store[key]
                removed += 1
        return removed


@pytest.fixture(autouse=True)
def _reset_slot_state() -> None:
    _active_streams.clear()
    _slots_expires.clear()
    yield
    _active_streams.clear()
    _slots_expires.clear()


def _use_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sse_concurrency, "_use_redis_backend", lambda: False)


def _use_redis(monkeypatch: pytest.MonkeyPatch, fake: _FakeRedis) -> None:
    monkeypatch.setattr(sse_concurrency, "_use_redis_backend", lambda: True)
    monkeypatch.setattr(redis_mod, "get_redis", AsyncMock(return_value=fake))


def _slot_key(user_id: UUID) -> str:
    return sse_concurrency._slot_key(user_id)


@pytest.mark.asyncio
async def test_memory_peak_three_acquires(monkeypatch: pytest.MonkeyPatch) -> None:
    """峰值态（memory）：连续 3 次成功，账本为 3。"""
    _use_memory(monkeypatch)
    user_id = uuid4()

    for _ in range(ACTIVE_LIMIT):
        assert await try_acquire_sse_slot(user_id)
    assert _active_streams[user_id] == ACTIVE_LIMIT


@pytest.mark.asyncio
async def test_redis_peak_three_acquires(monkeypatch: pytest.MonkeyPatch) -> None:
    """峰值态（redis）：incr 依次 1/2/3，expire 仅首次调用。"""
    fake = _FakeRedis()
    _use_redis(monkeypatch, fake)
    user_id = uuid4()

    for _ in range(ACTIVE_LIMIT):
        assert await try_acquire_sse_slot(user_id)

    key = _slot_key(user_id)
    assert fake._store[key] == ACTIVE_LIMIT
    expire_ops = [op for op in fake.ops if op[0] == "expire"]
    assert len(expire_ops) == 1
    assert expire_ops[0][1] == key


@pytest.mark.asyncio
async def test_memory_reject_keeps_peak_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """拒绝态（memory）：峰值时第 4 次返回 False，账本仍为 3。"""
    _use_memory(monkeypatch)
    user_id = uuid4()
    for _ in range(ACTIVE_LIMIT):
        assert await try_acquire_sse_slot(user_id)

    assert not await try_acquire_sse_slot(user_id)
    assert _active_streams[user_id] == ACTIVE_LIMIT


@pytest.mark.asyncio
async def test_redis_reject_compensates_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    """拒绝态（redis）：第 4 次 INCR=4 被拒后 DECR 补偿回 3（修复核心）。"""
    fake = _FakeRedis()
    _use_redis(monkeypatch, fake)
    user_id = uuid4()
    for _ in range(ACTIVE_LIMIT):
        assert await try_acquire_sse_slot(user_id)
    key = _slot_key(user_id)
    assert fake._store[key] == ACTIVE_LIMIT

    assert not await try_acquire_sse_slot(user_id)
    assert fake._store[key] == ACTIVE_LIMIT
    decr_ops = [op for op in fake.ops if op[0] == "decr"]
    assert len(decr_ops) == 1
    assert decr_ops[0][1] == key


@pytest.mark.asyncio
async def test_memory_release_and_idempotent_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """释放态（memory）：释放后回 2，无槽位时重复 release 幂等不抛。"""
    _use_memory(monkeypatch)
    user_id = uuid4()
    for _ in range(ACTIVE_LIMIT):
        assert await try_acquire_sse_slot(user_id)

    await release_sse_slot(user_id)
    assert _active_streams[user_id] == ACTIVE_LIMIT - 1

    await release_sse_slot(user_id)
    await release_sse_slot(user_id)
    assert user_id not in _active_streams
    await release_sse_slot(user_id)
    assert user_id not in _active_streams


@pytest.mark.asyncio
async def test_redis_release_deletes_zero_and_reacquires(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """释放态（redis）：归零即删，删后重新 acquire 从 1 计数。"""
    fake = _FakeRedis()
    _use_redis(monkeypatch, fake)
    user_id = uuid4()
    assert await try_acquire_sse_slot(user_id)
    key = _slot_key(user_id)
    assert fake._store[key] == 1

    await release_sse_slot(user_id)
    assert fake._store == {}
    delete_ops = [op for op in fake.ops if op[0] == "delete"]
    assert delete_ops and delete_ops[0][1] == key

    assert await try_acquire_sse_slot(user_id)
    assert fake._store[key] == 1


@pytest.mark.asyncio
async def test_redis_reject_then_real_occupancy_recovers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """拒绝后真实占用恢复：拒绝补偿回 3 → release → 2 → 再 acquire 成功。"""
    fake = _FakeRedis()
    _use_redis(monkeypatch, fake)
    user_id = uuid4()
    for _ in range(ACTIVE_LIMIT):
        assert await try_acquire_sse_slot(user_id)

    assert not await try_acquire_sse_slot(user_id)
    assert fake._store[_slot_key(user_id)] == ACTIVE_LIMIT

    await release_sse_slot(user_id)
    assert fake._store[_slot_key(user_id)] == ACTIVE_LIMIT - 1
    assert await try_acquire_sse_slot(user_id)


@pytest.mark.asyncio
async def test_memory_expired_slot_reacquires(monkeypatch: pytest.MonkeyPatch) -> None:
    """TTL 兜底（memory）：槽位过期后 acquire 成功，现有语义不回归。"""
    _use_memory(monkeypatch)
    user_id = uuid4()
    assert await try_acquire_sse_slot(user_id)

    _slots_expires[user_id] = time.monotonic() - 1
    assert await try_acquire_sse_slot(user_id)
    assert _active_streams[user_id] == 1


def test_source_reject_path_calls_compensation_helper() -> None:
    """源码哨兵：拒绝路径必须调用 `_decrement_redis_slot`（防回退）。"""
    acquire_src = inspect.getsource(sse_concurrency._acquire_redis_slot)
    assert "await _decrement_redis_slot(redis, key)" in acquire_src


def test_release_and_reject_converge_on_same_helper() -> None:
    """收敛哨兵：release 与拒绝路径引用同一 helper（防计数逻辑漂移）。"""
    acquire_src = inspect.getsource(sse_concurrency._acquire_redis_slot)
    release_src = inspect.getsource(sse_concurrency._release_redis_slot)
    assert "_decrement_redis_slot(" in acquire_src
    assert "_decrement_redis_slot(" in release_src
