"""跨库搜索 API（EW-E1 / Plan-RAG R1-1～R1-2）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    CurrentUser,
    DepartmentIdQuery,
    get_current_user,
)
from app.services.auth.api_rate_limit import ApiRateLimitKind, enforce_api_rate_limit
from app.services.org.scope import resolve_org_scope_for_workspace
from app.schemas.search import SearchDocumentsResponse, SearchMode
from app.services.search.content import search_documents_by_content
from app.services.search.documents import (
    normalize_limit,
    search_documents_by_filename,
    validate_search_query,
)
from app.services.workspace.scope import resolve_workspace

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/documents", response_model=SearchDocumentsResponse)
async def search_documents(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str, Query(description="搜索关键词，1～200 字符")],
    workspace: Annotated[str | None, Query(description="工作区：personal 或组织 UUID")] = None,
    mode: Annotated[
        SearchMode,
        Query(description="filename=文件名子串；content=PDF/文档正文"),
    ] = "filename",
    limit: Annotated[int | None, Query(ge=1, le=50, description="最大返回条数")] = None,
    department_id: DepartmentIdQuery = None,
) -> SearchDocumentsResponse:
    """跨库文档搜索：文件名子串或正文 tsvector（同 workspace 聚合）。"""
    enforce_api_rate_limit(ApiRateLimitKind.search, current_user.id)
    scope = await resolve_workspace(db, current_user, workspace)
    org_scope = await resolve_org_scope_for_workspace(
        db, current_user, scope, department_id=department_id
    )
    try:
        query = validate_search_query(q)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    effective_limit = normalize_limit(limit)
    hide_admin_only = (
        current_user.account_type.value == "enterprise"
        and current_user.org_role == "member"
    )
    if mode == "content":
        return await search_documents_by_content(
            db,
            scope,
            query,
            effective_limit,
            org_scope=org_scope,
            hide_admin_only=hide_admin_only,
        )
    return await search_documents_by_filename(
        db,
        scope,
        query,
        effective_limit,
        org_scope=org_scope,
        hide_admin_only=hide_admin_only,
    )
