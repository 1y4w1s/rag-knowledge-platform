"""G2-1.4：对话 thread 审计钩子 · chat.thread_created / message_sent / archived。"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.config import settings
from tests.conftest import create_test_kb as _create_kb
from tests.fixtures.audit_events import _count_audit_logs, _latest_audit_log
from tests.test_chat import GOLDEN_MD, _ingest_fixture, _parse_sse_events


async def _create_ask_thread(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    title: str = "审计会话",
) -> tuple[int, dict]:
    resp = await client.post(
        "/api/v1/ask/threads",
        headers=headers,
        json={"title": title},
        params={"workspace": "personal"},
    )
    return resp.status_code, resp.json()


async def _delete_ask_thread(
    client: AsyncClient,
    headers: dict[str, str],
    thread_id: str,
) -> int:
    resp = await client.delete(
        f"/api/v1/ask/threads/{thread_id}",
        headers=headers,
        params={"workspace": "personal"},
    )
    return resp.status_code


async def _ask_thread_chat(
    client: AsyncClient,
    headers: dict[str, str],
    thread_id: str,
    message: str,
) -> tuple[int, list[tuple[str, dict]]]:
    async with client.stream(
        "POST",
        f"/api/v1/ask/threads/{thread_id}/chat",
        headers=headers,
        json={"message": message},
        params={"workspace": "personal"},
    ) as resp:
        body = await resp.aread()
        events = _parse_sse_events(body.decode("utf-8"))
        return resp.status_code, events


async def _create_kb_thread(
    client: AsyncClient,
    headers: dict[str, str],
    kb_id: str,
    *,
    title: str = "库内审计会话",
) -> tuple[int, dict]:
    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/threads",
        headers=headers,
        json={"title": title},
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


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def rerank_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rerank_enabled", True)
    monkeypatch.setattr(settings, "rerank_provider", "mock")


@pytest.mark.asyncio
async def test_create_ask_thread_writes_audit_log(
    client: AsyncClient,
    register_and_login,
) -> None:
    """POST /ask/threads → chat.thread_created。"""
    headers, user = await register_and_login(prefix="chat-audit-create")
    before = await _count_audit_logs(action="chat.thread_created")

    status, body = await _create_ask_thread(client, headers, title="新建审计")
    assert status == 201

    after = await _count_audit_logs(action="chat.thread_created")
    assert after - before == 1

    latest = await _latest_audit_log(action="chat.thread_created")
    assert latest is not None
    assert latest.actor_user_id == uuid.UUID(user["id"])
    assert latest.resource_type == "chat_thread"
    assert latest.resource_id == uuid.UUID(body["id"])
    assert latest.details is not None
    assert latest.details["thread_id"] == body["id"]
    assert latest.details["thread_kind"] == "workspace"
    assert latest.details["workspace_kind"] == "personal"
    assert latest.details["kb_id"] is None


@pytest.mark.asyncio
async def test_delete_ask_thread_writes_audit_log(
    client: AsyncClient,
    register_and_login,
) -> None:
    """DELETE /ask/threads/{id} → chat.thread_archived。"""
    headers, user = await register_and_login(prefix="chat-audit-archive")
    _, created = await _create_ask_thread(client, headers, title="待归档")
    thread_id = created["id"]

    before = await _count_audit_logs(action="chat.thread_archived")
    assert await _delete_ask_thread(client, headers, thread_id) == 204
    after = await _count_audit_logs(action="chat.thread_archived")
    assert after - before == 1

    latest = await _latest_audit_log(action="chat.thread_archived")
    assert latest is not None
    assert latest.actor_user_id == uuid.UUID(user["id"])
    assert latest.resource_id == uuid.UUID(thread_id)
    assert latest.details == {
        "thread_id": thread_id,
        "thread_kind": "workspace",
    }


@pytest.mark.asyncio
async def test_ask_thread_chat_writes_message_sent_audit(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    rerank_mock: None,
) -> None:
    """POST /ask/threads/{id}/chat → chat.message_sent（不含问题全文）。"""
    headers, user = await register_and_login(prefix="chat-audit-msg")
    user_id = uuid.UUID(user["id"])

    kb = await _create_kb(
        client, headers, user, name="Ask Audit 库", workspace_kind="personal"
    )
    await _ingest_fixture(
        kb_id=uuid.UUID(kb["id"]),
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    _, created = await _create_ask_thread(client, headers, title="问答审计")
    thread_id = created["id"]
    question = "员工年假有多少天"

    before = await _count_audit_logs(action="chat.message_sent")
    status, events = await _ask_thread_chat(client, headers, thread_id, question)
    assert status == 200
    done = next(data for name, data in events if name == "done")
    after = await _count_audit_logs(action="chat.message_sent")
    assert after - before == 1

    latest = await _latest_audit_log(action="chat.message_sent")
    assert latest is not None
    assert latest.actor_user_id == user_id
    assert latest.resource_type == "chat_message"
    assert latest.resource_id == uuid.UUID(done["message_id"])
    assert latest.details is not None
    assert latest.details["thread_id"] == thread_id
    assert latest.details["thread_kind"] == "workspace"
    assert latest.details["message_id"] == done["message_id"]
    assert isinstance(latest.details["citation_count"], int)
    assert latest.details["citation_count"] >= 0
    assert isinstance(latest.details["retrieval_ms"], int)
    assert question not in str(latest.details)


@pytest.mark.asyncio
async def test_create_kb_thread_writes_audit_log(
    client: AsyncClient,
    register_and_login,
) -> None:
    """POST /knowledge-bases/{id}/threads → chat.thread_created。"""
    headers, user = await register_and_login(prefix="kb-chat-audit-create")
    kb = await _create_kb(
        client, headers, user, name="KB Audit 库", workspace_kind="personal"
    )

    before = await _count_audit_logs(action="chat.thread_created")
    status, body = await _create_kb_thread(client, headers, kb["id"], title="库内新建")
    assert status == 201

    after = await _count_audit_logs(action="chat.thread_created")
    assert after - before == 1

    latest = await _latest_audit_log(action="chat.thread_created")
    assert latest is not None
    assert latest.actor_user_id == uuid.UUID(user["id"])
    assert latest.kb_id == uuid.UUID(kb["id"])
    assert latest.details is not None
    assert latest.details["thread_kind"] == "knowledge_base"
    assert latest.details["kb_id"] == kb["id"]
    assert latest.details["thread_id"] == body["id"]


@pytest.mark.asyncio
async def test_delete_kb_thread_writes_audit_log(
    client: AsyncClient,
    register_and_login,
) -> None:
    """DELETE /knowledge-bases/{id}/threads/{id} → chat.thread_archived。"""
    headers, user = await register_and_login(prefix="kb-chat-audit-archive")
    kb = await _create_kb(
        client, headers, user, name="KB Archive 库", workspace_kind="personal"
    )
    _, created = await _create_kb_thread(client, headers, kb["id"], title="待删")
    thread_id = created["id"]

    before = await _count_audit_logs(action="chat.thread_archived")
    assert await _delete_kb_thread(client, headers, kb["id"], thread_id) == 204
    after = await _count_audit_logs(action="chat.thread_archived")
    assert after - before == 1

    latest = await _latest_audit_log(action="chat.thread_archived")
    assert latest is not None
    assert latest.kb_id == uuid.UUID(kb["id"])
    assert latest.details == {
        "thread_id": thread_id,
        "thread_kind": "knowledge_base",
    }


@pytest.mark.asyncio
async def test_kb_thread_chat_writes_message_sent_audit(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    rerank_mock: None,
) -> None:
    """POST /knowledge-bases/{id}/threads/{id}/chat → chat.message_sent。"""
    headers, user = await register_and_login(prefix="kb-chat-audit-msg")
    user_id = uuid.UUID(user["id"])

    kb = await _create_kb(
        client, headers, user, name="KB Msg Audit 库", workspace_kind="personal"
    )
    await _ingest_fixture(
        kb_id=uuid.UUID(kb["id"]),
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    _, created = await _create_kb_thread(client, headers, kb["id"], title="库内问答")
    thread_id = created["id"]
    question = "员工年假有多少天"

    before = await _count_audit_logs(action="chat.message_sent")
    status, events = await _kb_thread_chat(
        client, headers, kb["id"], thread_id, question
    )
    assert status == 200
    done = next(data for name, data in events if name == "done")
    after = await _count_audit_logs(action="chat.message_sent")
    assert after - before == 1

    latest = await _latest_audit_log(action="chat.message_sent")
    assert latest is not None
    assert latest.kb_id == uuid.UUID(kb["id"])
    assert latest.details is not None
    assert latest.details["thread_id"] == thread_id
    assert latest.details["thread_kind"] == "knowledge_base"
    assert latest.details["message_id"] == done["message_id"]
    assert question not in str(latest.details)
