"""检索相关性判定（Wave 3.3 + Plan-RAG R4-2）：无依据不喂 LLM、不吐 citation。"""

from __future__ import annotations

import re

from app.core.config import settings
from app.services.rag.types import RetrievedChunk

_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")
_LATIN_TERM = re.compile(r"[A-Za-z0-9_]{4,}")

SIMILARITY_FALLBACK_THRESHOLD = 0.45  # 字面匹配失败时的语义兜底阈值


def _significant_terms(query: str) -> list[str]:
    terms = _LATIN_TERM.findall(query)
    for run in _CJK_RUN.findall(query):
        if len(run) == 1:
            terms.append(run)
            continue
        for size in (2, 3):
            if len(run) < size:
                continue
            for i in range(len(run) - size + 1):
                terms.append(run[i : i + size])
    return terms


def query_overlaps_chunk(query: str, chunk: RetrievedChunk) -> bool:
    """查询与片段是否存在可观测的词面重叠（mock 嵌入分低时的兜底）。"""
    haystack = " ".join(
        part
        for part in (
            chunk.doc_name,
            chunk.section_title,
            chunk.heading_path,
            chunk.parent_content,
            chunk.content,
        )
        if part
    )
    return any(term in haystack for term in _significant_terms(query))


def _vector_scores_universally_weak(chunks: list[RetrievedChunk]) -> bool:
    """所有 chunk 的向量相似度均低于 retrieval_min_top1_similarity。

    相似度为 0.0 的 chunk（纯 FTS 结果）不计入——它们没有向量分数，
    不应触发「弱向量」拒答逻辑。
    """
    threshold = settings.retrieval_min_top1_similarity
    scored = [c for c in chunks if c.similarity and c.similarity > 0.0]
    if not scored:
        return False
    return all(c.similarity < threshold for c in scored)


def has_relevant_context(chunks: list[RetrievedChunk], query: str) -> bool:
    """Top-3 片段须与问题有词面重叠才视为有依据（R3-P1-1 / AC-4）。

    R4-2：有重叠时放行；
    无重叠时检查向量相似度（similarity）做语义兜底，
    避免字面不匹配但语义相关时误拒答。
    """
    if not chunks:
        return False

    top3 = chunks[:3]
    has_overlap = any(query_overlaps_chunk(query, chunk) for chunk in top3)
    if has_overlap:
        return True

    # 字面不匹配 → 语义兜底：检查向量相似度
    max_sim = max(c.similarity for c in top3)
    if max_sim >= SIMILARITY_FALLBACK_THRESHOLD:
        return True

    return False


def should_refuse_answer(chunks: list[RetrievedChunk], query: str) -> bool:
    """R4-2：检索空或无依据 → 走固定拒答话术，不调 LLM。"""
    return not has_relevant_context(chunks, query)


def filter_relevant_chunks(
    chunks: list[RetrievedChunk],
    query: str,
) -> list[RetrievedChunk]:
    """逐 chunk 相关性过滤：零词面重叠的 chunk 丢弃。

    与旧版的区别：旧版是 all-or-nothing（全部丢弃或全部保留）；
    新版逐 chunk 检查，不相关的 chunk 单独丢弃，保留部分相关结果。
    """
    if not chunks:
        return []
    return [c for c in chunks if query_overlaps_chunk(query, c)]
