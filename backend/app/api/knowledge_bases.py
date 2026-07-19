"""知识库 API 路由（Wave 2.1）。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.request_ip import get_client_ip
from app.core.deps import (
    CurrentUser,
    DepartmentIdQuery,
    get_current_user,
)
from app.services.org.scope import resolve_org_scope_for_workspace
from app.services.workspace.scope import resolve_workspace
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
)
from app.services.knowledge_base.crud import (
    create_knowledge_base,
    delete_knowledge_base,
    get_knowledge_base,
    update_knowledge_base,
)
from app.services.knowledge_base.listing import list_knowledge_bases

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


@router.get("", response_model=KnowledgeBaseListResponse)
async def list_kbs(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    workspace: Annotated[str | None, Query(description="工作区：personal 或组织 UUID")] = None,
    department_id: DepartmentIdQuery = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int | None, Query(ge=0)] = None,
    q: Annotated[str | None, Query(max_length=255, description="按名称/描述搜索")] = None,
    sort: Annotated[str | None, Query(description="排序模式")] = None,
) -> KnowledgeBaseListResponse:
    scope = await resolve_workspace(db, current_user, workspace)
    org_scope = await resolve_org_scope_for_workspace(
        db, current_user, scope, department_id=department_id
    )
    return await list_knowledge_bases(
        db,
        scope,
        org_scope=org_scope,
        limit=limit,
        offset=offset,
        q=q,
        sort=sort,
    )


@router.post("", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
async def create_kb(
    body: KnowledgeBaseCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    workspace: Annotated[str | None, Query(description="工作区：personal 或组织 UUID")] = None,
    department_id: DepartmentIdQuery = None,
) -> KnowledgeBaseResponse:
    scope = await resolve_workspace(db, current_user, workspace)
    return await create_knowledge_base(
        db, current_user, body, scope, department_id=department_id
    )


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_kb(
    kb_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    department_id: DepartmentIdQuery = None,
) -> KnowledgeBaseResponse:
    return await get_knowledge_base(
        db, current_user, kb_id, department_id=department_id
    )


@router.patch("/{kb_id}", response_model=KnowledgeBaseResponse)
async def patch_kb(
    kb_id: UUID,
    body: KnowledgeBaseUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KnowledgeBaseResponse:
    return await update_knowledge_base(db, current_user, kb_id, body)


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kb(
    kb_id: UUID,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await delete_knowledge_base(
        db, current_user, kb_id, ip=get_client_ip(request)
    )
