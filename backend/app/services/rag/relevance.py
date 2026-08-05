"""检索相关性判定（Wave 3.3 + Plan-RAG R4-2）：无依据不喂 LLM、不吐 citation。"""

from __future__ import annotations

import re

from app.core.config import settings
from app.services.rag.types import RetrievedChunk

_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")
_LATIN_TERM = re.compile(r"[A-Za-z0-9_]{4,}")

# 问句虚词 / 万能实体：单独命中不足以构成「有依据」（AC-4：公司火星/上市）
# M5 检索侧候选谓词收窄：高频泛词（员工/每年/参加/提前/多久/几天/正式/外部）
# 不再构成词面命中信号，避免单章题 2-gram 撞词（GQ-17 1.1/8.1、GQ-20 9.4 等）
_OVERLAP_STOPWORDS = frozenset(
    {
        "公司",
        "什么",
        "怎么",
        "如何",
        "是否",
        "可以",
        "政策",
        "计划",
        "相关",
        "内容",
        "问题",
        "一下",
        "这个",
        "那个",
        "哪些",
        "多少",
        "有没有",
        # M5 新增（草案 9 词，「可以」原有）
        "员工",
        "每年",
        "参加",
        "提前",
        "多久",
        "几天",
        "正式",
        "外部",
        "the",
        "what",
        "which",
        "where",
        "when",
        "how",
        "does",
        "company",
        "policy",
        "plan",
    }
)


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
    return [t for t in terms if t.lower() not in _OVERLAP_STOPWORDS]


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


def has_lexical_anchor(chunks: list[RetrievedChunk], query: str) -> bool:
    """锚点判定：Top-8 内存在 ≥1 个词面命中章节（M5 条件灰色带触发条件）。

    锚点是通用信号（查询是否「查得准字面」），不按 case_id 打点。
    """
    return any(query_overlaps_chunk(query, chunk) for chunk in chunks)


def is_grey_candidate(
    chunk: RetrievedChunk,
    query: str,
    *,
    has_anchor: bool,
) -> bool:
    """灰色带候选：无词面重叠且 lo ≤ similarity < hi（M5 条件灰色带）。

    - 有锚点（单章题类查询）→ lo = relevance_grey_anchor_lo（初值 0.63），
      低 sim 灰色噪声被过滤；
    - 无锚点（GQ-47 类纯语义查询）→ lo = relevance_similarity_fallback（0.45）
      宽带保底。
    """
    if query_overlaps_chunk(query, chunk):
        return False
    lo = (
        settings.relevance_grey_anchor_lo
        if has_anchor
        else settings.relevance_similarity_fallback
    )
    hi = settings.relevance_high_sim_reject
    return bool(chunk.similarity and lo <= chunk.similarity < hi)


def related_sections(
    chunks: list[RetrievedChunk],
    query: str,
) -> set[str]:
    """相关章节（去重）：词面命中 ∪ 灰色带候选。

    filter_relevant_chunks / check_citation_section_coverage 共享同一口径，
    防止谓词漂移（M3「与 filter 同一来源」红线延续）。
    """
    has_anchor = has_lexical_anchor(chunks, query)
    return {
        c.section_title
        for c in chunks
        if c.section_title
        and (
            query_overlaps_chunk(query, c)
            or is_grey_candidate(c, query, has_anchor=has_anchor)
        )
    }


def _vector_scores_universally_weak(chunks: list[RetrievedChunk]) -> bool:
    """所有 chunk 的向量相似度均低于 retrieval_min_top1_similarity。

    相似度为 0.0 的 chunk（纯 FTS 结果）不计入——它们没有向量分数，
    不应触发「弱向量」拒答逻辑。
    """
    threshold = settings.retrieval_min_top1_similarity
    scored = [c for c in chunks if getattr(c, "similarity", 0.0) and getattr(c, "similarity", 0.0) > 0.0]
    if not scored:
        return False
    return all(getattr(c, "similarity", 0.0) < threshold for c in scored)


def has_relevant_context(chunks: list[RetrievedChunk], query: str) -> bool:
    """Top-3 片段须与问题有词面重叠才视为有依据（R3-P1-1 / AC-4）。

    R4-2：有重叠时放行；
    无重叠时检查相似度做语义兜底（与 filter 共享条件灰色带下限：有锚点 →
    收紧到 relevance_grey_anchor_lo，无锚点 → 保持 relevance_similarity_fallback
    宽带），避免字面不匹配但语义相关时误拒答。
    """
    if not chunks:
        return False

    top3 = chunks[:3]
    if any(query_overlaps_chunk(query, chunk) for chunk in top3):
        return True

    # 字面不匹配 → 语义兜底：无锚点行为与旧版一致（max_sim ≥ 宽带 lo），
    # 有锚点（单章题类）时收紧到 relevance_grey_anchor_lo。
    lo = (
        settings.relevance_grey_anchor_lo
        if has_lexical_anchor(chunks, query)
        else settings.relevance_similarity_fallback
    )
    max_sim = max(getattr(c, "similarity", 0.0) for c in top3)
    return max_sim >= lo


def should_refuse_answer(chunks: list[RetrievedChunk], query: str) -> bool:
    """R4-2：检索空或无依据 → 走固定拒答话术，不调 LLM。"""
    return not has_relevant_context(chunks, query)


def filter_relevant_chunks(
    chunks: list[RetrievedChunk],
    query: str,
) -> list[RetrievedChunk]:
    """逐 chunk 相关性过滤：零词面重叠的 chunk 丢弃，灰色带语义兜底。

    保留规则：
    - 词面重叠 → 保留
    - 无词面重叠但 lo ≤ similarity < 0.9 → 保留（灰色带语义兜底）
      · 查询有词面锚点（单章题类）→ lo = relevance_grey_anchor_lo（0.63），低 sim 噪声被过滤
      · 无锚点（GQ-47 类纯语义查询）→ lo = relevance_similarity_fallback（0.45）宽带
    - 无词面重叠且 similarity ≥ 0.9 → 丢弃（AC-4：高相似假阳性防线）

    与旧版的区别：旧版是 all-or-nothing（全部丢弃或全部保留）；
    新版逐 chunk 检查，不相关的 chunk 单独丢弃，保留部分相关结果。
    """
    if not chunks:
        return []
    has_anchor = has_lexical_anchor(chunks, query)
    return [
        c for c in chunks
        if query_overlaps_chunk(query, c)
        or is_grey_candidate(c, query, has_anchor=has_anchor)
    ]
