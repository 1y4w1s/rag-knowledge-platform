"""M2 W1 · 证据充分性判定规则（只读，无副作用）。

四维度综合判定子查询检索结果是否充分：
  hit_count / top_sim_score / chunk_diversity / coverage_ratio
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EvidenceVerdict:
    """证据充分性判定结果。"""

    sufficient: bool  # True=证据充分，False=证据不足
    reason: str  # 判定原因（人类可读，≤80 字符）
    hit_count: int  # 检索命中数
    top_sim_score: float  # 最高相似度
    chunk_diversity: int  # 去重 chunk 数
    coverage_ratio: float  # 命中 chunk 覆盖的文档数 / hit_count


def check_evidence_sufficiency(
    hits: tuple[Any, ...] | list[Any],
    original_query: str,
    *,
    min_hit_count: int = 3,
    min_top_sim: float = 0.5,
    min_chunk_diversity: int = 2,
) -> EvidenceVerdict:
    """证据充分性判定规则（§S3.1 设计）。

    四维度综合判定：
      - hit_count >= min_hit_count（默认 3）
      - top_sim_score >= min_top_sim（默认 0.5 = relevance_low_sim_ceiling）
      - chunk_diversity >= min_chunk_diversity（默认 2，去重 chunk_id 数）
      - coverage_ratio > 0（至少覆盖 1 个文档）

    所有维度均满足 → sufficient=True；任一不满足 → sufficient=False。

    注意：此函数为只读判定，无副作用，不触发任何策略。
    调用方（W1 observation mode）负责记录判定结果。
    """
    hit_count = len(hits)

    if hit_count == 0:
        return EvidenceVerdict(
            sufficient=False,
            reason="无命中",
            hit_count=0,
            top_sim_score=0.0,
            chunk_diversity=0,
            coverage_ratio=0.0,
        )

    top_sim_score = max(float(h.score or 0.0) for h in hits)

    if top_sim_score < min_top_sim:
        return EvidenceVerdict(
            sufficient=False,
            reason=f"最高相似度 {top_sim_score:.3f} < {min_top_sim}",
            hit_count=hit_count,
            top_sim_score=top_sim_score,
            chunk_diversity=hit_count,  # 未达 sim 阈值时 diversity 退化为 hit_count
            coverage_ratio=0.0,
        )

    if hit_count < min_hit_count:
        return EvidenceVerdict(
            sufficient=False,
            reason=f"命中数 {hit_count} < {min_hit_count}",
            hit_count=hit_count,
            top_sim_score=top_sim_score,
            chunk_diversity=hit_count,
            coverage_ratio=0.0,
        )

    # chunk_diversity：去重 chunk_id 数；无 chunk_id 时退化为 hit_count
    chunk_ids = set()
    doc_names = set()
    for h in hits:
        cid = getattr(h, "chunk_id", None)
        chunk_ids.add(cid if cid is not None else id(h))
        dname = getattr(h, "doc_name", None)
        if dname is not None:
            doc_names.add(dname)

    chunk_diversity = len(chunk_ids)
    if chunk_diversity < min_chunk_diversity:
        return EvidenceVerdict(
            sufficient=False,
            reason=f"去重 chunk 数 {chunk_diversity} < {min_chunk_diversity}",
            hit_count=hit_count,
            top_sim_score=top_sim_score,
            chunk_diversity=chunk_diversity,
            coverage_ratio=0.0,
        )

    coverage_ratio = len(doc_names) / hit_count if hit_count > 0 else 0.0
    if coverage_ratio == 0:
        return EvidenceVerdict(
            sufficient=False,
            reason="无文档覆盖",
            hit_count=hit_count,
            top_sim_score=top_sim_score,
            chunk_diversity=chunk_diversity,
            coverage_ratio=coverage_ratio,
        )

    return EvidenceVerdict(
        sufficient=True,
        reason="证据充分",
        hit_count=hit_count,
        top_sim_score=top_sim_score,
        chunk_diversity=chunk_diversity,
        coverage_ratio=coverage_ratio,
    )
