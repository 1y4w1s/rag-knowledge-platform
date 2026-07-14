"""G3-0.3：ChatRequest.mode 默认 fast · schema 422 · OpenAPI 契约。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from app.models.enums import AgentMode
from app.schemas.chat import ChatRequest
from tests.conftest import create_test_kb, workspace_query


def test_chat_request_defaults_mode_fast() -> None:
    req = ChatRequest(message="hello")
    assert req.mode == AgentMode.fast


def test_chat_request_accepts_thorough() -> None:
    req = ChatRequest(message="hello", mode=AgentMode.thorough)
    assert req.mode == AgentMode.thorough


def test_chat_request_rejects_empty_message() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(message="")


def test_chat_request_accepts_mode_edit() -> None:
    """G4-E20：mode=edit 合法（G4-0.2 枚举扩展后）。"""
    req = ChatRequest(message="hello", mode=AgentMode.edit)
    assert req.mode == AgentMode.edit


def test_chat_request_rejects_invalid_mode() -> None:
    """G4-E20：非法 mode → 422（Pydantic 枚举校验）。"""
    with pytest.raises(ValidationError):
        ChatRequest(message="hello", mode="invalid")


@pytest.mark.asyncio
async def test_openapi_chat_request_mode_default_fast(client: AsyncClient) -> None:
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    components = resp.json()["components"]["schemas"]
    chat_request = components["ChatRequest"]
    mode_prop = chat_request["properties"]["mode"]
    assert mode_prop["default"] == "fast"
    assert mode_prop["$ref"] == "#/components/schemas/AgentMode"
    agent_mode = components["AgentMode"]
    assert set(agent_mode["enum"]) == {"fast", "thorough", "edit"}
    assert "mode" not in chat_request["required"]


async def _post_ask_thread_chat_raw(
    client: AsyncClient,
    headers: dict[str, str],
    thread_id: str,
    payload: dict,
    *,
    workspace: str,
) -> int:
    async with client.stream(
        "POST",
        f"/api/v1/ask/threads/{thread_id}/chat",
        headers=headers,
        json=payload,
        params={"workspace": workspace},
    ) as resp:
        await resp.aread()
        return resp.status_code


@pytest.mark.asyncio
async def test_e_empty_thread_chat_returns_422(
    client: AsyncClient,
    register_and_login,
) -> None:
    """E-empty：空 message → 422（schema min_length=1）。"""
    headers, user = await register_and_login(prefix="g3-empty")
    ws = workspace_query(user)
    create_resp = await client.post(
        "/api/v1/ask/threads",
        headers=headers,
        json={"title": "t"},
        params=ws,
    )
    assert create_resp.status_code == 201
    thread_id = create_resp.json()["id"]

    status = await _post_ask_thread_chat_raw(
        client,
        headers,
        thread_id,
        {"message": ""},
        workspace=ws["workspace"],
    )
    assert status == 422


@pytest.mark.asyncio
async def test_g4_e20_mode_edit_accepted(
    client: AsyncClient,
    register_and_login,
) -> None:
    """G4-E20：mode=edit 合法（schema 通过，不 422；无 KB 时业务 400）。"""
    headers, user = await register_and_login(prefix="g4-edit")
    ws = workspace_query(user)
    create_resp = await client.post(
        "/api/v1/ask/threads",
        headers=headers,
        json={"title": "t"},
        params=ws,
    )
    assert create_resp.status_code == 201
    thread_id = create_resp.json()["id"]

    status = await _post_ask_thread_chat_raw(
        client,
        headers,
        thread_id,
        {"message": "hello", "mode": "edit"},
        workspace=ws["workspace"],
    )
    # Schema 通过（非 422），无可见 KB 时业务层 400
    assert status != 422


@pytest.mark.asyncio
async def test_kb_thread_chat_omitted_mode_defaults_fast_path(
    client: AsyncClient,
    register_and_login,
) -> None:
    """不传 mode 时 schema 默认 fast；请求可进入 handler（非 422）。"""
    headers, user = await register_and_login(prefix="g3-default")
    kb = await create_test_kb(client, headers, user, name="g3-mode-default")
    kb_id = kb["id"]
    create_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/threads",
        headers=headers,
        json={"title": "t"},
    )
    assert create_resp.status_code == 201
    thread_id = create_resp.json()["id"]

    async with client.stream(
        "POST",
        f"/api/v1/knowledge-bases/{kb_id}/threads/{thread_id}/chat",
        headers=headers,
        json={"message": "年假政策"},
    ) as resp:
        await resp.aread()
        assert resp.status_code == 200
