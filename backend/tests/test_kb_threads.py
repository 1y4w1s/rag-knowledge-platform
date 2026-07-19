"""G2-1.3：库内 /knowledge-bases/{id}/threads CRUD + thread chat SSE · T-kb-thread-1～6。"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.rag.persistence import save_kb_chat_turn
from tests.conftest import create_test_kb as _create_kb
from tests.test_chat import GOLDEN_MD, _ingest_fixture, _parse_sse_events


async def _list_kb_threads(
    client: AsyncClient,
    headers: dict[str, str],
    kb_id: str,
) -> tuple[int, dict]:
    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb_id}/threads",
        headers=headers,
    )
    return resp.status_code, resp.json()


async def _create_kb_thread(
    client: AsyncClient,
    headers: dict[str, str],
    kb_id: str,
    *,
    title: str = "",
) -> tuple[int, dict]:
    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/threads",
        headers=headers,
        json={"title": title},
    )
    return resp.status_code, resp.json()


async def _patch_kb_thread(
    client: AsyncClient,
    headers: dict[str, str],
    kb_id: str,
    thread_id: str,
    body: dict,
) -> tuple[int, dict]:
    resp = await client.patch(
        f"/api/v1/knowledge-bases/{kb_id}/threads/{thread_id}",
        headers=headers,
        json=body,
    )
    return resp.status_code, resp.json()


async def _delete_kb_thread(
    client: AsyncClient,
    headers: dict[str, str],
    kb_id: str,
    thread_id: str,
) -> int:
    resp = await client.delete(
        f"/api/v1/knowledge-bases/{kb_id}/threads/{thread_id}",
        headers=headers,
    )
    return resp.status_code


async def _get_kb_thread_messages(
    client: AsyncClient,
    headers: dict[str, str],
    kb_id: str,
    thread_id: str,
) -> tuple[int, dict]:
    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb_id}/threads/{thread_id}/messages",
        headers=headers,
    )
    return resp.status_code, resp.json()


async def _kb_thread_chat(
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
        json={"message": message},
    ) as resp:
        body = await resp.aread()
        events = _parse_sse_events(body.decode("utf-8"))
        return resp.status_code, events


@pytest.mark.asyncio
async def test_t_kb_thread_1_post_and_list_threads_in_kb_scope(
    client: AsyncClient,
    register_and_login,
) -> None:
    """T-kb-thread-1：POST 新建空 thread · GET 列表含新 thread · 仅当前 kb + user。"""
    headers_a, user_a = await register_and_login(prefix="kb-thread-t1-a")
    headers_b, _user_b = await register_and_login(prefix="kb-thread-t1-b")

    kb_a = await _create_kb(client, headers_a, user_a, name="Thread 库 A")
    kb_b = await _create_kb(client, headers_b, _user_b, name="Thread 库 B")

    create_status, created = await _create_kb_thread(
        client, headers_a, kb_a["id"], title=""
    )
    assert create_status == 201
    assert created["title"] == ""
    assert created["status"] == "active"
    thread_id = created["id"]

    list_status, listed = await _list_kb_threads(client, headers_a, kb_a["id"])
    assert list_status == 200
    ids = {t["id"] for t in listed["threads"]}
    assert thread_id in ids

    other_kb_status, other_kb_body = await _list_kb_threads(
        client, headers_a, kb_b["id"]
    )
    assert other_kb_status == 403 or thread_id not in {
        t["id"] for t in other_kb_body.get("threads", [])
    }

    other_user_status, other_user_body = await _list_kb_threads(
        client, headers_b, kb_a["id"]
    )
    assert other_user_status == 403 or thread_id not in {
        t["id"] for t in other_user_body.get("threads", [])
    }


@pytest.mark.asyncio
async def test_t_kb_thread_2_thread_messages_isolated_by_thread_id(
    client: AsyncClient,
    register_and_login,
) -> None:
    """T-kb-thread-2：GET /threads/{id}/messages 只返回该 thread 的消息。"""
    headers, user = await register_and_login(prefix="kb-thread-t2")
    user_id = uuid.UUID(user["id"])

    kb = await _create_kb(client, headers, user, name="隔离测试库")
    kb_id = uuid.UUID(kb["id"])

    _, thread_a = await _create_kb_thread(client, headers, kb["id"], title="会话 A")
    _, thread_b = await _create_kb_thread(client, headers, kb["id"], title="会话 B")

    async with SessionLocal() as db:
        await save_kb_chat_turn(
            db,
            kb_id=kb_id,
            user_id=user_id,
            user_content="A 的问题",
            assistant_content="A 的回答",
            citations=[],
            thread_id=uuid.UUID(thread_a["id"]),
        )
        await save_kb_chat_turn(
            db,
            kb_id=kb_id,
            user_id=user_id,
            user_content="B 的问题",
            assistant_content="B 的回答",
            citations=[],
            thread_id=uuid.UUID(thread_b["id"]),
        )

    status_a, body_a = await _get_kb_thread_messages(
        client, headers, kb["id"], thread_a["id"]
    )
    assert status_a == 200
    assert [m["content"] for m in body_a["messages"]] == ["A 的问题", "A 的回答"]

    status_b, body_b = await _get_kb_thread_messages(
        client, headers, kb["id"], thread_b["id"]
    )
    assert status_b == 200
    assert [m["content"] for m in body_b["messages"]] == ["B 的问题", "B 的回答"]


@pytest.mark.asyncio
async def test_t_kb_thread_3_patch_thread_title(
    client: AsyncClient,
    register_and_login,
) -> None:
    """T-kb-thread-3：PATCH 改 title。"""
    headers, user = await register_and_login(prefix="kb-thread-t3")
    kb = await _create_kb(client, headers, user, name="PATCH 库")

    _, created = await _create_kb_thread(client, headers, kb["id"])
    thread_id = created["id"]

    patch_status, patched = await _patch_kb_thread(
        client,
        headers,
        kb["id"],
        thread_id,
        {"title": "库内第一个问题截断标题"},
    )
    assert patch_status == 200
    assert patched["title"] == "库内第一个问题截断标题"

    list_status, listed = await _list_kb_threads(client, headers, kb["id"])
    assert list_status == 200
    match = next(t for t in listed["threads"] if t["id"] == thread_id)
    assert match["title"] == "库内第一个问题截断标题"


@pytest.mark.asyncio
async def test_t_kb_thread_4_delete_archives_thread(
    client: AsyncClient,
    register_and_login,
) -> None:
    """T-kb-thread-4：DELETE 软删 · 列表不可见 · messages 404 · 重复删 404。"""
    headers, user = await register_and_login(prefix="kb-thread-t4")
    user_id = uuid.UUID(user["id"])
    kb = await _create_kb(client, headers, user, name="删除测试库")
    kb_id = uuid.UUID(kb["id"])

    _, created = await _create_kb_thread(
        client, headers, kb["id"], title="待删除"
    )
    thread_id = created["id"]

    async with SessionLocal() as db:
        await save_kb_chat_turn(
            db,
            kb_id=kb_id,
            user_id=user_id,
            user_content="待删消息",
            assistant_content="待删回答",
            citations=[],
            thread_id=uuid.UUID(thread_id),
        )

    delete_status = await _delete_kb_thread(client, headers, kb["id"], thread_id)
    assert delete_status == 204

    list_status, listed = await _list_kb_threads(client, headers, kb["id"])
    assert list_status == 200
    assert thread_id not in {t["id"] for t in listed["threads"]}

    msg_status, _ = await _get_kb_thread_messages(
        client, headers, kb["id"], thread_id
    )
    assert msg_status == 404

    again_status = await _delete_kb_thread(client, headers, kb["id"], thread_id)
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
async def test_t_kb_thread_5_thread_chat_saves_to_explicit_thread_only(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    rerank_mock: None,
) -> None:
    """T-kb-thread-5：POST /threads/{id}/chat SSE · 消息只进指定 thread。"""
    headers, user = await register_and_login(prefix="kb-thread-t5")
    user_id = uuid.UUID(user["id"])

    kb = await _create_kb(client, headers, user, name="KB Thread Chat 库")
    await _ingest_fixture(
        kb_id=uuid.UUID(kb["id"]),
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    _, thread_a = await _create_kb_thread(client, headers, kb["id"], title="会话 A")
    _, thread_b = await _create_kb_thread(client, headers, kb["id"], title="会话 B")

    status, events = await _kb_thread_chat(
        client,
        headers,
        kb["id"],
        thread_a["id"],
        "员工年假有多少天",
    )
    assert status == 200
    done = next(data for name, data in events if name == "done")
    assert done.get("message_id")

    status_a, body_a = await _get_kb_thread_messages(
        client, headers, kb["id"], thread_a["id"]
    )
    assert status_a == 200
    assert len(body_a["messages"]) == 2
    assert body_a["messages"][0]["content"] == "员工年假有多少天"

    status_b, body_b = await _get_kb_thread_messages(
        client, headers, kb["id"], thread_b["id"]
    )
    assert status_b == 200
    assert body_b["messages"] == []


@pytest.mark.asyncio
async def test_t_kb_thread_6_archived_thread_chat_returns_404(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    rerank_mock: None,
) -> None:
    """T-kb-thread-6：已归档 thread · POST chat → 404。"""
    headers, user = await register_and_login(prefix="kb-thread-t6")
    user_id = uuid.UUID(user["id"])

    kb = await _create_kb(client, headers, user, name="KB 归档 Chat 库")
    await _ingest_fixture(
        kb_id=uuid.UUID(kb["id"]),
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    _, created = await _create_kb_thread(client, headers, kb["id"], title="待归档")
    thread_id = created["id"]

    delete_status = await _delete_kb_thread(client, headers, kb["id"], thread_id)
    assert delete_status == 204

    status, _ = await _kb_thread_chat(
        client,
        headers,
        kb["id"],
        thread_id,
        "任意问题",
    )
    assert status == 404


@pytest.mark.asyncio
async def test_t_kb_thread_7_first_message_autotitles_empty_thread(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    rerank_mock: None,
) -> None:
    """T-kb-thread-7：库内首问后 title 为空 thread 自动截断为首问前 40 字。"""
    headers, user = await register_and_login(prefix="kb-thread-t7")
    user_id = uuid.UUID(user["id"])

    kb = await _create_kb(client, headers, user, name="KB 自动标题库")
    await _ingest_fixture(
        kb_id=uuid.UUID(kb["id"]),
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    _, created = await _create_kb_thread(client, headers, kb["id"], title="")
    thread_id = created["id"]
    question = "员工年假有多少天？"

    status, events = await _kb_thread_chat(
        client,
        headers,
        kb["id"],
        thread_id,
        question,
    )
    assert status == 200
    done = next(data for name, data in events if name == "done")
    assert done.get("message_id")

    list_status, listed = await _list_kb_threads(client, headers, kb["id"])
    assert list_status == 200
    thread = next(item for item in listed["threads"] if item["id"] == thread_id)
    assert thread["title"] == question
