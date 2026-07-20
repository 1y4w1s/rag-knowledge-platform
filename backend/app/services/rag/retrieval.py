"""Hybrid 检索入口：向量 + 全文 tsvector，RRF 融合 Top-K（Wave 3.4）。

编排入口（retrieve_chunks / retrieve_workspace_chunks），
策略决策委托给 planner.py，纯执行委托给 executor.py。
"""

from __future__ import annotations

import logging
import re
import time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.degradation import assess_degradation, degradation_requires_embed
from app.services.ingestion.embedder import embed_texts, try_embed_texts
from app.services.org.scope import OrgScope
from app.services.rag.diversity import apply_kb_diversity
from app.services.rag.executor import (
    enforce_kb_scope,
    enforce_workspace_scope,
    load_parent_contents,
    merge_recall_rows,
)
from app.services.rag.planner import adaptive_top_k, should_skip_rerank
from app.services.rag.rerank import rerank_chunks
from app.services.rag.rrf import reciprocal_rank_fusion
from app.services.rag.types import RetrievedChunk
from app.services.rag.vector_recall import vector_recall, _vector_recall_workspace
from app.services.rag.fts_recall import fts_recall, _fts_recall_workspace
from app.core.scope_utils import kb_scope_clause
from app.services.workspace.scope import WorkspaceScope
from app.services.rag.cache import get_query_cache, set_query_cache, query_cache_enabled
from app.core.latency import get_tracker

VECTOR_RECALL = settings.vector_recall_k
FTS_RECALL = settings.fts_recall_k
LLM_TOP_K = settings.llm_top_k
TS_CONFIG = "simple"

logger = logging.getLogger(__name__)

# ── 向后兼容导出（Phase 1 重构后，原函数已迁至 executor/planner） ──
from app.services.rag.executor import (
    chunk_to_citation,
    enforce_kb_scope,
    enforce_workspace_scope,
    excerpt as _excerpt,
    load_parent_contents,
    merge_recall_rows,
    visible_kb_clause,
    workspace_chunk_to_citation,
)
from app.services.rag.planner import adaptive_top_k as _adaptive_top_k, should_skip_rerank as _should_skip_rerank

# 私有别名——保持旧有调用方的 _enforce_kb_scope 等导入
_enforce_kb_scope = enforce_kb_scope
_enforce_workspace_scope = enforce_workspace_scope


async def retrieve_chunks(
    db: AsyncSession,
    *,
    kb_id: UUID,
    query: str,
    top_k: int = LLM_TOP_K,
    visible_kb_ids: frozenset[UUID] | None = None,
    hide_admin_only: bool = False,
) -> list[RetrievedChunk]:
    """向量 Top-20 + 全文 Top-20（同 kb_id），RRF 融合后 rerank 取 Top-K。"""
    if visible_kb_ids is not None and kb_id not in visible_kb_ids:
        return []

    # 查询缓存命中则直接返回
    if query_cache_enabled():
        cached = await get_query_cache(kb_id, query)
        if cached is not None:
            return cached

    _t = time.perf_counter
    t0 = _t()

    # 语言检测：判断 query 是否为英文
    # 英文 query → 用 bge-en 英文嵌入 + embedding_en 列
    ascii_chars = sum(1 for c in query if c.isascii() and c.isalpha())
    total_chars = sum(1 for c in query if c.isalpha())
    is_english = total_chars > 0 and (ascii_chars / total_chars) > 0.5
    embed_provider = "bge_en" if is_english else None
    embed_col = "embedding_en" if is_english else None

    # 2026-07-19: 嵌入降级感知——嵌入失效时跳过向量召回，走纯 FTS
    query_vec = None
    if degradation_requires_embed(assess_degradation()):
        vec = await try_embed_texts([query], provider=embed_provider)
        if vec is not None:
            query_vec = vec[0]
        elif embed_provider == "bge_en":
            # 英文嵌入失败（模型未下载/网络不通），回退到中文嵌入
            vec = await try_embed_texts([query])
            if vec is not None:
                query_vec = vec[0]
    if query_vec is None:
        get_tracker("retrieval.embed").record(0)
    else:
        get_tracker("retrieval.embed").record((_t() - t0) * 1000)

    t0 = _t()
    if query_vec is not None:
        vector_rows = await vector_recall(db, kb_id=kb_id, query_vec=query_vec,
            limit=VECTOR_RECALL, visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only,
            embedding_col=embed_col)
    else:
        vector_rows = []
    get_tracker("retrieval.vector_recall").record((_t() - t0) * 1000)

    t0 = _t()
    fts_rows = await fts_recall(db, kb_id=kb_id, query=query, limit=FTS_RECALL,
        visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only)
    get_tracker("retrieval.fts_recall").record((_t() - t0) * 1000)

    t0 = _t()
    fused = reciprocal_rank_fusion(
        [[row.chunk.id for row in vector_rows], [row.chunk.id for row in fts_rows]],
        k=settings.rrf_k,
        weights=[settings.rrf_vector_weight, settings.rrf_fts_weight],
        top_n=settings.rerank_input_top_n if settings.rerank_enabled else top_k,
    )

    merged = merge_recall_rows(vector_rows, fts_rows)
    parent_contents = await load_parent_contents(db, [row.chunk for row in merged.values()])
    candidates = _build_candidates(fused, merged, parent_contents, kb_id, None)

    t0 = _t()
    reranked = await rerank_chunks(query, candidates, top_k=top_k)
    get_tracker("retrieval.rerank").record((_t() - t0) * 1000)
    rerank_skipped = bool(settings.rerank_enabled and should_skip_rerank(candidates, fts_rows, query))
    if rerank_skipped:
        reranked = candidates[:top_k]

    result = reranked[:top_k]
    adaptive_k = adaptive_top_k(result, query)
    if not rerank_skipped and adaptive_k < len(result):
        result = result[:adaptive_k]

    # 低置信度 → expand_queries 多路召回补偿
    result = await _expand_if_low_confidence(db, result, query, kb_id, visible_kb_ids, hide_admin_only, top_k)

    # 复合问题 → decompose 子查询
    result = await _decompose_if_needed(db, reranked, result, query, kb_id, visible_kb_ids, hide_admin_only, top_k)

    result = enforce_kb_scope(result, kb_id=kb_id, visible_kb_ids=visible_kb_ids)

    # 写缓存（仅缓存 KB 级检索结果）
    if query_cache_enabled():
        await set_query_cache(kb_id, query, result)
    return result


async def retrieve_workspace_chunks(
    db: AsyncSession,
    *,
    query: str,
    scope: WorkspaceScope,
    org_scope: OrgScope | None = None,
    top_k: int = LLM_TOP_K,
    hide_admin_only: bool = False,
) -> list[RetrievedChunk]:
    """在 workspace 可见库集合内向量+全文→RRF→rerank→多样性→Top-K。"""
    visible_kb_ids = org_scope.visible_kb_ids if org_scope is not None else None
    if visible_kb_ids is not None and not visible_kb_ids:
        return []

    # 语言检测
    ascii_chars = sum(1 for c in query if c.isascii() and c.isalpha())
    total_chars = sum(1 for c in query if c.isalpha())
    is_english = total_chars > 0 and (ascii_chars / total_chars) > 0.5
    embed_provider = "bge_en" if is_english else None
    embed_col = "embedding_en" if is_english else None

    # 2026-07-19: 嵌入降级感知
    if degradation_requires_embed(assess_degradation()):
        query_vec = (await try_embed_texts([query], provider=embed_provider))[0]
    else:
        query_vec = None

    if query_vec is not None:
        vector_rows = await _vector_recall_workspace(db, scope=scope, org_scope=org_scope,
        query_vec=query_vec, limit=VECTOR_RECALL, visible_kb_ids=visible_kb_ids,
        hide_admin_only=hide_admin_only, embedding_col=embed_col)
    fts_rows = await _fts_recall_workspace(db, scope_clause=kb_scope_clause(scope, org_scope),
        query=query, limit=FTS_RECALL, visible_kb_ids=visible_kb_ids,
        hide_admin_only=hide_admin_only)

    fused = reciprocal_rank_fusion(
        [[row.chunk.id for row in vector_rows], [row.chunk.id for row in fts_rows]],
        k=settings.rrf_k,
        weights=[settings.rrf_vector_weight, settings.rrf_fts_weight],
        top_n=settings.rerank_input_top_n if settings.rerank_enabled else top_k,
    )

    merged = merge_recall_rows(vector_rows, fts_rows)
    parent_contents = await load_parent_contents(db, [row.chunk for row in merged.values()])
    candidates = _build_candidates(fused, merged, parent_contents, None, chunk_kb=True)

    rerank_pool = settings.rerank_input_top_n if settings.rerank_enabled else top_k
    reranked = await rerank_chunks(query, candidates, top_k=rerank_pool)
    diverse = apply_kb_diversity(reranked, query, top_k=top_k)
    return enforce_workspace_scope(diverse, visible_kb_ids=visible_kb_ids)


# ── 内部辅助（不暴露给外部） ──


def _build_candidates(fused, merged, parent_contents, kb_id, chunk_kb):
    """RRF 融合结果 → RetrievedChunk 列表。"""
    candidates: list[RetrievedChunk] = []
    for chunk_id, _rrf_score in fused:
        row = merged[chunk_id]
        chunk = row.chunk
        similarity = row.vector_similarity if row.vector_similarity is not None else 0.0
        parent_content = (parent_contents or {}).get(chunk.parent_chunk_id) if chunk.parent_chunk_id else None
        candidates.append(RetrievedChunk(
            kb_id=chunk.kb_id if chunk_kb else kb_id,
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            doc_name=row.filename,
            content=chunk.content,
            page_number=chunk.page_number,
            section_title=chunk.section_title,
            heading_path=chunk.heading_path,
            similarity=similarity,
            parent_content=parent_content,
            kb_name=row.kb_name,
        ))
    return candidates


async def _expand_if_low_confidence(db, result, query, kb_id, visible_kb_ids, hide_admin_only, top_k):
    """低置信度时 expand_queries 多路召回补偿。"""
    if not result or max(c.similarity for c in result) >= 0.6:
        return result
    try:
        from app.services.rag.generation import expand_queries
        expanded = await expand_queries(query)
        if len(expanded) <= 1:
            return result
        seen_ids = {c.chunk_id for c in result}
        for eq in expanded[1:]:
            if eq.lower().strip() == query.lower().strip():
                continue
            eq_vec = (await try_embed_texts([eq]))[0]
            eq_rows = await vector_recall(db, kb_id=kb_id, query_vec=eq_vec,
                limit=VECTOR_RECALL, visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only)
            for row in eq_rows:
                if row.chunk.id not in seen_ids:
                    seen_ids.add(row.chunk.id)
                    merged_row = merge_recall_rows(eq_rows, [])
                    for c in merged_row.values():
                        if c.chunk.id not in {x.chunk_id for x in result}:
                            result.append(RetrievedChunk(
                                kb_id=kb_id, chunk_id=c.chunk.id,
                                document_id=c.chunk.document_id, doc_name=c.filename,
                                content=c.chunk.content, page_number=c.chunk.page_number,
                                section_title=c.chunk.section_title,
                                heading_path=c.chunk.heading_path,
                                similarity=c.vector_similarity or 0.0,
                            ))
        return result[:top_k]
    except Exception:
        return result


async def _decompose_if_needed(db, reranked, result, query, kb_id, visible_kb_ids, hide_admin_only, top_k):
    """复合问题 → decompose 子查询补充召回。"""
    markers = ["和", "与", "以及", "还是", "或", "同时", "如果"]
    needs_decompose = any(m in query for m in markers)
    multi_q = query.count("？") > 1 or query.count("?") > 1
    if not (settings.rerank_enabled and reranked and (needs_decompose or multi_q or len(query) > 15)):
        return result
    try:
        from app.services.rag.generation import decompose_query
        sub_queries = await decompose_query(query)
        if len(sub_queries) <= 1:
            return result
        seen_ids = set(c.chunk_id for c in reranked)
        extra: list[RetrievedChunk] = []
        for sq in sub_queries:
            if sq.lower().strip() == query.lower().strip():
                continue
            sq_chunks = await retrieve_chunks(db, kb_id=kb_id, query=sq, top_k=top_k,
                visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only)
            for c in sq_chunks:
                if c.chunk_id not in seen_ids:
                    seen_ids.add(c.chunk_id)
                    extra.append(c)
        if extra:
            reranked = reranked + extra
            reranked = await rerank_chunks(query, reranked, top_k=top_k)
        return reranked
    except Exception:
        return result
