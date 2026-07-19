"""生成适配器：将睿阁的问答系统连接到 BenchmarkRunner。

非流式调用：检索 + 构造 messages + DeepSeek 生成 + 解析引用。

用法：
    from tests.benchmark.adapters.generation import GenerationAdapter
    adapter = GenerationAdapter(db, kb_id)
    runner.set_generate_fn(adapter.generate)
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from app.services.rag.generation import build_messages, stream_deepseek_tokens, no_context_reply_for
from app.services.rag.relevance import filter_relevant_chunks, should_refuse_answer
from app.services.rag.retrieval import retrieve_chunks

logger = logging.getLogger(__name__)


class GenerationAdapter:
    """将检索+生成包装为 BenchmarkRunner 兼容的回调。

    非流式问答：检索 → 构造 messages → 收集 DeepSeek 流式输出 → 返回 (answer, citations)。
    """

    def __init__(self, db, kb_id: UUID) -> None:
        self._db = db
        self._kb_id = kb_id

    async def generate(
        self, query: str, kb_id: UUID | None = None
    ) -> tuple[str, list[dict]]:
        """生成回调：供 BenchmarkRunner.run_generation() 使用。

        Returns:
            (answer_text, citations_list)
        """
        target_kb_id = kb_id or self._kb_id

        # 1. 检索
        chunks = await retrieve_chunks(
            self._db,
            kb_id=target_kb_id,
            query=query,
            top_k=5,
        )

        if not chunks:
            answer = no_context_reply_for(query)
            return answer, []

        # 1b. 相关性过滤 + 拒答门控
        chunks = filter_relevant_chunks(chunks, query)
        if should_refuse_answer(chunks, query):
            return no_context_reply_for(query), []

        # 2. 构造 messages（含检索片段）
        messages = build_messages(query, chunks)

        # 3. 流式生成并收集完整输出
        answer_parts: list[str] = []
        async for token in stream_deepseek_tokens(messages):
            answer_parts.append(token)
        answer = "".join(answer_parts)

        # 4. 提取引用（chunk → citation）
        from app.services.rag.retrieval import chunk_to_citation
        citations = [chunk_to_citation(c) for c in chunks]

        return answer, citations
