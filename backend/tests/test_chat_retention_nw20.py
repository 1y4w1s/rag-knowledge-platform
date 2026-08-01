"""NW-20：对话 thread 保留期 purge。"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.agent_run import AgentRun
from app.models.audit_log import AuditLog
from app.models.chat_feedback import ChatFeedback
from app.models.chat_message import ChatMessage
from app.models.chat_thread import ChatThread
from app.models.enums import (
    AgentRunMode,
    AgentRunStatus,
    MessageRole,
    ThreadKind,
    ThreadStatus,
)
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.services.chat.retention import purge_expired_chat_threads
from tests.conftest import create_test_kb
from tests.fixtures.audit_events import _count_audit_logs


async def _seed_thread_tree(
    *,
    user_id: uuid.UUID,
    kb_id: uuid.UUID,
    activity_at: datetime,
    status: ThreadStatus = ThreadStatus.active,
    with_feedback: bool = False,
    with_agent: bool = False,
    title: str = "retention test",
) -> uuid.UUID:
    """建 thread + user/assistant 消息；可选 feedback / agent_run。"""
    thread_id = uuid.uuid4()
    async with SessionLocal() as db:
        thread = ChatThread(
            id=thread_id,
            thread_kind=ThreadKind.knowledge_base,
            kb_id=kb_id,
            user_id=user_id,
            title=title,
            status=status,
            created_at=activity_at,
            updated_at=activity_at,
            last_message_at=activity_at,
        )
        db.add(thread)
        await db.flush()

        user_msg = ChatMessage(
            id=uuid.uuid4(),
            thread_kind=ThreadKind.knowledge_base,
            kb_id=kb_id,
            user_id=user_id,
            thread_id=thread_id,
            role=MessageRole.user,
            content="用户问题含隐私勿进 audit",
            created_at=activity_at,
        )
        asst_msg = ChatMessage(
            id=uuid.uuid4(),
            thread_kind=ThreadKind.knowledge_base,
            kb_id=kb_id,
            user_id=user_id,
            thread_id=thread_id,
            role=MessageRole.assistant,
            content="助手回答含片段",
            created_at=activity_at,
        )
        db.add(user_msg)
        db.add(asst_msg)
        await db.flush()

        if with_feedback:
            db.add(
                ChatFeedback(
                    id=uuid.uuid4(),
                    message_id=asst_msg.id,
                    user_id=user_id,
                    rating=0,
                    feedback_text="不该出现在 purge audit",
                )
            )

        if with_agent:
            db.add(
                AgentRun(
                    id=uuid.uuid4(),
                    thread_id=thread_id,
                    user_id=user_id,
                    mode=AgentRunMode.thorough,
                    status=AgentRunStatus.completed,
                    assistant_message_id=asst_msg.id,
                )
            )

        await db.commit()
    return thread_id


async def _latest_retention_audit() -> AuditLog:
    async with SessionLocal() as db:
        row = await db.scalar(
            select(AuditLog)
            .where(AuditLog.action == "chat.retention_purged")
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
        assert row is not None
        # detach details for use outside session
        _ = row.details
        db.expunge(row)
        return row


@pytest.mark.asyncio
async def test_retention_disabled_when_days_zero(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "chat_retention_days", 0)
    headers, user = await register_and_login(prefix="nw20-off")
    kb = await create_test_kb(client, headers, user, name="NW20关")
    old = datetime.now(timezone.utc) - timedelta(days=400)
    tid = await _seed_thread_tree(
        user_id=uuid.UUID(user["id"]),
        kb_id=uuid.UUID(kb["id"]),
        activity_at=old,
    )

    async with SessionLocal() as db:
        result = await purge_expired_chat_threads(db, dry_run=True)

    assert result.disabled is True
    assert result.found == 0
    assert result.deleted == 0
    async with SessionLocal() as db:
        assert await db.get(ChatThread, tid) is not None


@pytest.mark.asyncio
async def test_dry_run_lists_thread_id_no_delete(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "chat_retention_days", 30)
    monkeypatch.setattr(settings, "chat_purge_max_delete", 100)
    headers, user = await register_and_login(prefix="nw20-dry")
    kb = await create_test_kb(client, headers, user, name="NW20干跑")
    uid = uuid.UUID(user["id"])
    kid = uuid.UUID(kb["id"])
    now = datetime.now(timezone.utc)
    old_id = await _seed_thread_tree(
        user_id=uid, kb_id=kid, activity_at=now - timedelta(days=40), title="old"
    )
    new_id = await _seed_thread_tree(
        user_id=uid, kb_id=kid, activity_at=now - timedelta(days=5), title="new"
    )

    before = await _count_audit_logs(action="chat.retention_purged")
    async with SessionLocal() as db:
        result = await purge_expired_chat_threads(db, dry_run=True, now=now)

    assert result.dry_run is True
    assert result.deleted == 0
    found_ids = {i["thread_id"] for i in result.items}
    assert str(old_id) in found_ids
    assert str(new_id) not in found_ids
    assert await _count_audit_logs(action="chat.retention_purged") == before + 1

    row = await _latest_retention_audit()
    md = row.details or {}
    assert md["dry_run"] is True
    assert md["deleted"] == 0
    blob = str(md)
    assert "用户问题含隐私" not in blob
    assert "助手回答" not in blob
    assert "content" not in md

    async with SessionLocal() as db:
        assert await db.get(ChatThread, old_id) is not None
        assert await db.get(ChatThread, new_id) is not None


@pytest.mark.asyncio
async def test_apply_cascades_message_feedback_agent(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "chat_retention_days", 30)
    headers, user = await register_and_login(prefix="nw20-apply")
    kb = await create_test_kb(client, headers, user, name="NW20真删")
    uid = uuid.UUID(user["id"])
    kid = uuid.UUID(kb["id"])
    now = datetime.now(timezone.utc)
    old_id = await _seed_thread_tree(
        user_id=uid,
        kb_id=kid,
        activity_at=now - timedelta(days=60),
        status=ThreadStatus.archived,
        with_feedback=True,
        with_agent=True,
        title="purge-me",
    )
    keep_id = await _seed_thread_tree(
        user_id=uid,
        kb_id=kid,
        activity_at=now - timedelta(days=1),
        title="keep-me",
    )

    async with SessionLocal() as db:
        result = await purge_expired_chat_threads(db, dry_run=False, now=now)

    assert result.dry_run is False
    assert result.errors == 0
    assert str(old_id) in {i["thread_id"] for i in result.items}
    assert result.deleted >= 1

    async with SessionLocal() as db:
        assert await db.get(ChatThread, old_id) is None
        assert await db.get(ChatThread, keep_id) is not None
        msg_n = await db.scalar(
            select(func.count())
            .select_from(ChatMessage)
            .where(ChatMessage.thread_id == old_id)
        )
        assert int(msg_n or 0) == 0
        orphan_fb = await db.scalar(
            select(func.count())
            .select_from(ChatFeedback)
            .where(ChatFeedback.feedback_text == "不该出现在 purge audit")
        )
        assert int(orphan_fb or 0) == 0
        run_n = await db.scalar(
            select(func.count())
            .select_from(AgentRun)
            .where(AgentRun.thread_id == old_id)
        )
        assert int(run_n or 0) == 0
        assert await db.get(User, uid) is not None
        assert await db.get(KnowledgeBase, kid) is not None

    row = await _latest_retention_audit()
    md = row.details or {}
    assert md["dry_run"] is False
    assert md["deleted"] >= 1
    assert "用户问题含隐私" not in str(md)
    assert "不该出现在 purge audit" not in str(md)


@pytest.mark.asyncio
async def test_null_last_message_uses_created_at(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "chat_retention_days", 10)
    headers, user = await register_and_login(prefix="nw20-null")
    kb = await create_test_kb(client, headers, user, name="NW20空活动")
    uid = uuid.UUID(user["id"])
    kid = uuid.UUID(kb["id"])
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=20)
    tid = uuid.uuid4()
    async with SessionLocal() as db:
        db.add(
            ChatThread(
                id=tid,
                thread_kind=ThreadKind.knowledge_base,
                kb_id=kid,
                user_id=uid,
                title="no-msg",
                created_at=old,
                updated_at=old,
                last_message_at=None,
            )
        )
        await db.commit()

    async with SessionLocal() as db:
        result = await purge_expired_chat_threads(db, dry_run=True, now=now)

    assert str(tid) in {i["thread_id"] for i in result.items}
