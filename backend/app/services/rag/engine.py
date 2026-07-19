"""RAG 对话编排引擎 — 合并 KB 版和 Workspace 版公共逻辑。"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any, Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MessageRole
from app.services.rag.citations import resolve_citation
from app.services.rag.dedup import dedup_and_compress
from app.services.rag.generation import (
    build_messages,
    compress_history,
    expand_queries,
    no_context_reply_for,
    stream_deepseek_tokens,
)
from app.services.rag.persistence import save_chat_turn
from app.services.rag.relevance import filter_relevant_chunks, should_refuse_answer
from app.services.rag.retrieval import chunk_to_citation, retrieve_chunks, retrieve_workspace_chunks
from app.services.rag.safety_filter import output_safety_check
from app.services.rag.persistence import list_thread_messages, save_chat_turn
from app.core.config import settings

logger = logging.getLogger(__name__)


class ChatEngine:
    """RAG 对话编排引擎。

    提供stream_chat_events 和 stream_workspace_chat_events 的公共编排逻辑。
    通过 ChatConfig 控制检索范围、引文格式等差异。
    """

    def __init__(
        self,
        db: AsyncSession,
        user_id: UUID,
        message: str,
        workspace: str = "personal",
        kb_id: UUID | None = None,
        thread_id: UUID | None = None,
        scope=None,
        org_scope=None,
        skip_save: bool = False,
    ):
        self.db = db
        self.user_id = user_id
        self.message = message
        self.workspace = workspace
        self.kb_id = kb_id
        self.thread_id = thread_id
        self.scope = scope
        self.org_scope = org_scope
        self.retrieval_query = message
        self.history = None
        self.chunks: list = []
        self.citations: list[dict] = []
        self.skip_save = skip_save

    def _is_workspace(self) -> bool:
        return self.scope is not None

    async def _load_history(self) -> None:
        """加载多轮对话历史并改写查询。"""
        if self.thread_id is None:
            return
        from app.services.rag.generation import contextualize_query
        rows = await list_thread_messages(self.db, thread_id=self.thread_id, user_id=self.user_id)
        if rows:
            self.history = [
                {"role": msg.role.value, "content": msg.content}
                for msg in rows
            ]
            self.retrieval_query = await contextualize_query(self.message, self.history)

    async def _retrieve(self) -> list:
        """执行检索。"""
        if self._is_workspace():
            all_chunks = await retrieve_workspace_chunks(
                self.db, scope=self.scope, org_scope=self.org_scope,
                query=self.retrieval_query, top_k=settings.llm_top_k,
            )
        else:
            all_chunks = await retrieve_chunks(
                self.db, kb_id=self.kb_id, query=self.retrieval_query, top_k=settings.llm_top_k,
            )
        self.chunks = filter_relevant_chunks(all_chunks, self.retrieval_query)
        self.chunks = dedup_and_compress(self.chunks)

        # 空检索补偿
        if not self.chunks:
            rewritten = await self._expand_and_retry()
            if rewritten:
                self.chunks = rewritten

        return self.chunks

    async def _expand_and_retry(self) -> list | None:
        """空检索时改写查询重试。"""
        from app.services.rag.generation import rewrite_query
        rewritten = await rewrite_query(self.retrieval_query)
        if not rewritten or rewritten == self.retrieval_query:
            return None
        all_chunks = await retrieve_chunks(
            self.db, kb_id=self.kb_id, query=rewritten, top_k=settings.llm_top_k,
        ) if not self._is_workspace() else await retrieve_workspace_chunks(
            self.db, scope=self.scope, org_scope=self.org_scope,
            query=rewritten, top_k=settings.llm_top_k,
        )
        filtered = filter_relevant_chunks(all_chunks, self.retrieval_query)
        return dedup_and_compress(filtered)

    def _make_citations(self) -> list[dict]:
        if not self._is_workspace():
            from app.services.rag.retrieval import chunk_to_citation
            fn = chunk_to_citation
        else:
            from app.services.rag.retrieval import workspace_chunk_to_citation
            fn = workspace_chunk_to_citation
        return [fn(c) for c in self.chunks]

    async def _generate(self) -> AsyncIterator[dict]:
        """生成 SSE 事件流。"""
        for c in self._make_citations():
            yield {"event": "citation", "data": c}

        compressed = await compress_history(self.history) if self.history else None

        # R4-2：无依据拒答门控（语义兜底 + 词面重叠）
        if self.chunks and should_refuse_answer(self.chunks, self.retrieval_query):
            yield {"event": "token", "data": {"text": no_context_reply_for(self.message)}}
            yield {"event": "done", "data": {}}
            return

        if self.chunks:
            messages = build_messages(self.message, self.chunks, history=self.history, compressed_summary=compressed)
            token_stream = stream_deepseek_tokens(messages)
        else:
            token_stream = iter([])
            yield {"event": "token", "data": {"text": "知识库中未找到相关内容。"}}
            yield {"event": "done", "data": {}}
            return

        token_parts = []
        async for text in token_stream:
            if text:
                token_parts.append(text)
                yield {"event": "token", "data": {"text": text}}

        content = "".join(token_parts)
        safe_out, _ = output_safety_check(content)
        if not safe_out:
            yield {"event": "error", "data": {"detail": "回答被安全策略拦截"}}
            return

        # 自验证（可选）
        if settings.self_verify_enabled and self.chunks:
            from app.services.rag.generation import verify_answer
            verified, corrected = await verify_answer(content, self.chunks, self.message)
            if not verified and corrected:
                content = corrected
                yield {"event": "correction", "data": {"text": corrected}}

        # 引用 post-processing：验证 [片段N] 引用是否有效
        if self.chunks:
            import re as _re
            refs = _re.findall(r'\[片段(\d+)\]', content)
            invalid = [r for r in refs if not (1 <= int(r) <= len(self.chunks))]
            if invalid:
                logger.warning("无效引用: 片段%s 超出范围 (%d chunks)", invalid, len(self.chunks))
            elif not refs and self.chunks:
                logger.info("回答中无行内引用，由前端渲染 SSE citation 事件替代")

        # 落库
        await self._save(content)
        yield {"event": "done", "data": {}}

    async def _save(self, content: str) -> None:
        """保存对话记录。"""
        if self.skip_save:
            return
        await save_chat_turn(
            self.db,
            kb_id=self.kb_id,
            user_id=self.user_id,
            user_content=self.message,
            assistant_content=content,
            citations=self.citations,
            thread_id=self.thread_id,
        )

    async def stream(self) -> AsyncIterator[dict]:
        """主入口：编排检索→生成→落库全流程。"""
        await self._load_history()
        await self._retrieve()
        async for event in self._generate():
            yield event
