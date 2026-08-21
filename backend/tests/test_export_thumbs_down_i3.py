"""NW-10 I-3：👎 导出候选（过滤 · 问句对齐 · shape · 不写 golden）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import event

from app.core.database import SessionLocal
from app.core.database import engine
from app.models.chat_feedback import ChatFeedback
from app.models.chat_message import ChatMessage
from app.models.chat_thread import ChatThread
from app.models.enums import MessageRole, ThreadKind
from app.services.rag.feedback_export import (
    EXPORT_NOTE,
    candidates_to_export_dict,
    list_thumbs_down_candidates,
)
from app.services.rag.feedback_attribution import (
    ATTRIBUTION_LABELS,
    METHOD_RULES_V1,
)
from tests.conftest import create_test_kb


async def _seed_thread_with_feedback(
    *,
    user_id: uuid.UUID,
    kb_id: uuid.UUID,
    query: str,
    answer: str,
    rating: int,
    feedback_text: str | None = None,
    t0: datetime | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    """插入 user→assistant 两条消息 + 反馈；返回 (assistant_msg_id, feedback_id)。"""
    base = t0 or datetime.now(timezone.utc)
    thread_id = uuid.uuid4()
    user_msg_id = uuid.uuid4()
    asst_msg_id = uuid.uuid4()
    fb_id = uuid.uuid4()

    async with SessionLocal() as db:
        db.add(
            ChatThread(
                id=thread_id,
                thread_kind=ThreadKind.knowledge_base,
                kb_id=kb_id,
                user_id=user_id,
                title="I3 export thread",
            )
        )
        await db.flush()
        db.add(
            ChatMessage(
                id=user_msg_id,
                thread_kind=ThreadKind.knowledge_base,
                kb_id=kb_id,
                user_id=user_id,
                thread_id=thread_id,
                role=MessageRole.user,
                content=query,
                created_at=base,
            )
        )
        db.add(
            ChatMessage(
                id=asst_msg_id,
                thread_kind=ThreadKind.knowledge_base,
                kb_id=kb_id,
                user_id=user_id,
                thread_id=thread_id,
                role=MessageRole.assistant,
                content=answer,
                created_at=base + timedelta(seconds=1),
            )
        )
        db.add(
            ChatFeedback(
                id=fb_id,
                message_id=asst_msg_id,
                user_id=user_id,
                rating=rating,
                feedback_text=feedback_text,
            )
        )
        await db.commit()
    return asst_msg_id, fb_id


@pytest.mark.asyncio
async def test_export_only_thumbs_down_and_aligns_query(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="i3-export")
    kb = await create_test_kb(client, headers, user, name="I3 Export KB")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    down_msg, down_fb = await _seed_thread_with_feedback(
        user_id=user_id,
        kb_id=kb_id,
        query="年假有多少天？",
        answer="依据不足，无法回答。",
        rating=0,
        feedback_text="答非所问",
    )
    await _seed_thread_with_feedback(
        user_id=user_id,
        kb_id=kb_id,
        query="迟到怎么处理？",
        answer="迟到扣款规则见手册。",
        rating=1,
    )

    async with SessionLocal() as db:
        candidates = await list_thumbs_down_candidates(db, kb_id=kb_id)

    assert len(candidates) == 1
    c = candidates[0]
    assert c.message_id == down_msg
    assert c.feedback_id == down_fb
    assert c.query == "年假有多少天？"
    assert c.answer == "依据不足，无法回答。"
    assert c.kb_id == kb_id
    assert c.kb_name == "I3 Export KB"
    assert c.feedback_text == "答非所问"
    assert c.rater_user_id == user_id

    payload = candidates_to_export_dict(candidates)
    assert payload["version"] == "1.2"
    assert payload["kind"] == "thumbs_down_candidates"
    assert "NOT golden_qa" in payload["description"]
    assert payload["note"] == EXPORT_NOTE
    assert "Do not auto-ingest" in payload["note"]
    assert "attribution" in payload["note"].lower()
    assert "scaffold" in payload["note"].lower()
    assert payload["count"] == 1
    row = payload["candidates"][0]
    for key in (
        "feedback_id",
        "message_id",
        "thread_id",
        "kb_id",
        "kb_name",
        "query",
        "answer",
        "feedback_text",
        "rated_at",
        "rater_user_id",
        "attribution",
        "golden_suggestion",
    ):
        assert key in row
    assert row["query"] == "年假有多少天？"
    assert row["attribution"]["label"] in ATTRIBUTION_LABELS
    assert row["attribution"]["method"] == METHOD_RULES_V1
    assert row["attribution"]["confidence"] == "low"
    assert row["attribution"]["rationale"]
    assert row["golden_suggestion"]["status"] == "draft_only"
    # generation_bad → hit 骨架；字段全 null，禁止当 expect
    ph = row["golden_suggestion"]["expect_placeholder"]
    assert isinstance(ph, dict)
    assert ph["shape"] == "hit"
    assert ph["content_contains"] is None
    assert "fill_checklist" in row["golden_suggestion"]
    assert "NOT golden" in row["golden_suggestion"]["note"]
    # feedback「答非所问」优先于拒答形态
    assert row["attribution"]["label"] == "generation_bad"

@pytest.mark.asyncio
async def test_export_kb_filter_and_missing_query(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="i3-filter")
    kb_a = await create_test_kb(client, headers, user, name="I3 KB A")
    kb_b = await create_test_kb(client, headers, user, name="I3 KB B")
    user_id = uuid.UUID(user["id"])
    kb_a_id = uuid.UUID(kb_a["id"])
    kb_b_id = uuid.UUID(kb_b["id"])

    await _seed_thread_with_feedback(
        user_id=user_id,
        kb_id=kb_a_id,
        query="仅 A 库问句",
        answer="A 答",
        rating=0,
    )
    # 无前置 user：单独插一条 assistant + 👎
    thread_id = uuid.uuid4()
    asst_id = uuid.uuid4()
    async with SessionLocal() as db:
        db.add(
            ChatThread(
                id=thread_id,
                thread_kind=ThreadKind.knowledge_base,
                kb_id=kb_b_id,
                user_id=user_id,
                title="orphan asst",
            )
        )
        await db.flush()
        db.add(
            ChatMessage(
                id=asst_id,
                thread_kind=ThreadKind.knowledge_base,
                kb_id=kb_b_id,
                user_id=user_id,
                thread_id=thread_id,
                role=MessageRole.assistant,
                content="无问句的回答",
                created_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            ChatFeedback(
                id=uuid.uuid4(),
                message_id=asst_id,
                user_id=user_id,
                rating=0,
            )
        )
        await db.commit()

    async with SessionLocal() as db:
        only_a = await list_thumbs_down_candidates(db, kb_id=kb_a_id)
        only_b = await list_thumbs_down_candidates(db, kb_id=kb_b_id)

    assert len(only_a) == 1
    assert only_a[0].query == "仅 A 库问句"
    assert len(only_b) == 1
    assert only_b[0].query is None
    assert only_b[0].answer == "无问句的回答"


@pytest.mark.asyncio
async def test_export_batches_query_lookup_and_aligns_latest_round(
    client: AsyncClient,
    register_and_login,
) -> None:
    """同 thread 多轮反馈各自对齐前一条问句，且不逐条查库（N+1 回归）。"""
    headers, user = await register_and_login(prefix="i3-batch")
    kb = await create_test_kb(client, headers, user, name="I3 Batch KB")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    thread_id = uuid.uuid4()
    t0 = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        db.add(
            ChatThread(
                id=thread_id,
                thread_kind=ThreadKind.knowledge_base,
                kb_id=kb_id,
                user_id=user_id,
                title="multi-round export",
            )
        )
        await db.flush()
        first_user = ChatMessage(
            id=uuid.uuid4(),
            thread_kind=ThreadKind.knowledge_base,
            kb_id=kb_id,
            user_id=user_id,
            thread_id=thread_id,
            role=MessageRole.user,
            content="第一轮问句",
            created_at=t0,
        )
        first_asst = ChatMessage(
            id=uuid.uuid4(),
            thread_kind=ThreadKind.knowledge_base,
            kb_id=kb_id,
            user_id=user_id,
            thread_id=thread_id,
            role=MessageRole.assistant,
            content="第一轮回答",
            created_at=t0 + timedelta(seconds=1),
        )
        second_user = ChatMessage(
            id=uuid.uuid4(),
            thread_kind=ThreadKind.knowledge_base,
            kb_id=kb_id,
            user_id=user_id,
            thread_id=thread_id,
            role=MessageRole.user,
            content="第二轮问句",
            created_at=t0 + timedelta(seconds=2),
        )
        second_asst = ChatMessage(
            id=uuid.uuid4(),
            thread_kind=ThreadKind.knowledge_base,
            kb_id=kb_id,
            user_id=user_id,
            thread_id=thread_id,
            role=MessageRole.assistant,
            content="第二轮回答",
            created_at=t0 + timedelta(seconds=3),
        )
        db.add_all([first_user, first_asst, second_user, second_asst])
        await db.flush()
        fb1 = ChatFeedback(
            id=uuid.uuid4(),
            message_id=first_asst.id,
            user_id=user_id,
            rating=0,
        )
        fb2 = ChatFeedback(
            id=uuid.uuid4(),
            message_id=second_asst.id,
            user_id=user_id,
            rating=0,
        )
        db.add_all([fb1, fb2])
        # 第二轮之后的新问句：不应被当成第二轮回答的前置问句
        db.add(
            ChatMessage(
                id=uuid.uuid4(),
                thread_kind=ThreadKind.knowledge_base,
                kb_id=kb_id,
                user_id=user_id,
                thread_id=thread_id,
                role=MessageRole.user,
                content="第二轮之后的新问句",
                created_at=t0 + timedelta(seconds=4),
            )
        )
        await db.commit()

    executed = 0

    def _count_execute(
        _conn,
        _cursor,
        _statement,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        nonlocal executed
        executed += 1

    event.listen(engine.sync_engine, "before_cursor_execute", _count_execute)
    try:
        async with SessionLocal() as db:
            candidates = await list_thumbs_down_candidates(db, kb_id=kb_id)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _count_execute)

    assert len(candidates) == 2
    by_feedback = {c.feedback_id: c for c in candidates}
    assert by_feedback[fb1.id].query == "第一轮问句"
    assert by_feedback[fb2.id].query == "第二轮问句"
    assert executed <= 2
