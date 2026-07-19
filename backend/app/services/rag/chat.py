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
                        scope=scope, org_scope=org_scope, skip_save=True)
    t0 = time.perf_counter()
    answer_parts: list[str] = []
    engine_citations: list[dict] = []
    async for event in engine.stream():
        if event["event"] == "token":
            answer_parts.append(event["data"]["text"])
        if event["event"] == "done":
            continue
        yield _sse_event(event["event"], event.get("data", {}))
        if event["event"] == "citations":
            engine_citations = event["data"]

    assistant_content = "".join(answer_parts)
    safe_out, reasons = output_safety_check(assistant_content)
    if settings.self_verify_enabled and assistant_content and engine.chunks:
        from app.services.rag.generation import verify_answer
        try:
            verified, corrected = await verify_answer(assistant_content, engine.chunks, message)
            if not verified and corrected:
                assistant_content = corrected
                yield _sse_event("correction", {"text": corrected})
        except Exception:
            pass
    if not safe_out:
        logger.warning("LLM 输出安全违规（workspace chat）: reasons=%s", reasons)

    retrieval_duration_ms = int((time.perf_counter() - t0) * 1000)
    message_id = uuid.uuid4()
    await save_workspace_chat_turn(
        db,
        user_id=user_id,
        workspace_kind=scope.kind,
        workspace_org_id=scope.org_id,
        department_id=department_id,
        user_content=message,
        assistant_content=assistant_content,
        citations=engine_citations,
        assistant_message_id=message_id,
        retrieval_duration_ms=retrieval_duration_ms,
        thread_id=thread_id,
    )
    yield _sse_event("done", {"message_id": str(message_id), "citations": engine_citations})
