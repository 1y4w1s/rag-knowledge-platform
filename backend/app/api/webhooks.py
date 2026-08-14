"""Webhook 管理 API（Wave 7.5）。"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import AnyHttpUrl, BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, KbAction, get_current_user, require_kb_access
from app.models.webhook import Webhook
from app.core.config import settings
from app.services.audit.log import write_audit_log
from app.services.webhook.security import encrypt_secret
from app.services.webhook.ssrf import reject_ssrf_target
from datetime import datetime


def _reject_ssrf_target(url: str) -> str:
    """校验 webhook URL 不指向内网/回环/链路本地/云元数据地址（全地址族），且仅允许 HTTPS。"""
    reject_ssrf_target(
        url,
        allowed_schemes=frozenset({"https"}),
        allowed_domains=frozenset(settings.webhook_allowed_domains),
    )
    return url


router = APIRouter(prefix="/knowledge-bases/{kb_id}/webhooks", tags=["webhooks"])


class WebhookCreate(BaseModel):
    url: AnyHttpUrl
    secret: str = Field(min_length=8)
    events: str = "document.completed"

    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, v: AnyHttpUrl) -> AnyHttpUrl:
        _reject_ssrf_target(str(v))
        return v


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
        select(Webhook).where(Webhook.kb_id == kb_id, Webhook.is_active)
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
        url=str(body.url),
        secret=encrypt_secret(body.secret),
        events=body.events,
        created_by=current_user.id,
    )
    db.add(wh)
    await db.commit()
    await db.refresh(wh)

    await write_audit_log(
        db,
        action="webhook.create",
        actor_user_id=current_user.id,
        resource_type="webhook",
        resource_id=wh.id,
        kb_id=kb_id,
        metadata={
            "url": str(wh.url),
            "events": wh.events,
            "secret_encryption": "webhook_encryption_secret",
        },
    )
    await db.commit()

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

    wh_url = wh.url
    await db.delete(wh)
    await db.commit()

    await write_audit_log(
        db,
        action="webhook.delete",
        actor_user_id=current_user.id,
        resource_type="webhook",
        resource_id=webhook_id,
        kb_id=kb_id,
        metadata={"url": str(wh_url)},
    )
    await db.commit()
    return Response(status_code=204)
