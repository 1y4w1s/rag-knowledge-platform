"""AnswerMatchScorer — answer 子串匹配策略。

用于 CRAG 等外部基准测试集，匹配逻辑：
- expect.answer 的前 40 字符对 chunk.content 做 case-insensitive 子串匹配
"""
from .base import (
    EvalScorer, RetrievalScore, GenerationScore,
    Expect, RetrievedChunk, hit_positions, compute_scores,
)


class AnswerMatchScorer:
    """answer 子串匹配评分器。

    用于 CRAG 等只有 query+answer 的外部数据集。
    """

    def score_retrieval(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        expect: Expect,
        top_k: int = 3,
    ) -> RetrievalScore:
        match_positions: list[int] = []

        answer_key = expect.answer.lower().strip()[:40]
        if not answer_key:
            return RetrievalScore()

        for i, ck in enumerate(chunks[:top_k]):
            if answer_key in (ck.content or "").lower():
                match_positions.append(i)

        total_relevant = 1 if match_positions else 0
        return compute_scores(match_positions, total_relevant, expect, top_k)

    def score_generation(
        self,
        query: str,
        answer: str,
        expect: Expect,
        chunks: list[RetrievedChunk],
    ) -> GenerationScore:
        return GenerationScore()
