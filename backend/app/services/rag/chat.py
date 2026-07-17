"""RAG 对话编排：检索 → 相关性 gate → SSE → 落库（Wave 3.1～3.3）。"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rag.generation import (
    build_messages,
    compress_history,
    contextualize_query,
    decompose_query,
    expand_queries,
    rewrite_query,
    stream_deepseek_tokens,
    stream_no_context_reply,
)
from app.services.org.scope import OrgScope
from app.services.rag.persistence import (
    list_thread_messages,
    save_chat_turn,
    save_workspace_chat_turn,
)
from app.services.rag.relevance import filter_relevant_chunks
from app.services.rag.dedup import dedup_and_compress
from app.services.rag.retrieval import (
    RetrievedChunk,
    chunk_to_citation,
    retrieve_chunks,
    retrieve_workspace_chunks,
    workspace_chunk_to_citation,
)
from app.services.rag.safety_filter import input_safety_check, output_safety_check
from app.core.otel import get_tracer
from app.core.config import settings
from app.core.degradation import (
    assess_degradation,
    degradation_label,
    degradation_message,
)
from app.services.workspace.scope import WorkspaceScope

logger = logging.getLogger(__name__)

# 问候/闲聊查询（无需检索，直接 LLM）
_GREETING_PATTERNS = frozenset({
    "你好", "您好", "嗨", "hello", "hi", "hey",
    "谢谢", "感谢", "thank",
    "再见", "拜拜", "bye",
    "在吗", "在不在",
    "你是谁", "你叫什么",
})


def _is_greeting(query: str) -> bool:
    """判断用户输入是否为问候/闲聊（无需检索）。"""
    q = query.strip().lower()
    if len(q) <= 2:
        return True
    if len(q) <= 4 and q in _GREETING_PATTERNS:
        return True
    if q in _GREETING_PATTERNS:
        return True
    return False


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _timed_retrieve_chunks(db: AsyncSession, *, kb_id: UUID, query: str, visible_kb_ids: frozenset[UUID] | None = None, hide_admin_only: bool = False, top_k: int = 5) -> list:
    """retrieve_chunks 的超时包装。"""
    return await asyncio.wait_for(
        retrieve_chunks(db, kb_id=kb_id, query=query, top_k=top_k, visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only),
        timeout=settings.retrieval_timeout_seconds,
    )


async def _timed_retrieve_workspace_chunks(db: AsyncSession, *, query: str, scope: object, org_scope: object | None = None, hide_admin_only: bool = False, top_k: int = 5) -> list:
    """retrieve_workspace_chunks 的超时包装。"""
    return await asyncio.wait_for(
        retrieve_workspace_chunks(db, query=query, scope=scope, org_scope=org_scope, top_k=top_k, hide_admin_only=hide_admin_only),
        timeout=settings.retrieval_timeout_seconds,
    )


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
    """生成 SSE 帧：citation → token → done；无依据走拒绝分支；结束后落库。

    多轮上下文整合：先加载历史，将最新问题改写为独立检索查询后再检索。
    """
    # 1. 加载对话历史（多轮上下文记忆）
    history = None
    if thread_id is not None:
        history_rows = await list_thread_messages(db, thread_id=thread_id, user_id=user_id)
        if history_rows:
            history = [
                {"role": msg.role.value, "content": msg.content}
                for msg in history_rows
            ]

    # 1.5 输入安全过滤
    is_safe, block_reply = input_safety_check(message)
    if not is_safe:
        token_stream = stream_no_context_reply(block_reply)
        async for text in token_stream:
            if text:
                yield _sse_event("token", {"text": text})
        message_id = uuid.uuid4()
        await save_chat_turn(
            db, kb_id=kb_id, user_id=user_id,
            user_content=message, assistant_content=block_reply,
            citations=[], assistant_message_id=message_id,
            retrieval_duration_ms=0, thread_id=thread_id,
        )
        yield _sse_event("done", {"message_id": str(message_id), "citations": []})
        return

    # 1.75 降级评估：检查外部服务健康状况
    deg_level = assess_degradation()
    if deg_level >= 4:  # ALL_DOWN
        msg = degradation_message(deg_level)
        for char in msg:
            yield _sse_event("token", {"text": char})
        message_id = uuid.uuid4()
        await save_chat_turn(
            db, kb_id=kb_id, user_id=user_id,
            user_content=message, assistant_content=msg,
            citations=[], assistant_message_id=message_id,
            retrieval_duration_ms=0, thread_id=thread_id,
        )
        yield _sse_event("done", {"message_id": str(message_id), "citations": []})
        return
    logger.debug("降级等级: %s (L%d)", degradation_label(deg_level), int(deg_level))

    # 1.9 问候/闲聊查询 → 跳过检索，直接 LLM
    if _is_greeting(message):
        token_stream = stream_no_context_reply(message)
        async for text in token_stream:
            if text:
                yield _sse_event("token", {"text": text})
        message_id = uuid.uuid4()
        await save_chat_turn(
            db, kb_id=kb_id, user_id=user_id,
            user_content=message, assistant_content="".join(token_parts) if 'token_parts' in dir() else "".join([t async for t in stream_no_context_reply(message)])[:100],
            citations=[], assistant_message_id=message_id,
            retrieval_duration_ms=0, thread_id=thread_id,
        )
        yield _sse_event("done", {"message_id": str(message_id), "citations": []})
        return

    # 2. 将最新问题改写为独立检索查询（带历史上下文）
    retrieval_query = await contextualize_query(message, history) if history else message

    t0 = time.perf_counter()
    with get_tracer().start_as_current_span("rag.retrieve") as span:
        raw_chunks = await _timed_retrieve_chunks(
            db,
            kb_id=kb_id,
            query=retrieval_query,
            visible_kb_ids=visible_kb_ids,
            hide_admin_only=hide_admin_only,
        )
        span.set_attribute("kb_id", str(kb_id))
        span.set_attribute("chunk_count", len(raw_chunks))
    retrieval_duration_ms = int((time.perf_counter() - t0) * 1000)

    # 2.5 跨段 Query Rewrite：复合问题拆分子查询多路召回
    with get_tracer().start_as_current_span("rag.decompose_query"):
        sub_queries = await decompose_query(retrieval_query)
    if len(sub_queries) > 1:
        seen_ids: set[uuid.UUID] = set()
        merged: list[RetrievedChunk] = []
        for sq in sub_queries:
            if sq.lower().strip() == retrieval_query.lower().strip():
                continue
            sq_chunks = await _timed_retrieve_chunks(
                db, kb_id=kb_id, query=sq,
                visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only,
            )
            for c in sq_chunks:
                if c.chunk_id not in seen_ids:
                    seen_ids.add(c.chunk_id)
                    merged.append(c)
        if merged:
            raw_chunks = raw_chunks + merged

    with get_tracer().start_as_current_span("rag.filter_relevant"):
        chunks = filter_relevant_chunks(raw_chunks, retrieval_query)
        chunks = dedup_and_compress(chunks)
    citations = [chunk_to_citation(c) for c in chunks]

    for citation in citations:
        yield _sse_event("citation", citation)

    # 3. 历史压缩（超过 6 轮时压缩早期对话）
    with get_tracer().start_as_current_span("rag.history_compress"):
        compressed = await compress_history(history) if history else None

    # 4. Fast mode tool call：空检索时改写查询重试一次
    if not chunks:
        rewritten = await rewrite_query(retrieval_query)
        if rewritten:
            raw_chunks = await _timed_retrieve_chunks(
                db,
                kb_id=kb_id,
                query=rewritten,
                visible_kb_ids=visible_kb_ids,
                hide_admin_only=hide_admin_only,
            )
            chunks = filter_relevant_chunks(raw_chunks, rewritten)
            chunks = dedup_and_compress(chunks)
            if chunks:
                citations = [chunk_to_citation(c) for c in chunks]
                for citation in citations:
                    yield _sse_event("citation", citation)

    # 5. 用原始消息构造 prompt（保留对话中的指代和口语表达）
    if chunks:
        messages = build_messages(message, chunks, history=history, compressed_summary=compressed)
        with get_tracer().start_as_current_span("rag.llm_generate"):
            token_stream = stream_deepseek_tokens(messages)
    else:
        token_stream = stream_no_context_reply(message)

    token_parts: list[str] = []
    async for text in token_stream:
        if text:
            token_parts.append(text)
            yield _sse_event("token", {"text": text})

    assistant_content = "".join(token_parts)
    # 输出安全审计（已发送的 token 无法撤回，但可记录告警）
    safe_out, reasons = output_safety_check(assistant_content)
    if not safe_out:
        logger.warning("LLM 输出安全违规: reasons=%s", reasons)
    message_id = uuid.uuid4()
    with get_tracer().start_as_current_span("rag.save_turn"):
        await save_chat_turn(
            db,
            kb_id=kb_id,
            user_id=user_id,
            user_content=message,
            assistant_content=assistant_content,
            citations=citations,
            assistant_message_id=message_id,
            retrieval_duration_ms=retrieval_duration_ms,
            thread_id=thread_id,
        )

    yield _sse_event(
        "done",
        {
            "message_id": str(message_id),
            "citations": citations,
        },
    )


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
    """工作区对话：跨库检索 → gate → SSE（含 kb_name）→ workspace 落库。"""
    expanded = await expand_queries(message)
    all_chunks: list[RetrievedChunk] = []
    seen_chunk_ids: set[UUID] = set()
    t0 = time.perf_counter()
    for eq in expanded:
        raw = await _timed_retrieve_workspace_chunks(
            db, query=eq, scope=scope,
            org_scope=org_scope, hide_admin_only=hide_admin_only,
        )
        for c in raw:
            if c.chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(c.chunk_id)
                all_chunks.append(c)
    retrieval_duration_ms = int((time.perf_counter() - t0) * 1000)
    chunks = filter_relevant_chunks(all_chunks, message)
    chunks = dedup_and_compress(chunks)
    citations = [workspace_chunk_to_citation(c) for c in chunks]

    for citation in citations:
        yield _sse_event("citation", citation)

    # 加载对话历史（多轮上下文记忆）
    history = None
    if thread_id is not None:
        history_rows = await list_thread_messages(db, thread_id=thread_id, user_id=user_id)
        if history_rows:
            history = [
                {"role": msg.role.value, "content": msg.content}
                for msg in history_rows
            ]

    # Fast mode tool call：空检索时改写查询重试一次
    if not chunks:
        rewritten = await rewrite_query(message)
        if rewritten:
            raw_chunks = await _timed_retrieve_workspace_chunks(
                db,
                query=rewritten,
                scope=scope,
                org_scope=org_scope,
                hide_admin_only=hide_admin_only,
            )
            chunks = filter_relevant_chunks(raw_chunks, rewritten)
            chunks = dedup_and_compress(chunks)
            if chunks:
                citations = [workspace_chunk_to_citation(c) for c in chunks]
                for citation in citations:
                    yield _sse_event("citation", citation)

    compressed = await compress_history(history) if history else None

    if chunks:
        compressed = await compress_history(history) if history else None
        messages = build_messages(message, chunks, history=history, compressed_summary=compressed)
        token_stream = stream_deepseek_tokens(messages)
    else:
        token_stream = stream_no_context_reply(message)

    token_parts: list[str] = []
    async for text in token_stream:
        if text:
            token_parts.append(text)
            yield _sse_event("token", {"text": text})

    assistant_content = "".join(token_parts)
    safe_out, reasons = output_safety_check(assistant_content)
    if not safe_out:
        logger.warning("LLM 输出安全违规（workspace chat）: reasons=%s", reasons)
    message_id = uuid.uuid4()
    await save_workspace_chat_turn(
        db,
        user_id=user_id,
        workspace_kind=scope.kind,
        workspace_org_id=scope.org_id,
        department_id=department_id,
        user_content=message,
        assistant_content=assistant_content,
        citations=citations,
        assistant_message_id=message_id,
        retrieval_duration_ms=retrieval_duration_ms,
        thread_id=thread_id,
    )

    yield _sse_event(
        "done",
        {
            "message_id": str(message_id),
            "citations": citations,
        },
    )
