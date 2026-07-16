"""工作区 thread CRUD API（G2-1.1）：/ask/threads + /threads/{id}/messages。"""

from typing import Annotated
from uuid import UUID

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
)
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ask_common import (
    assert_has_visible_knowledge_bases,
    assert_team_business_allowed,
    citation_visible_in_scope,
)
from app.core.database import get_db
from app.core.deps import CurrentUser, DepartmentIdQuery, get_current_user
from app.models.enums import AgentMode, ThreadStatus
from app.schemas.chat import (
    ChatMessagesListResponse,
    ChatRequest,
    HistoryCitationPayload,
)
from app.schemas.thread import (
    ChatThreadCreateRequest,
    ChatThreadListResponse,
    ChatThreadPatchRequest,
    ChatThreadResponse,
)
from app.services.auth.api_rate_limit import ApiRateLimitKind, enforce_api_rate_limit
from app.services.org.scope import (
    can_user_adopt_in_workspace,
    resolve_org_scope_for_workspace,
)
from app.services.agent.dispatch import (
    build_workspace_tool_scope,
    create_edit_tool_planner,
    create_tool_planner,
)
from app.services.agent.stream import (
    stream_agent_edit_events,
    stream_agent_workspace_events,
)
from app.services.rag.chat import stream_workspace_chat_events
from app.services.rag.message_builder import SSE_HEADERS, build_chat_message_list
from app.services.rag.thread_generation_lock import (
    THREAD_GENERATION_BUSY_DETAIL,
    try_acquire_thread_generation_lock,
    wrap_stream_with_thread_generation_lock,
)
from app.services.rag.persistence import (
    list_workspace_chat_messages,
    save_workspace_chat_turn,
)
from app.services.rag.thread_persistence import (
    archive_workspace_thread,
    create_workspace_thread,
    export_thread_messages,
    get_thread_or_404,
    get_workspace_thread_for_user,
    hard_delete_message,
    list_workspace_threads,
    update_workspace_thread,
)
from app.services.workspace.scope import WorkspaceScope, resolve_workspace

router = APIRouter(prefix="/ask/threads", tags=["ask"])


async def _resolve_ask_scope(
    db: AsyncSession,
    current_user: CurrentUser,
    workspace: str | None,
    department_id: str | None,
) -> WorkspaceScope:
    scope = await resolve_workspace(db, current_user, workspace)
    assert_team_business_allowed(current_user, scope)
    return scope


def _thread_response(thread) -> ChatThreadResponse:
    return ChatThreadResponse.model_validate(thread)


async def _get_thread_or_404(
    db: AsyncSession,
    *,
    thread_id: UUID,
    current_user: CurrentUser,
    scope: WorkspaceScope,
    department_id: str | None,
) -> ChatThreadResponse:
    thread = await get_workspace_thread_for_user(
        db,
        thread_id=thread_id,
        user_id=current_user.id,
        workspace_kind=scope.kind,
        workspace_org_id=scope.org_id,
        department_id=department_id,
    )
    if thread is None:
        raise NotFoundError(detail="会话不存在")
    if thread.status == ThreadStatus.archived:
        raise NotFoundError(detail="会话不存在")
    return _thread_response(thread)


@router.get("", response_model=ChatThreadListResponse)
async def list_ask_threads(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    workspace: Annotated[str | None, Query(description="工作区：personal 或组织 UUID")] = None,
    department_id: DepartmentIdQuery = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ChatThreadListResponse:
    """当前 user + workspace scope 下的 workspace thread 列表。"""
    scope = await _resolve_ask_scope(db, current_user, workspace, department_id)
    rows = await list_workspace_threads(
        db,
        user_id=current_user.id,
        workspace_kind=scope.kind,
        workspace_org_id=scope.org_id,
        department_id=department_id,
        limit=limit,
    )
    return ChatThreadListResponse(threads=[_thread_response(row) for row in rows])


@router.post("", response_model=ChatThreadResponse, status_code=status.HTTP_201_CREATED)
async def create_ask_thread(
    body: ChatThreadCreateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    workspace: Annotated[str | None, Query(description="工作区：personal 或组织 UUID")] = None,
    department_id: DepartmentIdQuery = None,
) -> ChatThreadResponse:
    """新建空 thread（新建对话 · H2-3-A）。"""
    scope = await _resolve_ask_scope(db, current_user, workspace, department_id)
    thread = await create_workspace_thread(
        db,
        user_id=current_user.id,
        workspace_kind=scope.kind,
        workspace_org_id=scope.org_id,
        department_id=department_id,
        title=body.title,
    )
    return _thread_response(thread)


@router.patch("/{thread_id}", response_model=ChatThreadResponse)
async def patch_ask_thread(
    thread_id: UUID,
    body: ChatThreadPatchRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    workspace: Annotated[str | None, Query(description="工作区：personal 或组织 UUID")] = None,
    department_id: DepartmentIdQuery = None,
) -> ChatThreadResponse:
    """改 title 或归档 thread。"""
    scope = await _resolve_ask_scope(db, current_user, workspace, department_id)
    if body.title is None and body.status is None:
        raise BadRequestError(detail="至少提供 title 或 status")
    thread = await update_workspace_thread(
        db,
        thread_id=thread_id,
        user_id=current_user.id,
        workspace_kind=scope.kind,
        workspace_org_id=scope.org_id,
        department_id=department_id,
        title=body.title,
        status=body.status,
    )
    if thread is None:
        raise NotFoundError(detail="会话不存在")
    return _thread_response(thread)


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ask_thread(
    thread_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    workspace: Annotated[str | None, Query(description="工作区：personal 或组织 UUID")] = None,
    department_id: DepartmentIdQuery = None,
) -> None:
    """软删 thread（status=archived · H2-7-A）。"""
    scope = await _resolve_ask_scope(db, current_user, workspace, department_id)
    existing = await get_workspace_thread_for_user(
        db,
        thread_id=thread_id,
        user_id=current_user.id,
        workspace_kind=scope.kind,
        workspace_org_id=scope.org_id,
        department_id=department_id,
    )
    if existing is None or existing.status == ThreadStatus.archived:
        raise NotFoundError(detail="会话不存在")
    thread = await archive_workspace_thread(
        db,
        thread_id=thread_id,
        user_id=current_user.id,
        workspace_kind=scope.kind,
        workspace_org_id=scope.org_id,
        department_id=department_id,
    )
    if thread is None:
        raise NotFoundError(detail="会话不存在")


@router.post("/{thread_id}/chat")
async def post_ask_thread_chat(
    thread_id: UUID,
    body: ChatRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    workspace: Annotated[str | None, Query(description="工作区：personal 或组织 UUID")] = None,
    department_id: DepartmentIdQuery = None,
) -> StreamingResponse:
    """指定 thread 内工作区流式问答（G2-1.2 · 显式 thread_id 落库）。"""
    enforce_api_rate_limit(ApiRateLimitKind.chat, current_user.id)

    scope = await _resolve_ask_scope(db, current_user, workspace, department_id)
    await _get_thread_or_404(
        db,
        thread_id=thread_id,
        current_user=current_user,
        scope=scope,
        department_id=department_id,
    )

    org_scope = await resolve_org_scope_for_workspace(
        db, current_user, scope, department_id=department_id
    )
    await assert_has_visible_knowledge_bases(
        db, scope=scope, org_scope=org_scope, current_user=current_user
    )

    if not await try_acquire_thread_generation_lock(thread_id):
        raise ConflictError(
            detail=THREAD_GENERATION_BUSY_DETAIL,
        )

    sse_headers = SSE_HEADERS

    if body.mode == AgentMode.edit:
        # G4-2.3 · 编辑模式：/ask 跨库，目标库由 planner 运行时解析首个命中库。
        # fast/thorough 行为零改动（见 else/elif 分支）。
        stream = stream_agent_edit_events(
            db,
            user_id=current_user.id,
            message=body.message,
            thread_id=thread_id,
            workspace=scope,
            tool_scope=build_workspace_tool_scope(org_scope),
            planner=create_edit_tool_planner(body.message),
            org_scope=org_scope,
            workspace_mode=True,
            can_adopt=can_user_adopt_in_workspace(current_user, scope),
            save_turn=save_workspace_chat_turn,
            save_kwargs={
                "workspace_kind": scope.kind,
                "workspace_org_id": scope.org_id,
                "department_id": department_id,
                "thread_id": thread_id,
            },
        )
    elif body.mode == AgentMode.thorough:
        stream = stream_agent_workspace_events(
            db,
            scope=scope,
            org_scope=org_scope,
            user_id=current_user.id,
            message=body.message,
            department_id=department_id,
            thread_id=thread_id,
            tool_scope=build_workspace_tool_scope(org_scope),
            planner=create_tool_planner(body.message),
        )
    else:
        stream = stream_workspace_chat_events(
            db,
            scope=scope,
            org_scope=org_scope,
            user_id=current_user.id,
            message=body.message,
            department_id=department_id,
            thread_id=thread_id,
            hide_admin_only=(
                current_user.account_type.value == "enterprise"
                and current_user.org_role == "member"
            ),
        )

    return StreamingResponse(
        wrap_stream_with_thread_generation_lock(thread_id, stream),
        media_type="text/event-stream",
        headers=sse_headers,
    )


@router.get("/{thread_id}/messages", response_model=ChatMessagesListResponse)
async def get_ask_thread_messages(
    thread_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    workspace: Annotated[str | None, Query(description="工作区：personal 或组织 UUID")] = None,
    department_id: DepartmentIdQuery = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ChatMessagesListResponse:
    """按 thread 拉取工作区对话历史（替代 flat GET /ask/messages）。"""
    scope = await _resolve_ask_scope(db, current_user, workspace, department_id)
    await _get_thread_or_404(
        db,
        thread_id=thread_id,
        current_user=current_user,
        scope=scope,
        department_id=department_id,
    )

    rows = await list_workspace_chat_messages(
        db,
        user_id=current_user.id,
        workspace_kind=scope.kind,
        workspace_org_id=scope.org_id,
        department_id=department_id,
        limit=limit,
        thread_id=thread_id,
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
        include_approval=True,
    )
    return ChatMessagesListResponse(messages=messages)


@router.delete("/{thread_id}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ask_thread_message(
    thread_id: UUID,
    message_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """永久删除单条对话消息。"""
    deleted = await hard_delete_message(db, message_id=message_id, user_id=current_user.id)
    if not deleted:
        raise NotFoundError(detail="消息不存在")


@router.get("/{thread_id}/export")
async def export_ask_thread(
    thread_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """导出 thread 全部对话为 JSON 格式。"""
    messages = await export_thread_messages(db, thread_id, user_id=current_user.id)
    if messages is None:
        raise NotFoundError(detail="对话不存在")
    return {
        "thread_id": str(thread_id),
        "messages": [
            {
                "role": m.role.value,
                "content": m.content,
                "citations": m.citations,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }
