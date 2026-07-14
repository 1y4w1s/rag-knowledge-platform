"""RAG 对话编排：检索 → 相关性 gate → SSE → 落库（Wave 3.1～3.3）。"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rag.generation import (
    build_messages,
    compress_history,
    contextualize_query,
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
    chunk_to_citation,
    retrieve_chunks,
    retrieve_workspace_chunks,
    workspace_chunk_to_citation,
)
from app.services.workspace.scope import WorkspaceScope


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

    # 2. 将最新问题改写为独立检索查询（带历史上下文）
    retrieval_query = await contextualize_query(message, history) if history else message

    t0 = time.perf_counter()
    raw_chunks = await retrieve_chunks(
        db,
        kb_id=kb_id,
        query=retrieval_query,
        visible_kb_ids=visible_kb_ids,
        hide_admin_only=hide_admin_only,
    )
    retrieval_duration_ms = int((time.perf_counter() - t0) * 1000)
    chunks = filter_relevant_chunks(raw_chunks, retrieval_query)
    chunks = dedup_and_compress(chunks)
    citations = [chunk_to_citation(c) for c in chunks]

    for citation in citations:
        yield _sse_event("citation", citation)

    # 3. 历史压缩（超过 6 轮时压缩早期对话）
    compressed = await compress_history(history) if history else None

    # 4. Fast mode tool call：空检索时改写查询重试一次
    if not chunks:
        rewritten = await rewrite_query(retrieval_query)
        if rewritten:
            raw_chunks = await retrieve_chunks(
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
        token_stream = stream_deepseek_tokens(messages)
    else:
        token_stream = stream_no_context_reply(message)

    token_parts: list[str] = []
    async for text in token_stream:
        if text:
            token_parts.append(text)
            yield _sse_event("token", {"text": text})

    assistant_content = "".join(token_parts)
    message_id = uuid.uuid4()
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
    t0 = time.perf_counter()
    raw_chunks = await retrieve_workspace_chunks(
        db,
        query=message,
        scope=scope,
        org_scope=org_scope,
        hide_admin_only=hide_admin_only,
    )
    retrieval_duration_ms = int((time.perf_counter() - t0) * 1000)
    chunks = filter_relevant_chunks(raw_chunks, message)
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
            raw_chunks = await retrieve_workspace_chunks(
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
