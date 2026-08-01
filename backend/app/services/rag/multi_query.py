"""A1 多 query：变体生成 + 多路召回 + RRF（原问 vector+FTS，变体仅 vector）。

开关：QUERY_REWRITE_POLICY（默认 off；always ≡ 旧 query_rewrite_enabled；
conditional 见 planner.should_expand_queries）。本模块不引入通义嵌入。
"""

from __future__ import annotations

import logging
import time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.rag.embed_route import (
    detect_query_lang,
    resolve_query_embed,
    vector_recall_en_empty_fallback,
)
from app.services.rag.executor import merge_recall_rows
from app.services.rag.fts_recall import fts_recall, _fts_recall_workspace
from app.services.rag.confidence_reply import is_low_confidence
from app.services.rag.rrf import reciprocal_rank_fusion
from app.services.rag.types import _RecallRow
from app.services.rag.vector_recall import vector_recall, _vector_recall_workspace

logger = logging.getLogger(__name__)

# 向后兼容：旧名仍指向公共语言检测
_detect_english = detect_query_lang


def mock_expand_queries(query: str, *, max_variants: int | None = None) -> list[str]:
    """确定性变体（诊断/单测可复现，不调 LLM）。

    策略：原问 + 去问号口语化 + 抽中文名词片段（若有）。
    """
    cap = max_variants or settings.query_rewrite_max_variants
    q = (query or "").strip()
    if not q:
        return [q]
    variants = [q]
    stripped = q.rstrip("？?。.!！").strip()
    if stripped and stripped.lower() != q.lower():
        variants.append(stripped)
    # 去掉常见口语前缀，利于条款/专名命中
    for prefix in ("请问", "想问一下", "帮我查", "麻烦问", "我想知道"):
        if stripped.startswith(prefix) and len(stripped) > len(prefix) + 1:
            variants.append(stripped[len(prefix):].lstrip("，, ：:").strip())
            break
    return _dedupe_cap([q] + variants[1:], cap=cap)


async def build_query_variants(
    query: str,
    *,
    injected: list[str] | None = None,
    use_mock: bool = False,
) -> list[str]:
    """返回去重后的问法列表，原问始终第一。失败则 [query]。"""
    cap = settings.query_rewrite_max_variants
    q = (query or "").strip()
    if not q:
        return [query]

    if injected is not None:
        return _dedupe_cap([q] + list(injected), cap=cap)

    if use_mock:
        return mock_expand_queries(q, max_variants=cap)

    try:
        from app.services.rag.generation import expand_queries

        expanded = await expand_queries(q)
        return _dedupe_cap(expanded if expanded else [q], cap=cap)
    except Exception:
        logger.warning("expand_queries failed; fallback to single query", exc_info=True)
        return [q]


def _dedupe_cap(queries: list[str], *, cap: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in queries:
        key = item.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item.strip())
        if len(out) >= cap:
            break
    return out or queries[:1]


async def multi_query_kb_recall(
    db: AsyncSession,
    *,
    kb_id: UUID,
    query: str,
    vector_limit: int,
    fts_limit: int,
    top_n: int,
    visible_kb_ids: frozenset[UUID] | None = None,
    hide_admin_only: bool = False,
    injected_variants: list[str] | None = None,
    use_mock: bool = False,
    additive_fusion: bool = True,
) -> tuple[list[tuple[UUID, float]], dict[UUID, _RecallRow], list[str]]:
    """单库多 query 召回：原问 vector+FTS，变体仅 vector，再 RRF。

    additive_fusion=True（默认）：B2-b 原问优先 + 变体 newcomers 追加池尾
    （防稀释原问 Top-N，适合近义改写变体）。
    additive_fusion=False：纯 RRF 竞争（实验 M 复合题用——子查询是不同知识
    点/条件，需参与排名竞争才有机会进 Top-K）。
    """
    t0 = time.perf_counter()
    variants = await build_query_variants(
        query, injected=injected_variants, use_mock=use_mock
    )

    ranked_lists: list[list[UUID]] = []
    weights: list[float] = []
    all_vector_rows: list[_RecallRow] = []
    fts_rows: list[_RecallRow] = []

    # 原问：vector + FTS（B4 共用 resolve + 空英列回主）
    original = variants[0]
    route = await resolve_query_embed(original)
    orig_vec = route.query_vec
    embed_col = route.embedding_col
    v_rows: list = []  # 初始化为空，防止嵌入失败时后续引用未定义变量

    if orig_vec is not None:

        async def _kb_orig_recall(*, query_vec, embedding_col):
            return await vector_recall(
                db,
                kb_id=kb_id,
                query_vec=query_vec,
                limit=vector_limit,
                visible_kb_ids=visible_kb_ids,
                hide_admin_only=hide_admin_only,
                embedding_col=embedding_col,
            )

        v_rows = await vector_recall_en_empty_fallback(
            query=original,
            query_vec=orig_vec,
            embedding_col=embed_col,
            recall=_kb_orig_recall,
        )
        all_vector_rows.extend(v_rows)
        ranked_lists.append([r.chunk.id for r in v_rows])
        weights.append(settings.rrf_vector_weight)
    else:
        ranked_lists.append([])
        weights.append(settings.rrf_vector_weight)

    fts_rows = await fts_recall(
        db,
        kb_id=kb_id,
        query=original,
        limit=fts_limit,
        visible_kb_ids=visible_kb_ids,
        hide_admin_only=hide_admin_only,
    )
    ranked_lists.append([r.chunk.id for r in fts_rows])
    weights.append(settings.rrf_fts_weight)

    # B2-b：自适应变体权重（以 is_low_confidence 返回值为准）
    var_w = settings.query_rewrite_variant_weight
    if len(variants) > 1:
        _orig_chunks = [r.chunk for r in v_rows if hasattr(r, 'chunk')] + [
            r.chunk for r in fts_rows if hasattr(r, 'chunk')
        ]
        if _orig_chunks and is_low_confidence(_orig_chunks):
            var_w = 1.0  # 低置信 → 提权变体，让变体结果更积极进入池

    # 变体：vector + FTS（B2-a）
    var_fts_w = var_w * 0.5  # 变体 FTS 权重减半，防稀释原问
    for eq in variants[1:]:
        eq_route = await resolve_query_embed(eq)
        eq_vec = eq_route.query_vec
        eq_col = eq_route.embedding_col
        if eq_vec is None:
            continue

        async def _kb_eq_recall(*, query_vec, embedding_col, _eq=eq):
            return await vector_recall(
                db,
                kb_id=kb_id,
                query_vec=query_vec,
                limit=vector_limit,
                visible_kb_ids=visible_kb_ids,
                hide_admin_only=hide_admin_only,
                embedding_col=embedding_col,
            )

        eq_rows = await vector_recall_en_empty_fallback(
            query=eq,
            query_vec=eq_vec,
            embedding_col=eq_col,
            recall=_kb_eq_recall,
        )
        all_vector_rows.extend(eq_rows)
        ranked_lists.append([r.chunk.id for r in eq_rows])
        weights.append(var_w)

        # B2-a：变体 FTS 召回
        eq_fts = await fts_recall(
            db, kb_id=kb_id, query=eq, limit=vector_limit,
            visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only,
        )
        if eq_fts:
            all_vector_rows.extend(eq_fts)
            ranked_lists.append([r.chunk.id for r in eq_fts])
            weights.append(var_fts_w)

    fused = (
        _additive_fuse_original_priority(
            ranked_lists, weights=weights, top_n=top_n, newcomer_slots=5
        )
        if additive_fusion and len(variants) > 1 and len(ranked_lists) >= 2
        else reciprocal_rank_fusion(
            ranked_lists, k=settings.rrf_k, weights=weights, top_n=top_n
        )
    )
    merged = merge_recall_rows(all_vector_rows, fts_rows)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "multi_query kb recall variants=%d lists=%d top_n=%d additive=%s elapsed_ms=%.1f",
        len(variants),
        len(ranked_lists),
        top_n,
        additive_fusion,
        elapsed_ms,
    )
    return fused, merged, variants


def _additive_fuse_original_priority(
    ranked_lists: list[list[UUID]],
    *,
    weights: list[float],
    top_n: int,
    newcomer_slots: int = 5,
) -> list[tuple[UUID, float]]:
    """原问 Top-N 全保留，变体新 chunk 追加到池尾（池大小 = top_n + slots）。

    检索侧后续仍可按 top_k / rerank 截断；诊断 Top-20 看前 N 时与单 query 一致，
    额外 slots 专供召回缺口题进入更大候选池。
    """
    if len(ranked_lists) < 2:
        return reciprocal_rank_fusion(
            ranked_lists, k=settings.rrf_k, weights=weights, top_n=top_n
        )

    base = reciprocal_rank_fusion(
        ranked_lists[:2],
        k=settings.rrf_k,
        weights=weights[:2],
        top_n=top_n,
    )
    if len(ranked_lists) == 2:
        return base

    base_set = {cid for cid, _ in base}
    var_fused = reciprocal_rank_fusion(
        ranked_lists[2:],
        k=settings.rrf_k,
        weights=weights[2:],
        top_n=top_n,
    )
    newcomers = [(cid, score) for cid, score in var_fused if cid not in base_set]
    slots = min(newcomer_slots, len(newcomers))
    if slots <= 0:
        return base
    # 原问结果全部保留，新来者追加（总长 top_n+slots）
    return list(base) + newcomers[:slots]


async def multi_query_workspace_recall(
    db: AsyncSession,
    *,
    query: str,
    scope,
    org_scope,
    vector_limit: int,
    fts_limit: int,
    top_n: int,
    visible_kb_ids: frozenset[UUID] | None = None,
    hide_admin_only: bool = False,
    scope_clause,
    injected_variants: list[str] | None = None,
    use_mock: bool = False,
    additive_fusion: bool = True,
) -> tuple[list[tuple[UUID, float]], dict[UUID, _RecallRow], list[str]]:
    """workspace 多 query 召回（口径同单库）。additive_fusion 语义同 multi_query_kb_recall。"""
    t0 = time.perf_counter()
    variants = await build_query_variants(
        query, injected=injected_variants, use_mock=use_mock
    )

    ranked_lists: list[list[UUID]] = []
    weights: list[float] = []
    all_vector_rows: list[_RecallRow] = []

    original = variants[0]
    route = await resolve_query_embed(original)
    orig_vec = route.query_vec
    embed_col = route.embedding_col
    v_rows: list = []  # 初始化为空，防止嵌入失败时后续引用未定义变量

    if orig_vec is not None:

        async def _ws_orig_recall(*, query_vec, embedding_col):
            return await _vector_recall_workspace(
                db,
                scope=scope,
                org_scope=org_scope,
                query_vec=query_vec,
                limit=vector_limit,
                visible_kb_ids=visible_kb_ids,
                hide_admin_only=hide_admin_only,
                embedding_col=embedding_col,
            )

        v_rows = await vector_recall_en_empty_fallback(
            query=original,
            query_vec=orig_vec,
            embedding_col=embed_col,
            recall=_ws_orig_recall,
        )
        all_vector_rows.extend(v_rows)
        ranked_lists.append([r.chunk.id for r in v_rows])
        weights.append(settings.rrf_vector_weight)
    else:
        ranked_lists.append([])
        weights.append(settings.rrf_vector_weight)

    fts_rows = await _fts_recall_workspace(
        db,
        scope_clause=scope_clause,
        query=original,
        limit=fts_limit,
        visible_kb_ids=visible_kb_ids,
        hide_admin_only=hide_admin_only,
    )
    ranked_lists.append([r.chunk.id for r in fts_rows])
    weights.append(settings.rrf_fts_weight)

    # B2-b：自适应变体权重（以 is_low_confidence 返回值为准）
    var_w = settings.query_rewrite_variant_weight
    if len(variants) > 1:
        _orig_chunks = [r.chunk for r in v_rows if hasattr(r, 'chunk')] + [
            r.chunk for r in fts_rows if hasattr(r, 'chunk')
        ]
        if _orig_chunks and is_low_confidence(_orig_chunks):
            var_w = 1.0

    var_fts_w = var_w * 0.5  # B2-a 变体 FTS 权重减半
    for eq in variants[1:]:
        eq_route = await resolve_query_embed(eq)
        eq_vec = eq_route.query_vec
        eq_col = eq_route.embedding_col
        if eq_vec is None:
            continue

        async def _ws_eq_recall(*, query_vec, embedding_col):
            return await _vector_recall_workspace(
                db,
                scope=scope,
                org_scope=org_scope,
                query_vec=query_vec,
                limit=vector_limit,
                visible_kb_ids=visible_kb_ids,
                hide_admin_only=hide_admin_only,
                embedding_col=embedding_col,
            )

        eq_rows = await vector_recall_en_empty_fallback(
            query=eq,
            query_vec=eq_vec,
            embedding_col=eq_col,
            recall=_ws_eq_recall,
        )
        all_vector_rows.extend(eq_rows)
        ranked_lists.append([r.chunk.id for r in eq_rows])
        weights.append(var_w)

        # B2-a：变体 FTS 召回
        eq_fts = await _fts_recall_workspace(
            db, scope_clause=scope_clause, query=eq, limit=vector_limit,
            visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only,
        )
        if eq_fts:
            all_vector_rows.extend(eq_fts)
            ranked_lists.append([r.chunk.id for r in eq_fts])
            weights.append(var_fts_w)

    fused = (
        _additive_fuse_original_priority(
            ranked_lists, weights=weights, top_n=top_n, newcomer_slots=5
        )
        if additive_fusion and len(variants) > 1 and len(ranked_lists) >= 2
        else reciprocal_rank_fusion(
            ranked_lists, k=settings.rrf_k, weights=weights, top_n=top_n
        )
    )
    merged = merge_recall_rows(all_vector_rows, fts_rows)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "multi_query workspace recall variants=%d lists=%d top_n=%d additive=%s elapsed_ms=%.1f",
        len(variants),
        len(ranked_lists),
        top_n,
        additive_fusion,
        elapsed_ms,
    )
    return fused, merged, variants
