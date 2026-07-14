"""库内 thread CRUD API（G2-1.3）：/knowledge-bases/{kb_id}/threads/*。"""

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
from app.models.enums import AgentMode, ThreadStatus
from app.models.knowledge_base import KnowledgeBase
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
from app.services.org.scope import can_user_adopt_kb, resolve_org_scope
from app.services.agent.dispatch import (
    build_kb_tool_scope,
    create_edit_tool_planner,
    create_tool_planner,
    workspace_scope_for_kb,
)
from app.services.agent.stream import (
    stream_agent_kb_edit_events,
    stream_agent_kb_events,
)
from app.services.rag.chat import stream_chat_events
from app.services.rag.thread_generation_lock import (
    THREAD_GENERATION_BUSY_DETAIL,
    try_acquire_thread_generation_lock,
    wrap_stream_with_thread_generation_lock,
)
from app.services.rag.citations import is_kb_visible_in_org_scope
from app.services.rag.message_builder import SSE_HEADERS, build_chat_message_list
from app.services.rag.persistence import list_chat_messages
from app.services.rag.thread_persistence import (
    archive_kb_thread,
    create_kb_thread,
    get_kb_thread_for_user,
    list_kb_threads,
    update_kb_thread,
)

router = APIRouter(
    prefix="/knowledge-bases/{kb_id}/threads",
    tags=["chat"],
)


def _thread_response(thread) -> ChatThreadResponse:
    return ChatThreadResponse.model_validate(thread)


async def _get_kb_thread_or_404(
    db: AsyncSession,
    *,
    kb_id: UUID,
    thread_id: UUID,
    current_user: CurrentUser,
) -> ChatThreadResponse:
    thread = await get_kb_thread_for_user(
        db,
        thread_id=thread_id,
        kb_id=kb_id,
        user_id=current_user.id,
    )
    if thread is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在",
        )
    if thread.status == ThreadStatus.archived:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在",
        )
    return _thread_response(thread)


async def _require_kb_read_access(
    db: AsyncSession,
    *,
    kb_id: UUID,
    current_user: CurrentUser,
    department_id: str | None,
) -> KnowledgeBase:
    kb = await require_kb_access(
        kb_id=kb_id,
        action=KbAction.read,
        current_user=current_user,
        db=db,
        department_id=department_id,
    )
    return kb


@router.get("", response_model=ChatThreadListResponse)
async def list_kb_threads_api(
    kb_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    department_id: DepartmentIdQuery = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ChatThreadListResponse:
    """当前 user + kb_id 下库内 thread 列表。"""
    await _require_kb_read_access(
        db, kb_id=kb_id, current_user=current_user, department_id=department_id
    )
    rows = await list_kb_threads(
        db,
        kb_id=kb_id,
        user_id=current_user.id,
        limit=limit,
    )
    return ChatThreadListResponse(threads=[_thread_response(row) for row in rows])


@router.post("", response_model=ChatThreadResponse, status_code=status.HTTP_201_CREATED)
async def create_kb_thread_api(
    kb_id: UUID,
    body: ChatThreadCreateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    department_id: DepartmentIdQuery = None,
) -> ChatThreadResponse:
    """新建空库内 thread（新建对话 · H2-3-A）。"""
    await _require_kb_read_access(
        db, kb_id=kb_id, current_user=current_user, department_id=department_id
    )
    thread = await create_kb_thread(
        db,
        kb_id=kb_id,
        user_id=current_user.id,
        title=body.title,
    )
    return _thread_response(thread)


@router.patch("/{thread_id}", response_model=ChatThreadResponse)
async def patch_kb_thread_api(
    kb_id: UUID,
    thread_id: UUID,
    body: ChatThreadPatchRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    department_id: DepartmentIdQuery = None,
) -> ChatThreadResponse:
    """改 title 或归档库内 thread。"""
    await _require_kb_read_access(
        db, kb_id=kb_id, current_user=current_user, department_id=department_id
    )
    if body.title is None and body.status is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="至少提供 title 或 status",
        )
    thread = await update_kb_thread(
        db,
        thread_id=thread_id,
        kb_id=kb_id,
        user_id=current_user.id,
        title=body.title,
        status=body.status,
    )
    if thread is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在",
        )
    return _thread_response(thread)


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kb_thread_api(
    kb_id: UUID,
    thread_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    department_id: DepartmentIdQuery = None,
) -> None:
    """软删库内 thread（status=archived · H2-7-A）。"""
    await _require_kb_read_access(
        db, kb_id=kb_id, current_user=current_user, department_id=department_id
    )
    existing = await get_kb_thread_for_user(
        db,
        thread_id=thread_id,
        kb_id=kb_id,
        user_id=current_user.id,
    )
    if existing is None or existing.status == ThreadStatus.archived:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在",
        )
    thread = await archive_kb_thread(
        db,
        thread_id=thread_id,
        kb_id=kb_id,
        user_id=current_user.id,
    )
    if thread is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在",
        )


@router.post("/{thread_id}/chat")
async def post_kb_thread_chat(
    kb_id: UUID,
    thread_id: UUID,
    body: ChatRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    department_id: DepartmentIdQuery = None,
) -> StreamingResponse:
    """指定 thread 内库内流式问答（G2-1.3 · 显式 thread_id 落库）。"""
    enforce_api_rate_limit(ApiRateLimitKind.chat, current_user.id)

    kb = await _require_kb_read_access(
        db, kb_id=kb_id, current_user=current_user, department_id=department_id
    )
    await _get_kb_thread_or_404(
        db,
        kb_id=kb_id,
        thread_id=thread_id,
        current_user=current_user,
    )

    if not await try_acquire_thread_generation_lock(thread_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=THREAD_GENERATION_BUSY_DETAIL,
        )

    org_scope = None
    visible_kb_ids: frozenset[UUID] | None = None
    if kb.owner_org_id is not None and kb.owner_user_id is None:
        org_scope = await resolve_org_scope(db, current_user, department_id=department_id)
        visible_kb_ids = org_scope.visible_kb_ids

    sse_headers = SSE_HEADERS

    if body.mode == AgentMode.edit:
        # G4-2.3 · 库内编辑：默认目标库 = 路径 kb（G4-E19 / H4-2-B）。
        # planner 经 default_kb_id 截断到路径 kb，generate_faq_draft 落到正确库。
        stream = stream_agent_kb_edit_events(
            db,
            kb_id=kb_id,
            user_id=current_user.id,
            message=body.message,
            thread_id=thread_id,
            workspace=workspace_scope_for_kb(kb, user_id=current_user.id),
            tool_scope=build_kb_tool_scope(kb_id, visible_kb_ids),
            planner=create_edit_tool_planner(body.message, default_kb_id=kb_id),
            org_scope=org_scope,
            can_adopt=can_user_adopt_kb(current_user, kb, org_scope),
        )
    elif body.mode == AgentMode.thorough:
        stream = stream_agent_kb_events(
            db,
            kb_id=kb_id,
            user_id=current_user.id,
            message=body.message,
            thread_id=thread_id,
            workspace=workspace_scope_for_kb(kb, user_id=current_user.id),
            tool_scope=build_kb_tool_scope(kb_id, visible_kb_ids),
            planner=create_tool_planner(body.message),
            org_scope=org_scope,
        )
    else:
        stream = stream_chat_events(
            db,
            kb_id=kb_id,
            user_id=current_user.id,
            message=body.message,
            visible_kb_ids=visible_kb_ids,
            thread_id=thread_id,
        )

    return StreamingResponse(
        wrap_stream_with_thread_generation_lock(thread_id, stream),
        media_type="text/event-stream",
        headers=sse_headers,
    )


@router.get("/{thread_id}/messages", response_model=ChatMessagesListResponse)
async def get_kb_thread_messages(
    kb_id: UUID,
    thread_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    department_id: DepartmentIdQuery = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ChatMessagesListResponse:
    """按 thread 拉取库内对话历史。"""
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

    await _get_kb_thread_or_404(
        db,
        kb_id=kb_id,
        thread_id=thread_id,
        current_user=current_user,
    )

    rows = await list_chat_messages(
        db,
        kb_id=kb_id,
        user_id=current_user.id,
        limit=limit,
        thread_id=thread_id,
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
