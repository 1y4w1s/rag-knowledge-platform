"""工作区智能问答 API（G-1 Wave 2）：POST /ask/chat SSE + GET /ask/messages。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ask_common import (
    assert_has_visible_knowledge_bases,
    assert_team_business_allowed,
    citation_visible_in_scope,
)
from app.core.database import get_db
from app.core.deps import (
    CurrentUser,
    DepartmentIdQuery,
    get_current_user,
)
from app.schemas.chat import (
    ChatMessagesListResponse,
    ChatRequest,
    HistoryCitationPayload,
)
from app.services.auth.api_rate_limit import ApiRateLimitKind, enforce_api_rate_limit
from app.services.org.scope import resolve_org_scope_for_workspace
from app.services.rag.chat import stream_workspace_chat_events
from app.services.rag.message_builder import SSE_HEADERS, build_chat_message_list
from app.services.rag.persistence import list_workspace_chat_messages
from app.services.workspace.scope import resolve_workspace

router = APIRouter(prefix="/ask", tags=["ask"])


@router.post("/chat")
async def post_ask_chat(
    body: ChatRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    workspace: Annotated[str | None, Query(description="工作区：personal 或组织 UUID")] = None,
    department_id: DepartmentIdQuery = None,
) -> StreamingResponse:
    """工作区流式问答：跨 visible 库检索 + 引用含库名。"""
    enforce_api_rate_limit(ApiRateLimitKind.chat, current_user.id)

    scope = await resolve_workspace(db, current_user, workspace)
    assert_team_business_allowed(current_user, scope)
    org_scope = await resolve_org_scope_for_workspace(
        db, current_user, scope, department_id=department_id
    )
    await assert_has_visible_knowledge_bases(
        db, scope=scope, org_scope=org_scope, current_user=current_user
    )

    return StreamingResponse(
        stream_workspace_chat_events(
            db,
            scope=scope,
            org_scope=org_scope,
            user_id=current_user.id,
            message=body.message,
            department_id=department_id,
            hide_admin_only=(
                current_user.account_type.value == "enterprise"
                and current_user.org_role == "member"
            ),
        ),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.get("/messages", response_model=ChatMessagesListResponse)
async def get_ask_messages(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    workspace: Annotated[str | None, Query(description="工作区：personal 或组织 UUID")] = None,
    department_id: DepartmentIdQuery = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ChatMessagesListResponse:
    """工作区对话历史；不可见库 citation 标记 source_inaccessible（ORG-1.7 / E14）。"""
    scope = await resolve_workspace(db, current_user, workspace)
    assert_team_business_allowed(current_user, scope)

    rows = await list_workspace_chat_messages(
        db,
        user_id=current_user.id,
        workspace_kind=scope.kind,
        workspace_org_id=scope.org_id,
        department_id=department_id,
        limit=limit,
    )

    async def _citation_kb_visible(
        _payload: HistoryCitationPayload, _raw: dict
    ) -> bool:
        return await citation_visible_in_scope(
            db,
            current_user,
            _raw,
            scope=scope,
            department_id=department_id,
        )

    messages = await build_chat_message_list(
        db,
        rows,
        current_user=current_user,
        kb_visible_fn=_citation_kb_visible,
        department_id=department_id,
        include_approval=False,
    )
    return ChatMessagesListResponse(messages=messages)
