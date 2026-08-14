"""👎 反馈 → golden 人工候选导出（NW-10 I-3）。

只读 · 不写 golden_qa · 不改检索权重。
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_feedback import ChatFeedback
from app.models.chat_message import ChatMessage
from app.models.enums import MessageRole
from app.models.knowledge_base import KnowledgeBase

EXPORT_NOTE = (
    "Human must fill expect / case_id before merging into golden_qa.json. "
    "Do not auto-ingest. Export ≠ CI gate."
)


@dataclass(frozen=True)
class ThumbsDownCandidate:
    feedback_id: uuid.UUID
    message_id: uuid.UUID
    thread_id: uuid.UUID
    kb_id: uuid.UUID | None
    kb_name: str | None
    query: str | None
    answer: str
    feedback_text: str | None
    rated_at: datetime
    rater_user_id: uuid.UUID


async def _preceding_user_queries(
    db: AsyncSession,
    messages: list[ChatMessage],
) -> dict[uuid.UUID, str | None]:
    """批量取回相关 thread 的 user 消息，按消息时间做“前一条问句”对齐。"""
    thread_ids = {m.thread_id for m in messages}
    if not thread_ids:
        return {}

    stmt = (
        select(
            ChatMessage.id,
            ChatMessage.thread_id,
            ChatMessage.created_at,
            ChatMessage.content,
        )
        .where(
            ChatMessage.thread_id.in_(thread_ids),
            ChatMessage.role == MessageRole.user,
        )
    )
    by_thread: dict[uuid.UUID, list[tuple[datetime, str, uuid.UUID]]] = defaultdict(list)
    for msg_id, thread_id, created_at, content in await db.execute(stmt):
        by_thread[thread_id].append((created_at, content, msg_id))
    for items in by_thread.values():
        items.sort(key=lambda item: (item[0], item[2]))

    query_by_message_id: dict[uuid.UUID, str | None] = {}
    for message in messages:
        preceding = [
            content
            for created_at, content, _msg_id in by_thread.get(message.thread_id, ())
            if created_at < message.created_at
        ]
        query_by_message_id[message.id] = preceding[-1] if preceding else None
    return query_by_message_id


async def list_thumbs_down_candidates(
    db: AsyncSession,
    *,
    kb_id: uuid.UUID | None = None,
    since: datetime | None = None,
    limit: int = 500,
) -> list[ThumbsDownCandidate]:
    """只读列出 rating=0 的反馈，并尽量对齐同 thread 前一条 user 问句。"""
    stmt = (
        select(ChatFeedback, ChatMessage, KnowledgeBase.name)
        .join(ChatMessage, ChatFeedback.message_id == ChatMessage.id)
        .outerjoin(KnowledgeBase, ChatMessage.kb_id == KnowledgeBase.id)
        .where(
            ChatFeedback.rating == 0,
            ChatMessage.role == MessageRole.assistant,
        )
        .order_by(ChatFeedback.created_at.desc())
        .limit(limit)
    )
    if kb_id is not None:
        stmt = stmt.where(ChatMessage.kb_id == kb_id)
    if since is not None:
        stmt = stmt.where(ChatFeedback.created_at >= since)

    rows = (await db.execute(stmt)).all()
    query_by_message_id = await _preceding_user_queries(
        db, [msg for _, msg, _ in rows]
    )
    out: list[ThumbsDownCandidate] = []
    for fb, msg, kb_name in rows:
        out.append(
            ThumbsDownCandidate(
                feedback_id=fb.id,
                message_id=msg.id,
                thread_id=msg.thread_id,
                kb_id=msg.kb_id,
                kb_name=kb_name,
                query=query_by_message_id[msg.id],
                answer=msg.content,
                feedback_text=fb.feedback_text,
                rated_at=fb.created_at,
                rater_user_id=fb.user_id,
            )
        )
    return out


def candidate_to_dict(c: ThumbsDownCandidate) -> dict[str, Any]:
    return {
        "feedback_id": str(c.feedback_id),
        "message_id": str(c.message_id),
        "thread_id": str(c.thread_id),
        "kb_id": str(c.kb_id) if c.kb_id else None,
        "kb_name": c.kb_name,
        "query": c.query,
        "answer": c.answer,
        "feedback_text": c.feedback_text,
        "rated_at": c.rated_at.isoformat() if c.rated_at else None,
        "rater_user_id": str(c.rater_user_id),
    }


def candidates_to_export_dict(
    candidates: list[ThumbsDownCandidate],
) -> dict[str, Any]:
    """导出包装：显式 NOT golden_qa，供人工审题。"""
    return {
        "version": "1.0",
        "kind": "thumbs_down_candidates",
        "description": "thumbs-down candidates for manual golden review — NOT golden_qa",
        "note": EXPORT_NOTE,
        "count": len(candidates),
        "candidates": [candidate_to_dict(c) for c in candidates],
    }
