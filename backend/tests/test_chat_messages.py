"""EW-D4：GET .../messages 对话历史 API 测试。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.chat_message import ChatMessage
from app.models.chat_thread import ChatThread
from app.models.enums import MessageRole, ThreadKind
from tests.conftest import create_test_kb as _create_kb
from tests.test_chat import (
    GOLDEN_MD,
    _chat,
    _create_org_member_and_login,
    _ingest_fixture,
)


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


async def _get_messages(
    client: AsyncClient,
    headers: dict[str, str],
    kb_id: str,
    *,
    limit: int | None = None,
) -> tuple[int, dict]:
    params = f"?limit={limit}" if limit is not None else ""
    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb_id}/messages{params}",
        headers=headers,
    )
    return resp.status_code, resp.json()


@pytest.mark.asyncio
async def test_get_messages_without_token_returns_401(client: AsyncClient) -> None:
    status, _ = await _get_messages(client, {}, str(uuid.uuid4()))
    assert status == 401


@pytest.mark.asyncio
async def test_get_messages_forbidden_for_other_users_kb(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers_a, user_a = await register_and_login(prefix="msg-owner")
    kb = await _create_kb(client, headers_a, user_a, name="历史隔离库")
    kb_id = kb["id"]

    headers_b, _ = await register_and_login(prefix="msg-intruder")
    status, _ = await _get_messages(client, headers_b, kb_id)
    assert status == 403


@pytest.mark.asyncio
async def test_get_messages_empty_for_new_kb(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="msg-empty")
    kb = await _create_kb(client, headers, user, name="空历史库")
    status, body = await _get_messages(client, headers, kb["id"])
    assert status == 200
    assert body["messages"] == []


@pytest.mark.asyncio
async def test_get_messages_returns_chat_history_with_citations(
    client: AsyncClient,
    register_and_login,
    upload_dir,
) -> None:
    headers, user = await register_and_login(prefix="msg-history")
    kb = await _create_kb(client, headers, user, name="历史测试库")
    kb_id = kb["id"]
    user_id = uuid.UUID(user["id"])

    await _ingest_fixture(
        kb_id=uuid.UUID(kb_id),
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    chat_status, events = await _chat(
        client,
        headers,
        kb_id,
        "员工年假有几天？",
    )
    assert chat_status == 200
    done = next(data for name, data in events if name == "done")
    assistant_id = done["message_id"]

    status, body = await _get_messages(client, headers, kb_id)
    assert status == 200
    messages = body["messages"]
    assert len(messages) == 2

    user_msg, assistant_msg = messages
    assert user_msg["role"] == "user"
    assert user_msg["content"] == "员工年假有几天？"
    assert user_msg["citations"] is None

    assert assistant_msg["role"] == "assistant"
    assert assistant_msg["id"] == assistant_id
    assert assistant_msg["content"]
    assert isinstance(assistant_msg["citations"], list)
    assert len(assistant_msg["citations"]) >= 1
    assert all(c.get("doc_name") == GOLDEN_MD.name for c in assistant_msg["citations"])


@pytest.mark.asyncio
async def test_get_messages_marks_deleted_document_citation(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """Plan-3E-3：删源文档后历史 citation 带 document_deleted。"""
    headers, user = await register_and_login(prefix="msg-cite-del")
    kb = await _create_kb(client, headers, user, name="引用失效库")
    kb_id = kb["id"]

    doc = await _ingest_fixture(
        kb_id=uuid.UUID(kb_id),
        user_id=uuid.UUID(user["id"]),
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    chat_status, _events = await _chat(
        client,
        headers,
        kb_id,
        "员工年假有几天？",
    )
    assert chat_status == 200

    delete_resp = await client.delete(
        f"/api/v1/knowledge-bases/{kb_id}/documents/{doc.id}",
        headers=headers,
    )
    assert delete_resp.status_code == 204

    status, body = await _get_messages(client, headers, kb_id)
    assert status == 200
    assert body["messages"], "chat 落库后 messages 不应为空"
    assistant = next(m for m in body["messages"] if m["role"] == "assistant")
    assert assistant["citations"]
    assert assistant["citations"][0]["source_status"] == "document_deleted"


@pytest.mark.asyncio
async def test_get_messages_only_returns_current_users_rows(
    client: AsyncClient,
    register_and_login,
    upload_dir,
) -> None:
    """TECH 5.3：同库 admin / member 各只能看自己的 messages。"""
    admin_headers, admin_user = await register_and_login(
        prefix="msg-team-admin",
        account_type="enterprise",
        org_name="历史隔离公司",
    )
    kb = await _create_kb(client, admin_headers, admin_user, name="团队历史库")
    kb_id = kb["id"]

    await _ingest_fixture(
        kb_id=uuid.UUID(kb_id),
        user_id=uuid.UUID(admin_user["id"]),
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    member_headers, _member = await _create_org_member_and_login(
        client,
        org_id=admin_user["org_id"],
    )

    assert (await _chat(client, admin_headers, kb_id, "管理员提问"))[0] == 200
    assert (await _chat(client, member_headers, kb_id, "成员提问"))[0] == 200

    admin_status, admin_body = await _get_messages(client, admin_headers, kb_id)
    member_status, member_body = await _get_messages(client, member_headers, kb_id)

    assert admin_status == 200
    assert member_status == 200

    admin_user_msgs = [m for m in admin_body["messages"] if m["role"] == "user"]
    member_user_msgs = [m for m in member_body["messages"] if m["role"] == "user"]

    assert len(admin_user_msgs) == 1
    assert admin_user_msgs[0]["content"] == "管理员提问"
    assert len(member_user_msgs) == 1
    assert member_user_msgs[0]["content"] == "成员提问"


@pytest.mark.asyncio
async def test_org_member_can_get_messages_on_team_kb(
    client: AsyncClient,
    register_and_login,
) -> None:
    admin_headers, admin_user = await register_and_login(
        prefix="msg-member-read",
        account_type="enterprise",
        org_name="成员可读历史",
    )
    kb = await _create_kb(client, admin_headers, admin_user, name="成员历史库")
    kb_id = kb["id"]

    member_headers, _ = await _create_org_member_and_login(
        client,
        org_id=admin_user["org_id"],
    )

    assert (await _chat(client, member_headers, kb_id, "成员历史问题"))[0] == 200

    status, body = await _get_messages(client, member_headers, kb_id)
    assert status == 200
    assert len(body["messages"]) == 2
    assert body["messages"][0]["content"] == "成员历史问题"


@pytest.mark.asyncio
async def test_g4_e18_messages_return_approval_final_state(
    client: AsyncClient,
    register_and_login,
) -> None:
    """G4-E18：F5 刷新后 GET messages 带 approval 终态（H4-3-B）。"""
    headers, user = await register_and_login(prefix="g4e18")
    kb = await _create_kb(client, headers, user, name="G4-E18 审批终态库")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    # 直接在 DB 插入一条带 approval_status 的 assistant 消息
    async with SessionLocal() as db:
        thread = ChatThread(
            id=uuid.uuid4(),
            thread_kind=ThreadKind.knowledge_base,
            kb_id=kb_id,
            user_id=user_id,
            title="G4-E18 测试 thread",
        )
        db.add(thread)
        await db.flush()

        approval_data = {"status": "adopted", "document_id": str(uuid.uuid4())}
        msg = ChatMessage(
            id=uuid.uuid4(),
            thread_kind=ThreadKind.knowledge_base,
            kb_id=kb_id,
            user_id=user_id,
            thread_id=thread.id,
            role=MessageRole.assistant,
            content="已生成的 FAQ 草稿",
            citations=None,
            approval_id=None,
            approval_status=approval_data,
            created_at=datetime.now(timezone.utc),
        )
        db.add(msg)
        await db.commit()

    # 通过 API 读取消息，验证 approval 字段返回
    status, body = await _get_messages(client, headers, str(kb_id))
    assert status == 200
    messages = body["messages"]
    assert len(messages) >= 1

    assistant = next((m for m in messages if m["role"] == "assistant"), None)
    assert assistant is not None
    assert assistant["approval_id"] is None
    assert assistant["approval_status"] == approval_data


@pytest.mark.asyncio
async def test_g4_e18_messages_approval_null_for_normal_chat(
    client: AsyncClient,
    register_and_login,
    upload_dir,
) -> None:
    """G4-E18：普通对话消息 approval_id/status 为 null。"""
    headers, user = await register_and_login(prefix="g4e18-null")
    kb = await _create_kb(client, headers, user, name="G4-E18 普通消息库")
    kb_id = kb["id"]
    user_id = uuid.UUID(user["id"])

    await _ingest_fixture(
        kb_id=uuid.UUID(kb_id),
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    chat_status, _events = await _chat(
        client,
        headers,
        kb_id,
        "员工年假有几天？",
    )
    assert chat_status == 200

    status, body = await _get_messages(client, headers, kb_id)
    assert status == 200
    for msg in body["messages"]:
        assert msg.get("approval_id") is None
        assert msg.get("approval_status") is None
