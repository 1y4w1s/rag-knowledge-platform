"""G2-1.1～1.2：工作区 /ask/threads CRUD + thread chat SSE · T-thread-1～5。"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.rag.persistence import save_workspace_chat_turn
from app.services.workspace.scope import WorkspaceKind
from tests.conftest import create_test_kb as _create_kb
from tests.test_chat import GOLDEN_MD, _ingest_fixture, _parse_sse_events


def _workspace_params(workspace: str, department_id: str | None = None) -> dict[str, str]:
    params: dict[str, str] = {"workspace": workspace}
    if department_id is not None:
        params["department_id"] = department_id
    return params


async def _list_threads(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    workspace: str,
    department_id: str | None = None,
) -> tuple[int, dict]:
    resp = await client.get(
        "/api/v1/ask/threads",
        headers=headers,
        params=_workspace_params(workspace, department_id),
    )
    return resp.status_code, resp.json()


async def _create_thread(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    workspace: str,
    title: str = "",
    department_id: str | None = None,
) -> tuple[int, dict]:
    resp = await client.post(
        "/api/v1/ask/threads",
        headers=headers,
        json={"title": title},
        params=_workspace_params(workspace, department_id),
    )
    return resp.status_code, resp.json()


async def _patch_thread(
    client: AsyncClient,
    headers: dict[str, str],
    thread_id: str,
    *,
    workspace: str,
    body: dict,
    department_id: str | None = None,
) -> tuple[int, dict]:
    resp = await client.patch(
        f"/api/v1/ask/threads/{thread_id}",
        headers=headers,
        json=body,
        params=_workspace_params(workspace, department_id),
    )
    return resp.status_code, resp.json()


async def _delete_thread(
    client: AsyncClient,
    headers: dict[str, str],
    thread_id: str,
    *,
    workspace: str,
    department_id: str | None = None,
) -> int:
    resp = await client.delete(
        f"/api/v1/ask/threads/{thread_id}",
        headers=headers,
        params=_workspace_params(workspace, department_id),
    )
    return resp.status_code


async def _get_thread_messages(
    client: AsyncClient,
    headers: dict[str, str],
    thread_id: str,
    *,
    workspace: str,
    department_id: str | None = None,
) -> tuple[int, dict]:
    resp = await client.get(
        f"/api/v1/ask/threads/{thread_id}/messages",
        headers=headers,
        params=_workspace_params(workspace, department_id),
    )
    return resp.status_code, resp.json()


async def _ask_thread_chat(
    client: AsyncClient,
    headers: dict[str, str],
    thread_id: str,
    message: str,
    *,
    workspace: str,
    department_id: str | None = None,
) -> tuple[int, list[tuple[str, dict]]]:
    async with client.stream(
        "POST",
        f"/api/v1/ask/threads/{thread_id}/chat",
        headers=headers,
        json={"message": message},
        params=_workspace_params(workspace, department_id),
    ) as resp:
        body = await resp.aread()
        events = _parse_sse_events(body.decode("utf-8"))
        return resp.status_code, events


@pytest.mark.asyncio
async def test_t_thread_1_post_and_list_threads_in_workspace_scope(
    client: AsyncClient,
    register_and_login,
) -> None:
    """T-thread-1：POST 新建空 thread · GET 列表含新 thread · 仅当前 workspace scope。"""
    headers_a, user_a = await register_and_login(prefix="thread-t1-a")
    headers_b, _user_b = await register_and_login(prefix="thread-t1-b")

    create_status, created = await _create_thread(
        client, headers_a, workspace="personal", title=""
    )
    assert create_status == 201
    assert created["title"] == ""
    assert created["status"] == "active"
    thread_id = created["id"]

    list_status, listed = await _list_threads(client, headers_a, workspace="personal")
    assert list_status == 200
    ids = {t["id"] for t in listed["threads"]}
    assert thread_id in ids

    other_status, other_body = await _list_threads(client, headers_b, workspace="personal")
    assert other_status == 200
    assert thread_id not in {t["id"] for t in other_body["threads"]}


@pytest.mark.asyncio
async def test_t_thread_2_thread_messages_isolated_by_thread_id(
    client: AsyncClient,
    register_and_login,
) -> None:
    """T-thread-2：GET /threads/{id}/messages 只返回该 thread 的消息。"""
    headers, user = await register_and_login(prefix="thread-t2")
    user_id = uuid.UUID(user["id"])

    _, thread_a = await _create_thread(client, headers, workspace="personal", title="会话 A")
    _, thread_b = await _create_thread(client, headers, workspace="personal", title="会话 B")

    async with SessionLocal() as db:
        await save_workspace_chat_turn(
            db,
            user_id=user_id,
            workspace_kind=WorkspaceKind.personal,
            workspace_org_id=None,
            department_id=None,
            user_content="A 的问题",
            assistant_content="A 的回答",
            citations=[],
            thread_id=uuid.UUID(thread_a["id"]),
        )
        await save_workspace_chat_turn(
            db,
            user_id=user_id,
            workspace_kind=WorkspaceKind.personal,
            workspace_org_id=None,
            department_id=None,
            user_content="B 的问题",
            assistant_content="B 的回答",
            citations=[],
            thread_id=uuid.UUID(thread_b["id"]),
        )

    status_a, body_a = await _get_thread_messages(
        client, headers, thread_a["id"], workspace="personal"
    )
    assert status_a == 200
    assert [m["content"] for m in body_a["messages"]] == ["A 的问题", "A 的回答"]

    status_b, body_b = await _get_thread_messages(
        client, headers, thread_b["id"], workspace="personal"
    )
    assert status_b == 200
    assert [m["content"] for m in body_b["messages"]] == ["B 的问题", "B 的回答"]


@pytest.mark.asyncio
async def test_t_thread_3_patch_thread_title(
    client: AsyncClient,
    register_and_login,
) -> None:
    """T-thread-3：PATCH 改 title。"""
    headers, _user = await register_and_login(prefix="thread-t3")

    _, created = await _create_thread(client, headers, workspace="personal")
    thread_id = created["id"]

    patch_status, patched = await _patch_thread(
        client,
        headers,
        thread_id,
        workspace="personal",
        body={"title": "我的第一个问题截断标题"},
    )
    assert patch_status == 200
    assert patched["title"] == "我的第一个问题截断标题"

    list_status, listed = await _list_threads(client, headers, workspace="personal")
    assert list_status == 200
    match = next(t for t in listed["threads"] if t["id"] == thread_id)
    assert match["title"] == "我的第一个问题截断标题"


@pytest.mark.asyncio
async def test_t_thread_4_delete_archives_thread(
    client: AsyncClient,
    register_and_login,
) -> None:
    """T-thread-4：DELETE 软删 · 列表不可见 · messages 404 · 重复删 404。"""
    headers, user = await register_and_login(prefix="thread-t4")
    user_id = uuid.UUID(user["id"])

    _, created = await _create_thread(
        client, headers, workspace="personal", title="待删除"
    )
    thread_id = created["id"]

    async with SessionLocal() as db:
        await save_workspace_chat_turn(
            db,
            user_id=user_id,
            workspace_kind=WorkspaceKind.personal,
            workspace_org_id=None,
            department_id=None,
            user_content="待删消息",
            assistant_content="待删回答",
            citations=[],
            thread_id=uuid.UUID(thread_id),
        )

    delete_status = await _delete_thread(
        client, headers, thread_id, workspace="personal"
    )
    assert delete_status == 204

    list_status, listed = await _list_threads(client, headers, workspace="personal")
    assert list_status == 200
    assert thread_id not in {t["id"] for t in listed["threads"]}

    msg_status, _ = await _get_thread_messages(
        client, headers, thread_id, workspace="personal"
    )
    assert msg_status == 404

    again_status = await _delete_thread(
        client, headers, thread_id, workspace="personal"
    )
    assert again_status == 404


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def rerank_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rerank_enabled", True)
    monkeypatch.setattr(settings, "rerank_provider", "mock")


@pytest.mark.asyncio
async def test_t_thread_5_thread_chat_saves_to_explicit_thread_only(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    rerank_mock: None,
) -> None:
    """T-thread-5：POST /threads/{id}/chat SSE · 消息只进指定 thread。"""
    headers, user = await register_and_login(prefix="thread-t5")
    user_id = uuid.UUID(user["id"])

    kb = await _create_kb(client, headers, user, name="Thread Chat 库", workspace_kind="personal")
    await _ingest_fixture(
        kb_id=uuid.UUID(kb["id"]),
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    _, thread_a = await _create_thread(client, headers, workspace="personal", title="会话 A")
    _, thread_b = await _create_thread(client, headers, workspace="personal", title="会话 B")

    status, events = await _ask_thread_chat(
        client,
        headers,
        thread_a["id"],
        "员工年假有多少天",
        workspace="personal",
    )
    assert status == 200
    done = next(data for name, data in events if name == "done")
    assert done.get("message_id")

    status_a, body_a = await _get_thread_messages(
        client, headers, thread_a["id"], workspace="personal"
    )
    assert status_a == 200
    assert len(body_a["messages"]) == 2
    assert body_a["messages"][0]["content"] == "员工年假有多少天"

    status_b, body_b = await _get_thread_messages(
        client, headers, thread_b["id"], workspace="personal"
    )
    assert status_b == 200
    assert body_b["messages"] == []


@pytest.mark.asyncio
async def test_t_thread_6_archived_thread_chat_returns_404(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    rerank_mock: None,
) -> None:
    """T-thread-6：已归档 thread · POST chat → 404。"""
    headers, user = await register_and_login(prefix="thread-t6")
    user_id = uuid.UUID(user["id"])

    kb = await _create_kb(client, headers, user, name="归档 Chat 库", workspace_kind="personal")
    await _ingest_fixture(
        kb_id=uuid.UUID(kb["id"]),
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    _, created = await _create_thread(client, headers, workspace="personal", title="待归档")
    thread_id = created["id"]

    delete_status = await _delete_thread(client, headers, thread_id, workspace="personal")
    assert delete_status == 204

    status, _ = await _ask_thread_chat(
        client,
        headers,
        thread_id,
        "任意问题",
        workspace="personal",
    )
    assert status == 404


@pytest.mark.asyncio
async def test_t_thread_7_first_message_autotitles_empty_thread(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    rerank_mock: None,
) -> None:
    """T-thread-7：首问后 title 为空 thread 自动截断为首问前 40 字。"""
    headers, user = await register_and_login(prefix="thread-t7")
    user_id = uuid.UUID(user["id"])

    kb = await _create_kb(client, headers, user, name="自动标题库", workspace_kind="personal")
    await _ingest_fixture(
        kb_id=uuid.UUID(kb["id"]),
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    _, created = await _create_thread(client, headers, workspace="personal", title="")
    thread_id = created["id"]
    question = "员工年假有多少天？"

    status, events = await _ask_thread_chat(
        client,
        headers,
        thread_id,
        question,
        workspace="personal",
    )
    assert status == 200
    done = next(data for name, data in events if name == "done")
    assert done.get("message_id")

    list_status, listed = await _list_threads(client, headers, workspace="personal")
    assert list_status == 200
    thread = next(item for item in listed["threads"] if item["id"] == thread_id)
    assert thread["title"] == question


@pytest.mark.asyncio
async def test_t_thread_8_first_message_does_not_overwrite_existing_title(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    rerank_mock: None,
) -> None:
    """T-thread-8：已有 title 的 thread · 发消息不改标题。"""
    headers, user = await register_and_login(prefix="thread-t8")
    user_id = uuid.UUID(user["id"])

    kb = await _create_kb(client, headers, user, name="保留标题库", workspace_kind="personal")
    await _ingest_fixture(
        kb_id=uuid.UUID(kb["id"]),
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    custom_title = "我的固定标题"
    _, created = await _create_thread(
        client, headers, workspace="personal", title=custom_title
    )
    thread_id = created["id"]

    status, _ = await _ask_thread_chat(
        client,
        headers,
        thread_id,
        "任意问题",
        workspace="personal",
    )
    assert status == 200

    list_status, listed = await _list_threads(client, headers, workspace="personal")
    assert list_status == 200
    thread = next(item for item in listed["threads"] if item["id"] == thread_id)
    assert thread["title"] == custom_title
