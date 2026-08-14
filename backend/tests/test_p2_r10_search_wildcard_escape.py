"""P2-R10：消息搜索的 % / _ 按字面匹配，杜绝 LIKE 通配符注入。"""

from __future__ import annotations

import uuid

import pytest

from app.core.database import SessionLocal
from app.models.chat_message import ChatMessage
from app.models.chat_thread import ChatThread
from app.services.rag.persistence import save_chat_turn, search_chat_messages
from tests.conftest import create_test_kb


async def _seed_turn(
    db,
    *,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    user_content: str,
    assistant_content: str,
) -> uuid.UUID:
    return await save_chat_turn(
        db,
        kb_id=kb_id,
        user_id=user_id,
        user_content=user_content,
        assistant_content=assistant_content,
        citations=[],
    )


async def _set_thread_title(
    db,
    assistant_message_id: uuid.UUID,
    title: str,
) -> None:
    assistant = await db.get(ChatMessage, assistant_message_id)
    assert assistant is not None
    thread = await db.get(ChatThread, assistant.thread_id)
    assert thread is not None
    thread.title = title
    await db.commit()


def _hit_contents(items: list[tuple[ChatMessage, ChatThread]]) -> list[str]:
    return [message.content for message, _thread in items]


def _hit_titles(items: list[tuple[ChatMessage, ChatThread]]) -> list[str]:
    return [thread.title for _message, thread in items]


@pytest.mark.asyncio
async def test_search_percent_matches_literal_content_only(
    client,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="p2-r10-pct-content")
    kb_hit = await create_test_kb(client, headers, user, name="p2-r10-pct-hit")
    kb_miss = await create_test_kb(client, headers, user, name="p2-r10-pct-miss")
    user_id = uuid.UUID(user["id"])

    async with SessionLocal() as db:
        await _seed_turn(
            db,
            kb_id=uuid.UUID(kb_hit["id"]),
            user_id=user_id,
            user_content="请更新进度",
            assistant_content="本周目标 100% 完成",
        )
        await _seed_turn(
            db,
            kb_id=uuid.UUID(kb_miss["id"]),
            user_id=user_id,
            user_content="请更新进度",
            assistant_content="本周目标完成",
        )

        items, total = await search_chat_messages(
            db, user_id=user_id, query="100%"
        )
        assert total == 1
        assert _hit_contents(items) == ["本周目标 100% 完成"]

        items, total = await search_chat_messages(db, user_id=user_id, query="%")
        assert total == 1
        assert _hit_contents(items) == ["本周目标 100% 完成"]

        items, total = await search_chat_messages(
            db, user_id=user_id, query="本周目标"
        )
        assert total == 2
        assert set(_hit_contents(items)) == {"本周目标 100% 完成", "本周目标完成"}


@pytest.mark.asyncio
async def test_search_underscore_matches_literal_content_only(
    client,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="p2-r10-underscore-content")
    kb_literal = await create_test_kb(
        client, headers, user, name="p2-r10-under-literal"
    )
    kb_any_char = await create_test_kb(
        client, headers, user, name="p2-r10-under-any-char"
    )
    user_id = uuid.UUID(user["id"])

    async with SessionLocal() as db:
        await _seed_turn(
            db,
            kb_id=uuid.UUID(kb_literal["id"]),
            user_id=user_id,
            user_content="请确认版本",
            assistant_content="版本 v1_2 已发布",
        )
        await _seed_turn(
            db,
            kb_id=uuid.UUID(kb_any_char["id"]),
            user_id=user_id,
            user_content="请确认版本",
            assistant_content="版本 v1X2 已发布",
        )

        items, total = await search_chat_messages(
            db, user_id=user_id, query="v1_2"
        )
        assert total == 1
        assert _hit_contents(items) == ["版本 v1_2 已发布"]


@pytest.mark.asyncio
async def test_search_percent_matches_literal_title_only(
    client,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="p2-r10-pct-title")
    kb_hit = await create_test_kb(client, headers, user, name="p2-r10-title-hit")
    kb_miss = await create_test_kb(client, headers, user, name="p2-r10-title-miss")
    user_id = uuid.UUID(user["id"])

    async with SessionLocal() as db:
        hit_id = await _seed_turn(
            db,
            kb_id=uuid.UUID(kb_hit["id"]),
            user_id=user_id,
            user_content="请查看预算",
            assistant_content="预算讨论完毕",
        )
        await _seed_turn(
            db,
            kb_id=uuid.UUID(kb_miss["id"]),
            user_id=user_id,
            user_content="请查看预算",
            assistant_content="预算讨论完毕",
        )
        await _set_thread_title(db, hit_id, "配额 50% 已用")

        items, total = await search_chat_messages(
            db, user_id=user_id, query="50%"
        )
        assert total == 2
        assert set(_hit_titles(items)) == {"配额 50% 已用"}

        items, total = await search_chat_messages(db, user_id=user_id, query="%")
        assert total == 2
        assert set(_hit_titles(items)) == {"配额 50% 已用"}


@pytest.mark.asyncio
async def test_search_underscore_matches_literal_title_only(
    client,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="p2-r10-under-title")
    kb_hit = await create_test_kb(client, headers, user, name="p2-r10-t-under-hit")
    kb_miss = await create_test_kb(client, headers, user, name="p2-r10-t-under-miss")
    user_id = uuid.UUID(user["id"])

    async with SessionLocal() as db:
        hit_id = await _seed_turn(
            db,
            kb_id=uuid.UUID(kb_hit["id"]),
            user_id=user_id,
            user_content="请确认版本",
            assistant_content="版本讨论完毕",
        )
        await _seed_turn(
            db,
            kb_id=uuid.UUID(kb_miss["id"]),
            user_id=user_id,
            user_content="请确认版本",
            assistant_content="版本 v1X2 复盘",
        )
        await _set_thread_title(db, hit_id, "v1_2 复盘")

        items, total = await search_chat_messages(
            db, user_id=user_id, query="v1_2"
        )
        assert total == 2
        assert set(_hit_titles(items)) == {"v1_2 复盘"}
