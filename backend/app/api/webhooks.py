"""Webhook 管理 API（Wave 7.5）。"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import AnyHttpUrl, BaseModel, Field, field_validator
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import urlparse

from app.core.database import get_db
from app.core.deps import CurrentUser, KbAction, get_current_user, require_kb_access
from app.models.webhook import Webhook
from app.core.config import settings
from app.services.audit.log import write_audit_log
from app.services.webhook.security import encrypt_secret
from datetime import datetime

# 禁止的 SSRF 目标：内网/回环地址和云元数据
_FORBIDDEN_HOSTS = frozenset({
    "169.254.169.254", "metadata.google.internal", "100.100.100.200",
    "localhost", "127.0.0.1", "0.0.0.0",
    "[::1]", "[0:0:0:0:0:0:0:1]",
})


def _reject_ssrf_target(url: str) -> str:
    """校验 webhook URL 不指向内网/回环/元数据地址，且仅允许 HTTPS。"""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Webhook URL 仅支持 HTTPS")
    host = parsed.hostname or ""
    if host.lower() in _FORBIDDEN_HOSTS:
        raise ValueError("Webhook URL 不能指向内网或云元数据地址")
    if host.startswith("10.") or host.startswith("172.16.") or host.startswith("192.168."):
        raise ValueError("Webhook URL 不能指向内网地址")
    # P3：可选域名白名单（非空时启用）
    if settings.webhook_allowed_domains:
        allowed = any(
            host == d or host.endswith("." + d)
            for d in settings.webhook_allowed_domains
        )
        if not allowed:
            raise ValueError("Webhook URL 域名不在白名单内")
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
        metadata={"url": str(wh.url), "events": wh.events},
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
