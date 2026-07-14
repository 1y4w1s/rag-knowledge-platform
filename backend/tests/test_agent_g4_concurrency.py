"""G4-2.5 · 编辑模式并发 409 + 限流 30/h（测试固化 · 零生产改动）。

本文件只固化 plan §9 **G4-2.5** 的并发/限流行为，不修改任何生产代码：

- G4-E12（并行/连点 POST → 409）：编辑模式 `mode=edit` 在
  `POST /ask/threads/{id}/chat` 与 `POST /knowledge-bases/{kb_id}/threads/{id}/chat`
  上复用 G3 生成锁 `try_acquire_thread_generation_lock` + `wrap_stream_with_thread_generation_lock`，
  同一 thread 并行生成 → 一 200 / 一 409。fast/thorough 同理（零回归）。
- G4-E17（同用户 31 次/h 编辑 → 429）：编辑模式复用 `enforce_api_rate_limit(
  ApiRateLimitKind.chat, user_id)`（CHAT_MAX_REQUESTS=30/h）。同用户第 31 次编辑
  POST → 429。fast/thorough 同理（零回归 · chat 限额按 user_id 共享）。

验证取向：HTTP 层 409/429 行为，不依赖真实 LLM/embedding——把各 mode 对应的 SSE
流函数 patch 成极快/极慢的兜底生成器（与 `test_agent_thread_generation_lock.py` 同构），
从而把焦点放在「锁」与「限流」两条线上。`tests/test_agent_g4_edit_sse.py` 的
事件序 / approval_required / refusal 语义由该文件独立保障，本窗不回退。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

import pytest
from httpx import AsyncClient

from app.services.auth.api_rate_limit import reset_all_api_rate_limits
from app.services.rag.thread_generation_lock import (
    THREAD_GENERATION_BUSY_DETAIL,
    release_thread_generation_lock,
    reset_thread_generation_locks,
    try_acquire_thread_generation_lock,
)
from tests.conftest import create_test_kb, workspace_query

# (route, mode) → api 模块内被 endpoint 引用的 SSE 流全局名（用于 monkeypatch）。
_STREAM_TARGET: dict[tuple[str, str], str] = {
    ("ask", "edit"): "app.api.ask_threads.stream_agent_edit_events",
    ("ask", "fast"): "app.api.ask_threads.stream_workspace_chat_events",
    ("ask", "thorough"): "app.api.ask_threads.stream_agent_workspace_events",
    ("kb", "edit"): "app.api.kb_threads.stream_agent_kb_edit_events",
    ("kb", "fast"): "app.api.kb_threads.stream_chat_events",
    ("kb", "thorough"): "app.api.kb_threads.stream_agent_kb_events",
}


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


# --------------------------------------------------------------------------- #
# 兜底 SSE 流（patch 用，不依赖真实 LLM/embedding）
# --------------------------------------------------------------------------- #


async def _fast_stream(*_args, **_kwargs) -> AsyncIterator[str]:
    """极快流：立即吐 done，锁随之释放（用于 429 顺序连发场景）。"""
    yield 'event: done\ndata: {"message_id":"m-fast"}\n\n'


def _make_slow_stream(gate: asyncio.Event):
    """极慢流：进入即置 gate（表明锁已占用），再 sleep 持锁一段时间。

    用于并发 409 场景：第一条请求占锁并持锁期间，第二条请求命中 409。
    """

    async def _slow(*_args, **_kwargs) -> AsyncIterator[str]:
        gate.set()
        await asyncio.sleep(0.5)
        yield 'event: token\ndata: {"text":"x"}\n\n'
        yield 'event: done\ndata: {"message_id":"m-slow"}\n\n'

    return _slow


# --------------------------------------------------------------------------- #
# 路由 / thread 准备
# --------------------------------------------------------------------------- #


async def _setup_route(
    route: str, client: AsyncClient, headers: dict[str, str], user: dict
) -> tuple[str, dict, str]:
    """返回 (chat_url, post_extra, thread_id)。post_extra 含路由专属 query 参数。"""
    await create_test_kb(client, headers, user, name=f"并发库-{route}")
    if route == "ask":
        ws = workspace_query(user)
        create_resp = await client.post(
            "/api/v1/ask/threads",
            headers=headers,
            json={"title": "并发会话"},
            params=ws,
        )
        assert create_resp.status_code == 201, create_resp.text
        thread_id = create_resp.json()["id"]
        url = f"/api/v1/ask/threads/{thread_id}/chat"
        return url, {"params": ws}, thread_id
    # kb
    kb = await create_test_kb(client, headers, user, name=f"库内并发库-{route}")
    kb_id = kb["id"]
    create_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/threads",
        headers=headers,
        json={"title": "库内并发会话"},
    )
    assert create_resp.status_code == 201, create_resp.text
    thread_id = create_resp.json()["id"]
    url = f"/api/v1/knowledge-bases/{kb_id}/threads/{thread_id}/chat"
    return url, {}, thread_id


async def _post_chat(
    client: AsyncClient, url: str, headers: dict[str, str], mode: str, extra: dict
) -> int:
    async with client.stream(
        "POST",
        url,
        headers=headers,
        json={"message": f"并发编辑-{mode}", "mode": mode},
        **extra,
    ) as resp:
        await resp.aread()
        return resp.status_code


# --------------------------------------------------------------------------- #
# G4-E12 · 并行/连点 → 409（edit + fast + thorough 零回归）
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("route", ["ask", "kb"])
@pytest.mark.parametrize("mode", ["edit", "fast", "thorough"])
async def test_g4_e12_concurrent_one_200_one_409(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
    route: str,
    mode: str,
) -> None:
    """G4-E12 / 零回归：同一 thread 并行发起两请求 → 一 200、一 409。

    第一条请求占锁并以慢流持锁；第二条在锁占用期间发出 → 409。
    """
    headers, user = await register_and_login(prefix=f"g4-e12-{route}-{mode}")
    url, extra, _thread_id = await _setup_route(route, client, headers, user)

    gate = asyncio.Event()
    monkeypatch.setattr(_STREAM_TARGET[(route, mode)], _make_slow_stream(gate))

    async def _first() -> int:
        return await _post_chat(client, url, headers, mode, extra)

    t1 = asyncio.create_task(_first())
    # 等第一条真正进入流（锁已占），再发第二条，确保并发竞争窗口
    await asyncio.wait_for(gate.wait(), timeout=5)

    t2 = asyncio.create_task(_post_chat(client, url, headers, mode, extra))
    statuses = await asyncio.gather(t1, t2)

    assert set(statuses) == {200, 409}, statuses
    assert statuses.count(409) == 1, statuses


@pytest.mark.parametrize("route", ["ask", "kb"])
async def test_g4_e12_edit_while_generating_returns_409(
    client: AsyncClient,
    register_and_login,
    route: str,
) -> None:
    """G4-E12（确定性）：生成中（锁已占）再 POST 编辑 → 409 + 固定 detail。

    与 G3-E7 同构，仅 mode=edit，固化 edit 分支继承生成锁。
    """
    headers, user = await register_and_login(prefix=f"g4-e12-lock-{route}")
    url, extra, thread_id = await _setup_route(route, client, headers, user)
    thread_id = UUID(thread_id)

    assert await try_acquire_thread_generation_lock(thread_id) is True
    try:
        blocked = await client.post(
            url,
            headers=headers,
            json={"message": "第二条应 409", "mode": "edit"},
            **extra,
        )
        assert blocked.status_code == 409
        assert blocked.json()["detail"] == THREAD_GENERATION_BUSY_DETAIL
    finally:
        await release_thread_generation_lock(thread_id)


# --------------------------------------------------------------------------- #
# G4-E17 · 同用户 31 次/h 编辑 → 429（edit + fast + thorough 零回归）
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("route", ["ask", "kb"])
@pytest.mark.parametrize("mode", ["edit", "fast", "thorough"])
async def test_g4_e17_31st_request_per_hour_429(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
    route: str,
    mode: str,
) -> None:
    """G4-E17 / 零回归：同用户 30 次/h 内成功（200），第 31 次 → 429。

    每条请求以快流让锁即时释放，确保顺序连发不被 409 干扰——焦点纯粹在
    `enforce_api_rate_limit(ApiRateLimitKind.chat, user_id)`（默认 30/h）。
    """
    headers, user = await register_and_login(prefix=f"g4-e17-{route}-{mode}")
    url, extra, _thread_id = await _setup_route(route, client, headers, user)

    monkeypatch.setattr(_STREAM_TARGET[(route, mode)], _fast_stream)

    statuses: list[int] = []
    last_detail: str | None = None
    for i in range(31):
        async with client.stream(
            "POST",
            url,
            headers=headers,
            json={"message": f"编辑-{mode}-{i}", "mode": mode},
            **extra,
        ) as resp:
            await resp.aread()
            statuses.append(resp.status_code)
            if i == 30:
                last_detail = resp.json()["detail"]

    # 前 30 次均成功（限流未触顶、锁已即时释放）
    assert all(s == 200 for s in statuses[:30]), statuses
    # 第 31 次触发 429（chat 限额按 user_id 共享，edit/fast/thorough 同源）
    assert statuses[30] == 429, statuses
    assert last_detail is not None and "对话" in last_detail, last_detail
