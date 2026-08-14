"""Hybrid 检索入口：向量 + 全文 tsvector，RRF 融合 Top-K（Wave 3.4）。

编排入口（retrieve_chunks / retrieve_workspace_chunks），
策略决策委托给 planner.py，纯执行委托给 executor.py。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.core.config import settings
from app.core.degradation import (
    DegradationLevel,
    assess_degradation,
    degradation_requires_embed,
    degradation_requires_rerank,
)
from app.services.ingestion.embedder import try_embed_texts
from app.services.org.scope import OrgScope
from app.services.rag.diversity import apply_kb_diversity
from app.services.rag.embed_route import (
    resolve_query_embed,
    vector_recall_en_empty_fallback,
)
from app.services.rag.executor import (
    enforce_kb_scope,
    enforce_workspace_scope,
    load_parent_contents,
    merge_recall_rows,
)
from app.services.rag.planner import (
    RetrievalStrategy,
    adaptive_top_k,
    effective_query_rewrite_policy,
    effective_rerank_for_strategy,
    effective_rerank_policy,
    is_composite_query,
    is_short_query_for_rewrite,
    select_strategy,
    should_expand_queries,
    should_run_rerank,
    should_skip_rerank,
)
from app.services.rag.rerank import rerank_chunks
from app.services.rag.rrf import reciprocal_rank_fusion
from app.services.rag.types import RetrievedChunk
from app.services.rag.vector_recall import vector_recall, _vector_recall_workspace
from app.services.rag.fts_recall import fts_recall, _fts_recall_workspace
from app.services.rag.hyde import is_hyde_enabled
from app.core.scope_utils import kb_scope_clause
from app.services.workspace.scope import WorkspaceScope
from app.services.rag.cache import get_query_cache, set_query_cache, query_cache_enabled
from app.services.rag.cjk import segment_cjk
from app.core.latency import get_tracker
from app.models.document_chunk import DocumentChunk
from app.models.entity import Entity, EntityMention, Relation
from app.services.rag.query_ner import query_ner_sync

VECTOR_RECALL = settings.vector_recall_k
FTS_RECALL = settings.fts_recall_k
LLM_TOP_K = settings.llm_top_k
TS_CONFIG = "simple"
# 实验 M：复合题每子查询前置的结果数（实验：3 覆盖 ENT-014/098 命中，2 略紧）
_COMPOSITE_PREPEND = 3

logger = logging.getLogger(__name__)

# ── 向后兼容导出（Phase 1 重构后，原函数已迁至 executor/planner） ──
from app.services.rag.executor import (  # noqa: E402
    chunk_to_citation,  # noqa: F401
    excerpt as _excerpt,  # noqa: F401
    visible_kb_clause,  # noqa: F401
    workspace_chunk_to_citation,  # noqa: F401
)

# 私有别名——保持旧有调用方的 _enforce_kb_scope 等导入
_enforce_kb_scope = enforce_kb_scope
_enforce_workspace_scope = enforce_workspace_scope


def _rerank_pool_size(top_k: int) -> int:
    return settings.rerank_input_top_n if effective_rerank_policy() != "off" else top_k


async def _apply_rerank_policy(
    query: str,
    candidates: list[RetrievedChunk],
    *,
    top_k: int,
    fts_rows_for_skip: list | None = None,
    vector_top_ids: list[UUID] | None = None,
    fts_top_ids: list[UUID] | None = None,
    strategy: RetrievalStrategy | None = None,
) -> tuple[list[RetrievedChunk], bool]:
    """按 RERANK_POLICY 决定是否精排。返回 (结果前缀, 是否实际调用了 rerank)。

    B3：strategy=complex 时强制 always，不受 RERANK_POLICY 影响。
    """
    eff = effective_rerank_for_strategy(strategy, effective_rerank_policy()) if strategy else effective_rerank_policy()
    degraded = not degradation_requires_rerank(assess_degradation())
    if eff == "off" or degraded:
        return candidates[:top_k], False

    if eff == "always":
        if should_skip_rerank(candidates, fts_rows_for_skip or [], query):
            return candidates[:top_k], False
        return await rerank_chunks(query, candidates, top_k=top_k), True

    # conditional
    if should_run_rerank(
        candidates,
        vector_top_ids=vector_top_ids,
        fts_top_ids=fts_top_ids,
    ):
        return await rerank_chunks(query, candidates, top_k=top_k), True
    return candidates[:top_k], False


def _has_effective_fts(rows: list) -> bool:
    return any(getattr(r, "fts_rank", None) is not None and r.fts_rank > 0 for r in rows)


def _probe_should_expand(query: str, fused, merged) -> bool:
    """单问探针后是否扩多 query（空 parent 轻量候选）。"""
    probe = _build_candidates(fused, merged, {}, None, chunk_kb=True)
    fts_rows = [r for r in merged.values() if r.fts_rank is not None]
    return should_expand_queries(
        query, probe, has_effective_fts=_has_effective_fts(fts_rows)
    )


def concat_dedup(
    vector_rows: list,
    fts_rows: list,
    top_n: int,
) -> list[tuple[UUID, float]]:
    """向量 Top-K + FTS Top-K 简单拼接去重。

    向量结果优先排序，FTS 补充未出现的 chunk_id。
    返回格式与 RRF 一致：[(chunk_id, score), ...]。
    """
    seen: set[UUID] = set()
    result: list[tuple[UUID, float]] = []
    # 先走向量
    for rank, row in enumerate(vector_rows):
        if row.chunk.id not in seen:
            seen.add(row.chunk.id)
            result.append((row.chunk.id, float(len(vector_rows) - rank)))
            if len(result) >= top_n:
                return result
    # 再走 FTS 补齐
    for rank, row in enumerate(fts_rows):
        if row.chunk.id not in seen:
            seen.add(row.chunk.id)
            result.append((row.chunk.id, float(len(fts_rows) - rank)))
            if len(result) >= top_n:
                break
    return result


async def _kb_single_hybrid(
    db: AsyncSession,
    *,
    kb_id: UUID,
    query: str,
    top_n: int,
    visible_kb_ids: frozenset[UUID] | None,
    hide_admin_only: bool,
    hyde_query: str | None = None,  # B1 HyDE：假设文档（用于 embedding，None 则用 query）
) -> tuple[list, dict, list[UUID] | None, list[UUID] | None, list]:
    """单问 vector+FTS→RRF。返回 fused, merged, vector_top_ids, fts_top_ids, fts_rows。"""
    _t = time.perf_counter
    t0 = _t()
    allow_embed = degradation_requires_embed(assess_degradation())
    embed_query = hyde_query or query  # B1 HyDE：用假设文档做 embedding
    route = await resolve_query_embed(embed_query, allow_embed=allow_embed)
    query_vec = route.query_vec
    embed_col = route.embedding_col
    get_tracker("retrieval.embed").record(0 if query_vec is None else (_t() - t0) * 1000)

    t0 = _t()
    if query_vec is not None:
        async def _kb_recall(*, query_vec, embedding_col):
            return await vector_recall(
                db,
                kb_id=kb_id,
                query_vec=query_vec,
                limit=VECTOR_RECALL,
                visible_kb_ids=visible_kb_ids,
                hide_admin_only=hide_admin_only,
                embedding_col=embedding_col,
            )

        vector_rows = await vector_recall_en_empty_fallback(
            query=query,
            query_vec=query_vec,
            embedding_col=embed_col,
            recall=_kb_recall,
        )
    else:
        vector_rows = []
    get_tracker("retrieval.vector_recall").record((_t() - t0) * 1000)

    t0 = _t()
    fts_rows = await fts_recall(
        db, kb_id=kb_id, query=query, limit=FTS_RECALL,
        visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only,
    )
    get_tracker("retrieval.fts_recall").record((_t() - t0) * 1000)

    fusion_mode = settings.retrieval_fusion_mode

    if fusion_mode == "rrf":
        fused = reciprocal_rank_fusion(
            [[row.chunk.id for row in vector_rows], [row.chunk.id for row in fts_rows]],
            k=settings.rrf_k,
            weights=[settings.rrf_vector_weight, settings.rrf_fts_weight],
            top_n=top_n,
        )
    elif fusion_mode == "concat":
        fused = concat_dedup(vector_rows, fts_rows, top_n)
    elif fusion_mode == "vector_only":
        fused = [(row.chunk.id, float(len(vector_rows) - i))
                 for i, row in enumerate(vector_rows[:top_n])]
    else:
        raise ValueError(f"Unknown retrieval_fusion_mode: {fusion_mode}")

    merged = merge_recall_rows(vector_rows, fts_rows)
    return (
        fused,
        merged,
        [row.chunk.id for row in vector_rows[:3]],
        [row.chunk.id for row in fts_rows[:3]],
        fts_rows,
    )


async def _kb_multi_hybrid(
    db: AsyncSession,
    *,
    kb_id: UUID,
    query: str,
    top_n: int,
    visible_kb_ids: frozenset[UUID] | None,
    hide_admin_only: bool,
    injected_variants: list[str] | None = None,
) -> tuple[list, dict, list]:
    from app.services.rag.multi_query import multi_query_kb_recall

    t0 = time.perf_counter()
    fused, merged, _variants = await multi_query_kb_recall(
        db,
        kb_id=kb_id,
        query=query,
        vector_limit=VECTOR_RECALL,
        fts_limit=FTS_RECALL,
        top_n=top_n,
        visible_kb_ids=visible_kb_ids,
        hide_admin_only=hide_admin_only,
        injected_variants=injected_variants,
    )
    get_tracker("retrieval.vector_recall").record((time.perf_counter() - t0) * 1000)
    fts_rows = [r for r in merged.values() if r.fts_rank is not None]
    return fused, merged, fts_rows


async def _kb_composite_recall(
    db: AsyncSession,
    *,
    kb_id: UUID,
    query: str,
    top_n: int,
    visible_kb_ids: frozenset[UUID] | None,
    hide_admin_only: bool,
) -> tuple[list, dict, list]:
    """实验 M：复合题专用召回——decompose 子查询分别检索后前置融合。

    与 multi-query（近义改写变体）的区别：子查询是不同知识点/条件片段，
    与原文互补而非重叠。融合策略：子查询 fused Top-N **前置** + 原问 fused 接续
    （去重），避免 RRF 排名压制子查询命中（实验测得 target rank 被压到 4-6，
    Hit@3 评测不可见）。
    decompose 失败/无拆分时回落单问（fused 仅原问路，等价 single）。
    """
    from app.services.rag.generation import decompose_query

    # 1) 原问保底（vector+FTS RRF）
    fused_base, merged, _v_ids, _f_ids, fts_rows = await _kb_single_hybrid(
        db, kb_id=kb_id, query=query, top_n=top_n,
        visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only,
    )
    base_ids = [cid for cid, _ in fused_base]
    if not base_ids:
        return fused_base, merged, fts_rows

    # 2) decompose 子查询（检索导向 prompt，LLM）
    sub = await decompose_query(query)
    sub_queries = [s for s in sub if s.strip().lower() != query.strip().lower()]

    # 3) 子查询 fused Top-N 前置（去重），原问 fused 接续
    front: list[tuple[UUID, float]] = []
    seen: set[UUID] = set()
    for sq in sub_queries:
        f2, m2, _v2, _f2, _fr2 = await _kb_single_hybrid(
            db, kb_id=kb_id, query=sq, top_n=top_n,
            visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only,
        )
        for cid, score in f2[: _COMPOSITE_PREPEND]:
            if cid not in seen:
                seen.add(cid)
                front.append((cid, score))
                if cid in m2:
                    merged[cid] = m2[cid]
        fts_rows = fts_rows + [r for r in _fr2 if r.chunk.id not in {x.chunk.id for x in fts_rows}]

    final = front + [(cid, s) for cid, s in fused_base if cid not in seen]
    logger.info(
        "composite recall kb query_len=%d sub_queries=%d front=%d top_n=%d",
        len(query), len(sub_queries), len(front), top_n,
    )
    return final[: top_n + len(front)], merged, fts_rows


async def _ws_composite_recall(
    db: AsyncSession,
    *,
    query: str,
    scope: WorkspaceScope,
    org_scope: OrgScope | None,
    top_n: int,
    visible_kb_ids: frozenset[UUID] | None,
    hide_admin_only: bool,
    scope_clause,
) -> tuple[list, dict, list]:
    """workspace 版复合题专用召回（口径同 _kb_composite_recall）。"""
    from app.services.rag.generation import decompose_query

    # 1) 原问保底
    fused_base, merged, _v_ids, _f_ids, fts_rows = await _ws_single_hybrid(
        db, query=query, scope=scope, org_scope=org_scope, top_n=top_n,
        visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only,
        scope_clause=scope_clause,
    )
    base_ids = [cid for cid, _ in fused_base]
    if not base_ids:
        return fused_base, merged, fts_rows

    # 2) decompose 子查询
    sub = await decompose_query(query)
    sub_queries = [s for s in sub if s.strip().lower() != query.strip().lower()]

    # 3) 子查询 fused Top-N 前置（去重），原问 fused 接续
    front: list[tuple[UUID, float]] = []
    seen: set[UUID] = set()
    for sq in sub_queries:
        f2, m2, _v2, _f2, _fr2 = await _ws_single_hybrid(
            db, query=sq, scope=scope, org_scope=org_scope, top_n=top_n,
            visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only,
            scope_clause=scope_clause,
        )
        for cid, score in f2[: _COMPOSITE_PREPEND]:
            if cid not in seen:
                seen.add(cid)
                front.append((cid, score))
                if cid in m2:
                    merged[cid] = m2[cid]
        fts_rows = fts_rows + [r for r in _fr2 if r.chunk.id not in {x.chunk.id for x in fts_rows}]

    final = front + [(cid, s) for cid, s in fused_base if cid not in seen]
    logger.info(
        "composite recall ws query_len=%d sub_queries=%d front=%d top_n=%d",
        len(query), len(sub_queries), len(front), top_n,
    )
    return final[: top_n + len(front)], merged, fts_rows


async def retrieve_chunks(
    db: AsyncSession,
    *,
    kb_id: UUID,
    query: str,
    top_k: int = LLM_TOP_K,
    visible_kb_ids: frozenset[UUID] | None = None,
    hide_admin_only: bool = False,
    context: list[dict[str, str]] | None = None,
) -> list[RetrievedChunk]:
    """向量 Top-20 + 全文 Top-20（同 kb_id），RRF 融合后按 policy 条件精排取 Top-K。"""
    if visible_kb_ids is not None and kb_id not in visible_kb_ids:
        return []

    # 查询缓存命中则直接返回
    if query_cache_enabled():
        cached = await get_query_cache(kb_id, query, hide_admin_only=hide_admin_only)
        if cached is not None:
            return cached

    top_n = _rerank_pool_size(top_k)
    rw_policy = effective_query_rewrite_policy()
    used_multi = False
    _force_multi = False
    vector_top_ids: list[UUID] | None = None
    fts_top_ids: list[UUID] | None = None

    # B3：自适应检索策略
    strategy = select_strategy(query)

    # 实验 M：复合题 → 子查询拆分召回（跳过 complex 强制 multi，避免双重 LLM）
    used_composite = is_composite_query(query)
    if used_composite:
        fused, merged, fts_rows_for_skip = await _kb_composite_recall(
            db, kb_id=kb_id, query=query, top_n=top_n,
            visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only,
        )
        used_multi = True
        vector_top_ids = None
        fts_top_ids = None
        _force_multi = False
        hyde_variants = None

    # simple → 混合检索 + RRF（保留 FTS），跳过 multi-query 和 rerank
    elif strategy == RetrievalStrategy.simple:
        fused, merged, _v_ids, _f_ids, _fr_skip = await _kb_single_hybrid(
            db, kb_id=kb_id, query=query, top_n=top_n,
            visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only,
        )
        if not fused:
            strategy = RetrievalStrategy.medium
            hyde_variants = None
        else:
            _parent = await load_parent_contents(db, [row.chunk for row in merged.values()])
            _cand = _build_candidates(fused, merged, _parent, kb_id, None)
            result = enforce_kb_scope(
                _cand[:top_k], kb_id=kb_id, visible_kb_ids=visible_kb_ids,
            )
            logger.info("strategy=simple query_len=%d top_k=%d", len(query), len(result))
            return result

    # complex → 强制多查询 + HyDE + Rerank（对齐 workspace 路径）
    elif strategy == RetrievalStrategy.complex:
        # B3：complex 路径强制 multi-query（无论 rw_policy）
        if rw_policy not in ("always", "conditional"):
            rw_policy = "conditional"  # 临时提升以触发多 query
        _force_multi = True
        # B3：complex 路径生成 HyDE 并通过 injected_variants 注入
        hyde_variants: list[str] | None = None
        if is_hyde_enabled():
            from app.services.rag.hyde import generate_hypothetical_document
            hyde_doc = await generate_hypothetical_document(query)
            if hyde_doc:
                hyde_variants = [hyde_doc]
    else:
        _force_multi = False
        hyde_variants = None

    want_multi = (
        not used_composite
        and (
            _force_multi
            or rw_policy == "always"
            or (rw_policy == "conditional" and is_short_query_for_rewrite(query))
        )
    )
    if want_multi:
        fused, merged, fts_rows_for_skip = await _kb_multi_hybrid(
            db, kb_id=kb_id, query=query, top_n=top_n,
            visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only,
            injected_variants=hyde_variants,
        )
        used_multi = True
    elif not used_composite:
        # ── 首检：原始 query ──
        fused, merged, vector_top_ids, fts_top_ids, fts_rows_for_skip = (
            await _kb_single_hybrid(
                db, kb_id=kb_id, query=query, top_n=top_n,
                visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only,
            )
        )
        if rw_policy == "conditional" and _probe_should_expand(query, fused, merged):
            logger.info("query_rewrite conditional expand reason=miss_pool")
            fused, merged, fts_rows_for_skip = await _kb_multi_hybrid(
                db, kb_id=kb_id, query=query, top_n=top_n,
                visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only,
                injected_variants=hyde_variants,
            )
            used_multi = True
            vector_top_ids = None
            fts_top_ids = None

    # A3：条款号 / 文档名路由（加法追加，不稀释原问 Top-N）
    if settings.clause_route_enabled:
        from app.services.rag.route_recall import apply_clause_route_kb

        fused, merged = await apply_clause_route_kb(
            db,
            kb_id=kb_id,
            query=query,
            fused=fused,
            merged=merged,
            visible_kb_ids=visible_kb_ids,
            hide_admin_only=hide_admin_only,
        )

    parent_contents = await load_parent_contents(db, [row.chunk for row in merged.values()])
    candidates = _build_candidates(fused, merged, parent_contents, kb_id, None)

    # 实验 M：复合题跳过强制 rerank（bge-reranker 把 FAQ 段落型正确答案
    # 洗出 top-3，破坏子查询前置结果）。实验 N 后 complex 不再强制 always
    # （effective_rerank_for_strategy 透传 base_policy），此处 rerank_strategy=None
    # 仍确保 composite 题即使全局 RERANK_POLICY=always 也跳过 rerank。
    rerank_strategy = None if used_composite else strategy
    t0 = time.perf_counter()
    reranked, did_rerank = await _apply_rerank_policy(
        query,
        candidates,
        top_k=top_k,
        fts_rows_for_skip=fts_rows_for_skip,
        vector_top_ids=vector_top_ids,
        fts_top_ids=fts_top_ids,
        strategy=rerank_strategy,
    )
    get_tracker("retrieval.rerank").record((time.perf_counter() - t0) * 1000)

    result = reranked[:top_k]
    adaptive_k = adaptive_top_k(result, query)
    # 方案 B：composite 复合题跳过 adaptive 截断，保底 top_k=8 全量送生成
    # （GQ-77 根因：39 字查询 adaptive_k=3 截掉子查询前置的第 4 位命中章节，
    #  又因 used_multi 跳过 expand 救回 → 送生成上下文缺章）。
    # 非复合题维持旧行为：policy=off 时仍可自适应截断；always/conditional 跳过精排时不截
    if (
        not used_composite
        and (did_rerank or effective_rerank_policy() == "off")
        and adaptive_k < len(result)
    ):
        result = result[:adaptive_k]

    # 已走 A1 多 query 时不叠低置信度 expand / decompose（避免双重 LLM）
    if not used_multi:
        result = await _expand_if_low_confidence(
            db, result, query, kb_id, visible_kb_ids, hide_admin_only, top_k
        )
        result = await _decompose_if_needed(
            db, reranked, result, query, kb_id, visible_kb_ids, hide_admin_only, top_k
        )

    result = enforce_kb_scope(result, kb_id=kb_id, visible_kb_ids=visible_kb_ids)

    # B1 HyDE：低置信度重试（门控，仅 single 路径）
    if not used_multi and is_hyde_enabled():
        from app.services.rag.hyde import generate_hypothetical_document
        from app.services.rag.confidence_reply import is_low_confidence

        if is_low_confidence(result):
            hyde_doc = await generate_hypothetical_document(query)
            if hyde_doc:
                _f2, _m2, _v2, _f2_ids, _fr2 = await _kb_single_hybrid(
                    db, kb_id=kb_id, query=query, top_n=top_n,
                    hyde_query=hyde_doc,
                    visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only,
                )
                if _f2 and _m2:
                    _pc = await load_parent_contents(db, [row.chunk for row in _m2.values()])
                    _cand2 = _build_candidates(_f2, _m2, _pc, kb_id, None)
                    _rer2, _ = await _apply_rerank_policy(query, _cand2, top_k=top_k)
                    result2 = enforce_kb_scope(_rer2, kb_id=kb_id, visible_kb_ids=visible_kb_ids)
                    if result2:
                        result = result2
                        logger.info("hyde: low_confidence 重检成功 query_len=%d top1_sim=%.3f",
                                    len(query),
                                    result[0].similarity if result[0].similarity else 0)

    # D1 GraphRAG：实体匹配召回（低权重 0.3，不参与 rerank/adaptive_k）
    result = await graph_entity_recall(db, kb_id, query, result, context=context)

    # 写缓存（仅缓存 KB 级检索结果；图谱结果一并入库，冷/热缓存一致，P0-1）
    if query_cache_enabled():
        await set_query_cache(kb_id, query, result, hide_admin_only=hide_admin_only)
    return result


async def _ws_single_hybrid(
    db: AsyncSession,
    *,
    query: str,
    scope: WorkspaceScope,
    org_scope: OrgScope | None,
    top_n: int,
    visible_kb_ids: frozenset[UUID] | None,
    hide_admin_only: bool,
    scope_clause,
    hyde_query: str | None = None,  # B1 HyDE
) -> tuple[list, dict, list[UUID] | None, list[UUID] | None, list]:
    allow_embed = degradation_requires_embed(assess_degradation())
    embed_query = hyde_query or query  # B1 HyDE：用假设文档做 embedding
    route = await resolve_query_embed(embed_query, allow_embed=allow_embed)
    query_vec = route.query_vec
    embed_col = route.embedding_col

    vector_rows: list = []
    if query_vec is not None:
        async def _ws_recall(*, query_vec, embedding_col):
            return await _vector_recall_workspace(
                db,
                scope=scope,
                org_scope=org_scope,
                query_vec=query_vec,
                limit=VECTOR_RECALL,
                visible_kb_ids=visible_kb_ids,
                hide_admin_only=hide_admin_only,
                embedding_col=embedding_col,
            )

        vector_rows = await vector_recall_en_empty_fallback(
            query=query,
            query_vec=query_vec,
            embedding_col=embed_col,
            recall=_ws_recall,
        )
    fts_rows = await _fts_recall_workspace(
        db, scope_clause=scope_clause,
        query=query, limit=FTS_RECALL, visible_kb_ids=visible_kb_ids,
        hide_admin_only=hide_admin_only,
    )
    fused = reciprocal_rank_fusion(
        [[row.chunk.id for row in vector_rows], [row.chunk.id for row in fts_rows]],
        k=settings.rrf_k,
        weights=[settings.rrf_vector_weight, settings.rrf_fts_weight],
        top_n=top_n,
    )
    merged = merge_recall_rows(vector_rows, fts_rows)
    return (
        fused,
        merged,
        [row.chunk.id for row in vector_rows[:3]],
        [row.chunk.id for row in fts_rows[:3]],
        fts_rows,
    )


async def retrieve_workspace_chunks(
    db: AsyncSession,
    *,
    query: str,
    scope: WorkspaceScope,
    org_scope: OrgScope | None = None,
    top_k: int = LLM_TOP_K,
    hide_admin_only: bool = False,
) -> list[RetrievedChunk]:
    """在 workspace 可见库集合内向量+全文→RRF→按 policy 条件精排→多样性→Top-K。"""
    visible_kb_ids = org_scope.visible_kb_ids if org_scope is not None else None
    if visible_kb_ids is not None and not visible_kb_ids:
        return []

    top_n = _rerank_pool_size(top_k)
    scope_clause = kb_scope_clause(scope, org_scope)
    vector_top_ids: list[UUID] | None = None
    fts_top_ids: list[UUID] | None = None
    rw_policy = effective_query_rewrite_policy()
    _force_multi = False

    # B3：自适应检索策略
    strategy = select_strategy(query)

    # 实验 M：复合题 → 子查询拆分召回（跳过 complex 强制 multi，避免双重 LLM）
    used_composite = is_composite_query(query)
    if used_composite:
        fused, merged, fts_rows_for_skip = await _ws_composite_recall(
            db, query=query, scope=scope, org_scope=org_scope, top_n=top_n,
            visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only,
            scope_clause=scope_clause,
        )
        vector_top_ids = None
        fts_top_ids = None
        _force_multi = False
        hyde_variants = None

    # simple → 混合检索（保留 FTS），跳过 multi-query 和 rerank
    elif strategy == RetrievalStrategy.simple:
        fused, merged, _v_ids, _f_ids, _fr_skip = await _ws_single_hybrid(
            db, query=query, scope=scope, org_scope=org_scope, top_n=top_n,
            visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only,
            scope_clause=scope_clause,
        )
        if fused:
            _parent = await load_parent_contents(db, [row.chunk for row in merged.values()])
            _cand = _build_candidates(fused, merged, _parent, None, chunk_kb=True)
            logger.info("strategy=simple_ws query_len=%d top_k=%d", len(query), len(_cand[:top_k]))
            return _cand[:top_k]
        strategy = RetrievalStrategy.medium
        hyde_variants = None

    # complex → 强制多查询 + HyDE 注入
    elif strategy == RetrievalStrategy.complex:
        # B3：complex 路径强制 multi-query（无论 rw_policy）
        if rw_policy not in ("always", "conditional"):
            rw_policy = "conditional"  # 临时提升到 conditional 以触发多 query
        _force_multi = True
        # B3：生成 HyDE 并通过 injected_variants 注入
        hyde_variants: list[str] | None = None
        if is_hyde_enabled():
            from app.services.rag.hyde import generate_hypothetical_document
            hyde_doc = await generate_hypothetical_document(query)
            if hyde_doc:
                hyde_variants = [hyde_doc]
    else:
        _force_multi = False
        hyde_variants = None
    want_multi = (
        not used_composite
        and (
            _force_multi
            or rw_policy == "always"
            or (rw_policy == "conditional" and is_short_query_for_rewrite(query))
        )
    )
    if want_multi:
        from app.services.rag.multi_query import multi_query_workspace_recall

        fused, merged, _variants = await multi_query_workspace_recall(
            db,
            query=query,
            scope=scope,
            org_scope=org_scope,
            vector_limit=VECTOR_RECALL,
            fts_limit=FTS_RECALL,
            top_n=top_n,
            visible_kb_ids=visible_kb_ids,
            hide_admin_only=hide_admin_only,
            scope_clause=scope_clause,
            injected_variants=hyde_variants,
        )
        fts_rows_for_skip = [r for r in merged.values() if r.fts_rank is not None]
    elif not used_composite:
        # B1 HyDE
        hyde_query: str | None = None
        if is_hyde_enabled():
            from app.services.rag.hyde import generate_hypothetical_document
            hyde_query = await generate_hypothetical_document(query)

        fused, merged, vector_top_ids, fts_top_ids, fts_rows_for_skip = (
            await _ws_single_hybrid(
                db, query=query, scope=scope, org_scope=org_scope, top_n=top_n,
                hyde_query=hyde_query,
                visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only,
                scope_clause=scope_clause,
            )
        )
        if rw_policy == "conditional" and _probe_should_expand(query, fused, merged):
            from app.services.rag.multi_query import multi_query_workspace_recall

            fused, merged, _variants = await multi_query_workspace_recall(
                db,
                query=query,
                scope=scope,
                org_scope=org_scope,
                vector_limit=VECTOR_RECALL,
                fts_limit=FTS_RECALL,
                top_n=top_n,
                visible_kb_ids=visible_kb_ids,
                hide_admin_only=hide_admin_only,
                scope_clause=scope_clause,
            )
            fts_rows_for_skip = [r for r in merged.values() if r.fts_rank is not None]
            vector_top_ids = None
            fts_top_ids = None

    if settings.clause_route_enabled:
        from app.services.rag.route_recall import apply_clause_route_workspace

        fused, merged = await apply_clause_route_workspace(
            db,
            query=query,
            fused=fused,
            merged=merged,
            scope_clause=scope_clause,
            visible_kb_ids=visible_kb_ids,
            hide_admin_only=hide_admin_only,
        )

    parent_contents = await load_parent_contents(db, [row.chunk for row in merged.values()])
    candidates = _build_candidates(fused, merged, parent_contents, None, chunk_kb=True)

    # 实验 M：复合题跳过强制 rerank（同 KB 路径，避免洗掉子查询前置结果）
    rerank_strategy = None if used_composite else strategy
    rerank_pool = _rerank_pool_size(top_k)
    reranked, _did = await _apply_rerank_policy(
        query,
        candidates,
        top_k=rerank_pool,
        fts_rows_for_skip=fts_rows_for_skip,
        vector_top_ids=vector_top_ids,
        fts_top_ids=fts_top_ids,
        strategy=rerank_strategy,
    )
    diverse = apply_kb_diversity(reranked, query, top_k=top_k)
    return enforce_workspace_scope(diverse, visible_kb_ids=visible_kb_ids)


# ── D1 GraphRAG：实体匹配召回 ──


async def graph_entity_recall(
    db: AsyncSession,
    kb_id: UUID,
    query: str,
    result: list[RetrievedChunk],
    context: list[dict[str, str]] | None = None,
) -> list[RetrievedChunk]:
    """通过词法匹配实体名，召回关联 chunk，追加到 result 末尾。

    插在写缓存之前、return 之前，不参与 rerank / adaptive_k 等步骤。
    图谱召回的结果随 result 一并写入查询缓存（P0-1：缓存命中不再丢图谱）。
    """
    if not settings.graph_recall_enabled:
        return result

    tokens = segment_cjk(query).split()
    tokens = [t.strip() for t in tokens if t.strip()]

    # ILIKE 子串匹配 entity name
    matched_entity_ids: set[UUID] = set()
    for token in tokens:
        escaped = token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = select(Entity).where(
            Entity.kb_id == kb_id,
            Entity.name.ilike(f"%{escaped}%"),
        )
        rows = await db.execute(stmt)
        for ent in rows.scalars().all():
            matched_entity_ids.add(ent.id)

    # ── 步骤 2：词法匹配未命中 → NER 兜底触发 ──
    if not matched_entity_ids and settings.graph_recall_enabled:
        try:
            ner_names = await asyncio.to_thread(query_ner_sync, query, context)
            if ner_names:
                for name in ner_names:
                    escaped = name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                    stmt = select(Entity).where(
                        Entity.kb_id == kb_id,
                        Entity.name.ilike(f"%{escaped}%"),
                    )
                    rows = await db.execute(stmt)
                    for ent in rows.scalars().all():
                        matched_entity_ids.add(ent.id)
        except Exception:
            logger.exception("query_ner_sync 兜底失败")

    if not matched_entity_ids:
        return result

    # ── 步骤 3：1 跳 — 查 entity_mentions → chunk_ids（similarity=0.3） ──
    mention_stmt = select(EntityMention.chunk_id).where(
        EntityMention.entity_id.in_(matched_entity_ids)
    )
    mention_rows = await db.execute(mention_stmt)
    chunk_ids = {row[0] for row in mention_rows}

    existing_ids = {c.chunk_id for c in result}

    # 1 跳：有 mention chunk 且不在 result 中时才构造 RetrievedChunk
    if chunk_ids:
        new_chunk_ids = chunk_ids - existing_ids
        if new_chunk_ids:
            chunk_stmt = select(DocumentChunk).where(
                DocumentChunk.id.in_(new_chunk_ids)
            )
            chunk_rows = await db.execute(chunk_stmt)
            for chunk in chunk_rows.scalars().all():
                result.append(RetrievedChunk(
                    kb_id=kb_id,
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    doc_name="",
                    content=chunk.content,
                    page_number=chunk.page_number,
                    section_title=chunk.section_title,
                    heading_path=chunk.heading_path,
                    similarity=0.3,
                ))

    # ── 步骤 4：2 跳 — 关系扩散（新增） ──
    # 此时 matched_entity_ids 必然非空（步骤 1/2 已在 L661-662 守卫）
    # 4a. 查 relations 表：所有涉及 matched 实体的关系
    relation_stmt = select(Relation).where(
        Relation.kb_id == kb_id,
        or_(
            Relation.source_id.in_(matched_entity_ids),
            Relation.target_id.in_(matched_entity_ids),
        ),
    )
    rel_rows = await db.execute(relation_stmt)
    relations = rel_rows.scalars().all()

    if relations:
        # 4b. 收集 2 跳实体 ID（关系的另一端，且不在 matched_entity_ids 中）
        hop2_entity_ids: set[UUID] = set()
        for rel in relations:
            if rel.source_id in matched_entity_ids:
                hop2_entity_ids.add(rel.target_id)
            if rel.target_id in matched_entity_ids:
                hop2_entity_ids.add(rel.source_id)
        hop2_entity_ids -= matched_entity_ids  # 去自环

        if hop2_entity_ids:
            # 4c. 查 2 跳实体的 entity_mentions
            mention2_stmt = select(EntityMention.chunk_id).where(
                EntityMention.entity_id.in_(hop2_entity_ids)
            )
            mention2_rows = await db.execute(mention2_stmt)
            hop2_chunk_ids = {row[0] for row in mention2_rows}

            # 4d. 去重（已有 result 中的 chunk_id）
            existing_ids = {c.chunk_id for c in result}
            new_hop2_ids = hop2_chunk_ids - existing_ids

            if new_hop2_ids:
                chunk2_stmt = select(DocumentChunk).where(
                    DocumentChunk.id.in_(new_hop2_ids)
                )
                chunk2_rows = await db.execute(chunk2_stmt)
                for chunk in chunk2_rows.scalars().all():
                    result.append(RetrievedChunk(
                        kb_id=kb_id,
                        chunk_id=chunk.id,
                        document_id=chunk.document_id,
                        doc_name="",
                        content=chunk.content,
                        page_number=chunk.page_number,
                        section_title=chunk.section_title,
                        heading_path=chunk.heading_path,
                        similarity=0.25,
                    ))

    return result


# ── 内部辅助（不暴露给外部） ──


def _build_candidates(fused, merged, parent_contents, kb_id, chunk_kb):
    """RRF 融合结果 → RetrievedChunk 列表。"""
    candidates: list[RetrievedChunk] = []
    for chunk_id, rrf_score in fused:
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
            rrf_score=float(rrf_score),
        ))
    return candidates


def _resolve_static_variant_rules_path() -> Path:
    raw = settings.static_variant_rules_path
    path = Path(raw)
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parents[3] / path


_STATIC_VARIANT_RULES_CACHE: dict | None = None
_STATIC_VARIANT_RULES_CACHE_AT: float = 0.0
_STATIC_VARIANT_RULES_CACHE_TTL: float = 60.0


def _load_static_variant_rules() -> dict:
    global _STATIC_VARIANT_RULES_CACHE, _STATIC_VARIANT_RULES_CACHE_AT
    now = time.monotonic()
    if _STATIC_VARIANT_RULES_CACHE is not None and now - _STATIC_VARIANT_RULES_CACHE_AT < _STATIC_VARIANT_RULES_CACHE_TTL:
        return _STATIC_VARIANT_RULES_CACHE
    try:
        rules = json.loads(_resolve_static_variant_rules_path().read_text(encoding="utf-8"))
    except Exception:
        logger.warning("static variant rules load failed; fallback to empty rules", exc_info=True)
        rules = {"rules": []}
    _STATIC_VARIANT_RULES_CACHE = rules
    _STATIC_VARIANT_RULES_CACHE_AT = now
    return rules


def static_query_variants(query: str) -> list[str]:
    """Return deterministic variants for a query hit by static rules."""
    normalized = (query or "").lower().strip()
    if not normalized:
        return []
    variants: list[str] = []
    for rule in _load_static_variant_rules().get("rules", []):
        if any(keyword.lower() in normalized for keyword in rule.get("keywords", [])):
            for variant in rule.get("variants", []):
                if variant and variant not in variants:
                    variants.append(variant)
    return variants


async def _expand_if_low_confidence(db, result, query, kb_id, visible_kb_ids, hide_admin_only, top_k):
    """低置信度时 expand_queries 多路召回补偿。"""
    if not result or max(c.similarity for c in result) >= 0.6:
        return result
    try:
        if assess_degradation() >= DegradationLevel.LLM_DOWN:
            expanded = [query] + static_query_variants(query)
        else:
            from app.services.rag.generation import expand_queries
            expanded = await expand_queries(query)
        if len(expanded) <= 1:
            return result
        seen_ids = {c.chunk_id for c in result}
        for eq in expanded[1:]:
            if eq.lower().strip() == query.lower().strip():
                continue
            eq_vecs = await try_embed_texts([eq])
            if eq_vecs is None:
                continue
            eq_vec = eq_vecs[0]
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
