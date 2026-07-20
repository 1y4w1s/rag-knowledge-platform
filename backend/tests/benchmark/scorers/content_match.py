"""ContentMatchScorer — content_contains 子串匹配策略。

匹配规则（与旧 runner.py 一致，但提取为独立类）：
1. content_contains 对 chunk.content 做 case-insensitive 子串匹配
2. section_title 对 chunk.section_title 做精确匹配
3. heading_path_contains 对 heading_path 做 case-insensitive 子串匹配
4. page_number 对 chunk.page_number 做精确匹配
5. 返回 top_k 内的命中情况
"""
from typing import Any
from .base import (
    EvalScorer, RetrievalScore, GenerationScore,
    Expect, RetrievedChunk, hit_positions, compute_scores,
)


class ContentMatchScorer:
    """content_contains 子串匹配评分器。

    用于 Golden QA、Expense QA、Enterprise QA 等自建测试集。
    """

    def score_retrieval(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        expect: Expect,
        top_k: int = 3,
    ) -> RetrievalScore:
        match_positions: list[int] = []
        matched_expects: set[str] = set()

        for i, ck in enumerate(chunks[:top_k]):
            content = ck.content.lower()
            heading = (ck.heading_path or ck.section_title or "").lower()
            ok = True

            # content_contains 子串匹配
            if expect.content_contains:
                if expect.content_contains.lower() not in content:
                    ok = False

            # section_title 精确匹配
            if ok and expect.section_title:
                if ck.section_title != expect.section_title:
                    ok = False

            # heading_path_contains 子串匹配
            if ok and expect.heading_path_contains:
                if expect.heading_path_contains.lower() not in heading:
                    ok = False

            # page_number 精确匹配
            if ok and expect.page_number is not None:
                if ck.page_number != expect.page_number:
                    ok = False

            if ok:
                key = expect.content_contains or expect.section_title or str(i)
                if key not in matched_expects:
                    matched_expects.add(key)
                match_positions.append(i)

        total_relevant = len(matched_expects)
        return compute_scores(match_positions, total_relevant, expect, top_k)

    def score_generation(
        self,
        query: str,
        answer: str,
        expect: Expect,
        chunks: list[RetrievedChunk],
    ) -> GenerationScore:
        """生成评分暂不实现，留待 W6。"""
        return GenerationScore()
