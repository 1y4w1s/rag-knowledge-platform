"""G3-2.5 · thread 生成锁 · G3-E7（并行 POST 同 thread → 409）。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from app.services.auth import api_rate_limit as rl
from app.services.auth.api_rate_limit import reset_all_api_rate_limits
from app.services.rag import thread_generation_lock as lock_mod
from app.services.rag.thread_generation_lock import (
    THREAD_GENERATION_BUSY_DETAIL,
    release_thread_generation_lock,
    reset_thread_generation_locks,
    try_acquire_thread_generation_lock,
    wrap_stream_with_thread_generation_lock,
)
from tests.conftest import create_test_kb, workspace_query


@pytest.fixture(autouse=True)
def _isolate_thread_generation_locks() -> None:
    reset_thread_generation_locks()
    yield
    reset_thread_generation_locks()


@pytest.fixture(autouse=True)
def _isolate_api_rate_limits() -> None:
    reset_all_api_rate_limits()
    yield
    reset_all_api_rate_limits()


@pytest.fixture
def low_api_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rl, "CHAT_MAX_REQUESTS", 30)


async def _slow_stream(*frames: str) -> AsyncIterator[str]:
    await asyncio.sleep(0.3)
    for frame in frames:
        yield frame


@pytest.mark.asyncio
async def test_thread_generation_lock_acquire_and_release() -> None:
    """单元：占用 → 拒绝 → 释放 → 可再占。"""
    thread_id = uuid4()
    assert await try_acquire_thread_generation_lock(thread_id) is True
    assert await try_acquire_thread_generation_lock(thread_id) is False
    await release_thread_generation_lock(thread_id)
    assert await try_acquire_thread_generation_lock(thread_id) is True
    await release_thread_generation_lock(thread_id)


@pytest.mark.asyncio
async def test_wrap_stream_releases_lock_on_completion() -> None:
    """单元：流结束后自动释放。"""
    thread_id = uuid4()
    assert await try_acquire_thread_generation_lock(thread_id) is True

    async for _ in wrap_stream_with_thread_generation_lock(
        thread_id, _slow_stream("event: done\ndata: {}\n\n")
    ):
        pass

    assert await try_acquire_thread_generation_lock(thread_id) is True
    await release_thread_generation_lock(thread_id)


@pytest.mark.asyncio
async def test_wrap_stream_releases_lock_on_error() -> None:
    """单元：流异常时仍释放。"""
    thread_id = uuid4()
    assert await try_acquire_thread_generation_lock(thread_id) is True

    async def _failing() -> AsyncIterator[str]:
        yield "event: token\ndata: {}\n\n"
        raise RuntimeError("stream failed")

    with pytest.raises(RuntimeError, match="stream failed"):
        async for _ in wrap_stream_with_thread_generation_lock(thread_id, _failing()):
            pass

    assert await try_acquire_thread_generation_lock(thread_id) is True
    await release_thread_generation_lock(thread_id)


@pytest.mark.asyncio
async def test_g3_e7_kb_fast_post_while_locked_returns_409(
    client: AsyncClient,
    register_and_login,
) -> None:
    """G3-E7：库内快速模式 · thread 生成中再 POST → 409。"""
    headers, user = await register_and_login(prefix="g3-e7-kb-fast")
    kb = await create_test_kb(client, headers, user, name="并发锁库")
    kb_id = kb["id"]
    create_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/threads",
        headers=headers,
        json={"title": "并发会话"},
    )
    assert create_resp.status_code == 201
    thread_id = UUID(create_resp.json()["id"])

    assert await try_acquire_thread_generation_lock(thread_id) is True
    try:
        blocked = await client.post(
            f"/api/v1/knowledge-bases/{kb_id}/threads/{thread_id}/chat",
            headers=headers,
            json={"message": "第二条应 409", "mode": "fast"},
        )
        assert blocked.status_code == 409
        assert blocked.json()["detail"] == THREAD_GENERATION_BUSY_DETAIL
    finally:
        await release_thread_generation_lock(thread_id)


@pytest.mark.asyncio
async def test_g3_e7_ask_thorough_post_while_locked_returns_409(
    client: AsyncClient,
    register_and_login,
) -> None:
    """G3-E7：工作区精准模式 · thread 生成中再 POST → 409。"""
    headers, user = await register_and_login(prefix="g3-e7-ask-thorough")
    ws = workspace_query(user)
    await create_test_kb(client, headers, user, name="工作区并发库")

    create_resp = await client.post(
        "/api/v1/ask/threads",
        headers=headers,
        json={"title": "工作区并发"},
        params=ws,
    )
    assert create_resp.status_code == 201
    thread_id = UUID(create_resp.json()["id"])

    assert await try_acquire_thread_generation_lock(thread_id) is True
    try:
        blocked = await client.post(
            f"/api/v1/ask/threads/{thread_id}/chat",
            headers=headers,
            json={"message": "第二条应 409", "mode": "thorough"},
            params=ws,
        )
        assert blocked.status_code == 409
        assert blocked.json()["detail"] == THREAD_GENERATION_BUSY_DETAIL
    finally:
        await release_thread_generation_lock(thread_id)


@pytest.mark.asyncio
async def test_g3_e7_concurrent_acquire_only_one_succeeds() -> None:
    """G3-E7：同 thread 双占 · 仅一个成功（并发语义单元测）。"""
    thread_id = uuid4()

    async def _try() -> bool:
        return await try_acquire_thread_generation_lock(thread_id)

    results = await asyncio.gather(_try(), _try())
    assert sorted(results) == [False, True]
    await release_thread_generation_lock(thread_id)


@pytest.mark.asyncio
async def test_g3_e7_different_threads_not_blocked(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G3-E7：不同 thread 可并行生成。"""
    headers, user = await register_and_login(prefix="g3-e7-diff-thread")
    kb = await create_test_kb(client, headers, user, name="不同 thread 库")
    kb_id = kb["id"]

    thread_ids: list[str] = []
    for title in ("会话 A", "会话 B"):
        create_resp = await client.post(
            f"/api/v1/knowledge-bases/{kb_id}/threads",
            headers=headers,
            json={"title": title},
        )
        assert create_resp.status_code == 201
        thread_ids.append(create_resp.json()["id"])

    async def _patched_stream(*_args, **_kwargs) -> AsyncIterator[str]:
        async for frame in _slow_stream(
            'event: token\ndata: {"text":"ok"}\n\n',
            'event: done\ndata: {"message_id":"m1"}\n\n',
        ):
            yield frame

    monkeypatch.setattr("app.api.kb_threads.stream_chat_events", _patched_stream)

    gate = asyncio.Event()
    started: list[UUID] = []

    async def _stream_one(thread_id: str) -> int:
        async with client.stream(
            "POST",
            f"/api/v1/knowledge-bases/{kb_id}/threads/{thread_id}/chat",
            headers=headers,
            json={"message": "并行", "mode": "fast"},
        ) as resp:
            started.append(UUID(thread_id))
            if len(started) == 1:
                gate.set()
            await resp.aread()
            return resp.status_code

    first_task = asyncio.create_task(_stream_one(thread_ids[0]))
    await gate.wait()

    second_task = asyncio.create_task(_stream_one(thread_ids[1]))
    statuses = await asyncio.gather(first_task, second_task)
    assert statuses == [200, 200]


@pytest.mark.asyncio
async def test_g3_e7_sequential_posts_after_release_succeed(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G3-E7：首条完成后 · 同 thread 可再 POST。"""
    headers, user = await register_and_login(prefix="g3-e7-seq")
    kb = await create_test_kb(client, headers, user, name="顺序库")
    kb_id = kb["id"]
    create_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/threads",
        headers=headers,
        json={"title": "顺序会话"},
    )
    thread_id = create_resp.json()["id"]

    async def _patched_stream(*_args, **_kwargs) -> AsyncIterator[str]:
        async for frame in _slow_stream(
            'event: done\ndata: {"message_id":"m1"}\n\n',
        ):
            yield frame

    monkeypatch.setattr("app.api.kb_threads.stream_chat_events", _patched_stream)

    async with client.stream(
        "POST",
        f"/api/v1/knowledge-bases/{kb_id}/threads/{thread_id}/chat",
        headers=headers,
        json={"message": "第一条", "mode": "fast"},
    ) as first:
        assert first.status_code == 200
        await first.aread()

    second = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/threads/{thread_id}/chat",
        headers=headers,
        json={"message": "第二条", "mode": "fast"},
    )
    assert second.status_code == 200

    lock_mod.reset_thread_generation_locks()
