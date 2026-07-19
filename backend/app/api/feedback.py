"""点赞/点踩反馈 API。"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.schemas.feedback import (
    FeedbackCreate,
    FeedbackListResponse,
    FeedbackResponse,
    FeedbackStatsResponse,
)
from app.services.rag.feedback import (
    delete_feedback,
    get_feedback_stats,
    get_message_feedback,
    list_user_feedback,
    upsert_feedback,
)

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse, status_code=201)
async def submit_feedback(
    body: FeedbackCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FeedbackResponse:
    """提交或更新对某条消息的点赞/点踩。

    每人每消息只能有一条反馈；重复提交会更新 rating。
    消息必须属于当前用户。
    """
    try:
        fb = await upsert_feedback(
            db,
            user_id=current_user.id,
            message_id=body.message_id,
            rating=body.rating,
            feedback_text=body.feedback_text,
        )
        return FeedbackResponse.model_validate(fb)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/messages/{message_id}", response_model=FeedbackResponse | None)
async def get_feedback(
    message_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FeedbackResponse | None:
    """查看当前用户对某条消息的反馈。无反馈时返回 null。"""
    fb = await get_message_feedback(db, message_id=message_id, user_id=current_user.id)
    return FeedbackResponse.model_validate(fb) if fb else None


@router.get("/stats", response_model=FeedbackStatsResponse)
async def feedback_stats(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    kb_id: uuid.UUID | None = None,
) -> FeedbackStatsResponse:
    """获取当前用户的反馈统计。可选按 kb_id 过滤。"""
    stats = await get_feedback_stats(db, user_id=current_user.id, kb_id=kb_id)
    return FeedbackStatsResponse(**stats)


@router.get("/history", response_model=FeedbackListResponse)
async def feedback_history(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> FeedbackListResponse:
    """分页列出当前用户的反馈历史。"""
    items = await list_user_feedback(db, user_id=current_user.id, limit=limit, offset=offset)
    return FeedbackListResponse(
        items=[FeedbackResponse.model_validate(fb) for fb in items],
        total=len(items),
    )


@router.delete("/{feedback_id}", status_code=204, response_model=None)
async def remove_feedback(
    feedback_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """撤回（删除）一条反馈。"""
    ok = await delete_feedback(db, feedback_id=feedback_id, user_id=current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="反馈不存在")
