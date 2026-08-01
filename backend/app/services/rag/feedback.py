"""点赞/点踩反馈业务层（R6-4 / NW-10：只记元数据，不改检索）。"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_feedback import ChatFeedback
from app.models.chat_message import ChatMessage
from app.models.enums import MessageRole
from app.models.knowledge_base import KnowledgeBase
from app.services.audit.chat import audit_feedback_upserted


async def upsert_feedback(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    message_id: uuid.UUID,
    rating: int,
    feedback_text: str | None = None,
) -> ChatFeedback:
    """创建或更新反馈（每人每消息一条）。rating: 1=up, 0=down。仅 assistant 消息。"""
    stmt = select(ChatMessage).where(
        ChatMessage.id == message_id,
        ChatMessage.user_id == user_id,
    )
    msg = (await db.execute(stmt)).scalar_one_or_none()
    if msg is None:
        raise ValueError("消息不存在或不属于当前用户")
    if msg.role != MessageRole.assistant:
        raise ValueError("只能对助手回答反馈")

    stmt = select(ChatFeedback).where(
        ChatFeedback.message_id == message_id,
        ChatFeedback.user_id == user_id,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing:
        existing.rating = rating
        existing.feedback_text = feedback_text
        feedback = existing
    else:
        feedback = ChatFeedback(
            message_id=message_id,
            user_id=user_id,
            rating=rating,
            feedback_text=feedback_text,
        )
        db.add(feedback)

    await db.flush()
    await audit_feedback_upserted(
        db,
        actor_user_id=user_id,
        message_id=message_id,
        feedback_id=feedback.id,
        rating=rating,
        kb_id=msg.kb_id,
    )
    await db.commit()
    await db.refresh(feedback)
    return feedback


async def get_message_feedback(
    db: AsyncSession,
    *,
    message_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> ChatFeedback | None:
    """获取单条消息的反馈。可指定 user_id 过滤。"""
    stmt = select(ChatFeedback).where(ChatFeedback.message_id == message_id)
    if user_id is not None:
        stmt = stmt.where(ChatFeedback.user_id == user_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_user_feedback(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
) -> list[ChatFeedback]:
    """分页列出当前用户的反馈历史。"""
    stmt = (
        select(ChatFeedback)
        .where(ChatFeedback.user_id == user_id)
        .order_by(ChatFeedback.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


async def get_feedback_stats(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    kb_id: uuid.UUID | None = None,
    org_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """获取反馈聚合统计。

    - 传 user_id：仅该用户（Member / 默认）
    - 不传 user_id + kb_id：该库全部反馈（Admin 聚合）
    - 不传 user_id + org_id：组织可见范围内全部（Admin 无 kb 时）
    """
    query = select(
        func.count().label("total"),
        func.sum(ChatFeedback.rating).label("thumbs_up"),
        func.count() - func.sum(ChatFeedback.rating).label("thumbs_down"),
    ).select_from(ChatFeedback)

    needs_message_join = kb_id is not None or (
        user_id is None and org_id is not None
    )
    if needs_message_join:
        query = query.join(
            ChatMessage,
            ChatFeedback.message_id == ChatMessage.id,
        )

    if user_id is not None:
        query = query.where(ChatFeedback.user_id == user_id)

    if kb_id is not None:
        query = query.where(ChatMessage.kb_id == kb_id)
    elif user_id is None and org_id is not None:
        org_kb_ids = select(KnowledgeBase.id).where(
            KnowledgeBase.owner_org_id == org_id
        )
        query = query.where(
            or_(
                ChatMessage.kb_id.in_(org_kb_ids),
                ChatMessage.workspace_org_id == org_id,
            )
        )

    row = (await db.execute(query)).one()

    total = row.total or 0
    thumbs_up = int(row.thumbs_up or 0) if total > 0 else 0
    thumbs_down = total - thumbs_up

    return {
        "total": total,
        "thumbs_up": thumbs_up,
        "thumbs_down": thumbs_down,
        "approval_rate": round(thumbs_up / total, 4) if total > 0 else 0.0,
    }


async def delete_feedback(
    db: AsyncSession,
    *,
    feedback_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """删除某条反馈（撤回）。"""
    stmt = select(ChatFeedback).where(
        ChatFeedback.id == feedback_id,
        ChatFeedback.user_id == user_id,
    )
    fb = (await db.execute(stmt)).scalar_one_or_none()
    if fb is None:
        return False
    await db.delete(fb)
    await db.commit()
    return True
