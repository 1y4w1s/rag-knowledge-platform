"""评分引擎核心接口定义。

每个 Scorer 实现一种匹配策略，接受 query + chunks + expect，
返回 RetrievalScore 和 GenerationScore。
"""
from __future__ import annotations
import math
import logging
from dataclasses import dataclass, field
from typing import Protocol, Any

logger = logging.getLogger(__name__)


# ── 数据模型 ──

@dataclass
class RetrievalScore:
    """检索评分结果。"""
    hit_at_1: bool = False
    hit_at_3: bool = False
    hit_at_5: bool = False
    mrr: float = 0.0
    ndcg_at_k: float = 0.0
    correct_rejection: bool = False
    precision_at_k: float = 0.0
    recall_at_k: float = 0.0
    map_contribution: float = 0.0
    match_details: list[dict] = field(default_factory=list)


@dataclass
class GenerationScore:
    """生成评分结果。"""
    faithfulness: float = 0.0
    correctness: float = 0.0
    citation_accuracy: float = 0.0
    error: str | None = None


@dataclass
class Expect:
    """TestCase 的 expect 字段，统一模型。
    从 cases.json 的 expect 对象解析。
    """
    content_contains: str = ""
    section_title: str = ""
    heading_path_contains: str = ""
    page_number: int | None = None
    answer: str = ""  # CRAG 等外部基准用

    @classmethod
    def from_case(cls, case: dict) -> Expect:
        exp = case.get("expect") or {}
        return cls(
            content_contains=exp.get("content_contains", ""),
            section_title=exp.get("section_title", ""),
            heading_path_contains=exp.get("heading_path_contains", ""),
            page_number=exp.get("page_number"),
            answer=case.get("answer", ""),
        )


@dataclass
class RetrievedChunk:
    """检索结果中的单个 chunk，适配不同数据源。"""
    chunk_id: str
    content: str
    section_title: str = ""
    heading_path: str = ""
    page_number: int | None = None
    similarity: float = 0.0

    @classmethod
    def from_raw(cls, chunk: Any) -> RetrievedChunk:
        """从任意 chunk 对象转换（兼容 ORM / dict / dataclass）。"""
        if hasattr(chunk, "chunk_id"):
            return cls(
                chunk_id=str(chunk.chunk_id),
                content=(chunk.content or ""),
                section_title=getattr(chunk, "section_title", "") or "",
                heading_path=getattr(chunk, "heading_path", "") or "",
                page_number=getattr(chunk, "page_number", None),
                similarity=getattr(chunk, "similarity", 0.0),
            )
        if isinstance(chunk, dict):
            return cls(
                chunk_id=str(chunk.get("chunk_id", "")),
                content=chunk.get("content", ""),
                section_title=chunk.get("section_title", ""),
                heading_path=chunk.get("heading_path", ""),
                page_number=chunk.get("page_number"),
                similarity=chunk.get("similarity", 0.0),
            )
        return cls(chunk_id=str(id(chunk)), content=str(chunk))


# ── Scorer 协议 ──

class EvalScorer(Protocol):
    """评分策略接口。每个 Scorer 实现一种匹配逻辑。

    使用 Protocol 而非 ABC，便于单元测试 mock。
    """

    def score_retrieval(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        expect: Expect,
        top_k: int = 3,
    ) -> RetrievalScore:
        ...

    def score_generation(
        self,
        query: str,
        answer: str,
        expect: Expect,
        chunks: list[RetrievedChunk],
    ) -> GenerationScore:
        ...


# ── 工具函数 ──

def ndcg_at_k(match_positions: list[int], k: int) -> float:
    """标准 NDCG@K 计算（log2 折扣）。"""
    if not match_positions:
        return 0.0
    dcg = sum(1.0 / math.log2(pos + 2) for pos in match_positions if pos < k)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(match_positions), k)))
    return dcg / ideal if ideal > 0 else 0.0


def hit_positions(
    chunks: list[RetrievedChunk],
    expect: Expect,
    top_k: int,
) -> tuple[list[int], int]:
    """匹配 expect 条件，返回命中位置列表和总相关数。
    
    通用逻辑，各 Scorer 可复用。
    """
    match_positions: list[int] = []
    matched_expects: set[int] = set()
    total_relevant = 0

    for i, ck in enumerate(chunks[:top_k]):
        content = ck.content.lower()
        heading = (ck.heading_path or ck.section_title or "").lower()

        matched = False
        if expect.content_contains:
            if expect.content_contains.lower() in content:
                matched = True

        if not matched and expect.answer:
            if expect.answer.lower() in content:
                matched = True

        if matched and expect.content_contains:
            # 去重：同一 content_contains 在不同 chunk 只计一次
            key = expect.content_contains
            if key not in matched_expects:
                matched_expects.add(key)
                total_relevant += 1

        if matched:
            match_positions.append(i)

    if not matched_expects and match_positions:
        total_relevant = 1  # answer-match 场景

    return match_positions, total_relevant


def compute_scores(
    match_positions: list[int],
    total_relevant: int,
    expect: Expect,
    top_k: int,
) -> RetrievalScore:
    """从匹配位置计算全套指标。"""
    hit_1 = any(p < 1 for p in match_positions)
    hit_3 = any(p < 3 for p in match_positions)
    hit_5 = any(p < 5 for p in match_positions)
    mrr = 1.0 / (match_positions[0] + 1) if match_positions else 0.0
    ndcg = ndcg_at_k(match_positions, top_k)
    correct_rejection = bool(
        getattr(expect, "expect_rejection", False) and not match_positions
    )

    precision = total_relevant / max(1, top_k)
    recall_denom = max(1, len(expect.content_contains) if expect.content_contains else 1)
    recall = min(1.0, total_relevant / recall_denom) if total_relevant > 0 else 0.0

    map_contrib = 0.0
    if match_positions:
        running_hits = 0
        for rank, pos in enumerate(match_positions, 1):
            running_hits += 1
            if pos < top_k:
                map_contrib += running_hits / (pos + 1)

    return RetrievalScore(
        hit_at_1=hit_1,
        hit_at_3=hit_3,
        hit_at_5=hit_5,
        mrr=mrr,
        ndcg_at_k=ndcg,
        correct_rejection=correct_rejection,
        precision_at_k=precision,
        recall_at_k=recall,
        map_contribution=map_contrib,
    )
