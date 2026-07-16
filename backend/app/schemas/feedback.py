"""反馈 API 数据模型。"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    """提交反馈请求。"""
    message_id: uuid.UUID = Field(..., description="被评价消息的 id（来自 SSE done 事件）")
    rating: int = Field(..., ge=0, le=1, description="1=thumbs up, 0=thumbs down")
    feedback_text: str | None = Field(None, max_length=2000, description="可选评价文字")


class FeedbackUpdate(BaseModel):
    """修改反馈请求。"""
    rating: int = Field(..., ge=0, le=1)
    feedback_text: str | None = Field(None, max_length=2000)


class FeedbackResponse(BaseModel):
    """单条反馈响应。"""
    id: uuid.UUID
    message_id: uuid.UUID
    rating: int
    feedback_text: str | None
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class FeedbackStatsResponse(BaseModel):
    """反馈统计响应。"""
    total: int
    thumbs_up: int
    thumbs_down: int
    approval_rate: float

    model_config = {"from_attributes": True}


class FeedbackListResponse(BaseModel):
    """反馈列表响应。"""
    items: list[FeedbackResponse]
    total: int
