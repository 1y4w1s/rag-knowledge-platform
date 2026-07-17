"""Webhook 管理 API（Wave 7.5）。"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, KbAction, get_current_user, require_kb_access
from app.models.webhook import Webhook
from pydantic import BaseModel
from datetime import datetime


router = APIRouter(prefix="/knowledge-bases/{kb_id}/webhooks", tags=["webhooks"])


class WebhookCreate(BaseModel):
    url: str
    secret: str
    events: str = "document.completed"


class WebhookResponse(BaseModel):
    id: UUID
    url: str
    events: str
    is_active: bool
    created_at: datetime


@router.get("")
async def list_webhooks(
    kb_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[WebhookResponse]:
    await require_kb_access(kb_id=kb_id, action=KbAction.admin, current_user=current_user, db=db)
    result = await db.execute(
        select(Webhook).where(Webhook.kb_id == kb_id, Webhook.is_active == True)
    )
    return [
        WebhookResponse(id=w.id, url=w.url, events=w.events, is_active=w.is_active, created_at=w.created_at)
        for w in result.scalars().all()
    ]


@router.post("", response_model=WebhookResponse, status_code=201)
async def create_webhook(
    kb_id: UUID,
    body: WebhookCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WebhookResponse:
    await require_kb_access(kb_id=kb_id, action=KbAction.admin, current_user=current_user, db=db)

    wh = Webhook(
        kb_id=kb_id,
        url=body.url,
        secret=body.secret,
        events=body.events,
        created_by=current_user.id,
    )
    db.add(wh)
    await db.commit()
    await db.refresh(wh)
    return WebhookResponse(id=wh.id, url=wh.url, events=wh.events, is_active=wh.is_active, created_at=wh.created_at)


@router.delete("/{webhook_id}")
async def delete_webhook(
    kb_id: UUID,
    webhook_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await require_kb_access(kb_id=kb_id, action=KbAction.admin, current_user=current_user, db=db)
    wh = await db.get(Webhook, webhook_id)
    if wh is None or wh.kb_id != kb_id:
        raise HTTPException(status_code=404, detail="Webhook 不存在")
    await db.delete(wh)
    await db.commit()
    return Response(status_code=204)
