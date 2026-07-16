"""点赞/点踩反馈业务层。"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_feedback import ChatFeedback
from app.models.chat_message import ChatMessage
from app.models.enums import ThreadKind
from app.models.user import User


async def upsert_feedback(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    message_id: uuid.UUID,
    rating: int,
    feedback_text: str | None = None,
) -> ChatFeedback:
    """创建或更新反馈（每人每消息一条）。rating: 1=up, 0=down。"""
    # 验证 message 存在且属于该用户
    stmt = select(ChatMessage).where(
        ChatMessage.id == message_id,
        ChatMessage.user_id == user_id,
    )
    msg = (await db.execute(stmt)).scalar_one_or_none()
    if msg is None:
        raise ValueError("消息不存在或不属于当前用户")

    # Upsert
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
) -> dict[str, Any]:
    """获取反馈聚合统计。可选按 user_id 或 kb_id 过滤。"""
    query = select(
        func.count().label("total"),
        func.sum(ChatFeedback.rating).label("thumbs_up"),  # sum=rating (1=up, 0=down)
        func.count() - func.sum(ChatFeedback.rating).label("thumbs_down"),
    ).select_from(ChatFeedback)

    if user_id is not None:
        query = query.where(ChatFeedback.user_id == user_id)

    if kb_id is not None:
        query = query.join(
            ChatMessage,
            ChatFeedback.message_id == ChatMessage.id,
        ).where(ChatMessage.kb_id == kb_id)

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
