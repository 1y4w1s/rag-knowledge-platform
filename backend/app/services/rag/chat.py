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

from app.services.rag.engine import ChatEngine
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
    """生成 SSE 帧：citation → token → done；无依据走拒绝分支；结束后落库。"""
    engine = ChatEngine(db, user_id=user_id, message=message, kb_id=kb_id, thread_id=thread_id)
    async for event in engine.stream():
        yield _sse_event(event["event"], event.get("data", {}))
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
    engine = ChatEngine(db, user_id=user_id, message=message, thread_id=thread_id,
                        scope=scope, org_scope=org_scope)
    async for event in engine.stream():
        yield _sse_event(event["event"], event.get("data", {}))
    retrieval_query = message
    if thread_id is not None:
        history_rows = await list_thread_messages(db, thread_id=thread_id, user_id=user_id)
        if history_rows:
            history = [
                {"role": msg.role.value, "content": msg.content}
                for msg in history_rows
            ]
            retrieval_query = await contextualize_query(message, history) if history else message

    expanded = await expand_queries(retrieval_query)
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
    chunks = filter_relevant_chunks(all_chunks, retrieval_query)
    chunks = dedup_and_compress(chunks)
    citations = [workspace_chunk_to_citation(c) for c in chunks]

    for citation in citations:
        yield _sse_event("citation", citation)

    # 加载对话历史（多轮上下文记忆）
    # Fast mode tool call：空检索时改写查询重试一次
    if not chunks:
        rewritten = await rewrite_query(retrieval_query)
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

    # 自验证：检查生成内容是否与检索片段一致（配置开关）
    if settings.self_verify_enabled and chunks:
        try:
            from app.services.rag.generation import verify_answer
            verified, corrected = await verify_answer(assistant_content, chunks, message)
            if not verified and corrected:
                logger.info("自验证修正: case_id=%s", message[:30])
                assistant_content = corrected
                # 重发修正后的 content 覆盖
                yield _sse_event("correction", {"text": corrected})
        except Exception as e:
            logger.warning("自验证异常: %s", e)

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
