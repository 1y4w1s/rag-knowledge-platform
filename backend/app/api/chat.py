"""RAG 对话 API（Wave 3.1～3.2 · EW-D4 历史）：POST chat SSE + GET messages。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    CurrentUser,
    DepartmentIdQuery,
    KbAction,
    _assert_kb_action_allowed,
    _assert_kb_ownership,
    get_current_user,
    require_kb_access,
)
from app.schemas.chat import (
    ChatMessagesListResponse,
    ChatRequest,
    HistoryCitationPayload,
)
from app.schemas.citation import CitationResolveResponse
from app.models.knowledge_base import KnowledgeBase
from app.services.auth.api_rate_limit import ApiRateLimitKind, enforce_api_rate_limit
from app.services.org.scope import resolve_org_scope
from app.services.rag.chat import stream_chat_events
from app.services.rag.citations import (
    is_kb_visible_in_org_scope,
    resolve_citation,
)
from app.services.rag.message_builder import SSE_HEADERS, build_chat_message_list
from app.services.rag.persistence import list_chat_messages

router = APIRouter(
    prefix="/knowledge-bases/{kb_id}",
    tags=["chat"],
)


@router.post("/chat")
async def post_chat(
    kb_id: UUID,
    body: ChatRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    department_id: DepartmentIdQuery = None,
) -> StreamingResponse:
    enforce_api_rate_limit(ApiRateLimitKind.chat, current_user.id)

    kb = await require_kb_access(
        kb_id=kb_id,
        action=KbAction.read,
        current_user=current_user,
        db=db,
        department_id=department_id,
    )

    visible_kb_ids: frozenset[UUID] | None = None
    if kb.owner_org_id is not None and kb.owner_user_id is None:
        org_scope = await resolve_org_scope(db, current_user, department_id=department_id)
        visible_kb_ids = org_scope.visible_kb_ids

    return StreamingResponse(
        stream_chat_events(
            db,
            kb_id=kb_id,
            user_id=current_user.id,
            message=body.message,
            visible_kb_ids=visible_kb_ids,
            hide_admin_only=(
                current_user.account_type.value == "enterprise"
                and current_user.org_role == "member"
            ),
        ),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.get("/messages", response_model=ChatMessagesListResponse)
async def get_chat_messages(
    kb_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    department_id: DepartmentIdQuery = None,
) -> ChatMessagesListResponse:
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在",
        )

    _assert_kb_ownership(kb, current_user)
    _assert_kb_action_allowed(current_user, KbAction.read)

    kb_visible = await is_kb_visible_in_org_scope(
        db, current_user, kb, department_id=department_id
    )
    rows = await list_chat_messages(
        db,
        kb_id=kb_id,
        user_id=current_user.id,
        limit=limit,
    )
    if not kb_visible and not rows:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该资料库",
        )

    async def _kb_visible(
        _payload: HistoryCitationPayload, _raw: dict
    ) -> bool:
        return kb_visible

    messages = await build_chat_message_list(
        db,
        rows,
        current_user=current_user,
        kb_visible_fn=_kb_visible,
        department_id=department_id,
        include_approval=True,
        kb_id=kb_id,
    )
    return ChatMessagesListResponse(messages=messages)

@router.get("/citations/resolve", response_model=CitationResolveResponse)
async def get_citation_resolve(
    kb_id: UUID,
    document_id: UUID,
    chunk_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    department_id: DepartmentIdQuery = None,
) -> CitationResolveResponse:
    return await resolve_citation(
        db,
        current_user,
        kb_id,
        document_id,
        chunk_id,
        department_id=department_id,
    )
