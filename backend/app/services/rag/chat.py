"""RAG 对话编排：检索 → 相关性 gate → SSE → 落库（Wave 3.1～3.3 · E1 多轮 · A1 DWC）。

A1（DWC）：chat 两条写入路径（库内 / 工作区）统一收敛到 ``turn_writer.finalize_turn``
单一提交编排（user → assistant → run 终态 → 审计 → 一次 commit）；SSE generator 用
try/finally 兜底，断线/异常仍落库（P1-08）。预提交外壳：流开始前一次 commit
user 消息 + pending assistant，断线不丢问句。
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from functools import partial
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_thread import ChatThread
from app.models.enums import MessageStatus
from app.services.observability.metrics_registry import inc_chats_total
from app.services.org.scope import OrgScope
from app.services.rag.engine import ChatEngine
from app.services.rag.sse_concurrency import release_sse_slot, try_acquire_sse_slot
from app.services.workspace.scope import WorkspaceScope


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


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


async def _finalize_chat_turn(
    db: AsyncSession,
    *,
    thread: ChatThread,
    user_id: UUID,
    user_message_id: UUID,
    user_content: str,
    assistant_message_id: UUID,
    assistant_content: str,
    citations: list[dict],
    status: MessageStatus,
    common: dict,
    retrieval_duration_ms: int,
    audit: bool,
) -> UUID:
    """chat 路径经 turn_writer 收敛：消息 + 审计一次 commit（A1 DWC）。"""
    from app.services.audit.chat import audit_message_sent
    from app.services.rag.turn_writer import TurnMessage, finalize_turn

    audit_events: tuple = ()
    if audit:
        audit_events = (
            partial(
                audit_message_sent,
                thread=thread,
                actor_user_id=user_id,
                assistant_message_id=assistant_message_id,
                citation_count=len(citations),
                retrieval_ms=retrieval_duration_ms,
            ),
        )
    return await finalize_turn(
        db,
        thread=thread,
        user_id=user_id,
        user_msg=TurnMessage(content=user_content, message_id=user_message_id),
        assistant_msg=TurnMessage(
            content=assistant_content,
            citations=citations,
            status=status,
            message_id=assistant_message_id,
            retrieval_duration_ms=retrieval_duration_ms,
        ),
        common=common,
        audit_events=audit_events,
    )


async def _precommit_turn_shell(
    db: AsyncSession,
    *,
    thread: ChatThread,
    user_id: UUID,
    user_content: str,
    common: dict,
    pending_kwargs: dict,
) -> tuple[UUID, UUID]:
    """预提交外壳（P1-08）：user 消息 + pending assistant 一次 commit。

    返回 (user_message_id, pending_assistant_id)。断线后问句与占位 assistant
    均已落库，后续 finalize_turn 原地收尾。
    """
    from app.models.chat_message import ChatMessage as ChatMessageModel
    from app.models.enums import MessageRole
    from app.services.rag.persistence import create_pending_message

    # user 消息先以 pending 态预提交：多轮历史加载会过滤 pending，避免本轮消息
    # 污染检索上下文（E1）；finalize_turn 原地完成化。
    user_row = ChatMessageModel(
        **common,
        role=MessageRole.user,
        content=user_content,
        status=MessageStatus.pending,
        citations=None,
    )
    db.add(user_row)
    pending_msg = await create_pending_message(
        db,
        thread_id=thread.id,
        user_id=user_id,
        query=user_content,
        **pending_kwargs,
    )
    await db.commit()
    return user_row.id, pending_msg.id


async def _run_chat_stream(
    db: AsyncSession,
    *,
    engine: ChatEngine,
    thread: ChatThread,
    user_id: UUID,
    user_message_id: UUID,
    user_content: str,
    assistant_message_id: UUID,
    common: dict,
    t0: float,
) -> AsyncIterator[str]:
    """库内/工作区共用 SSE 流式循环 + A1 DWC 兜底落库。

    try/finally：正常完成 / 断线（GeneratorExit）/ 异常均收敛到 finalize_turn
    单一提交；断开或异常时保存已生成 partial（P1-08），并释放 SSE slot。
    """
    done_yielded = False
    safety_blocked = False
    answer_parts: list[str] = []
    try:
        async for event in engine.stream():
            if event["event"] == "error":
                safety_blocked = True
            if event["event"] == "token":
                answer_parts.append(event["data"].get("text", ""))
            if event["event"] == "done":
                done_yielded = True
                event["data"]["message_id"] = str(assistant_message_id)
            yield _sse_event(event["event"], event.get("data", {}))
    except GeneratorExit:
        raise
    finally:
        status = MessageStatus.completed if done_yielded else MessageStatus.interrupted
        content = "" if safety_blocked else ("".join(answer_parts) or engine.collected_text)
        await _finalize_chat_turn(
            db,
            thread=thread,
            user_id=user_id,
            user_message_id=user_message_id,
            user_content=user_content,
            assistant_message_id=assistant_message_id,
            assistant_content=content,
            citations=list(engine.citations) if engine.citations else [],
            status=status,
            common=common,
            retrieval_duration_ms=int((time.perf_counter() - t0) * 1000),
            audit=done_yielded,
        )
        await release_sse_slot(user_id)


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
    """库内 fast SSE：citation → token → done；thread 内多轮记忆（A1 DWC）。"""
    inc_chats_total()

    # 用户级 SSE 并发限制
    if not await try_acquire_sse_slot(user_id):
        raise asyncio.CancelledError("SSE concurrency limit exceeded")

    from app.models.enums import ThreadKind
    from app.services.rag.thread_persistence import resolve_thread_for_message

    thread = await resolve_thread_for_message(
        db,
        thread_id=thread_id,
        thread_kind=ThreadKind.knowledge_base,
        kb_id=kb_id,
        user_id=user_id,
    )
    common = {
        "thread_kind": ThreadKind.knowledge_base,
        "kb_id": kb_id,
        "user_id": user_id,
        "thread_id": thread.id,
    }
    user_message_id, assistant_message_id = await _precommit_turn_shell(
        db,
        thread=thread,
        user_id=user_id,
        user_content=message,
        common=common,
        pending_kwargs={
            "thread_kind": ThreadKind.knowledge_base,
            "kb_id": kb_id,
        },
    )

    engine = ChatEngine(
        db,
        user_id=user_id,
        message=message,
        kb_id=kb_id,
        thread_id=thread_id or thread.id,
        visible_kb_ids=visible_kb_ids,
        hide_admin_only=hide_admin_only,
        skip_save=True,
        assistant_message_id=assistant_message_id,
    )
    stream = _run_chat_stream(
        db,
        engine=engine,
        thread=thread,
        user_id=user_id,
        user_message_id=user_message_id,
        user_content=message,
        assistant_message_id=assistant_message_id,
        common=common,
        t0=time.perf_counter(),
    )
    try:
        async for frame in stream:
            yield frame
    finally:
        # 外层 GeneratorExit（客户端断开）不会自动传入内层生成器；
        # 显式 aclose 让 _run_chat_stream 的 try/finally 兜底落库（P1-08）。
        await stream.aclose()


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
    """工作区 fast SSE：跨库检索 → engine 编排 → workspace 落库（A1 DWC）。"""
    inc_chats_total()

    # 用户级 SSE 并发限制
    if not await try_acquire_sse_slot(user_id):
        raise asyncio.CancelledError("SSE concurrency limit exceeded")

    from app.models.enums import ThreadKind
    from app.services.rag.thread_persistence import (
        normalize_workspace_department_key,
        resolve_thread_for_message,
    )

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
    common = {
        "thread_kind": ThreadKind.workspace,
        "kb_id": None,
        "user_id": user_id,
        "workspace_kind": scope.kind.value,
        "workspace_org_id": scope.org_id,
        "workspace_department_key": department_key,
        "thread_id": thread.id,
    }
    user_message_id, assistant_message_id = await _precommit_turn_shell(
        db,
        thread=thread,
        user_id=user_id,
        user_content=message,
        common=common,
        pending_kwargs={
            "thread_kind": ThreadKind.workspace,
            "workspace_kind": scope.kind.value,
            "workspace_org_id": scope.org_id,
            "workspace_department_key": department_key,
        },
    )

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
    stream = _run_chat_stream(
        db,
        engine=engine,
        thread=thread,
        user_id=user_id,
        user_message_id=user_message_id,
        user_content=message,
        assistant_message_id=assistant_message_id,
        common=common,
        t0=time.perf_counter(),
    )
    try:
        async for frame in stream:
            yield frame
    finally:
        await stream.aclose()
