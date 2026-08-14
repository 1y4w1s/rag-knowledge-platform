"""RAG 对话编排引擎 — 合并 KB 版和 Workspace 版公共逻辑。"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.degradation import assess_degradation, degradation_requires_llm
from app.core.latency import get_tracker
from app.services.observability.metrics_registry import inc_chat_answer
from app.services.rag.chat_llm import has_available_chat_provider_key
from app.services.rag.degraded_answer import stream_degraded_fragment_reply
from app.services.rag.dedup import dedup_and_compress
from app.services.rag.citation_align import align_citations_to_answer
from app.services.rag.confidence_reply import (
    AnswerConfidence,
    classify_answer_confidence,
    partial_answer_disclaimer_for,
    with_partial_disclaimer,
)
from app.services.rag.generation import (
    SYSTEM_PROMPT,
    build_messages,
    check_citation_density,
    check_citation_section_coverage,
    compress_history,
    no_context_reply_for,
    stream_deepseek_tokens,
)
from app.services.rag.generation import SECTION_MISSING_ISSUE_TEMPLATE
from app.services.rag.multi_turn import prepare_multi_turn_query
from app.services.rag.persistence import save_chat_turn
from app.services.rag.relevance import filter_relevant_chunks
from app.services.rag.retrieval import (
    chunk_to_citation,
    retrieve_chunks,
    retrieve_workspace_chunks,
    workspace_chunk_to_citation,
)
from app.services.rag.safety_filter import input_safety_check, output_safety_check
from app.services.rag.cache import llm_response_cache

logger = logging.getLogger(__name__)


class ChatEngine:
    """RAG 对话编排引擎（fast · thread 内多轮）。"""

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
        visible_kb_ids: frozenset[UUID] | None = None,
        hide_admin_only: bool = False,
        assistant_message_id: uuid.UUID | None = None,
    ):
        self.db = db
        self.user_id = user_id
        self.message = message
        self.workspace = workspace
        self.kb_id = kb_id
        self.thread_id = thread_id
        self.scope = scope
        self.org_scope = org_scope
        self.visible_kb_ids = visible_kb_ids
        self.hide_admin_only = hide_admin_only
        self.retrieval_query = message
        self.history: list[dict[str, str]] | None = None
        self.chunks: list = []
        self.citations: list[dict] = []
        self.skip_save = skip_save
        self.collected_text: str = ""
        self._assistant_message_id = assistant_message_id
        self._t0 = time.perf_counter()

    def _is_workspace(self) -> bool:
        return self.scope is not None

    def _retrieval_ms(self) -> int:
        return int((time.perf_counter() - self._t0) * 1000)

    async def _load_history(self) -> None:
        """加载多轮对话历史并改写检索查询。"""
        history, retrieval_query = await prepare_multi_turn_query(
            self.db,
            message=self.message,
            user_id=self.user_id,
            thread_id=self.thread_id,
        )
        self.history = history
        self.retrieval_query = retrieval_query

    async def _retrieve(self) -> list:
        """执行检索（隔离参数透传）。"""
        if self._is_workspace():
            all_chunks = await retrieve_workspace_chunks(
                self.db,
                scope=self.scope,
                org_scope=self.org_scope,
                query=self.retrieval_query,
                top_k=settings.llm_top_k,
                hide_admin_only=self.hide_admin_only,
            )
        else:
            all_chunks = await retrieve_chunks(
                self.db,
                kb_id=self.kb_id,
                query=self.retrieval_query,
                top_k=settings.llm_top_k,
                visible_kb_ids=self.visible_kb_ids,
                hide_admin_only=self.hide_admin_only,
                context=self.history,
            )
        self.chunks = filter_relevant_chunks(all_chunks, self.retrieval_query)
        self.chunks = dedup_and_compress(self.chunks)

        if not self.chunks:
            logger.warning(
                "没有检索到相关片段，将走无引用生成 (query=%s)",
                self.retrieval_query[:80],
            )

        return self.chunks

    def _make_citations(self) -> list[dict]:
        fn = workspace_chunk_to_citation if self._is_workspace() else chunk_to_citation
        return [fn(c) for c in self.chunks]

    async def _save(self, content: str, citations: list[dict]) -> uuid.UUID | None:
        """保存对话记录；skip_save 时不写库。

        如果有预创建的 pending assistant message（_assistant_message_id），
        则 finalize 该消息并同时创建 user 消息，不走传统的 save_chat_turn 双写路径。
        """
        if self.skip_save:
            return None
        if self._assistant_message_id is not None:
            from app.services.rag.persistence import finalize_message
            from app.models.chat_message import ChatMessage as CMsg
            from app.models.enums import MessageRole, MessageStatus, ThreadKind

            await finalize_message(
                self.db, self._assistant_message_id,
                content=content,
                citations=citations,
                status=MessageStatus.completed,
                retrieval_duration_ms=self._retrieval_ms(),
            )
            # 同时创建 user 消息
            self.db.add(CMsg(
                thread_kind=ThreadKind.knowledge_base,
                kb_id=self.kb_id,
                user_id=self.user_id,
                thread_id=self.thread_id,
                role=MessageRole.user,
                content=self.message,
                status=MessageStatus.completed,
            ))
            await self.db.commit()
            return self._assistant_message_id
        return await save_chat_turn(
            self.db,
            kb_id=self.kb_id,
            user_id=self.user_id,
            user_content=self.message,
            assistant_content=content,
            citations=citations,
            thread_id=self.thread_id,
            retrieval_duration_ms=self._retrieval_ms(),
        )

    async def _emit_refusal(self, block_reply: str | None = None) -> AsyncIterator[dict]:
        """无依据/安全拦截拒答：无 citation · 固定话术 · 落库 · done 契约。"""
        from app.services.rag.generation import stream_no_context_reply

        self.citations = []
        parts: list[str] = []
        if block_reply is None:
            async for text in stream_no_context_reply(self.message):
                if text:
                    parts.append(text)
                    yield {"event": "token", "data": {"text": text}}
        else:
            parts.append(block_reply)
            yield {"event": "token", "data": {"text": block_reply}}
        full = "".join(parts) or no_context_reply_for(self.message)
        message_id = await self._save(full, [])
        done: dict = {"citations": []}
        if message_id is not None:
            done["message_id"] = str(message_id)
        yield {"event": "done", "data": done}

    async def _emit_degraded_reply(self) -> AsyncIterator[dict]:
        """L1 降级：返回原文片段 + 降级说明，不调 LLM、不写 LLM 缓存。"""
        parts: list[str] = []
        async for text in stream_degraded_fragment_reply(self.message, self.chunks):
            if text:
                parts.append(text)
                self.collected_text += text
                yield {"event": "token", "data": {"text": text}}

        content = "".join(parts)
        safe_out, _ = output_safety_check(content)
        if not safe_out:
            yield {"event": "error", "data": {"detail": "回答被安全策略拦截"}}
            return

        fn = workspace_chunk_to_citation if self._is_workspace() else chunk_to_citation
        self.citations = align_citations_to_answer(
            content,
            self.chunks,
            to_citation=fn,
        )
        message_id = await self._save(content, self.citations)
        done: dict = {"citations": self.citations}
        if message_id is not None:
            done["message_id"] = str(message_id)
        yield {"event": "done", "data": done}

    async def _generate(self) -> AsyncIterator[dict]:
        """生成 SSE：citation → token → done（含 message_id / citations）。"""
        confidence = classify_answer_confidence(self.chunks, self.retrieval_query)
        # H1：终态置信度计数（classify 后立刻；不改拒答阈值）
        inc_chat_answer(confidence.value, "fast")
        # R4-2：先门控，拒答不吐 citation
        if confidence is AnswerConfidence.refuse:
            async for event in self._emit_refusal():
                yield event
            return

        self.citations = self._make_citations()
        for c in self.citations:
            yield {"event": "citation", "data": c}

        # L1：LLM 全挂或未配置任何 chat provider key 时，
        # 在 compress/build_messages 之前切换确定性降级回答
        if (
            not degradation_requires_llm(assess_degradation())
            or not has_available_chat_provider_key()
        ):
            async for event in self._emit_degraded_reply():
                yield event
            return

        compressed = await compress_history(self.history) if self.history else None
        messages = build_messages(
            self.message,
            self.chunks,
            history=self.history,
            compressed_summary=compressed,
            answer_confidence=confidence,
        )

        # ── LLM 响应缓存检查 ────────────────────────────────────────
        cached = await llm_response_cache.get(
            str(self.kb_id) if self.kb_id else None,
            self.workspace,
            messages,
            str(self.user_id),
        )
        if cached is not None:
            self.citations = cached.get("citations", self.citations)
            content = cached.get("content", "")
            if content:
                yield {"event": "token", "data": {"text": content}}
            done: dict = {"citations": self.citations}
            if cached.get("message_id"):
                done["message_id"] = cached["message_id"]
            yield {"event": "done", "data": done}
            self.citations = cached.get("citations", [])
            return

        token_parts: list[str] = []
        if confidence is AnswerConfidence.low:
            disclaimer = partial_answer_disclaimer_for(self.message)
            token_parts.append(disclaimer)
            token_parts.append("\n\n")
            yield {"event": "token", "data": {"text": disclaimer + "\n\n"}}

        try:
            async for text in stream_deepseek_tokens(messages):
                if text:
                    token_parts.append(text)
                    self.collected_text += text
                    yield {"event": "token", "data": {"text": text}}
        except Exception as exc:
            # L1 异常兜底：provider 双失败把熔断器打开后的竞态窗口切到降级流
            logger.warning(
                "module=rag_degradation operation=llm_all_down mode=fast error=%s",
                exc,
            )
            self.collected_text = ""
            async for event in self._emit_degraded_reply():
                yield event
            return

        content = "".join(token_parts)
        safe_out, _ = output_safety_check(content)
        if not safe_out:
            yield {"event": "error", "data": {"detail": "回答被安全策略拦截"}}
            return

        if settings.self_verify_enabled and self.chunks:
            from app.services.rag.generation import verify_answer

            # 校验只看模型正文，避免 disclaimer 干扰；落库仍保留前缀
            body_for_verify = content
            if confidence is AnswerConfidence.low:
                prefix = partial_answer_disclaimer_for(self.message) + "\n\n"
                if body_for_verify.startswith(prefix):
                    body_for_verify = body_for_verify[len(prefix) :]

            verified, corrected = await verify_answer(
                body_for_verify, self.chunks, self.message
            )
            if not verified and corrected:
                content = (
                    with_partial_disclaimer(self.message, corrected)
                    if confidence is AnswerConfidence.low
                    else corrected
                )
                yield {"event": "correction", "data": {"text": content}}
            elif not verified:
                # M9-P2-1（P2-04）：verify 失败且无纠正稿 → fail-closed，
                # 不保留未验证正文，按 R4-2 拒答口径替换并清空引用
                content = no_context_reply_for(self.message)
                self.citations = []
                yield {"event": "correction", "data": {"text": content}}
                message_id = await self._save(content, [])
                done = {"citations": []}
                if message_id is not None:
                    done["message_id"] = str(message_id)
                yield {"event": "done", "data": done}
                return

        # ── 第2层：引用密度校验 + 低密度重生成（上限 = citation_density_regenerate_limit）─────
        density_passed = True
        for _attempt in range(settings.citation_density_regenerate_limit):
            if not (
                settings.citation_density_check_enabled
                and self.chunks
                and confidence is not AnswerConfidence.refuse
            ):
                break
            # 校验引用密度（跳过 disclaimer 前缀）
            body_for_density = content
            if confidence is AnswerConfidence.low:
                prefix = partial_answer_disclaimer_for(self.message) + "\n\n"
                if body_for_density.startswith(prefix):
                    body_for_density = body_for_density[len(prefix) :]

            density_passed, density, issues = check_citation_density(
                body_for_density, self.chunks
            )
            missing_sections: list[str] = []
            if density_passed:
                # 第2层叠加：章节覆盖校验（GQ-47 类隐性跨章题，相关章节 ≥2 才启用）
                coverage_passed, missing_sections = check_citation_section_coverage(
                    body_for_density, self.chunks, self.retrieval_query,
                )
                if coverage_passed:
                    break
                density_passed = False  # 标记需重生成，复用下方 REGENERATE 分支

            # 重生成——用 REGENERATE_PROMPT 增压约束
            from app.services.rag.generation import REGENERATE_PROMPT

            density_issue_lines = [f"- 「{s[:60]}」" for s in issues[:5]]
            section_issue_lines = [
                SECTION_MISSING_ISSUE_TEMPLATE.format(section=s)
                for s in missing_sections
            ]
            issues_text = "\n".join(density_issue_lines + section_issue_lines)
            # H1/H2：重生成上下文与 build_messages 同排序（similarity 升序）
            # 且全量覆盖候选相关章节（上限 llm_top_k=8，与首次生成一致）
            chunks_text = "\n---\n".join(
                f"[片段{i+1}] {c.parent_content or c.content}"
                for i, c in enumerate(
                    sorted(self.chunks, key=lambda c: c.similarity, reverse=False)[
                        : settings.llm_top_k
                    ]
                )
            )

            regen_messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": REGENERATE_PROMPT.format(
                    issues_text=issues_text,
                    chunks=chunks_text[:2000],
                    query=self.retrieval_query,
                )},
            ]

            # 发送重生成事件（前端可展示"正在补充引用…"）
            yield {"event": "regenerating", "data": {
                "reason": (
                    f"引用未覆盖全部相关章节（{len(missing_sections)} 章），正在重新生成…"
                    if missing_sections
                    else f"引用密度不足（{density:.0%}），正在重新生成…"
                ),
            }}

            # 清空已收集内容，重新流式
            token_parts = []
            async for text in stream_deepseek_tokens(regen_messages):
                if text:
                    token_parts.append(text)
                    yield {"event": "token", "data": {"text": text}}

            content = "".join(token_parts)

        # F1：流式 citation 为候选；done/落库按正文 [片段N] 硬对齐（漏标 keep-all）
        fn = workspace_chunk_to_citation if self._is_workspace() else chunk_to_citation
        strip = (
            partial_answer_disclaimer_for(self.message)
            if confidence is AnswerConfidence.low
            else None
        )
        self.citations = align_citations_to_answer(
            content,
            self.chunks,
            to_citation=fn,
            strip_prefix=strip,
        )

        message_id = await self._save(content, self.citations)

        # ── 写入 LLM 响应缓存 ──────────────────────────────────────
        cache_payload = {
            "content": content,
            "citations": self.citations,
            "confidence": confidence.value,
        }
        if message_id is not None:
            cache_payload["message_id"] = str(message_id)
        await llm_response_cache.set(
            str(self.kb_id) if self.kb_id else None,
            self.workspace,
            messages,
            cache_payload,
            str(self.user_id),
        )

        done: dict = {"citations": self.citations}
        if message_id is not None:
            done["message_id"] = str(message_id)
        yield {"event": "done", "data": done}

    async def stream(self) -> AsyncIterator[dict]:
        """主入口：加载历史 → 输入安全检查 → 检索 → 生成 → 落库。"""
        self._t0 = time.perf_counter()
        await self._load_history()

        safe, block_reply = input_safety_check(self.retrieval_query)
        if not safe:
            async for event in self._emit_refusal(block_reply):
                yield event
            return

        await self._retrieve()
        get_tracker("retrieval.retrieval_e2e").record(float(self._retrieval_ms()))
        async for event in self._generate():
            yield event
