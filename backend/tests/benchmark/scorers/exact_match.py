"""ExactMatchScorer — 精确匹配策略（预留）。

精确匹配要求 chunk.content 完全等于 expect.content_contains。
当前未使用，为 Phase 3 外部基准预留。
"""
from .base import (
    EvalScorer, RetrievalScore, GenerationScore,
    Expect, RetrievedChunk, compute_scores,
)


class ExactMatchScorer:
    """精确匹配评分器（预留）。"""

    def score_retrieval(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        expect: Expect,
        top_k: int = 3,
    ) -> RetrievalScore:
        match_positions: list[int] = []
        for i, ck in enumerate(chunks[:top_k]):
            content = (ck.content or "").strip()
            if expect.content_contains and content == expect.content_contains.strip():
                match_positions.append(i)

        total_relevant = len(match_positions)
        return compute_scores(match_positions, total_relevant, expect, top_k)

    def score_generation(
        self,
        query: str,
        answer: str,
        expect: Expect,
        chunks: list[RetrievedChunk],
    ) -> GenerationScore:
        return GenerationScore()
