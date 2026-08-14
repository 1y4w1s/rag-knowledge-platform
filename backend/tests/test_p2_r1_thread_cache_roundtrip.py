"""P2-R1：对话 thread 列表缓存 round-trip 保真回归。

- 恢复对象必须带 thread_kind / status 枚举、datetime 时间字段与 last_message_at；
- 旧格式载荷（缺 thread_kind、丢 last_message_at）必须回退 DB，不得返回残缺对象。
"""

from __future__ import annotations

import fnmatch
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.core.database import SessionLocal
from app.models.chat_thread import ChatThread
from app.models.enums import ThreadKind, ThreadStatus
from app.services.rag import thread_persistence as tp
from app.services.rag.persistence import save_kb_chat_turn
from tests.conftest import create_test_kb


class FakeRedis:
    """thread 列表缓存最小 Redis 替身。"""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self._store.pop(key, None)

    async def keys(self, pattern: str) -> list[str]:
        return [key for key in self._store if fnmatch.fnmatchcase(key, pattern)]


def _make_thread(*, kind: ThreadKind, last_message_at: datetime | None) -> ChatThread:
    now = datetime(2026, 8, 10, 8, 30, tzinfo=timezone.utc)
    return ChatThread(
        id=uuid.uuid4(),
        thread_kind=kind,
        user_id=uuid.uuid4(),
        title="预算讨论",
        status=ThreadStatus.active,
        created_at=now,
        updated_at=now,
        last_message_at=last_message_at,
    )


def _use_fake_redis(monkeypatch) -> FakeRedis:
    fake = FakeRedis()
    monkeypatch.setattr(tp, "_get_redis", AsyncMock(return_value=fake))
    return fake


@pytest.mark.asyncio
async def test_cache_roundtrip_preserves_kind_status_and_datetimes(monkeypatch) -> None:
    _use_fake_redis(monkeypatch)
    thread = _make_thread(
        kind=ThreadKind.knowledge_base,
        last_message_at=datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc),
    )

    await tp._cache_thread_list("tl:u:knowledge_base:kb", [thread])
    restored = await tp._load_cached_threads("tl:u:knowledge_base:kb")

    assert restored is not None and len(restored) == 1
    got = restored[0]
    assert got.id == thread.id
    assert got.thread_kind == ThreadKind.knowledge_base
    assert got.status == ThreadStatus.active
    assert isinstance(got.created_at, datetime)
    assert isinstance(got.updated_at, datetime)
    assert got.created_at == thread.created_at
    assert got.updated_at == thread.updated_at
    assert got.last_message_at == thread.last_message_at
    assert got.last_message_at is not None


@pytest.mark.asyncio
async def test_cache_roundtrip_workspace_thread_keeps_null_last_message(monkeypatch) -> None:
    _use_fake_redis(monkeypatch)
    thread = _make_thread(kind=ThreadKind.workspace, last_message_at=None)

    await tp._cache_thread_list("tl:u:workspace:personal", [thread])
    restored = await tp._load_cached_threads("tl:u:workspace:personal")

    assert restored is not None and len(restored) == 1
    assert restored[0].thread_kind == ThreadKind.workspace
    assert restored[0].last_message_at is None


@pytest.mark.asyncio
async def test_legacy_cache_payload_without_thread_kind_falls_back(monkeypatch) -> None:
    fake = _use_fake_redis(monkeypatch)
    old_payload = [
        {
            "id": str(uuid.uuid4()),
            "title": "旧缓存",
            "status": "active",
            "created_at": "2026-08-10T08:30:00+00:00",
            "updated_at": "2026-08-10T08:30:00+00:00",
            # 旧实现不写 thread_kind，且丢弃 last_message_at
        }
    ]
    fake._store["tl:u:knowledge_base:kb"] = json.dumps(old_payload)

    assert await tp._load_cached_threads("tl:u:knowledge_base:kb") is None


@pytest.mark.asyncio
async def test_kb_thread_list_hit_from_cache_returns_last_message_at(
    client,
    register_and_login,
    monkeypatch,
) -> None:
    fake = _use_fake_redis(monkeypatch)
    headers, user = await register_and_login(prefix="p2-r1-cache")
    kb = await create_test_kb(client, headers, user, name="p2-r1-cache")

    async with SessionLocal() as db:
        await save_kb_chat_turn(
            db,
            kb_id=uuid.UUID(kb["id"]),
            user_id=uuid.UUID(user["id"]),
            user_content="缓存问题",
            assistant_content="缓存回答",
            citations=[],
        )

    url = f"/api/v1/knowledge-bases/{kb['id']}/threads"
    first = await client.get(url, headers=headers)
    assert first.status_code == 200
    first_item = first.json()["threads"][0]
    assert first_item["last_message_at"] is not None
    assert len(fake._store) > 0

    second = await client.get(url, headers=headers)
    assert second.status_code == 200
    second_item = second.json()["threads"][0]
    assert second_item["id"] == first_item["id"]
    assert second_item["last_message_at"] == first_item["last_message_at"]
