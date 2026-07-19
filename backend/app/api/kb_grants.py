"""资料库跨部门 grant CRUD API（ORG-4.2）。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.request_ip import get_client_ip
from app.core.deps import CurrentUser, get_current_user
from app.schemas.kb_grant import KbGrantCreate, KbGrantListResponse, KbGrantResponse
from app.services.knowledge_base.grants import (
    create_kb_grant,
    delete_kb_grant,
    list_kb_grants,
)

router = APIRouter(prefix="/knowledge-bases", tags=["kb-grants"])


@router.get("/{kb_id}/grants", response_model=KbGrantListResponse)
async def get_kb_grants(
    kb_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KbGrantListResponse:
    return await list_kb_grants(db, current_user, kb_id)


@router.post(
    "/{kb_id}/grants",
    response_model=KbGrantResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_kb_grant(
    kb_id: UUID,
    body: KbGrantCreate,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KbGrantResponse:
    return await create_kb_grant(
        db,
        current_user,
        kb_id,
        body,
        ip=get_client_ip(request),
    )


@router.delete("/{kb_id}/grants/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kb_grant_by_id(
    kb_id: UUID,
    grant_id: UUID,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await delete_kb_grant(
        db,
        current_user,
        kb_id,
        grant_id,
        ip=get_client_ip(request),
    )
