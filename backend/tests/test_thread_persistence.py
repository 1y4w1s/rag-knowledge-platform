"""G2-0.3：persistence 按 thread 读写 · thread_id NOT NULL。"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.chat_message import ChatMessage
from app.models.chat_thread import ChatThread
from app.models.enums import MessageRole, ThreadKind, ThreadStatus
from app.services.rag.persistence import (
    list_chat_messages,
    list_thread_messages,
    list_workspace_chat_messages,
    save_chat_turn,
    save_workspace_chat_turn,
)
from app.services.workspace.scope import WorkspaceKind
from tests.conftest import create_test_kb


@pytest.mark.asyncio
async def test_save_kb_chat_turn_sets_thread_id(
    client,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="thread-kb")
    kb = await create_test_kb(client, headers, user, name="thread-kb")

    async with SessionLocal() as db:
        assistant_id = await save_chat_turn(
            db,
            kb_id=uuid.UUID(kb["id"]),
            user_id=uuid.UUID(user["id"]),
            user_content="库内问题",
            assistant_content="库内回答",
            citations=[],
        )

        assistant = await db.get(ChatMessage, assistant_id)
        assert assistant is not None
        assert assistant.thread_id is not None

        user_msg = (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.thread_id == assistant.thread_id)
                .where(ChatMessage.role == MessageRole.user)
            )
        ).scalar_one()
        assert user_msg.thread_id == assistant.thread_id

        thread = await db.get(ChatThread, assistant.thread_id)
        assert thread is not None
        assert thread.thread_kind == ThreadKind.knowledge_base
        assert thread.kb_id == uuid.UUID(kb["id"])
        assert thread.user_id == uuid.UUID(user["id"])
        assert thread.status == ThreadStatus.active
        assert thread.last_message_at is not None


@pytest.mark.asyncio
async def test_save_workspace_chat_turn_sets_thread_id(
    register_and_login,
) -> None:
    _, user = await register_and_login(prefix="thread-ws")

    async with SessionLocal() as db:
        assistant_id = await save_workspace_chat_turn(
            db,
            user_id=uuid.UUID(user["id"]),
            workspace_kind=WorkspaceKind.personal,
            workspace_org_id=None,
            department_id=None,
            user_content="工作区问题",
            assistant_content="工作区回答",
            citations=[],
        )

        assistant = await db.get(ChatMessage, assistant_id)
        assert assistant is not None
        assert assistant.thread_id is not None

        thread = await db.get(ChatThread, assistant.thread_id)
        assert thread is not None
        assert thread.thread_kind == ThreadKind.workspace
        assert thread.workspace_kind == WorkspaceKind.personal.value
        assert thread.workspace_org_id is None


@pytest.mark.asyncio
async def test_save_reuses_active_thread_in_same_scope(
    client,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="thread-reuse")
    kb = await create_test_kb(client, headers, user, name="thread-reuse")

    async with SessionLocal() as db:
        first_id = await save_chat_turn(
            db,
            kb_id=uuid.UUID(kb["id"]),
            user_id=uuid.UUID(user["id"]),
            user_content="第一轮",
            assistant_content="回答一",
            citations=[],
        )
        second_id = await save_chat_turn(
            db,
            kb_id=uuid.UUID(kb["id"]),
            user_id=uuid.UUID(user["id"]),
            user_content="第二轮",
            assistant_content="回答二",
            citations=[],
        )

        first = await db.get(ChatMessage, first_id)
        second = await db.get(ChatMessage, second_id)
        assert first is not None and second is not None
        assert first.thread_id == second.thread_id


@pytest.mark.asyncio
async def test_list_thread_messages_returns_chronological_turns(
    client,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="thread-list")
    kb = await create_test_kb(client, headers, user, name="thread-list")

    async with SessionLocal() as db:
        await save_chat_turn(
            db,
            kb_id=uuid.UUID(kb["id"]),
            user_id=uuid.UUID(user["id"]),
            user_content="问题 A",
            assistant_content="回答 A",
            citations=[],
        )
        await save_chat_turn(
            db,
            kb_id=uuid.UUID(kb["id"]),
            user_id=uuid.UUID(user["id"]),
            user_content="问题 B",
            assistant_content="回答 B",
            citations=[],
        )

        thread_id = (
            await db.execute(
                select(ChatThread.id)
                .where(ChatThread.kb_id == uuid.UUID(kb["id"]))
                .where(ChatThread.user_id == uuid.UUID(user["id"]))
            )
        ).scalar_one()

        by_thread = await list_thread_messages(
            db,
            thread_id=thread_id,
            user_id=uuid.UUID(user["id"]),
        )
        by_scope = await list_chat_messages(
            db,
            kb_id=uuid.UUID(kb["id"]),
            user_id=uuid.UUID(user["id"]),
        )

    assert len(by_thread) == 4
    assert [m.content for m in by_thread] == ["问题 A", "回答 A", "问题 B", "回答 B"]
    assert [m.id for m in by_thread] == [m.id for m in by_scope]


@pytest.mark.asyncio
async def test_list_workspace_messages_joins_threads(
    register_and_login,
) -> None:
    _, user = await register_and_login(prefix="thread-ws-list")

    async with SessionLocal() as db:
        await save_workspace_chat_turn(
            db,
            user_id=uuid.UUID(user["id"]),
            workspace_kind=WorkspaceKind.personal,
            workspace_org_id=None,
            department_id=None,
            user_content="ws 问题",
            assistant_content="ws 回答",
            citations=[],
        )

        rows = await list_workspace_chat_messages(
            db,
            user_id=uuid.UUID(user["id"]),
            workspace_kind=WorkspaceKind.personal,
            workspace_org_id=None,
            department_id=None,
        )

    assert len(rows) == 2
    assert rows[0].role == MessageRole.user
    assert rows[0].thread_id == rows[1].thread_id
