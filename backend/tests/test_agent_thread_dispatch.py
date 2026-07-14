"""G3-2.4：ask/kb thread chat mode dispatch · G3-E3～E5。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services.auth import api_rate_limit as rl
from app.services.auth.api_rate_limit import reset_all_api_rate_limits
from tests.conftest import create_test_kb, workspace_query
from tests.test_chat import _parse_sse_events


@pytest.fixture(autouse=True)
def _isolate_api_rate_limits() -> None:
    reset_all_api_rate_limits()
    yield
    reset_all_api_rate_limits()


@pytest.fixture
def low_api_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rl, "CHAT_MAX_REQUESTS", 3)
    monkeypatch.setattr(rl, "UPLOAD_MAX_REQUESTS", 3)


async def _post_ask_thread_chat(
    client: AsyncClient,
    headers: dict[str, str],
    thread_id: str,
    payload: dict,
    *,
    workspace: str,
) -> tuple[int, list[tuple[str, dict]]]:
    async with client.stream(
        "POST",
        f"/api/v1/ask/threads/{thread_id}/chat",
        headers=headers,
        json=payload,
        params={"workspace": workspace},
    ) as resp:
        body = await resp.aread()
        events = _parse_sse_events(body.decode("utf-8"))
        return resp.status_code, events


async def _post_kb_thread_chat(
    client: AsyncClient,
    headers: dict[str, str],
    kb_id: str,
    thread_id: str,
    payload: dict,
) -> tuple[int, list[tuple[str, dict]]]:
    async with client.stream(
        "POST",
        f"/api/v1/knowledge-bases/{kb_id}/threads/{thread_id}/chat",
        headers=headers,
        json=payload,
    ) as resp:
        body = await resp.aread()
        events = _parse_sse_events(body.decode("utf-8"))
        return resp.status_code, events


@pytest.mark.asyncio
async def test_g3_e3_thorough_no_visible_kb_returns_400(
    client: AsyncClient,
    register_and_login,
) -> None:
    """G3-E3：无可见库 · 精准模式 → 400 · 不进入 Agent。"""
    headers, user = await register_and_login(prefix="g3-e3")
    ws = workspace_query(user)
    create_resp = await client.post(
        "/api/v1/ask/threads",
        headers=headers,
        json={"title": "空库会话"},
        params=ws,
    )
    assert create_resp.status_code == 201
    thread_id = create_resp.json()["id"]

    status, _ = await _post_ask_thread_chat(
        client,
        headers,
        thread_id,
        {"message": "年假", "mode": "thorough"},
        workspace=ws["workspace"],
    )
    assert status == 400
    blocked = await client.post(
        f"/api/v1/ask/threads/{thread_id}/chat",
        headers=headers,
        json={"message": "年假", "mode": "thorough"},
        params=ws,
    )
    assert blocked.status_code == 400
    assert blocked.json()["detail"] == "无可用资料库"


@pytest.mark.asyncio
async def test_g3_e4_thorough_thread_chat_rate_limit_429(
    client: AsyncClient,
    register_and_login,
    low_api_limits: None,
) -> None:
    """G3-E4：精准模式 thread chat 与快速共用 chat 限流。"""
    headers, user = await register_and_login(prefix="g3-e4")
    kb = await create_test_kb(client, headers, user, name="限流精准库")
    kb_id = kb["id"]
    create_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/threads",
        headers=headers,
        json={"title": "限流会话"},
    )
    assert create_resp.status_code == 201
    thread_id = create_resp.json()["id"]

    for i in range(3):
        status, _ = await _post_kb_thread_chat(
            client,
            headers,
            kb_id,
            thread_id,
            {"message": f"问题 {i}", "mode": "thorough"},
        )
        assert status == 200

    blocked = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/threads/{thread_id}/chat",
        headers=headers,
        json={"message": "第 4 次应被限流", "mode": "thorough"},
    )
    assert blocked.status_code == 429
    assert "对话" in blocked.json()["detail"]


@pytest.mark.asyncio
async def test_g3_e5_fast_thread_chat_has_no_tool_sse(
    client: AsyncClient,
    register_and_login,
) -> None:
    """G3-E5：快速模式 thread chat 无 tool_* SSE。"""
    headers, user = await register_and_login(prefix="g3-e5")
    kb = await create_test_kb(client, headers, user, name="快速模式库")
    kb_id = kb["id"]
    create_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/threads",
        headers=headers,
        json={"title": "快速会话"},
    )
    assert create_resp.status_code == 201
    thread_id = create_resp.json()["id"]

    status, events = await _post_kb_thread_chat(
        client,
        headers,
        kb_id,
        thread_id,
        {"message": "年假政策", "mode": "fast"},
    )
    assert status == 200
    tool_events = [
        name
        for name, _ in events
        if name in {"tool_start", "tool_result", "agent_budget"}
    ]
    assert tool_events == []


@pytest.mark.asyncio
async def test_g3_e5_ask_fast_thread_chat_has_no_tool_sse(
    client: AsyncClient,
    register_and_login,
) -> None:
    """G3-E5：工作区快速模式同样无 tool_* SSE。"""
    headers, user = await register_and_login(prefix="g3-e5-ask")
    ws = workspace_query(user)
    kb = await create_test_kb(client, headers, user, name="工作区快速库")
    assert kb["id"]

    create_resp = await client.post(
        "/api/v1/ask/threads",
        headers=headers,
        json={"title": "工作区快速"},
        params=ws,
    )
    assert create_resp.status_code == 201
    thread_id = create_resp.json()["id"]

    status, events = await _post_ask_thread_chat(
        client,
        headers,
        thread_id,
        {"message": "年假", "mode": "fast"},
        workspace=ws["workspace"],
    )
    assert status == 200
    tool_events = [
        name
        for name, _ in events
        if name in {"tool_start", "tool_result", "agent_budget"}
    ]
    assert tool_events == []


@pytest.mark.asyncio
async def test_g3_thorough_kb_thread_chat_uses_agent_path(
    client: AsyncClient,
    register_and_login,
) -> None:
    """G3-2.4：库内精准走 stream_agent_kb_events（含 tool_* · agent_run_id）。"""
    headers, user = await register_and_login(prefix="g3-dispatch-kb")
    kb = await create_test_kb(client, headers, user, name="精准 dispatch 库")
    kb_id = kb["id"]
    create_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/threads",
        headers=headers,
        json={"title": "精准"},
    )
    assert create_resp.status_code == 201
    thread_id = create_resp.json()["id"]

    status, events = await _post_kb_thread_chat(
        client,
        headers,
        kb_id,
        thread_id,
        {"message": "年假", "mode": "thorough"},
    )
    assert status == 200
    assert any(name == "tool_start" for name, _ in events)
    assert any(name == "tool_result" for name, _ in events)
    assert any(name == "agent_budget" for name, _ in events)
    done = next(data for name, data in events if name == "done")
    assert done.get("agent_run_id")


@pytest.mark.asyncio
async def test_g3_thorough_ask_thread_chat_uses_agent_path(
    client: AsyncClient,
    register_and_login,
) -> None:
    """G3-2.4：工作区精准走 stream_agent_workspace_events。"""
    headers, user = await register_and_login(prefix="g3-dispatch-ask")
    ws = workspace_query(user)
    await create_test_kb(client, headers, user, name="工作区精准库")

    create_resp = await client.post(
        "/api/v1/ask/threads",
        headers=headers,
        json={"title": "工作区精准"},
        params=ws,
    )
    assert create_resp.status_code == 201
    thread_id = create_resp.json()["id"]

    status, events = await _post_ask_thread_chat(
        client,
        headers,
        thread_id,
        {"message": "年假", "mode": "thorough"},
        workspace=ws["workspace"],
    )
    assert status == 200
    assert any(name == "tool_start" for name, _ in events)
    done = next(data for name, data in events if name == "done")
    assert done.get("agent_run_id")
