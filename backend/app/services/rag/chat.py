"""RAG 对话编排：检索 → 相关性 gate → SSE → 落库（Wave 3.1～3.3 · E1 多轮）。"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.observability.metrics_registry import inc_chats_total
from app.services.org.scope import OrgScope
from app.services.rag.engine import ChatEngine
from app.services.rag.generation import verify_answer
from app.services.rag.persistence import save_workspace_chat_turn
from app.services.rag.safety_filter import output_safety_check
from app.services.rag.sse_concurrency import try_acquire_sse_slot, release_sse_slot


async def _with_sse_slot(
    user_id: UUID,
    stream: AsyncIterator[str],
) -> AsyncIterator[str]:
    """SSE 流式包装：持有 slot 期间流式输出，结束后释放。"""
    slot_ok = await try_acquire_sse_slot(user_id)
    if not slot_ok:
        yield _sse_event("error", {"detail": "同时进行的对话过多，请等待当前对话完成"})
        return
    try:
        async for item in stream:
            yield item
    finally:
        await release_sse_slot(user_id)
from app.services.workspace.scope import WorkspaceScope

logger = logging.getLogger(__name__)


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def stream_chat_events(
    db: AsyncSession,
    *,
    kb_id: UUID,
    user_id: UUID,
    message: str,
    visible_kb_ids: frozenset[UUID] | None = None,
    thread_id: UUID | None = None,
    hide_admin_only: bool = False,
) -> AsyncIterator[str]:
    """库内 fast SSE：citation → token → done；thread 内多轮记忆。"""
    inc_chats_total()

    # 用户级 SSE 并发限制
    if not await try_acquire_sse_slot(user_id):
        raise asyncio.CancelledError("SSE concurrency limit exceeded")

    # 提前落库 pending 消息（SSE 中断时保留已生成内容）
    from app.services.rag.persistence import create_pending_message, finalize_message
    from app.models.enums import MessageStatus, ThreadKind
    from app.services.rag.thread_persistence import resolve_thread_for_message

    thread = await resolve_thread_for_message(
        db,
        thread_id=thread_id,
        thread_kind=ThreadKind.knowledge_base,
        kb_id=kb_id,
        user_id=user_id,
    )
    pending_msg = await create_pending_message(
        db,
        thread_id=thread.id,
        user_id=user_id,
        query=message,
        thread_kind=ThreadKind.knowledge_base,
        kb_id=kb_id,
    )
    assistant_message_id = pending_msg.id
    await db.commit()

    engine = ChatEngine(
        db,
        user_id=user_id,
        message=message,
        kb_id=kb_id,
        thread_id=thread_id or thread.id,
        visible_kb_ids=visible_kb_ids,
        hide_admin_only=hide_admin_only,
        assistant_message_id=assistant_message_id,
    )
    try:
        async for event in engine.stream():
            yield _sse_event(event["event"], event.get("data", {}))
    except GeneratorExit:
        # SSE 中断 → 保存已生成的 partial answer
        partial = engine.collected_text
        if partial:
            await finalize_message(
                db, assistant_message_id,
                content=partial,
                citations=list(engine.citations) if engine.citations else [],
                status=MessageStatus.interrupted,
            )
        raise
    finally:
        await release_sse_slot(user_id)


async def stream_workspace_chat_events(
    db: AsyncSession,
    *,
    scope: WorkspaceScope,
    org_scope: OrgScope | None,
    user_id: UUID,
    message: str,
    department_id: str | None,
    thread_id: UUID | None = None,
    hide_admin_only: bool = False,
) -> AsyncIterator[str]:
    """工作区 fast SSE：跨库检索 → engine 编排 → workspace 落库。"""
    inc_chats_total()

    # 提前落库 pending 消息（防止 SSE 中断后丢问句）
    from app.services.rag.persistence import (
        create_pending_message,
        finalize_message,
    )
    from app.services.rag.thread_persistence import (
        resolve_thread_for_message,
        normalize_workspace_department_key,
    )
    from app.models.enums import MessageStatus, ThreadKind

    department_key = normalize_workspace_department_key(department_id)
    thread = await resolve_thread_for_message(
        db,
        thread_id=thread_id,
        thread_kind=ThreadKind.workspace,
        kb_id=None,
        user_id=user_id,
        workspace_kind=scope.kind,
        workspace_org_id=scope.org_id,
        department_key=department_key,
    )
    pending_msg = await create_pending_message(
        db,
        thread_id=thread.id,
        user_id=user_id,
        query=message,
        thread_kind=ThreadKind.workspace,
        workspace_kind=scope.kind.value,
        workspace_org_id=scope.org_id,
        workspace_department_key=department_key,
    )
    assistant_message_id = pending_msg.id

    engine = ChatEngine(
        db,
        user_id=user_id,
        message=message,
        thread_id=thread_id,
        scope=scope,
        org_scope=org_scope,
        skip_save=True,
        hide_admin_only=hide_admin_only,
        assistant_message_id=assistant_message_id,
    )
    t0 = time.perf_counter()
    answer_parts: list[str] = []
    try:
        async for event in engine.stream():
            if event["event"] == "token":
                answer_parts.append(event["data"].get("text", ""))
            if event["event"] == "done":
                continue
            yield _sse_event(event["event"], event.get("data", {}))
    except GeneratorExit:
        # SSE 中断 → 保存已生成的 partial answer
        partial = engine.collected_text or "".join(answer_parts)
        if partial:
            await finalize_message(
                db, assistant_message_id,
                content=partial,
                citations=list(engine.citations) if engine.citations else [],
                status=MessageStatus.interrupted,
                retrieval_duration_ms=int((time.perf_counter() - t0) * 1000),
            )
        raise  # 继续传播 GeneratorExit

    assistant_content = "".join(answer_parts)
    citations = list(engine.citations)
    safe_out, reasons = output_safety_check(assistant_content)
    if settings.self_verify_enabled and assistant_content and engine.chunks:
        try:
            verified, corrected = await verify_answer(
                assistant_content, engine.chunks, message
            )
            if not verified and corrected:
                assistant_content = corrected
                yield _sse_event("correction", {"text": corrected})
        except Exception:
            pass
    if not safe_out:
        logger.warning("LLM 输出安全违规（workspace chat）: reasons=%s", reasons)

    # 使用预创建的 pending message_id，避免重复创建
    await finalize_message(
        db, assistant_message_id,
        content=assistant_content,
        citations=citations,
        status=MessageStatus.completed,
        retrieval_duration_ms=int((time.perf_counter() - t0) * 1000),
    )

    # 同时创建 user 消息
    from app.models.chat_message import ChatMessage as ChatMessageModel
    db.add(ChatMessageModel(
        thread_kind=ThreadKind.workspace,
        kb_id=None,
        user_id=user_id,
        thread_id=thread.id,
        role=MessageRole.user,
        content=message,
        status=MessageStatus.completed,
        workspace_kind=scope.kind.value,
        workspace_org_id=scope.org_id,
        workspace_department_key=department_key,
    ))
    await db.commit()

    yield _sse_event(
        "done",
        {"message_id": str(assistant_message_id), "citations": citations},
    )
