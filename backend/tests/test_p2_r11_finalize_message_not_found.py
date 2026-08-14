"""P2-R11：finalize_message 消息不存在时显式抛错，杜绝调用方误以为存成功。"""

from __future__ import annotations

import uuid

import pytest

from app.core.database import SessionLocal
from app.core.exceptions import NotFoundError
from app.models.chat_message import ChatMessage
from app.models.enums import MessageStatus, ThreadKind
from app.services.rag.persistence import (
    create_pending_message,
    finalize_message,
    save_chat_turn,
)
from tests.conftest import create_test_kb


@pytest.mark.asyncio
async def test_finalize_message_missing_raises_not_found(
    client,
    register_and_login,
) -> None:
    """P2-R11：message_id 不存在 → 抛 404，不再静默吞掉。"""
    headers, user = await register_and_login(prefix="p2-r11-missing")
    await create_test_kb(client, headers, user, name="p2-r11-missing")
    missing_id = uuid.uuid4()

    async with SessionLocal() as db:
        with pytest.raises(NotFoundError, match="消息不存在"):
            await finalize_message(
                db,
                missing_id,
                content="回答",
                citations=[{"chunk_id": str(uuid.uuid4())}],
            )
        assert await db.get(ChatMessage, missing_id) is None


@pytest.mark.asyncio
async def test_finalize_message_updates_pending_message(
    client,
    register_and_login,
) -> None:
    """正常路径不回退：pending assistant 消息按终态完成化并落库。"""
    headers, user = await register_and_login(prefix="p2-r11-happy")
    kb = await create_test_kb(client, headers, user, name="p2-r11-happy")
    user_id = uuid.UUID(user["id"])
    kb_id = uuid.UUID(kb["id"])
    citation = {"chunk_id": str(uuid.uuid4())}

    async with SessionLocal() as db:
        assistant_id = await save_chat_turn(
            db,
            kb_id=kb_id,
            user_id=user_id,
            user_content="问题",
            assistant_content="占位回答",
            citations=[],
        )
        assistant = await db.get(ChatMessage, assistant_id)
        assert assistant is not None
        pending = await create_pending_message(
            db,
            thread_id=assistant.thread_id,
            user_id=user_id,
            query="问题",
            thread_kind=ThreadKind.knowledge_base,
            kb_id=kb_id,
        )
        assert pending.status == MessageStatus.pending
        assert pending.content == ""

        await finalize_message(
            db,
            pending.id,
            content="正式回答",
            citations=[citation],
            status=MessageStatus.completed,
            retrieval_duration_ms=37,
        )

    async with SessionLocal() as db:
        saved = await db.get(ChatMessage, pending.id)
        assert saved is not None
        assert saved.content == "正式回答"
        assert saved.citations == [citation]
        assert saved.status == MessageStatus.completed
        assert saved.retrieval_duration_ms == 37
