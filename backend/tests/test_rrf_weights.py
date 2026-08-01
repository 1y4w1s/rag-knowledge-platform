"""A4：RRF 权重传入 reciprocal_rank_fusion 的稳定行为。"""

from uuid import uuid4

from app.services.rag.rrf import reciprocal_rank_fusion


def test_rrf_higher_fts_weight_promotes_fts_only_chunk() -> None:
    """FTS 权重升高时，仅在 FTS 路靠前的 chunk 应更靠前。"""
    a, b = uuid4(), uuid4()
    # vector: a 第1、b 第2；fts: b 第1、a 第2
    fused_equal = reciprocal_rank_fusion(
        [[a, b], [b, a]],
        k=60,
        weights=[1.0, 1.0],
        top_n=2,
    )
    fused_fts_heavy = reciprocal_rank_fusion(
        [[a, b], [b, a]],
        k=60,
        weights=[1.0, 2.0],
        top_n=2,
    )
    equal_scores = {cid: score for cid, score in fused_equal}
    heavy_scores = {cid: score for cid, score in fused_fts_heavy}
    assert fused_fts_heavy[0][0] == b
    assert heavy_scores[b] > equal_scores[b]
