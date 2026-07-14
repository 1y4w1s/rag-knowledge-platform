"""Reciprocal Rank Fusion（Wave 3.4）：合并多路召回排名。"""

from __future__ import annotations

from uuid import UUID

DEFAULT_RRF_K = 60


def reciprocal_rank_fusion(
    ranked_lists: list[list[UUID]],
    *,
    k: int = DEFAULT_RRF_K,
    top_n: int = 5,
    weights: list[float] | None = None,
) -> list[tuple[UUID, float]]:
    """按 RRF 分数合并多路排名；分数相同按 chunk_id 稳定排序。"""
    if weights is not None and len(weights) != len(ranked_lists):
        raise ValueError("weights length must match ranked_lists length")

    scores: dict[UUID, float] = {}
    for list_idx, ranked in enumerate(ranked_lists):
        weight = 1.0 if weights is None else weights[list_idx]
        for rank, chunk_id in enumerate(ranked, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + weight / (k + rank)

    ordered = sorted(scores.items(), key=lambda item: (-item[1], str(item[0])))
    return ordered[:top_n]
