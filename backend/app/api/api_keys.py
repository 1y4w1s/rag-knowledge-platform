"""API Key 管理端点（API Key 管理）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, CurrentUser
from app.models.api_key import ApiKey
from app.services.auth.api_key_auth import generate_api_key, hash_api_key

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


# ── Schemas ─────────────────────────────────────────────

class ApiKeyCreateRequest(BaseModel):
    name: str
    scopes: str = ""


class ApiKeyCreateResponse(BaseModel):
    id: str
    name: str
    prefix: str
    raw_key: str
    scopes: str
    created_at: datetime


class ApiKeyItem(BaseModel):
    id: str
    name: str
    prefix: str
    scopes: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None


class ApiKeyListResponse(BaseModel):
    items: list[ApiKeyItem]


# ── Endpoints ───────────────────────────────────────────

@router.post("", response_model=ApiKeyCreateResponse, status_code=201)
async def create_api_key(
    body: ApiKeyCreateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiKeyCreateResponse:
    """创建新的 API Key。返回 raw_key 仅此一次。"""
    raw_key, prefix, key_hash = generate_api_key()

    api_key = ApiKey(
        id=uuid.uuid4(),
        user_id=current_user.id,
        key_hash=key_hash,
        prefix=prefix,
        name=body.name,
        scopes=body.scopes,
        is_active=True,
    )
    db.add(api_key)
    await db.flush()

    return ApiKeyCreateResponse(
        id=str(api_key.id),
        name=api_key.name,
        prefix=api_key.prefix,
        raw_key=raw_key,
        scopes=api_key.scopes,
        created_at=api_key.created_at,
    )


@router.get("", response_model=ApiKeyListResponse)
async def list_api_keys(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiKeyListResponse:
    """列出当前用户的所有 API Key（不含 raw_key）。"""
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.user_id == current_user.id)
        .order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()
    return ApiKeyListResponse(
        items=[
            ApiKeyItem(
                id=str(k.id),
                name=k.name,
                prefix=k.prefix,
                scopes=k.scopes,
                is_active=k.is_active,
                created_at=k.created_at,
                last_used_at=k.last_used_at,
                expires_at=k.expires_at,
            )
            for k in keys
        ]
    )


@router.delete("/{key_id}", status_code=204, response_model=None)
async def delete_api_key(
    key_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """撤销（删除）指定的 API Key。"""
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.user_id == current_user.id,
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key 不存在",
        )

    api_key.is_active = False
    await db.flush()
