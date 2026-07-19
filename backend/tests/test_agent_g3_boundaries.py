"""G3-4.1：Agent 边界 + SSE 序 · G3-E1～E8 · E-budget（HTTP/SSE 集成）。

与 Wave 1～3 单测互补；各 E 用例分布：
  E-budget / G3-E8 runtime → test_agent_runtime.py
  G3-E2 scope/tool → test_agent_tools_scope.py · test_agent_semantic_search.py
  G3-E3～E5 dispatch → test_agent_thread_dispatch.py
  G3-E6 gate → test_agent_finalize.py
  G3-E7 409 → test_agent_thread_generation_lock.py
  G3-E8 schema → test_agent_chat_request.py
  G3-E1 abort（前端 rollback/SSE）→ frontend thread-stream-abort.test.ts
本模块补：G3-E1 服务端锁释放 · E-budget/E2/E6/SSE 序 HTTP 路径。
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.enums import AgentRunStatus
from app.services.agent.runs import get_agent_run_for_user
from app.services.agent.tools.scope import FORBIDDEN_KB_SUMMARY
from app.services.agent.types import AgentStepRecord, ToolCallPlan
from app.services.auth.api_rate_limit import reset_all_api_rate_limits
from app.services.rag.thread_generation_lock import (
    release_thread_generation_lock,
    reset_thread_generation_locks,
    try_acquire_thread_generation_lock,
    wrap_stream_with_thread_generation_lock,
)
from tests.conftest import create_test_kb
from tests.test_chat import GOLDEN_MD, _parse_sse_events, _ingest_fixture
from tests.test_r4_4_streaming import _assert_agent_tool_phase_before_citations


@dataclass
class _InfiniteListKbPlanner:
    """E-budget：planner 无限供给 list_knowledge_bases · runtime 应 cap 5 步。"""

    async def next_tool_call(
        self,
        *,
        query: str,
        step_index: int,
        steps_used: int,
        max_steps: int,
        prior_steps: tuple[AgentStepRecord, ...],
    ) -> ToolCallPlan | None:
        del query, step_index, steps_used, max_steps, prior_steps
        return ToolCallPlan(tool_name="list_knowledge_bases", args={})


@dataclass
class _ForbiddenKbSemanticPlanner:
    """G3-E2：semantic_search 传越权 kb_id。"""

    forbidden_kb_id: UUID
    query: str = "年假"
    _done: bool = field(default=False, init=False)

    async def next_tool_call(
        self,
        *,
        query: str,
        step_index: int,
        steps_used: int,
        max_steps: int,
        prior_steps: tuple[AgentStepRecord, ...],
    ) -> ToolCallPlan | None:
        del query, step_index, steps_used, max_steps, prior_steps
        if self._done:
            return None
        self._done = True
        return ToolCallPlan(
            tool_name="semantic_search",
            args={"query": self.query, "kb_ids": [str(self.forbidden_kb_id)]},
        )


async def _slow_sse_stream(*frames: str) -> AsyncIterator[str]:
    for frame in frames:
        yield frame
        await asyncio.sleep(0.15)


def _assert_citations_before_tokens(events: list[tuple[str, dict]]) -> None:
    """R4-4 / §3.3：全部 citation 在首条 token 前。"""
    first_token_idx = next(
        (i for i, (name, _) in enumerate(events) if name == "token"),
        len(events),
    )
    for i, (name, _) in enumerate(events):
        if name == "citation":
            assert i < first_token_idx


def _assert_thorough_sse_order(events: list[tuple[str, dict]]) -> None:
    """§3.3 精准模式：tool 块 → citation* → token* → done。"""
    _assert_agent_tool_phase_before_citations(events)
    _assert_citations_before_tokens(events)
    assert events[-1][0] == "done"


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
def rerank_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rerank_enabled", True)
    monkeypatch.setattr(settings, "rerank_provider", "mock")


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


async def _post_kb_thorough(
    client: AsyncClient,
    headers: dict[str, str],
    kb_id: str,
    thread_id: str,
    message: str,
) -> tuple[int, list[tuple[str, dict]]]:
    async with client.stream(
        "POST",
        f"/api/v1/knowledge-bases/{kb_id}/threads/{thread_id}/chat",
        headers=headers,
        json={"message": message, "mode": "thorough"},
    ) as resp:
        body = await resp.aread()
        return resp.status_code, _parse_sse_events(body.decode("utf-8"))


@pytest.mark.asyncio
async def test_g3_e1_wrap_stream_early_break_releases_lock() -> None:
    """G3-E1：消费方提前退出 SSE · thread 生成锁仍释放（对齐前端 Abort 后果）。"""
    thread_id = uuid.uuid4()
    assert await try_acquire_thread_generation_lock(thread_id) is True

    stream = wrap_stream_with_thread_generation_lock(
        thread_id,
        _slow_sse_stream(
            'event: token\ndata: {"text":"partial"}\n\n',
            'event: done\ndata: {"message_id":"m1"}\n\n',
        ),
    )
    try:
        async for _ in stream:
            break
    finally:
        await stream.aclose()

    assert await try_acquire_thread_generation_lock(thread_id) is True
    await release_thread_generation_lock(thread_id)


@pytest.mark.asyncio
async def test_g3_e1_http_disconnect_releases_lock_for_next_post(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G3-E1：客户端断开 mid-stream · 同 thread 可立即再 POST（非 409）。"""
    headers, user = await register_and_login(prefix="g3-e1-abort")
    kb = await create_test_kb(client, headers, user, name="Abort 测试库")
    kb_id = kb["id"]
    create_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/threads",
        headers=headers,
        json={"title": "Abort 会话"},
    )
    assert create_resp.status_code == 201
    thread_id = create_resp.json()["id"]

    async def _slow_agent_stream(*_args, **_kwargs) -> AsyncIterator[str]:
        async for frame in _slow_sse_stream(
            'event: tool_start\ndata: {"step":1,"tool":"list_knowledge_bases","args_summary":"列库"}\n\n',
            'event: tool_result\ndata: {"step":1,"tool":"list_knowledge_bases","ok":true,"summary":"可见库 1 个","latency_ms":1}\n\n',
            'event: agent_budget\ndata: {"steps_used":1,"max_steps":5,"capped":false}\n\n',
            'event: token\ndata: {"text":"still generating"}\n\n',
            'event: done\ndata: {"message_id":"00000000-0000-0000-0000-000000000001"}\n\n',
        ):
            yield frame

    monkeypatch.setattr("app.api.kb_threads.stream_agent_kb_events", _slow_agent_stream)

    async with client.stream(
        "POST",
        f"/api/v1/knowledge-bases/{kb_id}/threads/{thread_id}/chat",
        headers=headers,
        json={"message": "第一条", "mode": "thorough"},
    ) as resp:
        assert resp.status_code == 200
        async for chunk in resp.aiter_bytes():
            if chunk:
                break

    await asyncio.sleep(0.05)

    second = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/threads/{thread_id}/chat",
        headers=headers,
        json={"message": "第二条", "mode": "fast"},
    )
    assert second.status_code == 200


@pytest.mark.asyncio
async def test_e_budget_http_five_steps_capped_still_completes(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E-budget：HTTP 精准 5/5 · agent_budget.capped · 仍 token+done。"""
    headers, user = await register_and_login(prefix="g3-budget-http")
    kb = await create_test_kb(client, headers, user, name="Budget 库")
    kb_id = kb["id"]
    create_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/threads",
        headers=headers,
        json={"title": "Budget"},
    )
    thread_id = create_resp.json()["id"]

    monkeypatch.setattr(
        "app.api.kb_threads.create_tool_planner",
        lambda _msg: _InfiniteListKbPlanner(),
    )

    status, events = await _post_kb_thorough(
        client, headers, kb_id, thread_id, "复杂跨库对比题"
    )
    assert status == 200
    _assert_thorough_sse_order(events)

    budgets = [data for name, data in events if name == "agent_budget"]
    assert len(budgets) == 5
    assert budgets[-1]["steps_used"] == 5
    assert budgets[-1]["max_steps"] == 5
    assert budgets[-1]["capped"] is True

    tool_results = [data for name, data in events if name == "tool_result"]
    assert len(tool_results) == 5
    assert tool_results[-1].get("capped") is True

    assert any(name == "token" for name, _ in events)
    done = next(data for name, data in events if name == "done")
    assert done.get("agent_run_id")

    run_id = UUID(done["agent_run_id"])
    async with SessionLocal() as db:
        run = await get_agent_run_for_user(
            db, run_id=run_id, user_id=UUID(user["id"])
        )
    assert run is not None
    assert run.status == AgentRunStatus.capped
    assert run.steps_used == 5


@pytest.mark.asyncio
async def test_g3_e2_http_thorough_forbidden_kb_tool_result(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G3-E2：HTTP 精准 · 越权 kb_id → tool_result ok=false · 非 500。"""
    headers, user = await register_and_login(prefix="g3-e2-http")
    kb = await create_test_kb(client, headers, user, name="可见库")
    kb_id = kb["id"]
    forbidden = uuid.uuid4()

    create_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/threads",
        headers=headers,
        json={"title": "越权"},
    )
    thread_id = create_resp.json()["id"]

    monkeypatch.setattr(
        "app.api.kb_threads.create_tool_planner",
        lambda _msg: _ForbiddenKbSemanticPlanner(forbidden_kb_id=forbidden),
    )

    status, events = await _post_kb_thorough(
        client, headers, kb_id, thread_id, "查越权库"
    )
    assert status == 200

    denied = next(data for name, data in events if name == "tool_result")
    assert denied["ok"] is False
    assert denied["summary"] == FORBIDDEN_KB_SUMMARY
    assert events[-1][0] == "done"


@pytest.mark.asyncio
async def test_g3_e6_http_thorough_empty_kb_no_citations(
    client: AsyncClient,
    register_and_login,
) -> None:
    """G3-E6：空库精准 · 无 citation · 拒答 token。"""
    headers, user = await register_and_login(prefix="g3-e6-http")
    kb = await create_test_kb(client, headers, user, name="空库")
    kb_id = kb["id"]
    create_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/threads",
        headers=headers,
        json={"title": "空库会话"},
    )
    thread_id = create_resp.json()["id"]

    status, events = await _post_kb_thorough(
        client, headers, kb_id, thread_id, "员工年假有几天？"
    )
    assert status == 200
    assert not any(name == "citation" for name, _ in events)
    tokens = "".join(data.get("text", "") for name, data in events if name == "token")
    assert "未找到" in tokens or "No relevant content" in tokens
    done = next(data for name, data in events if name == "done")
    assert done.get("citations") == []


@pytest.mark.asyncio
async def test_g3_sse_kb_thorough_http_event_order(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    rerank_mock: None,
) -> None:
    """§3.3 / G3-E9：库内精准 HTTP · tool_* → citation → token → done。"""
    headers, user = await register_and_login(prefix="g3-sse-kb")
    kb = await create_test_kb(client, headers, user, name="SSE 序库")
    kb_id = kb["id"]
    user_id = UUID(user["id"])

    await _ingest_fixture(
        kb_id=UUID(kb_id),
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    create_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/threads",
        headers=headers,
        json={"title": "SSE"},
    )
    thread_id = create_resp.json()["id"]

    status, events = await _post_kb_thorough(
        client, headers, kb_id, thread_id, "员工年假有几天？"
    )
    assert status == 200
    _assert_thorough_sse_order(events)
    assert any(name == "citation" for name, _ in events)
    assert any(name == "agent_budget" for name, _ in events)
