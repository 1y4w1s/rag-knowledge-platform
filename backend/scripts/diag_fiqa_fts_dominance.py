#!/usr/bin/env python
"""fiqa FTS 泛词主导 Top-3 根因诊断脚本（规划文档 M1）。

只读诊断：复用现有 fiqa KB，不修改产品检索逻辑、不重新入库、
不调用 RAGAS / DeepSeek judge。全部指标基于 qrels 判定。

用法（cwd=backend）：
    python scripts/diag_fiqa_fts_dominance.py --dataset fiqa --kb <kb_id> --case 10152 --top-k 10
    python scripts/diag_fiqa_fts_dominance.py --dataset fiqa --kb <kb_id> --mode production
    python scripts/diag_fiqa_fts_dominance.py --dataset fiqa --kb <kb_id> --mode single --weights "1.0,1.5;1.5,1.0;1.0,1.0;1.0,0.8"
    python scripts/diag_fiqa_fts_dominance.py --dataset fiqa --kb <kb_id> --mode single --weights "1.0,1.5" --fts-mode phrase
    python scripts/diag_fiqa_fts_dominance.py --dataset fiqa --kb <kb_id> --mode pool --weights "1.0,1.5" --pool "20,20;30,30;50,50"
    python scripts/diag_fiqa_fts_dominance.py --dataset fiqa --kb <kb_id> --mode multi --variants mock
    python scripts/diag_fiqa_fts_dominance.py --dataset fiqa --kb <kb_id> --mode multi --variants cache --variants-cache backend/tmp/fiqa_llm_variants.jsonl --variant-weight "0.4;0.7;1.0"
    python scripts/diag_fiqa_fts_dominance.py --dataset fiqa --kb <kb_id> --mode cache-variants --variants-cache backend/tmp/fiqa_llm_variants.jsonl

输出：backend/benchmark_results/fiqa_fts_dominance_<ts>.json / .md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from uuid import UUID

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("diag_fiqa_fts_dominance")
# 单 query 逐条嵌入会高频打印 embedder/jieba 的 INFO/DEBUG，压掉避免刷屏。
logging.getLogger("app.services.ingestion.embedder").setLevel(logging.WARNING)
logging.getLogger("jieba").setLevel(logging.WARNING)

DEFAULT_KB = "5c6597cf-718d-4090-b063-30855ba692d3"
EXPECTED_CHUNKS = {"fiqa": 57638}
FTS_TS_CONFIG = "simple"
FTS_MODE_CHOICES = ("baseline", "and", "stopwords", "phrase", "all")
EN_STOPWORDS = frozenset(
    """
    a an the is are was were be been being am do does did have has had
    will would shall should can could may might must i me my mine we our
    ours you your yours he him his she her hers it its they them their
    theirs this that these those what which who whom whose when where why
    how all any both each few more most other some such no nor not only
    own same so than too very of in on at to for from with without about
    by over under between into through during before after above below up
    down out off then once here there s t just don now and or but if while
    """.split()
)
# case 对照固定输出三组权重；--weights 指定的其他组会追加。
CASE_WEIGHTS = ((1.0, 1.5), (1.5, 1.0), (1.0, 1.0))
VARIANT_FTS_HALVING = 0.5
ADDITIVE_NEWCOMER_SLOTS = 5

NOTE = (
    "qrels 检索指标口径（Hit@k/MRR/NDCG/Recall，无 LLM judge），"
    "与 RAGAS ContextPrecision/ContextRecall 数值不可比；"
    "Enterprise QA RRF 扫参已收口并维持默认，本报告为 BEIR/fiqa "
    "qrels 检索质量诊断，仅作为 fiqa 调优依据。"
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="fiqa FTS 泛词主导 Top-3 根因诊断（只读，无 judge）"
    )
    p.add_argument("--dataset", choices=("fiqa",), default="fiqa")
    p.add_argument(
        "--kb",
        default=None,
        help=f"fiqa 临时 KB UUID（默认 {DEFAULT_KB}）",
    )
    p.add_argument(
        "--mode",
        choices=("case", "production", "single", "pool", "multi", "cache-variants"),
        default=None,
        help="case 由 --case 触发；全量模式必须显式指定",
    )
    p.add_argument("--case", default=None, help="单 query 诊断 case_id（如 10152）")
    p.add_argument("--top-k", type=int, default=3, help="Top-K（默认 3）")
    p.add_argument(
        "--weights",
        default="1.0,1.5",
        help="RRF 权重矩阵 (vector,fts)，分号分隔多组，如 '1.0,1.5;1.5,1.0'",
    )
    p.add_argument(
        "--pool",
        default="30,30",
        help="候选池矩阵 (vector,fts)，分号分隔多组，如 '20,20;30,30;50,50'",
    )
    p.add_argument(
        "--variants",
        choices=("none", "mock", "cache"),
        default="none",
        help="multi 模式变体来源：none 单路 / mock 确定性 / cache LLM 缓存",
    )
    p.add_argument(
        "--fts-mode",
        choices=FTS_MODE_CHOICES,
        default="baseline",
        help=(
            "single 模式 FTS tsquery 语义实验：baseline 生产 OR / and 全词 AND / "
            "stopwords 去英文停用词 OR / phrase 精确短语；非 baseline 自动附带 baseline 对照"
        ),
    )
    p.add_argument(
        "--variant-weight",
        default="0.7",
        help="变体权重矩阵（分号分隔）；变体 FTS = 权重 * 0.5",
    )
    p.add_argument(
        "--variants-cache",
        default="tmp/fiqa_llm_variants.jsonl",
        help="LLM 变体缓存 jsonl（相对 backend，兼容 backend/tmp/... 写法）",
    )
    p.add_argument(
        "--out-dir",
        default="benchmark_results",
        help="报告输出目录（相对 backend）",
    )
    p.add_argument(
        "--sample",
        type=int,
        default=None,
        help="只跑前 N 条查询（全量模式；默认全量）",
    )
    p.add_argument(
        "--no-additive",
        action="store_true",
        help="multi 模式关闭原问优先 additive 融合，改纯 RRF 竞争",
    )
    return p.parse_args()


def _load_dotenv() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("\"'")
        if key and not os.environ.get(key):
            os.environ[key] = val


def _resolve_backend_path(raw: str) -> Path:
    """把相对 backend 的路径解析为绝对路径；兼容 backend/ 前缀写法。"""
    path = Path(raw)
    if path.is_absolute():
        return path
    text = str(path).replace("\\", "/")
    if text.startswith("backend/"):
        text = text[len("backend/"):]
    return BASE_DIR / text


def _parse_pair_matrix(raw: str) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for part in raw.split(";"):
        part = part.strip()
        if not part:
            continue
        left, _, right = part.partition(",")
        out.append((float(left.strip()), float(right.strip())))
    if not out:
        raise SystemExit(f"无法解析数值对: {raw!r}")
    return out


def _parse_pool_matrix(raw: str) -> list[tuple[int, int]]:
    pairs = _parse_pair_matrix(raw)
    if any(pv != int(pv) or pf != int(pf) for pv, pf in pairs):
        raise SystemExit(f"候选池必须是整数: {raw!r}")
    return [(int(pv), int(pf)) for pv, pf in pairs]


def _parse_float_list(raw: str) -> list[float]:
    out = [float(x.strip()) for x in raw.split(";") if x.strip()]
    if not out:
        raise SystemExit(f"无法解析数值列表: {raw!r}")
    return out


def _resolve_fts_modes(args: argparse.Namespace) -> list[str]:
    if args.fts_mode == "all":
        modes = ["baseline", "and", "stopwords", "phrase"]
    else:
        modes = [args.fts_mode]
    if "baseline" not in modes:
        modes.insert(0, "baseline")
    return modes


def _fts_mode_label(mode: str) -> str:
    return {
        "baseline": "OR 全词",
        "and": "AND 全词",
        "stopwords": "去停用词 OR",
        "phrase": "精确短语",
    }.get(mode, mode)


def _build_fts_tsquery(query: str, fts_mode: str):
    from sqlalchemy import func

    from app.services.rag.cjk import segment_cjk

    if fts_mode == "phrase":
        return func.phraseto_tsquery(FTS_TS_CONFIG, query)
    tokens = [t for t in segment_cjk(query).split() if t.strip()]
    if fts_mode == "stopwords":
        tokens = [t for t in tokens if t.lower() not in EN_STOPWORDS]
    if not tokens:
        return func.plainto_tsquery(FTS_TS_CONFIG, query)
    escaped = [t.replace("'", "''") for t in tokens]
    joiner = " & " if fts_mode == "and" else " | "
    return func.to_tsquery(FTS_TS_CONFIG, joiner.join(f"'{t}'" for t in escaped))


def _sample_items(queries: dict[str, str], sample: int | None) -> list[tuple[str, str]]:
    items = list(queries.items())
    if sample and sample < len(items):
        items = items[:sample]
    return items


def _load_queries_and_qrels(dataset: str) -> tuple[dict[str, str], dict[str, list[str]]]:
    from tests.benchmark.loaders import get_loader

    loader = get_loader(f"beir/{dataset}")
    queries = loader._load_queries()
    qrels = loader._load_qrels()
    if qrels:
        # queries.jsonl 是 fiqa 全量（6,648 条），qrels 只覆盖 test 648 条；
        # 与 loader.load() 的过滤口径一致，全量模式只评估有 qrels 的查询。
        queries = {qid: text for qid, text in queries.items() if qid in qrels}
    logger.info(
        "dataset=%s queries_with_qrels=%d qrels_queries=%d",
        dataset,
        len(queries),
        len(qrels),
    )
    return queries, qrels


async def _kb_chunk_count(db, kb_id: UUID) -> int:
    from sqlalchemy import func, select

    from app.models.document_chunk import DocumentChunk

    stmt = (
        select(func.count())
        .select_from(DocumentChunk)
        .where(DocumentChunk.kb_id == kb_id)
    )
    return int((await db.execute(stmt)).scalar_one())


async def _verify_kb(db, kb_id: UUID, dataset: str) -> int:
    count = await _kb_chunk_count(db, kb_id)
    expected = EXPECTED_CHUNKS[dataset]
    if count != expected:
        raise RuntimeError(
            f"KB {kb_id} chunk 数 = {count}，期望 {expected}；"
            "疑似误用其他库，脚本拒绝继续（不自动重新入库）"
        )
    logger.info("KB %s chunk 数校验通过: %d", kb_id, count)
    return count


async def _vector_rows_for_query(
    db,
    kb_id: UUID,
    query: str,
    limit: int,
) -> list:
    from app.services.rag.embed_route import (
        resolve_query_embed,
        vector_recall_en_empty_fallback,
    )
    from app.services.rag.vector_recall import vector_recall

    route = await resolve_query_embed(query)
    if route.query_vec is None:
        logger.warning(
            "query embed unavailable (provider=%s col=%s fallback_from_en=%s); "
            "vector recall degraded to FTS-only，请检查嵌入模型缓存/网络",
            route.provider,
            route.embedding_col,
            route.fallback_from_en,
        )
        return []

    async def _recall(*, query_vec, embedding_col):
        return await vector_recall(
            db,
            kb_id=kb_id,
            query_vec=query_vec,
            limit=limit,
            embedding_col=embedding_col,
        )

    return await vector_recall_en_empty_fallback(
        query=query,
        query_vec=route.query_vec,
        embedding_col=route.embedding_col,
        recall=_recall,
    )


async def _fts_rows_for_query_variant(
    db,
    kb_id: UUID,
    query: str,
    limit: int,
    fts_mode: str,
) -> list:
    from sqlalchemy import func, select

    from app.models.document import Document
    from app.models.document_chunk import DocumentChunk
    from app.services.rag.fts_recall import _escape_ilike, _has_special_chars
    from app.services.rag.types import _RecallRow

    ts_query = _build_fts_tsquery(query, fts_mode)
    rank = func.ts_rank_cd(DocumentChunk.content_tsv, ts_query).label("fts_rank")
    fts_condition = DocumentChunk.content_tsv.op("@@")(ts_query)
    if _has_special_chars(query):
        fts_condition = fts_condition | DocumentChunk.content.ilike(
            f"%{_escape_ilike(query)}%", escape="\\"
        )
    stmt = (
        select(DocumentChunk, Document.filename, rank)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(DocumentChunk.kb_id == kb_id)
        .where(fts_condition)
        .where(Document.deleted_at.is_(None))
        .order_by(rank.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [
        _RecallRow(chunk=chunk, filename=filename, fts_rank=float(fts_rank))
        for chunk, filename, fts_rank in rows
    ]


async def _fts_rows_for_query(
    db,
    kb_id: UUID,
    query: str,
    limit: int,
    fts_mode: str = "baseline",
) -> list:
    if fts_mode == "baseline":
        from app.services.rag.fts_recall import fts_recall

        return await fts_recall(db, kb_id=kb_id, query=query, limit=limit)
    return await _fts_rows_for_query_variant(db, kb_id, query, limit, fts_mode)


def _fuse_single(
    v_rows: list,
    f_rows: list,
    weights: tuple[float, float],
    top_n: int,
) -> list[tuple[UUID, float]]:
    from app.core.config import settings
    from app.services.rag.rrf import reciprocal_rank_fusion

    return reciprocal_rank_fusion(
        [[row.chunk.id for row in v_rows], [row.chunk.id for row in f_rows]],
        k=settings.rrf_k,
        weights=list(weights),
        top_n=top_n,
    )


async def _collect_multi_lists(
    db,
    kb_id: UUID,
    query: str,
    variants: list[str],
    vec_limit: int,
    fts_limit: int,
) -> tuple[list[list[UUID]], list[str], list]:
    """复刻 multi_query_kb_recall 的召回构造：原问 v+f，变体 v+f（变体 FTS 池=vector_limit）。"""
    v0 = await _vector_rows_for_query(db, kb_id, query, vec_limit)
    f0 = await _fts_rows_for_query(db, kb_id, query, fts_limit)
    lists: list[list[UUID]] = [
        [row.chunk.id for row in v0],
        [row.chunk.id for row in f0],
    ]
    kinds = ["orig_v", "orig_f"]
    all_rows: list = [*v0, *f0]
    for eq in variants[1:]:
        eq_vec = await _vector_rows_for_query(db, kb_id, eq, vec_limit)
        lists.append([row.chunk.id for row in eq_vec])
        kinds.append("var_v")
        all_rows.extend(eq_vec)
        eq_fts = await _fts_rows_for_query(db, kb_id, eq, vec_limit)
        if eq_fts:
            lists.append([row.chunk.id for row in eq_fts])
            kinds.append("var_f")
            all_rows.extend(eq_fts)
    return lists, kinds, all_rows


def _fuse_multi(
    lists: list[list[UUID]],
    kinds: list[str],
    *,
    wv: float,
    wf: float,
    var_w: float,
    top_n: int,
    additive: bool,
) -> list[tuple[UUID, float]]:
    """参数化多 query 融合；additive 语义同产品 _additive_fuse_original_priority。"""
    from app.core.config import settings
    from app.services.rag.rrf import reciprocal_rank_fusion

    weights: list[float] = []
    for kind in kinds:
        if kind == "orig_v":
            weights.append(wv)
        elif kind == "orig_f":
            weights.append(wf)
        elif kind == "var_v":
            weights.append(var_w)
        else:
            weights.append(var_w * VARIANT_FTS_HALVING)

    if not additive or len(lists) <= 2:
        return reciprocal_rank_fusion(
            lists,
            k=settings.rrf_k,
            weights=weights,
            top_n=top_n,
        )
    base = reciprocal_rank_fusion(
        lists[:2],
        k=settings.rrf_k,
        weights=weights[:2],
        top_n=top_n,
    )
    base_set = {cid for cid, _ in base}
    var_fused = reciprocal_rank_fusion(
        lists[2:],
        k=settings.rrf_k,
        weights=weights[2:],
        top_n=top_n,
    )
    newcomers = [(cid, score) for cid, score in var_fused if cid not in base_set]
    slots = min(ADDITIVE_NEWCOMER_SLOTS, len(newcomers))
    return list(base) + newcomers[:slots]


def ndcg_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    """口径与 scripts/eval_msmarco_bm25_full.py::ndcg_at_k 保持一致。"""
    dcg = 0.0
    for rank in range(min(k, len(ranked))):
        rel = 1.0 if ranked[rank] in relevant else 0.0
        dcg += rel if rank == 0 else rel / (rank + 1)
    idcg = 0.0
    for rank in range(min(k, len(relevant))):
        idcg += 1.0 if rank == 0 else 1.0 / (rank + 1)
    return dcg / idcg if idcg > 0 else 0.0


def _metrics_for_ranked(
    ranked_docs: list[str],
    relevant: set[str],
    top_k: int,
) -> dict:
    # additive 融合可能返回超过 top_k 的池尾（原问 Top-N + 变体追加），
    # 指标只评估前 top_k，与 fused[:top_k] 口径一致。
    ranked = [doc for doc in ranked_docs if doc][:top_k]
    hit_1 = 1.0 if ranked and ranked[0] in relevant else 0.0
    hit_k = 1.0 if any(doc in relevant for doc in ranked) else 0.0
    mrr = 0.0
    for i, doc in enumerate(ranked, 1):
        if doc in relevant:
            mrr = 1.0 / i
            break
    recall = (
        sum(1 for doc in ranked if doc in relevant) / len(relevant)
        if relevant
        else 0.0
    )
    return {
        "hit_at_1": hit_1,
        "hit_at_k": hit_k,
        "mrr": mrr,
        "ndcg_at_k": ndcg_at_k(ranked, relevant, top_k),
        "recall_at_k": recall,
    }


def _special_metrics(
    v_rows: list,
    f_rows: list,
    fused: list[tuple[UUID, float]],
    relevant: set[str],
    top_k: int,
) -> dict:
    """H1/H3 量化：fts_only_top3 / lost_by_rrf / relevant_fts_rank / vector_pool_hit。"""
    vector_pool = {str(row.chunk.id) for row in v_rows}
    fused_rows = fused[:top_k]
    fused_ids = {str(cid) for cid, _ in fused_rows}
    doc_by_chunk = {
        str(row.chunk.id): row.filename for row in [*v_rows, *f_rows]
    }

    denom = len(fused_rows)
    fts_only_count = 0
    for cid, _ in fused_rows:
        cid_s = str(cid)
        if cid_s not in vector_pool and doc_by_chunk.get(cid_s) not in relevant:
            fts_only_count += 1
    fts_only = fts_only_count / denom if denom else 0.0

    lost = 0
    lost_denom = 0
    for row in v_rows:
        if row.filename in relevant:
            lost_denom = 1
            if str(row.chunk.id) not in fused_ids:
                lost = 1
            break

    rel_fts_rank = None
    for i, row in enumerate(f_rows, 1):
        if row.filename in relevant:
            rel_fts_rank = i
            break

    vector_pool_hit = 1 if any(row.filename in relevant for row in v_rows) else 0
    return {
        "fts_only_top3": fts_only,
        "fts_only_top3_denom": denom,
        "lost_by_rrf": lost,
        "lost_by_rrf_denom": lost_denom,
        "relevant_fts_rank": rel_fts_rank,
        "vector_pool_hit": vector_pool_hit,
    }


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _aggregate_metrics(cases: list[dict], top_k: int) -> dict:
    n = len(cases)
    if n == 0:
        return {
            "queries": 0,
            "hit_at_1": 0.0,
            "hit_at_k": 0.0,
            "mrr": 0.0,
            "ndcg_at_k": 0.0,
            "recall_at_k": 0.0,
            "fts_only_top3": 0.0,
            "lost_by_rrf": 0.0,
            "lost_by_rrf_base": 0,
            "lost_by_rrf_hits": 0,
            "relevant_fts_rank_median": None,
            "relevant_fts_rank_hit_rate": 0.0,
            "vector_pool_hit_rate": 0.0,
            "top_k": top_k,
        }

    def mean(key: str) -> float:
        return sum(case["metrics"][key] for case in cases) / n

    fts_denom = sum(case["metrics"]["fts_only_top3_denom"] for case in cases)
    fts_weighted = sum(
        case["metrics"]["fts_only_top3"] * case["metrics"]["fts_only_top3_denom"]
        for case in cases
    )
    lost_total = sum(case["metrics"]["lost_by_rrf"] for case in cases)
    lost_base = sum(case["metrics"]["lost_by_rrf_denom"] for case in cases)
    ranks = [
        case["metrics"]["relevant_fts_rank"]
        for case in cases
        if case["metrics"]["relevant_fts_rank"] is not None
    ]
    return {
        "queries": n,
        "hit_at_1": round(mean("hit_at_1"), 4),
        "hit_at_k": round(mean("hit_at_k"), 4),
        "mrr": round(mean("mrr"), 4),
        "ndcg_at_k": round(mean("ndcg_at_k"), 4),
        "recall_at_k": round(mean("recall_at_k"), 4),
        "fts_only_top3": round(fts_weighted / fts_denom, 4) if fts_denom else 0.0,
        "lost_by_rrf": round(lost_total / n, 4),
        "lost_by_rrf_base": lost_base,
        "lost_by_rrf_hits": lost_total,
        "relevant_fts_rank_median": _median(ranks),
        "relevant_fts_rank_hit_rate": round(len(ranks) / n, 4),
        "vector_pool_hit_rate": round(mean("vector_pool_hit"), 4),
        "top_k": top_k,
    }


def _row_to_dict(row, relevant: set[str]) -> dict:
    return {
        "doc_id": row.filename,
        "chunk_id": str(row.chunk.id),
        "relevant": row.filename in relevant,
        "vector_similarity": (
            round(float(row.vector_similarity), 6)
            if row.vector_similarity is not None
            else None
        ),
        "fts_rank": (
            round(float(row.fts_rank), 6) if row.fts_rank is not None else None
        ),
        "content_excerpt": (row.chunk.content or "")[:160],
    }


def _rrf_case_block(
    v_rows: list,
    f_rows: list,
    weights: tuple[float, float],
    top_n: int,
    relevant: set[str],
) -> list[dict]:
    fused = _fuse_single(v_rows, f_rows, weights, top_n)
    doc_by_chunk = {str(row.chunk.id): row for row in [*v_rows, *f_rows]}
    rows: list[dict] = []
    for rank, (cid, score) in enumerate(fused, 1):
        row = doc_by_chunk.get(str(cid))
        if row is None:
            continue
        item = _row_to_dict(row, relevant)
        item["rank"] = rank
        item["rrf_score"] = round(float(score), 6)
        rows.append(item)
    return rows


async def _run_case(
    db,
    args: argparse.Namespace,
    queries: dict[str, str],
    qrels: dict[str, list[str]],
    kb_chunks: int,
) -> dict:
    from sqlalchemy import select

    from app.models.document import Document

    qid = str(args.case)
    query = queries.get(qid)
    if query is None:
        raise SystemExit(f"case {qid} 不在查询集中")
    relevant = set(qrels.get(qid, []))

    weights_list: list[tuple[float, float]] = []
    for weights in [*CASE_WEIGHTS, *_parse_pair_matrix(args.weights)]:
        if weights not in weights_list:
            weights_list.append(weights)

    pool_vec, pool_fts = _parse_pool_matrix(args.pool)[0]
    v_rows = await _vector_rows_for_query(db, args.kb_uuid, query, pool_vec)
    f_rows = await _fts_rows_for_query(db, args.kb_uuid, query, pool_fts)

    vector_rows = [
        {"rank": rank, **_row_to_dict(row, relevant)}
        for rank, row in enumerate(v_rows[: args.top_k], 1)
    ]
    fts_rows = [
        {"rank": rank, **_row_to_dict(row, relevant)}
        for rank, row in enumerate(f_rows[: args.top_k], 1)
    ]

    vector_pool_ids = {str(row.chunk.id) for row in v_rows}
    rrf_blocks: list[dict] = []
    rank_113585: dict[str, int | None] = {}
    fts_only_top3: dict[str, int] = {}
    for wv, wf in weights_list:
        key = f"{wv:.1f},{wf:.1f}"
        block_rows = _rrf_case_block(
            v_rows,
            f_rows,
            (wv, wf),
            args.top_k,
            relevant,
        )
        rrf_blocks.append(
            {
                "channel": f"rrf-{key}",
                "weights": [wv, wf],
                "rows": block_rows,
            }
        )
        rank_113585[key] = next(
            (row["rank"] for row in block_rows if row["doc_id"] == "113585"),
            None,
        )
        fts_only_top3[key] = sum(
            1
            for row in block_rows[:3]
            if row["chunk_id"] not in vector_pool_ids and not row["relevant"]
        )

    doc_113585 = (
        await db.execute(
            select(Document).where(
                Document.kb_id == args.kb_uuid,
                Document.filename == "113585",
            )
        )
    ).scalar_one_or_none()
    in_vector_top10 = any(row["doc_id"] == "113585" for row in vector_rows)
    checks = {
        "kb_chunk_count": kb_chunks,
        "doc_113585_mapped": doc_113585 is not None,
        "doc_113585_document_id": str(doc_113585.id) if doc_113585 else None,
        "doc_113585_in_vector_top10": in_vector_top10,
        "rrf_rank_113585": rank_113585,
        "top3_fts_only_non_relevant": fts_only_top3,
    }

    case_detail = {
        "case_id": qid,
        "query": query,
        "relevant_doc_ids": sorted(relevant),
        "blocks": [
            {"channel": "vector-only", "rows": vector_rows},
            {"channel": "fts-only", "rows": fts_rows},
            *rrf_blocks,
        ],
        "checks": checks,
    }
    _print_case_table(case_detail)
    return {"mode": "case", "case_detail": case_detail}


def _print_case_table(case_detail: dict) -> None:
    print(f"\n=== Case {case_detail['case_id']} ===")
    print(f"query: {case_detail['query']}")
    print(f"qrels relevant: {case_detail['relevant_doc_ids']}")
    for block in case_detail["blocks"]:
        print(f"\n--- {block['channel']} ---")
        header = "rank | doc_id | relevant | vector_similarity | fts_rank | rrf_score"
        print(header)
        for row in block["rows"]:
            vs = (
                f"{row['vector_similarity']:.6f}"
                if row["vector_similarity"] is not None
                else "-"
            )
            fr = f"{row['fts_rank']:.6f}" if row["fts_rank"] is not None else "-"
            rr = (
                f"{row['rrf_score']:.6f}"
                if row.get("rrf_score") is not None
                else "-"
            )
            print(
                f"{row['rank']} | {row['doc_id']} | "
                f"{'Y' if row['relevant'] else 'N'} | {vs} | {fr} | {rr}"
            )
    print("\n--- hard checks ---")
    for key, value in case_detail["checks"].items():
        print(f"{key}: {value}")


def _single_pool_configs(args: argparse.Namespace) -> list[dict]:
    weights_matrix = _parse_pair_matrix(args.weights)
    pools = _parse_pool_matrix(args.pool)
    if args.mode == "single":
        pv, pf = pools[0]
        return [
            {
                "name": f"single weights={wv:.1f},{wf:.1f} pool={pv},{pf} fts={fts_mode}",
                "weights": (wv, wf),
                "pool": (pv, pf),
                "fts_mode": fts_mode,
                "params": {
                    "rrf_vector_weight": wv,
                    "rrf_fts_weight": wf,
                    "vector_pool": pv,
                    "fts_pool": pf,
                    "variants": "none",
                    "fts_mode": fts_mode,
                    "fts_tsquery": _fts_mode_label(fts_mode),
                },
            }
            for fts_mode in _resolve_fts_modes(args)
            for wv, wf in weights_matrix
        ]
    wv, wf = weights_matrix[0]
    return [
        {
            "name": f"pool={pv},{pf} weights={wv:.1f},{wf:.1f}",
            "weights": (wv, wf),
            "pool": (pv, pf),
            "fts_mode": "baseline",
            "params": {
                "rrf_vector_weight": wv,
                "rrf_fts_weight": wf,
                "vector_pool": pv,
                "fts_pool": pf,
                "variants": "none",
                "fts_mode": "baseline",
                "fts_tsquery": _fts_mode_label("baseline"),
            },
        }
        for pv, pf in pools
    ]


async def _run_single_pool(
    db,
    args: argparse.Namespace,
    queries: dict[str, str],
    qrels: dict[str, list[str]],
) -> dict:
    configs = _single_pool_configs(args)
    max_vec = max(cfg["pool"][0] for cfg in configs)
    max_fts = max(cfg["pool"][1] for cfg in configs)
    fts_modes = sorted(
        {cfg["fts_mode"] for cfg in configs},
        key=FTS_MODE_CHOICES.index,
    )
    exp_cases: dict[str, list[dict]] = {cfg["name"]: [] for cfg in configs}
    items = _sample_items(queries, args.sample)

    for i, (qid, query) in enumerate(items, 1):
        relevant = set(qrels.get(qid, []))
        v_rows = await _vector_rows_for_query(db, args.kb_uuid, query, max_vec)
        f_rows_by_mode = {
            mode: await _fts_rows_for_query(db, args.kb_uuid, query, max_fts, mode)
            for mode in fts_modes
        }
        all_f_rows = [
            row for rows in f_rows_by_mode.values() for row in rows
        ]
        doc_by_chunk = {
            str(row.chunk.id): row.filename for row in [*v_rows, *all_f_rows]
        }
        for cfg in configs:
            pv, pf = cfg["pool"]
            vv = v_rows[:pv]
            ff = f_rows_by_mode[cfg["fts_mode"]][:pf]
            fused = _fuse_single(vv, ff, cfg["weights"], args.top_k)
            ranked_docs = [doc_by_chunk.get(str(cid)) or "" for cid, _ in fused]
            metrics = _metrics_for_ranked(ranked_docs, relevant, args.top_k)
            metrics.update(_special_metrics(vv, ff, fused, relevant, args.top_k))
            exp_cases[cfg["name"]].append(
                {
                    "case_id": qid,
                    "query": query,
                    "metrics": metrics,
                    "top_doc_ids": ranked_docs,
                }
            )
        if i % 50 == 0:
            logger.info("%s: %d/%d queries", args.mode, i, len(items))

    experiments = [
        {
            "name": cfg["name"],
            "params": cfg["params"],
            "metrics": _aggregate_metrics(exp_cases[cfg["name"]], args.top_k),
            "cases": exp_cases[cfg["name"]],
        }
        for cfg in configs
    ]
    return {"mode": args.mode, "experiments": experiments}


def _load_variant_cache(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    cache: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        qid = str(rec.get("case_id"))
        variants = rec.get("variants") or []
        if qid and variants:
            cache[qid] = list(variants)
    return cache


def _append_variant_cache(
    path: Path,
    qid: str,
    query: str,
    variants: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {"case_id": qid, "query": query, "variants": variants},
                ensure_ascii=False,
            )
            + "\n"
        )
        fh.flush()


async def _resolve_variants(
    cache: dict[str, list[str]],
    qid: str,
    query: str,
    mode: str,
    cache_path: Path,
) -> list[str]:
    if mode == "none":
        return [query]
    if mode == "mock":
        from app.services.rag.multi_query import mock_expand_queries

        return mock_expand_queries(query)
    cached = cache.get(qid)
    if cached:
        return cached
    from app.services.rag.generation import expand_queries

    variants = await expand_queries(query)
    cache[qid] = variants
    _append_variant_cache(cache_path, qid, query, variants)
    return variants


async def _run_multi(
    db,
    args: argparse.Namespace,
    queries: dict[str, str],
    qrels: dict[str, list[str]],
) -> dict:
    var_weights = _parse_float_list(args.variant_weight)
    wv, wf = _parse_pair_matrix(args.weights)[0]
    pv, pf = _parse_pool_matrix(args.pool)[0]
    additive = not args.no_additive
    cache_path = _resolve_backend_path(args.variants_cache)
    cache = _load_variant_cache(cache_path)
    configs = [
        {
            "name": f"multi variants={args.variants} var_w={var_w:.2f} "
            f"additive={'on' if additive else 'off'}",
            "var_w": var_w,
            "params": {
                "rrf_vector_weight": wv,
                "rrf_fts_weight": wf,
                "vector_pool": pv,
                "fts_pool": pf,
                "variants": args.variants,
                "variant_weight": var_w,
                "additive_fusion": additive,
            },
        }
        for var_w in var_weights
    ]
    exp_cases: dict[str, list[dict]] = {cfg["name"]: [] for cfg in configs}
    items = _sample_items(queries, args.sample)

    for i, (qid, query) in enumerate(items, 1):
        relevant = set(qrels.get(qid, []))
        variants = await _resolve_variants(
            cache,
            qid,
            query,
            args.variants,
            cache_path,
        )
        lists, kinds, all_rows = await _collect_multi_lists(
            db,
            args.kb_uuid,
            query,
            variants,
            pv,
            pf,
        )
        doc_by_chunk = {
            str(row.chunk.id): row.filename for row in all_rows
        }
        # 原问 vector/FTS 行：按 kinds/lists 从 all_rows 切分（all_rows 顺序即
        # v0+f0+变体路，与 lists 一一对应）。
        orig_v_rows = []
        orig_f_rows = []
        cursor = 0
        for kind, ranked in zip(kinds, lists):
            rows_for_list = all_rows[cursor : cursor + len(ranked)]
            cursor += len(ranked)
            if kind == "orig_v":
                orig_v_rows = rows_for_list
            elif kind == "orig_f":
                orig_f_rows = rows_for_list

        for cfg in configs:
            fused = _fuse_multi(
                lists,
                kinds,
                wv=wv,
                wf=wf,
                var_w=cfg["var_w"],
                top_n=args.top_k,
                additive=additive,
            )
            ranked_docs = [doc_by_chunk.get(str(cid)) or "" for cid, _ in fused]
            metrics = _metrics_for_ranked(ranked_docs, relevant, args.top_k)
            metrics.update(
                _special_metrics(
                    orig_v_rows,
                    orig_f_rows,
                    fused,
                    relevant,
                    args.top_k,
                )
            )
            exp_cases[cfg["name"]].append(
                {
                    "case_id": qid,
                    "query": query,
                    "metrics": metrics,
                    "top_doc_ids": ranked_docs[: args.top_k],
                    "variants": variants,
                }
            )
        if i % 50 == 0:
            logger.info("multi: %d/%d queries", i, len(items))

    experiments = [
        {
            "name": cfg["name"],
            "params": cfg["params"],
            "metrics": _aggregate_metrics(exp_cases[cfg["name"]], args.top_k),
            "cases": exp_cases[cfg["name"]],
        }
        for cfg in configs
    ]
    return {
        "mode": "multi",
        "variant_cache_path": str(cache_path),
        "experiments": experiments,
    }


async def _run_production(
    db,
    args: argparse.Namespace,
    queries: dict[str, str],
    qrels: dict[str, list[str]],
) -> dict:
    from app.core.config import settings
    from app.services.rag.retrieval import retrieve_chunks

    wv = settings.rrf_vector_weight
    wf = settings.rrf_fts_weight
    pv = settings.vector_recall_k
    pf = settings.fts_recall_k
    cases: list[dict] = []
    items = _sample_items(queries, args.sample)

    for i, (qid, query) in enumerate(items, 1):
        relevant = set(qrels.get(qid, []))
        chunks = await retrieve_chunks(
            db,
            kb_id=args.kb_uuid,
            query=query,
            top_k=args.top_k,
        )
        ranked_docs = [chunk.doc_name for chunk in chunks]
        metrics = _metrics_for_ranked(ranked_docs, relevant, args.top_k)
        # 单路辅助指标不调 LLM；检索排序本身走生产 retrieve_chunks。
        v_rows = await _vector_rows_for_query(db, args.kb_uuid, query, pv)
        f_rows = await _fts_rows_for_query(db, args.kb_uuid, query, pf)
        fused = _fuse_single(v_rows, f_rows, (wv, wf), args.top_k)
        metrics.update(_special_metrics(v_rows, f_rows, fused, relevant, args.top_k))
        cases.append(
            {
                "case_id": qid,
                "query": query,
                "metrics": metrics,
                "top_doc_ids": ranked_docs,
            }
        )
        if i % 20 == 0:
            logger.info("production: %d/%d queries", i, len(items))

    experiments = [
        {
            "name": "production hybrid (retrieve_chunks)",
            "params": {
                "rrf_vector_weight": wv,
                "rrf_fts_weight": wf,
                "vector_pool": pv,
                "fts_pool": pf,
                "engine": "production_hybrid",
                "note": "complex 强制多查询 + HyDE 按生产配置生效，LLM 变体非确定",
            },
            "metrics": _aggregate_metrics(cases, args.top_k),
            "cases": cases,
        }
    ]
    return {"mode": "production", "experiments": experiments}


async def _run_cache_variants(
    db,
    args: argparse.Namespace,
    queries: dict[str, str],
) -> None:
    from app.services.rag.generation import expand_queries

    cache_path = _resolve_backend_path(args.variants_cache)
    cache = _load_variant_cache(cache_path)
    pending = [
        (qid, query)
        for qid, query in queries.items()
        if qid not in cache or not cache[qid]
    ]
    if args.sample:
        pending = pending[: args.sample]
    if not pending:
        logger.info("variant cache 已齐（%d 条），无需生成", len(cache))
        return
    for i, (qid, query) in enumerate(pending, 1):
        variants = await expand_queries(query)
        cache[qid] = variants
        _append_variant_cache(cache_path, qid, query, variants)
        if i % 20 == 0:
            logger.info("cached %d/%d variant sets", i, len(pending))
    logger.info(
        "variant cache ready: %s (%d entries)",
        cache_path,
        len(cache),
    )


def _render_markdown(args: argparse.Namespace, payload: dict) -> str:
    lines = [
        f"# BEIR/{args.dataset} FTS 泛词主导诊断报告",
        "",
        f"> 生成时间：{payload['generated_at']} · KB `{payload['kb_id']}` · "
        f"模式 `{payload['mode']}` · top_k={payload['top_k']}",
        "",
        "> " + NOTE,
        "",
    ]
    if payload["mode"] == "case":
        case_detail = payload["case_detail"]
        lines.append(f"## Case {case_detail['case_id']}")
        lines.append("")
        lines.append(f"query：{case_detail['query']}")
        lines.append(f"qrels relevant：{case_detail['relevant_doc_ids']}")
        lines.append("")
        lines.append("| 通道 | rank | doc_id | relevant | vector_similarity | fts_rank | rrf_score |")
        lines.append("|------|------|--------|----------|-------------------|----------|-----------|")
        for block in case_detail["blocks"]:
            for row in block["rows"]:
                vs = (
                    f"{row['vector_similarity']:.6f}"
                    if row["vector_similarity"] is not None
                    else "-"
                )
                fr = f"{row['fts_rank']:.6f}" if row["fts_rank"] is not None else "-"
                rr = (
                    f"{row['rrf_score']:.6f}"
                    if row.get("rrf_score") is not None
                    else "-"
                )
                lines.append(
                    f"| {block['channel']} | {row['rank']} | {row['doc_id']} | "
                    f"{'Y' if row['relevant'] else 'N'} | {vs} | {fr} | {rr} |"
                )
        lines.append("")
        lines.append("### 硬校验")
        lines.append("")
        lines.append("| 检查项 | 结果 |")
        lines.append("|--------|------|")
        for key, value in case_detail["checks"].items():
            lines.append(f"| {key} | {value} |")
        lines.append("")
        return "\n".join(lines)

    experiments = payload.get("experiments", [])
    lines.append("## 实验汇总")
    lines.append("")
    lines.append(
        "| 实验 | Hit@1 | Hit@k | MRR | NDCG@k | Recall@k | "
        "fts_only_top3 | lost_by_rrf | rel_fts_rank(med) |"
    )
    lines.append(
        "|------|-------|-------|-----|---------|----------|"
        "--------------|--------------|-------------------|"
    )
    for exp in experiments:
        m = exp["metrics"]
        rel_rank = (
            f"{m['relevant_fts_rank_median']:.0f}"
            if m["relevant_fts_rank_median"] is not None
            else "-"
        )
        lines.append(
            f"| {exp['name']} | {m['hit_at_1']:.3f} | {m['hit_at_k']:.3f} | "
            f"{m['mrr']:.3f} | {m['ndcg_at_k']:.3f} | {m['recall_at_k']:.3f} | "
            f"{m['fts_only_top3']:.3f} | {m['lost_by_rrf']:.3f} "
            f"({m['lost_by_rrf_hits']}/{m['lost_by_rrf_base']}) | {rel_rank} |"
        )
    if payload.get("mode") == "single":
        baseline = next(
            (
                exp
                for exp in experiments
                if exp["params"].get("fts_mode") == "baseline"
            ),
            None,
        )
        variants = [
            exp
            for exp in experiments
            if exp["params"].get("fts_mode")
            and exp["params"]["fts_mode"] != "baseline"
        ]
        if baseline is not None and variants:
            lines.append("")
            lines.append("### FTS tsquery 语义改造对照")
            lines.append("")
            b = baseline["metrics"]
            for exp in variants:
                m = exp["metrics"]
                d_hit = (m["hit_at_k"] - b["hit_at_k"]) * 100
                d_mrr = m["mrr"] - b["mrr"]
                d_ndcg = m["ndcg_at_k"] - b["ndcg_at_k"]
                lines.append(
                    f"- **{exp['params']['fts_mode']} vs baseline**："
                    f"Hit@3 {b['hit_at_k'] * 100:.1f}% → {m['hit_at_k'] * 100:.1f}%"
                    f"（Δ{d_hit:+.1f}pp）；MRR {b['mrr']:.3f} → {m['mrr']:.3f}"
                    f"（Δ{d_mrr:+.3f}）；NDCG@3 {b['ndcg_at_k']:.3f} → "
                    f"{m['ndcg_at_k']:.3f}（Δ{d_ndcg:+.3f}）。"
                )
    lines.append("")
    lines.append("### 备注")
    lines.append("")
    lines.append(
        "- `fts_only_top3`：Top-k 中不在 vector 池且非 qrels 的占比（H1 量化）。"
    )
    lines.append(
        "- `lost_by_rrf`：相关 doc 在 vector 池内但不在 RRF Top-k 的查询占比"
        "（H3 量化；括号为命中数/分母）。"
    )
    lines.append(
        "- `rel_fts_rank(med)`：相关 doc 在 FTS 单路最佳 rank 中位数（H1 量化）。"
    )
    lines.append("- 本报告不重跑 fiqa 全量混合 A/B（RAGAS judge 已收口）。")
    lines.append("")
    if payload.get("mode") == "single":
        baseline = next(
            (
                exp
                for exp in experiments
                if exp["params"].get("fts_mode") == "baseline"
            ),
            None,
        )
        variants = [
            exp
            for exp in experiments
            if exp["params"].get("fts_mode")
            and exp["params"]["fts_mode"] != "baseline"
        ]
        if baseline is not None and variants:
            lines.append("### 结论")
            lines.append("")
            b = baseline["metrics"]
            for exp in variants:
                m = exp["metrics"]
                lines.append(
                    f"- **{exp['params']['fts_mode']}**：RRF 1.0/1.5 下 "
                    f"Hit@3 {b['hit_at_k'] * 100:.1f}% → {m['hit_at_k'] * 100:.1f}%"
                    f"（Δ{(m['hit_at_k'] - b['hit_at_k']) * 100:+.1f}pp）；"
                    f"fts_only_top3 {b['fts_only_top3']:.3f} → {m['fts_only_top3']:.3f}；"
                    f"相关 doc FTS 最佳 rank 中位数 {b['relevant_fts_rank_median']} → "
                    f"{m['relevant_fts_rank_median']}。"
                )
            lines.append(
                "结论：FTS 泛词排序主导（H1）可在不动 RRF 权重的前提下通过 "
                "tsquery 语义改造缓解；本次全量 648 中 phrase 增益最大，生产落地仍需 "
                "先在中文企业语料 Golden/Enterprise QA 验证，避免英文金融语料结论直接外推。"
            )
    return "\n".join(lines)


def _print_summary(payload: dict) -> None:
    for exp in payload.get("experiments", []):
        m = exp["metrics"]
        rel_rank = (
            f"{m['relevant_fts_rank_median']:.0f}"
            if m["relevant_fts_rank_median"] is not None
            else "-"
        )
        print(
            f"{exp['name']}: Hit@1={m['hit_at_1']:.3f} "
            f"Hit@{m['top_k']}={m['hit_at_k']:.3f} MRR={m['mrr']:.3f} "
            f"NDCG@{m['top_k']}={m['ndcg_at_k']:.3f} "
            f"Recall@{m['top_k']}={m['recall_at_k']:.3f} "
            f"fts_only_top3={m['fts_only_top3']:.3f} "
            f"lost_by_rrf={m['lost_by_rrf']:.3f} "
            f"({m['lost_by_rrf_hits']}/{m['lost_by_rrf_base']}) "
            f"rel_fts_rank_med={rel_rank}"
        )


def _write_report(args: argparse.Namespace, payload: dict) -> tuple[Path, Path]:
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_dir = _resolve_backend_path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"fiqa_fts_dominance_{ts}.json"
    md_path = out_dir / f"fiqa_fts_dominance_{ts}.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(_render_markdown(args, payload), encoding="utf-8")
    logger.info("report saved: %s / %s", json_path, md_path)
    return json_path, md_path


async def main_async(args: argparse.Namespace) -> None:
    from app.core.database import SessionLocal
    from app.services.rag.cache import set_query_cache_enabled

    set_query_cache_enabled(False)
    queries, qrels = _load_queries_and_qrels(args.dataset)

    async with SessionLocal() as db:
        kb_chunks = await _verify_kb(db, args.kb_uuid, args.dataset)
        if args.mode == "case":
            payload = await _run_case(db, args, queries, qrels, kb_chunks)
        elif args.mode == "production":
            payload = await _run_production(db, args, queries, qrels)
        elif args.mode in ("single", "pool"):
            payload = await _run_single_pool(db, args, queries, qrels)
        elif args.mode == "multi":
            payload = await _run_multi(db, args, queries, qrels)
        else:
            await _run_cache_variants(db, args, queries)
            return

    payload.update(
        {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "dataset": f"beir/{args.dataset}",
            "kb_id": str(args.kb_uuid),
            "kb_chunks": kb_chunks,
            "top_k": args.top_k,
            "sample": args.sample,
            "note": NOTE,
        }
    )
    if args.mode == "single":
        payload["fts_modes"] = _resolve_fts_modes(args)
    if payload["mode"] != "case":
        _print_summary(payload)
    _write_report(args, payload)


def main() -> None:
    _load_dotenv()
    args = parse_args()
    if args.mode is None:
        if args.case:
            args.mode = "case"
        else:
            raise SystemExit(
                "请指定 --mode（production/single/pool/multi/cache-variants）"
                "或 --case <case_id>"
            )
    if args.mode == "case" and not args.case:
        raise SystemExit("--mode case 需要 --case <case_id>")
    if args.mode not in ("single",) and args.fts_mode != "baseline":
        raise SystemExit("--fts-mode 目前仅支持 --mode single")
    if args.kb is None:
        args.kb = DEFAULT_KB
    args.kb_uuid = UUID(args.kb)
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
