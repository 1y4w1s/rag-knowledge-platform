"""对话消息落库与历史查询（Wave 3.2 · EW-D4 · G1-0.2 · G2-0.3 thread）。"""

from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage
from app.models.chat_thread import ChatThread
from app.models.enums import MessageRole, ThreadKind
from app.services.audit.chat import audit_message_sent
from app.services.rag.thread_persistence import (
    maybe_autotitle_thread_from_first_message,
    normalize_workspace_department_key,
    resolve_thread_for_message,
    touch_thread,
)
from app.services.workspace.scope import WorkspaceKind


def _sort_messages_chronologically(rows: list[ChatMessage]) -> list[ChatMessage]:
    rows.sort(key=lambda row: (row.created_at, 0 if row.role == MessageRole.user else 1))
    return rows


async def _save_turn(
    db: AsyncSession,
    *,
    thread: ChatThread,
    common: dict,
    user_id: UUID,
    user_content: str,
    assistant_content: str,
    citations: list[dict],
    assistant_id: UUID,
    retrieval_duration_ms: int | None = None,
) -> UUID:
    """写入 user + assistant 两条 ChatMessage，执行 auto-title、touch、审计、commit。"""
    db.add(
        ChatMessage(
            **common,
            role=MessageRole.user,
            content=user_content,
            citations=None,
        )
    )
    db.add(
        ChatMessage(
            id=assistant_id,
            **common,
            role=MessageRole.assistant,
            content=assistant_content,
            citations=citations,
            retrieval_duration_ms=retrieval_duration_ms,
        )
    )
    await maybe_autotitle_thread_from_first_message(db, thread, user_content)
    await touch_thread(db, thread.id)
    await audit_message_sent(
        db,
        thread=thread,
        actor_user_id=user_id,
        assistant_message_id=assistant_id,
        citation_count=len(citations),
        retrieval_ms=retrieval_duration_ms,
    )
    await db.commit()
    return assistant_id


async def save_kb_chat_turn(
    db: AsyncSession,
    *,
    kb_id: UUID,
    user_id: UUID,
    user_content: str,
    assistant_content: str,
    citations: list[dict],
    assistant_message_id: UUID | None = None,
    retrieval_duration_ms: int | None = None,
    thread_id: UUID | None = None,
) -> UUID:
    """写入一轮资料库对话（thread_kind=knowledge_base），返回 assistant message id。"""
    thread = await resolve_thread_for_message(
        db,
        thread_id=thread_id,
        thread_kind=ThreadKind.knowledge_base,
        kb_id=kb_id,
        user_id=user_id,
    )
    assistant_id = assistant_message_id or uuid.uuid4()
    common = {
        "thread_kind": ThreadKind.knowledge_base,
        "kb_id": kb_id,
        "user_id": user_id,
        "thread_id": thread.id,
    }
    return await _save_turn(
        db,
        thread=thread,
        common=common,
        user_id=user_id,
        user_content=user_content,
        assistant_content=assistant_content,
        citations=citations,
        assistant_id=assistant_id,
        retrieval_duration_ms=retrieval_duration_ms,
    )


async def save_workspace_chat_turn(
    db: AsyncSession,
    *,
    user_id: UUID,
    workspace_kind: WorkspaceKind,
    workspace_org_id: UUID | None,
    department_id: str | None,
    user_content: str,
    assistant_content: str,
    citations: list[dict],
    assistant_message_id: UUID | None = None,
    retrieval_duration_ms: int | None = None,
    thread_id: UUID | None = None,
) -> UUID:
    """写入一轮工作区对话（thread_kind=workspace · kb_id 为空），返回 assistant id。"""
    department_key = normalize_workspace_department_key(department_id)
    thread = await resolve_thread_for_message(
        db,
        thread_id=thread_id,
        thread_kind=ThreadKind.workspace,
        kb_id=None,
        user_id=user_id,
        workspace_kind=workspace_kind,
        workspace_org_id=workspace_org_id,
        department_key=department_key,
    )
    assistant_id = assistant_message_id or uuid.uuid4()
    common = {
        "thread_kind": ThreadKind.workspace,
        "kb_id": None,
        "user_id": user_id,
        "workspace_kind": workspace_kind.value,
        "workspace_org_id": workspace_org_id,
        "workspace_department_key": department_key,
        "thread_id": thread.id,
    }
    return await _save_turn(
        db,
        thread=thread,
        common=common,
        user_id=user_id,
        user_content=user_content,
        assistant_content=assistant_content,
        citations=citations,
        assistant_id=assistant_id,
        retrieval_duration_ms=retrieval_duration_ms,
    )


async def save_chat_turn(
    db: AsyncSession,
    *,
    kb_id: UUID,
    user_id: UUID,
    user_content: str,
    assistant_content: str,
    citations: list[dict],
    assistant_message_id: UUID | None = None,
    retrieval_duration_ms: int | None = None,
    thread_id: UUID | None = None,
) -> UUID:
    """兼容别名：库内 chat 仍调用 save_kb_chat_turn。"""
    return await save_kb_chat_turn(
        db,
        kb_id=kb_id,
        user_id=user_id,
        user_content=user_content,
        assistant_content=assistant_content,
        citations=citations,
        assistant_message_id=assistant_message_id,
        retrieval_duration_ms=retrieval_duration_ms,
        thread_id=thread_id,
    )


async def get_message_by_id(
    db: AsyncSession,
    message_id: UUID,
) -> ChatMessage | None:
    """按 message_id 查询单条消息（含 citations）。"""
    return await db.get(ChatMessage, message_id)


async def list_thread_messages(
    db: AsyncSession,
    *,
    thread_id: UUID,
    user_id: UUID,
    limit: int = 50,
) -> list[ChatMessage]:
    """返回指定 thread 下最近 N 条消息（时间正序）。"""
    capped = max(1, min(limit, 100))
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .where(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(capped)
    )
    rows = list(result.scalars().all())
    rows.reverse()
    return _sort_messages_chronologically(rows)


async def list_chat_messages(
    db: AsyncSession,
    *,
    kb_id: UUID,
    user_id: UUID,
    limit: int = 50,
    thread_id: UUID | None = None,
) -> list[ChatMessage]:
    """返回当前用户在指定资料库下最近 N 条消息（时间正序）。"""
    if thread_id is not None:
        return await list_thread_messages(
            db, thread_id=thread_id, user_id=user_id, limit=limit
        )

    capped = max(1, min(limit, 100))
    result = await db.execute(
        select(ChatMessage)
        .join(ChatThread, ChatMessage.thread_id == ChatThread.id)
        .where(ChatMessage.thread_kind == ThreadKind.knowledge_base)
        .where(ChatMessage.kb_id == kb_id)
        .where(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(capped)
    )
    rows = list(result.scalars().all())
    rows.reverse()
    return _sort_messages_chronologically(rows)


async def list_workspace_chat_messages(
    db: AsyncSession,
    *,
    user_id: UUID,
    workspace_kind: WorkspaceKind,
    workspace_org_id: UUID | None,
    department_id: str | None,
    limit: int = 50,
    thread_id: UUID | None = None,
) -> list[ChatMessage]:
    """返回当前用户在工作区上下文下最近 N 条消息（时间正序）。"""
    if thread_id is not None:
        return await list_thread_messages(
            db, thread_id=thread_id, user_id=user_id, limit=limit
        )

    capped = max(1, min(limit, 100))
    department_key = normalize_workspace_department_key(department_id)
    stmt = (
        select(ChatMessage)
        .join(ChatThread, ChatMessage.thread_id == ChatThread.id)
        .where(ChatMessage.thread_kind == ThreadKind.workspace)
        .where(ChatMessage.user_id == user_id)
        .where(ChatMessage.workspace_kind == workspace_kind.value)
    )
    if workspace_kind == WorkspaceKind.personal:
        stmt = stmt.where(ChatMessage.workspace_org_id.is_(None))
    else:
        stmt = stmt.where(ChatMessage.workspace_org_id == workspace_org_id)
    if department_key is None:
        stmt = stmt.where(ChatMessage.workspace_department_key.is_(None))
    else:
        stmt = stmt.where(ChatMessage.workspace_department_key == department_key)

    result = await db.execute(
        stmt.order_by(ChatMessage.created_at.desc()).limit(capped)
    )
    rows = list(result.scalars().all())
    rows.reverse()
    return _sort_messages_chronologically(rows)
