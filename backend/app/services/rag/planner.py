"""检索策略决策（Phase 1 从 retrieval.py 拆分）。

职责：
- 是否跳过 Rerank 的置信度评估
- 自适应 Top-K 数量
- Query Understanding 相关辅助函数

纯函数——不依赖 DB 连接。
"""

from app.services.rag.types import RetrievedChunk


def should_skip_rerank(
    candidates: list[RetrievedChunk],
    fts_rows: list,
    query: str,
) -> bool:
    """4 信号置信度评估：是否跳过 Rerank。

    Returns:
        True → 跳过 Rerank（RRF 顺序直接返回）
        False → 保留 Rerank
    """
    if not candidates:
        return True

    max_sim = max(c.similarity for c in candidates)
    query_len = len(query)
    fts_high = fts_rows and fts_rows[0].fts_rank is not None and fts_rows[0].fts_rank > 0.1
    only_one = len(candidates) <= 1

    if only_one:
        return True
    if max_sim > 0.85:
        return True
    if max_sim > 0.70 and fts_high:
        return True
    if fts_high and query_len < 10:
        return True
    return False


def adaptive_top_k(candidates: list[RetrievedChunk], query: str) -> int:
    """根据置信度自适应调整送入 LLM 的 chunk 数量。"""
    if not candidates:
        return 0

    max_sim = max(c.similarity for c in candidates)
    query_len = len(query)

    if max_sim > 0.85:
        return 2
    elif max_sim > 0.70 or query_len > 20:
        return 3
    else:
        return min(len(candidates), 5)
