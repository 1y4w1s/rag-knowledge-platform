"""生成适配器：将索隐的问答系统连接到 BenchmarkRunner。

非流式调用：检索 + 构造 messages + DeepSeek 生成 + 解析引用。

用法：
    from tests.benchmark.adapters.generation import GenerationAdapter
    adapter = GenerationAdapter(db, kb_id)
    runner.set_generate_fn(adapter.generate)
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.services.rag.generation import build_messages, stream_deepseek_tokens, no_context_reply_for, verify_answer
from app.services.rag.relevance import filter_relevant_chunks, should_refuse_answer
from app.services.rag.retrieval import retrieve_chunks
from app.services.rag.types import RetrievedChunk

logger = logging.getLogger(__name__)


# ── 辅助：类型安全转换 ──


def _safe_as_retrieved_chunk(obj: object) -> RetrievedChunk:
    """将任意对象安全转换为 RetrievedChunk。

    如果 obj 已经是 RetrievedChunk，直接返回；
    如果是 DocumentChunk ORM 实例或其他 duck-typed 对象，提取兼容字段。

    防御性编程：防止因类型不一致导致下游访问 .similarity 等属性时崩溃。
    """
    if isinstance(obj, RetrievedChunk):
        return obj
    # DocumentChunk ORM 兜底（或其他 Object）
    from uuid import uuid4

    return RetrievedChunk(
        kb_id=getattr(obj, "kb_id", uuid4()),
        chunk_id=getattr(obj, "id", getattr(obj, "chunk_id", uuid4())),
        document_id=getattr(obj, "document_id", uuid4()),
        doc_name=getattr(obj, "doc_name", getattr(obj, "document_id", "")),
        content=getattr(obj, "content", str(obj)),
        page_number=getattr(obj, "page_number", None),
        section_title=getattr(obj, "section_title", None),
        heading_path=getattr(obj, "heading_path", None),
        similarity=getattr(obj, "similarity", 0.0),
        parent_content=getattr(obj, "parent_content", None),
        kb_name=getattr(obj, "kb_name", None),
        rrf_score=getattr(obj, "rrf_score", None),
    )


# ── Adapter ──


class GenerationAdapter:
    """将检索+生成包装为 BenchmarkRunner 兼容的回调。

    非流式问答：检索 → 构造 messages → 收集 DeepSeek 流式输出 → 返回 (answer, citations)。
    """

    def __init__(self, db, kb_id: UUID) -> None:
        self._db = db
        self._kb_id = kb_id
        # M1 摸底：最近一次送模上下文统计（评测脚本侧读取，不影响生成行为）
        self.last_context_chars = 0
        self.last_chunk_count = 0

    async def generate(
        self, query: str, kb_id: UUID | None = None
    ) -> tuple[str, list[dict]]:
        """生成回调：供 BenchmarkRunner.run_generation() 使用。

        Returns:
            (answer_text, citations_list)
        """
        target_kb_id = kb_id or self._kb_id

        # 1. 检索（top_k=8：实测优于 5，5 会砍掉部分正确 chunk）
        raw_chunks = await retrieve_chunks(
            self._db,
            kb_id=target_kb_id,
            query=query,
            top_k=8,
        )

        if not raw_chunks:
            answer = no_context_reply_for(query)
            return answer, []

        # 1a. 类型安全转换：确保所有 chunk 都是 RetrievedChunk 实例
        # （防御性编程：防止 DocumentChunk ORM 对象被误传入下游）
        chunks = [_safe_as_retrieved_chunk(c) for c in raw_chunks]

        # 1b. 相关性过滤 + 拒答门控
        chunks = filter_relevant_chunks(chunks, query)
        if should_refuse_answer(chunks, query):
            return no_context_reply_for(query), []

        # 2. 构造 messages（含检索片段）
        messages = build_messages(query, chunks)
        # M1 摸底：记录送模上下文字符数与片段数（评测侧输出分布，不动生成行为）
        ctx_parts = [
            m.get("content", "") for m in messages
            if isinstance(m.get("content"), str) and m["content"].startswith("【检索片段】")
        ]
        self.last_context_chars = sum(len(p) for p in ctx_parts)
        self.last_chunk_count = len(chunks)

        # 3. 流式生成并收集完整输出
        answer_parts: list[str] = []
        async for token in stream_deepseek_tokens(messages):
            answer_parts.append(token)
        answer = "".join(answer_parts)

        # 3a. Claim-level 验证 + 纠正（实验 G）
        if answer.strip() and chunks:
            verified, corrected = await verify_answer(answer, chunks, query)
            if not verified and corrected:
                logger.info("Claim-level 验证未通过，已纠正生成 (query=%s…)", query[:40])
                answer = corrected

        # 4. 提取引用（chunk → citation）
        from app.services.rag.retrieval import chunk_to_citation

        citations = [chunk_to_citation(c) for c in chunks]

        return answer, citations
