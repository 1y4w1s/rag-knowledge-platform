"""库内 thread CRUD API（G2-1.3）：/knowledge-bases/{kb_id}/threads/*。"""

from typing import Annotated
from uuid import UUID

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.request_ip import get_client_ip
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
    create_document_write_planner,
    create_edit_tool_planner,
    create_tool_planner,
    detect_write_intent,
    workspace_scope_for_kb,
)
from app.services.agent.stream import (
    stream_agent_document_write_events,
    stream_agent_kb_edit_events,
    stream_agent_kb_events,
)
from app.services.rag.chat import stream_chat_events
from app.services.rag.thread_generation_lock import (
    THREAD_GENERATION_BUSY_DETAIL,
    release_thread_generation_lock,
    try_acquire_thread_generation_lock,
    wrap_stream_with_thread_generation_lock,
)
from app.services.rag.citations import is_kb_visible_in_org_scope
from app.services.rag.message_builder import SSE_HEADERS, build_chat_message_list
from app.services.rag.persistence import list_chat_messages, save_chat_turn
from app.services.rag.thread_persistence import (
    archive_kb_thread,
    create_kb_thread,
    export_thread_messages,
    get_kb_thread_for_user,
    hard_delete_message,
    list_kb_threads,
    update_kb_thread,
)

router = APIRouter(
    prefix="/knowledge-bases/{kb_id}/threads",
    tags=["chat"],
)


def _agent_member_flag(current_user: CurrentUser) -> bool:
    """H1/M6：Agent 工具链 member 标志（enterprise Member → hide_admin_only）。"""
    return (
        current_user.account_type.value == "enterprise"
        and current_user.org_role == "member"
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
        raise NotFoundError(detail="会话不存在")
    if thread.status == ThreadStatus.archived:
        raise NotFoundError(detail="会话不存在")
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
        raise BadRequestError(detail="至少提供 title 或 status")
    thread = await update_kb_thread(
        db,
        thread_id=thread_id,
        kb_id=kb_id,
        user_id=current_user.id,
        title=body.title,
        status=body.status,
    )
    if thread is None:
        raise NotFoundError(detail="会话不存在")
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
        raise NotFoundError(detail="会话不存在")
    thread = await archive_kb_thread(
        db,
        thread_id=thread_id,
        kb_id=kb_id,
        user_id=current_user.id,
    )
    if thread is None:
        raise NotFoundError(detail="会话不存在")


@router.post("/{thread_id}/chat")
async def post_kb_thread_chat(
    kb_id: UUID,
    thread_id: UUID,
    request: Request,
    body: ChatRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    department_id: DepartmentIdQuery = None,
) -> StreamingResponse:
    """指定 thread 内库内流式问答（G2-1.3 · 显式 thread_id 落库）。"""
    await enforce_api_rate_limit(
        ApiRateLimitKind.chat, current_user.id, ip=get_client_ip(request)
    )

    kb = await _require_kb_read_access(
        db, kb_id=kb_id, current_user=current_user, department_id=department_id
    )
    await _get_kb_thread_or_404(
        db,
        kb_id=kb_id,
        thread_id=thread_id,
        current_user=current_user,
    )

    # H6（T4）：scope 解析与写权限门禁全部在锁之前完成——锁后仅做纯流构造，
    # 构造异常也由下方 try/except 释放锁，杜绝「获取锁后异常 → 永久 409」。
    org_scope = None
    visible_kb_ids: frozenset[UUID] | None = None
    if kb.owner_org_id is not None and kb.owner_user_id is None:
        org_scope = await resolve_org_scope(db, current_user, department_id=department_id)
        visible_kb_ids = org_scope.visible_kb_ids
    can_adopt_kb = can_user_adopt_kb(current_user, kb, org_scope)

    # G5 · 文档操作模式（库内）：仅 Admin/Owner 可进入（锁前 403，不占锁）
    if body.mode == AgentMode.document_write and not can_adopt_kb:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅知识库管理员可发起文档写操作",
        )

    if not await try_acquire_thread_generation_lock(thread_id):
        raise ConflictError(detail=THREAD_GENERATION_BUSY_DETAIL)

    sse_headers = SSE_HEADERS
    try:
        if body.mode == AgentMode.document_write:
            # G5 · 文档操作模式（库内）：默认目标库 = 路径 kb（同 G4-E19）。
            stream = stream_agent_document_write_events(
                db,
                kb_id=kb_id,
                user_id=current_user.id,
                message=body.message,
                thread_id=thread_id,
                workspace=workspace_scope_for_kb(kb, user_id=current_user.id),
                tool_scope=build_kb_tool_scope(
                    kb_id,
                    visible_kb_ids,
                    member=_agent_member_flag(current_user),
                ),
                planner=create_document_write_planner(body.message, default_kb_id=kb_id),
                org_scope=org_scope,
                current_user=current_user,
                can_adopt=True,
                save_turn=save_chat_turn,
                save_kwargs={"kb_id": kb_id, "thread_id": thread_id},
            )
        elif body.mode == AgentMode.edit:
            # G4-2.3 · 库内编辑：默认目标库 = 路径 kb（G4-E19 / H4-2-B）。
            stream = stream_agent_kb_edit_events(
                db,
                kb_id=kb_id,
                user_id=current_user.id,
                message=body.message,
                thread_id=thread_id,
                workspace=workspace_scope_for_kb(kb, user_id=current_user.id),
                tool_scope=build_kb_tool_scope(
                    kb_id,
                    visible_kb_ids,
                    member=_agent_member_flag(current_user),
                ),
                planner=create_edit_tool_planner(body.message, default_kb_id=kb_id),
                org_scope=org_scope,
                current_user=current_user,
                can_adopt=can_adopt_kb,
            )
        elif body.mode == AgentMode.thorough:
            stream = stream_agent_kb_events(
                db,
                kb_id=kb_id,
                user_id=current_user.id,
                message=body.message,
                thread_id=thread_id,
                workspace=workspace_scope_for_kb(kb, user_id=current_user.id),
                tool_scope=build_kb_tool_scope(
                    kb_id,
                    visible_kb_ids,
                    member=_agent_member_flag(current_user),
                ),
                planner=create_tool_planner(body.message, default_kb_id=kb_id),
                org_scope=org_scope,
                current_user=current_user,
            )
        else:
            # B 路径自动识别（fast 模式 · 仅库管理员）：命中写意图 → 文档操作/编辑流，
            # 否则普通库内问答。Member / 疑问句 / 无具体文档名 → 不触发（情景 4-7）。
            intent = (
                detect_write_intent(body.message) if can_adopt_kb else None
            )
            if intent is not None and intent.operation in ("delete", "restore"):
                stream = stream_agent_document_write_events(
                    db,
                    kb_id=kb_id,
                    user_id=current_user.id,
                    message=body.message,
                    thread_id=thread_id,
                    workspace=workspace_scope_for_kb(kb, user_id=current_user.id),
                    tool_scope=build_kb_tool_scope(
                        kb_id,
                        visible_kb_ids,
                        member=_agent_member_flag(current_user),
                    ),
                    planner=create_document_write_planner(
                        body.message, default_kb_id=kb_id
                    ),
                    org_scope=org_scope,
                    current_user=current_user,
                    can_adopt=True,
                    double_confirm=True,
                    save_turn=save_chat_turn,
                    save_kwargs={"kb_id": kb_id, "thread_id": thread_id},
                )
            elif intent is not None and intent.operation == "create":
                # 创建草稿 → 复用库内编辑流（generate_faq_draft → approval_required）
                stream = stream_agent_kb_edit_events(
                    db,
                    kb_id=kb_id,
                    user_id=current_user.id,
                    message=body.message,
                    thread_id=thread_id,
                    workspace=workspace_scope_for_kb(kb, user_id=current_user.id),
                    tool_scope=build_kb_tool_scope(
                        kb_id,
                        visible_kb_ids,
                        member=_agent_member_flag(current_user),
                    ),
                    planner=create_edit_tool_planner(
                        body.message, default_kb_id=kb_id
                    ),
                    org_scope=org_scope,
                    current_user=current_user,
                    can_adopt=can_adopt_kb,
                )
            else:
                stream = stream_chat_events(
                    db,
                    kb_id=kb_id,
                    user_id=current_user.id,
                    message=body.message,
                    visible_kb_ids=visible_kb_ids,
                    thread_id=thread_id,
                    hide_admin_only=(
                        current_user.account_type.value == "enterprise"
                        and current_user.org_role == "member"
                    ),
                )

        return StreamingResponse(
            wrap_stream_with_thread_generation_lock(thread_id, stream, request=request),
            media_type="text/event-stream",
            headers=sse_headers,
        )
    except BaseException:
        # H6：构造流阶段任何异常都释放锁（正常路径由 wrap_stream_... finally 释放）。
        await release_thread_generation_lock(thread_id)
        raise


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
        raise NotFoundError(detail="知识库不存在")

    _assert_kb_ownership(kb, current_user)
    await _assert_kb_action_allowed(
        current_user, KbAction.read, db=db, kb_id=kb_id
    )

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
        raise ForbiddenError(detail="无权访问该资料库")

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


@router.delete("/{thread_id}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kb_thread_message(
    thread_id: UUID,
    message_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    kb_id: UUID,
) -> None:
    """永久删除单条对话消息。"""
    deleted = await hard_delete_message(db, message_id=message_id, user_id=current_user.id)
    if not deleted:
        raise NotFoundError(detail="消息不存在")


@router.get("/{thread_id}/export")
async def export_kb_thread(
    thread_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    kb_id: UUID,
) -> dict:
    """导出 thread 全部对话为 JSON 格式。"""
    messages = await export_thread_messages(db, thread_id, user_id=current_user.id)
    if messages is None:
        raise NotFoundError(detail="对话不存在")
    return {
        "thread_id": str(thread_id),
        "kb_id": str(kb_id),
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
