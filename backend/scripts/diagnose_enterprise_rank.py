"""Enterprise QA · RRF 名次小诊断（P0-A 决策用）

目标：区分
  - HIT@3：金标已在 Top-3（检索够用）
  - RANK_4_20：金标在 RRF 4～20（精排失败 → 倾向 A2 BGE reranker）
  - MISS_POOL：金标不在 Top-20（召回失败 → 倾向 A1 多 query）
  - NEEDLE_ABSENT：库内任何 chunk 都不含 content_contains（题标/切片问题，非 A1/A2）

用法（容器内）：
  python /tmp/diagnose_enterprise_rank.py
  python /tmp/diagnose_enterprise_rank.py --qa enterprise_qa/v1.0/cases.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"

POOL_K = 20
HIT_K = 3

_FIXTURES_CANDIDATES = [
    Path("/app/tests/fixtures"),
    Path(__file__).resolve().parent.parent / "tests" / "fixtures",
]
FIXTURES = next((p for p in _FIXTURES_CANDIDATES if p.exists()), _FIXTURES_CANDIDATES[0])


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Enterprise QA RRF rank diagnosis")
    p.add_argument(
        "--qa",
        default="enterprise_qa.json",
        help="相对 fixtures 的 QA 路径（默认 enterprise_qa.json）",
    )
    p.add_argument("--limit", type=int, default=0, help="只跑前 N 道可评分题（0=全量）")
    p.add_argument(
        "--out",
        default="",
        help="结果 JSON 路径（默认 /tmp 或 benchmark_results）",
    )
    p.add_argument(
        "--multi-query",
        action="store_true",
        help="用 A1 multi_query RRF（原问 vector+FTS，变体仅 vector）",
    )
    p.add_argument(
        "--mock-variants",
        action="store_true",
        help="与 --multi-query 联用：确定性 mock 变体（不调 DeepSeek，可复现）",
    )
    p.add_argument(
        "--clause-route",
        action="store_true",
        help="启用 A3 条款号/文档名路由（加法追加）",
    )
    p.add_argument(
        "--no-clause-route",
        action="store_true",
        help="强制关闭 A3 路由（对比基线）",
    )
    p.add_argument(
        "--rerank",
        action="store_true",
        help="对 RRF Top-N 再跑 BGE/配置的 rerank（A2 · 等价 always 且不走 skip）",
    )
    p.add_argument(
        "--no-rerank",
        action="store_true",
        help="强制关闭 rerank（对比基线）",
    )
    p.add_argument(
        "--rerank-policy",
        choices=("off", "always", "conditional"),
        default=None,
        help="走生产 _apply_rerank_policy（含 always 高置信 skip / conditional 门闩）",
    )
    p.add_argument(
        "--ab-rerank",
        action="store_true",
        help="U1-C/I-0：同池一次入库，对照 RRF vs always vs conditional（写 lift+触发率）",
    )
    p.add_argument(
        "--rrf-vector-weight",
        type=float,
        default=None,
        help="覆盖 settings.rrf_vector_weight（A4）",
    )
    p.add_argument(
        "--rrf-fts-weight",
        type=float,
        default=None,
        help="覆盖 settings.rrf_fts_weight（A4）",
    )
    p.add_argument(
        "--refuse-check",
        action="store_true",
        help="对 Top-3 跑 should_refuse_answer，输出拒答门控统计（A4）",
    )
    p.add_argument(
        "--refuse-fallback",
        type=float,
        default=None,
        help="覆盖 settings.relevance_similarity_fallback（需 --refuse-check）",
    )
    return p.parse_args()


def _find_rank(pool, needle: str) -> tuple[int | None, str | None]:
    for idx, ck in enumerate(pool, start=1):
        body = ck.parent_content or ck.content or ""
        if _needle_in_text(needle, body) or _needle_in_text(needle, ck.content or ""):
            return idx, ck.doc_name
    return None, None


def _needle_in_text(needle: str, text: str) -> bool:
    if not needle:
        return False
    return needle.lower() in (text or "").lower()


def _classify(rank: int | None, needle_in_corpus: bool, *, pool_k: int = POOL_K) -> str:
    if not needle_in_corpus:
        return "NEEDLE_ABSENT"
    if rank is None:
        return "MISS_POOL"
    if rank <= HIT_K:
        return "HIT_AT_3"
    if rank <= pool_k:
        return "RANK_4_20"
    return "MISS_POOL"


async def _ingest_acme(kb_id: uuid.UUID, user_id: uuid.UUID, upload_dir: Path) -> list[str]:
    """入库 acme 文档；诊断场景跳过英文双嵌，省内存（中文 Enterprise 问法为主）。"""
    from app.core.database import SessionLocal
    from app.models.document import Document
    from app.models.enums import DocumentStatus
    from app.services.ingestion import pipeline as ingestion_pipeline

    # monkeypatch：跳过 bge_en，避免 2GB 容器 OOM
    async def _embed_only_zh(embed_inputs):
        return await ingestion_pipeline.try_embed_texts(embed_inputs), None

    orig = getattr(ingestion_pipeline, "_embed_zh_and_en", None)
    # pipeline 内联双嵌；改 patch embed_texts(provider=bge_en) 路径
    from app.services.ingestion import embedder as embedder_mod

    async def _no_en(texts, provider=None):
        if (provider or "").lower() == "bge_en":
            return [[0.0] * 384 for _ in texts]  # 占位，诊断不测英文路
        return await embedder_mod.embed_texts.__wrapped__(texts, provider=provider)  # type: ignore[attr-defined]

    # 更稳：直接让 pipeline 里的 embed_texts(..., provider="bge_en") 返回 None 失败并被吞
    _real_embed = embedder_mod.embed_texts

    async def _embed_skip_en(texts, provider=None):
        if (provider or "").lower() == "bge_en":
            raise RuntimeError("diag: skip bge_en")
        return await _real_embed(texts, provider=provider)

    embedder_mod.embed_texts = _embed_skip_en  # type: ignore[assignment]
    ingestion_pipeline.embed_texts = _embed_skip_en  # type: ignore[assignment]

    doc_files = sorted(FIXTURES.glob("acme_*.md"))
    if not doc_files:
        raise SystemExit(f"未找到 acme_*.md：{FIXTURES}")

    names: list[str] = []
    try:
        for f in doc_files:
            doc_id = uuid.uuid4()
            storage_dir = upload_dir / str(kb_id) / str(doc_id)
            storage_dir.mkdir(parents=True, exist_ok=True)
            storage_path = storage_dir / f.name
            storage_path.write_bytes(f.read_bytes())

            async with SessionLocal() as db:
                doc = Document(
                    id=doc_id,
                    kb_id=kb_id,
                    filename=f.name,
                    file_type="md",
                    file_size=storage_path.stat().st_size,
                    storage_path=str(storage_path),
                    status=DocumentStatus.queued,
                    uploaded_by=user_id,
                )
                db.add(doc)
                await db.commit()

            await ingestion_pipeline.process_document_ingestion(doc_id)
            names.append(f.name)
            print(f"  ingested: {f.name}", flush=True)
    finally:
        embedder_mod.embed_texts = _real_embed  # type: ignore[assignment]
        ingestion_pipeline.embed_texts = _real_embed  # type: ignore[assignment]
        _ = orig
        _ = _embed_only_zh
        _ = _no_en
    return names


async def _load_corpus_texts(db, kb_id: uuid.UUID) -> list[str]:
    from sqlalchemy import select
    from app.models.document_chunk import DocumentChunk

    rows = (
        await db.execute(
            select(DocumentChunk.content).where(DocumentChunk.kb_id == kb_id)
        )
    ).scalars().all()
    return [c or "" for c in rows]


def _corpus_has_needle(corpus: list[str], needle: str) -> bool:
    if not needle:
        return False
    needle_l = needle.lower()
    return any(needle_l in c.lower() for c in corpus)


def _is_route_subset(case: dict, query: str) -> bool:
    """Route 子集：条款号，或 cue/文件名与 source_doc 可对齐，或问法可触发路由。"""
    from pathlib import Path
    from app.services.rag.route_extract import (
        extract_clause_tokens,
        extract_filename_cues,
        should_attempt_route,
    )

    if extract_clause_tokens(query):
        return True
    if not should_attempt_route(query):
        return False
    source = (case.get("source_doc") or "").lower()
    stem = Path(case.get("source_doc") or "").stem
    cues = extract_filename_cues(query)
    for c in cues:
        if len(c) >= 2 and c.lower() in source:
            return True
    for part in re.split(r"[_\-\s]+", stem):
        if len(part) >= 2 and part in query:
            return True
    # 专名 cue（ASCII≥2）视为可路由子集——与标题命中路径一致
    if any(re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{1,31}", c) for c in cues):
        return True
    return False


async def _rrf_pool(
    db,
    kb_id: uuid.UUID,
    query: str,
    top_n: int = POOL_K,
    *,
    multi_query: bool = False,
    mock_variants: bool = False,
    clause_route: bool = False,
):
    """纯 RRF Top-N（关 rerank）。multi_query / clause_route 可叠加。

    返回: pool, n_vec, n_fts, variants, vector_top_ids, fts_top_ids, fts_rows
    """
    from app.core.config import settings
    from app.services.ingestion.embedder import try_embed_texts
    from app.services.rag.vector_recall import vector_recall
    from app.services.rag.fts_recall import fts_recall
    from app.services.rag.rrf import reciprocal_rank_fusion
    from app.services.rag.executor import merge_recall_rows, load_parent_contents
    from app.services.rag.types import RetrievedChunk
    from app.services.rag.retrieval import VECTOR_RECALL, FTS_RECALL

    variants = [query]
    vector_rows: list = []
    fts_rows: list = []
    if multi_query:
        from app.services.rag.multi_query import multi_query_kb_recall

        fused, merged, variants = await multi_query_kb_recall(
            db,
            kb_id=kb_id,
            query=query,
            vector_limit=VECTOR_RECALL,
            fts_limit=FTS_RECALL,
            top_n=top_n,
            use_mock=mock_variants,
        )
        n_vec = sum(1 for r in merged.values() if r.vector_similarity is not None)
        n_fts = sum(1 for r in merged.values() if r.fts_rank is not None)
        # multi_query 合并后无单路原始序；条件精排 B 信号置空
        vector_top_ids = None
        fts_top_ids = None
        fts_rows = [r for r in merged.values() if r.fts_rank is not None]
    else:
        ascii_chars = sum(1 for c in query if c.isascii() and c.isalpha())
        total_chars = sum(1 for c in query if c.isalpha())
        is_english = total_chars > 0 and (ascii_chars / total_chars) > 0.5
        embed_provider = "bge_en" if is_english else None
        embed_col = "embedding_en" if is_english else None

        query_vec = None
        vec = await try_embed_texts([query], provider=embed_provider)
        if vec is not None:
            query_vec = vec[0]
        elif embed_provider == "bge_en":
            vec = await try_embed_texts([query])
            if vec is not None:
                query_vec = vec[0]
                embed_col = None

        if query_vec is not None:
            vector_rows = await vector_recall(
                db,
                kb_id=kb_id,
                query_vec=query_vec,
                limit=VECTOR_RECALL,
                embedding_col=embed_col,
            )
        fts_rows = await fts_recall(db, kb_id=kb_id, query=query, limit=FTS_RECALL)

        fused = reciprocal_rank_fusion(
            [[row.chunk.id for row in vector_rows], [row.chunk.id for row in fts_rows]],
            k=settings.rrf_k,
            weights=[settings.rrf_vector_weight, settings.rrf_fts_weight],
            top_n=top_n,
        )
        merged = merge_recall_rows(vector_rows, fts_rows)
        n_vec = len(vector_rows)
        n_fts = len(fts_rows)
        vector_top_ids = [row.chunk.id for row in vector_rows[:3]]
        fts_top_ids = [row.chunk.id for row in fts_rows[:3]]

    if clause_route:
        from app.services.rag.route_recall import apply_clause_route_kb

        # 诊断临时开开关（apply 内也会检查 settings）
        prev = settings.clause_route_enabled
        settings.clause_route_enabled = True
        try:
            fused, merged = await apply_clause_route_kb(
                db, kb_id=kb_id, query=query, fused=fused, merged=merged
            )
        finally:
            settings.clause_route_enabled = prev

    parent_contents = await load_parent_contents(
        db, [row.chunk for row in merged.values()]
    )
    out: list[RetrievedChunk] = []
    for chunk_id, rrf_score in fused:
        row = merged.get(chunk_id)
        if row is None:
            continue
        chunk = row.chunk
        out.append(
            RetrievedChunk(
                kb_id=kb_id,
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                doc_name=row.filename,
                content=chunk.content,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                heading_path=chunk.heading_path,
                similarity=float(row.vector_similarity or 0.0),
                parent_content=parent_contents.get(chunk.parent_chunk_id)
                if chunk.parent_chunk_id
                else None,
                rrf_score=float(rrf_score),
            )
        )
    return out, n_vec, n_fts, variants, vector_top_ids, fts_top_ids, fts_rows


async def _policy_rerank(
    query: str,
    pool,
    *,
    policy: str,
    vector_top_ids,
    fts_top_ids,
    fts_rows,
):
    """临时切 settings.rerank_policy，走生产 _apply_rerank_policy。"""
    from app.core.config import settings
    from app.services.rag.retrieval import _apply_rerank_policy

    prev_policy = settings.rerank_policy
    prev_enabled = settings.rerank_enabled
    settings.rerank_policy = policy
    settings.rerank_enabled = policy != "off"
    if settings.rerank_provider.lower() in ("", "mock") and policy != "off":
        settings.rerank_provider = "bge"
    try:
        return await _apply_rerank_policy(
            query,
            pool,
            top_k=len(pool),
            fts_rows_for_skip=fts_rows or [],
            vector_top_ids=vector_top_ids,
            fts_top_ids=fts_top_ids,
        )
    finally:
        settings.rerank_policy = prev_policy
        settings.rerank_enabled = prev_enabled


def _lift_stats(rows: list[dict], *, post_key: str, rrf_key: str = "bucket_rrf") -> dict:
    lifted = [
        r
        for r in rows
        if r.get(rrf_key) == "RANK_4_20" and r.get(post_key) == "HIT_AT_3"
    ]
    hurt = [
        r
        for r in rows
        if r.get(rrf_key) == "HIT_AT_3" and r.get(post_key) != "HIT_AT_3"
    ]
    rrf_rank420 = sum(1 for r in rows if r.get(rrf_key) == "RANK_4_20")
    rrf_hit3 = sum(1 for r in rows if r.get(rrf_key) == "HIT_AT_3")
    post_hit3 = sum(1 for r in rows if r.get(post_key) == "HIT_AT_3")
    post_rank420 = sum(1 for r in rows if r.get(post_key) == "RANK_4_20")
    return {
        "rrf_hit_at_3": rrf_hit3,
        "rrf_rank_4_20": rrf_rank420,
        "post_hit_at_3": post_hit3,
        "post_rank_4_20": post_rank420,
        "rank_4_20_lifted_to_hit3": len(lifted),
        "rank_4_20_lifted_rate": round(len(lifted) / rrf_rank420, 4) if rrf_rank420 else 0.0,
        "hit_at_3_hurt": len(hurt),
        "net_hit_at_3_delta": post_hit3 - rrf_hit3,
        "net_rank_4_20_delta": post_rank420 - rrf_rank420,
        "lifted_case_ids": [r.get("case_id") for r in lifted],
        "hurt_case_ids": [r.get("case_id") for r in hurt],
    }


async def main() -> None:
    args = parse_args()
    qa_path = FIXTURES / args.qa
    if not qa_path.exists():
        raise SystemExit(f"QA 文件不存在: {qa_path}")

    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.core.config import settings
    from app.core.database import SessionLocal

    use_clause_route = bool(args.clause_route)
    if args.no_clause_route:
        use_clause_route = False
        settings.clause_route_enabled = False
    elif args.clause_route:
        settings.clause_route_enabled = True

    use_ab = bool(args.ab_rerank)
    policy = args.rerank_policy
    use_rerank = bool(args.rerank) or (policy in ("always", "conditional"))
    if args.no_rerank and not use_ab:
        use_rerank = False
        policy = "off"
        settings.rerank_enabled = False
        settings.rerank_policy = "off"
    elif use_ab:
        use_rerank = True
        if settings.rerank_provider.lower() in ("", "mock"):
            settings.rerank_provider = "bge"
    elif policy is not None:
        settings.rerank_policy = policy
        settings.rerank_enabled = policy != "off"
        if policy != "off" and settings.rerank_provider.lower() in ("", "mock"):
            settings.rerank_provider = "bge"
    elif args.rerank:
        settings.rerank_enabled = True
        # 诊断默认走 BGE 真路径（除非已显式配置其他 provider）
        if settings.rerank_provider.lower() in ("", "mock"):
            settings.rerank_provider = "bge"

    if args.rrf_vector_weight is not None:
        settings.rrf_vector_weight = float(args.rrf_vector_weight)
    if args.rrf_fts_weight is not None:
        settings.rrf_fts_weight = float(args.rrf_fts_weight)
    if args.refuse_fallback is not None:
        settings.relevance_similarity_fallback = float(args.refuse_fallback)

    use_refuse_check = bool(args.refuse_check)

    print(f"fixtures={FIXTURES}", flush=True)
    print(f"qa={qa_path}", flush=True)
    print(
        f"embedding_provider={settings.embedding_provider} "
        f"model={settings.embedding_model} dim={settings.embedding_dim} "
        f"rerank_enabled={settings.rerank_enabled} "
        f"rerank_provider={settings.rerank_provider} "
        f"rerank_policy={settings.rerank_policy} "
        f"diag_rerank={use_rerank} ab_rerank={use_ab} "
        f"cli_policy={policy} "
        f"multi_query={args.multi_query} mock_variants={args.mock_variants} "
        f"clause_route={use_clause_route} "
        f"rrf_v={settings.rrf_vector_weight} rrf_fts={settings.rrf_fts_weight} "
        f"refuse_check={use_refuse_check} "
        f"refuse_fallback={settings.relevance_similarity_fallback}",
        flush=True,
    )

    data = json.loads(qa_path.read_text(encoding="utf-8"))
    all_cases = data["cases"]
    scored_cases = [
        c
        for c in all_cases
        if not c.get("expect_rejection")
        and (c.get("expect") or {}).get("content_contains")
    ]
    if args.limit > 0:
        scored_cases = scored_cases[: args.limit]

    rejection_cases = [c for c in all_cases if c.get("expect_rejection")]
    rejection_n = len(rejection_cases)
    print(
        f"cases total={len(all_cases)} rejection={rejection_n} "
        f"scored_with_needle={len(scored_cases)}",
        flush=True,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"diag-{uuid.uuid4().hex[:8]}@e.com"
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "username": f"diag{uuid.uuid4().hex[:8]}",
                "password": "DiagPass123!",
                "account_type": "personal",
            },
        )
        r = await client.post(
            "/api/v1/auth/login",
            json={"identifier": email, "password": "DiagPass123!"},
        )
        token_data = r.json()
        headers = {"Authorization": f"Bearer {token_data['access_token']}"}
        user_id = uuid.UUID(token_data["user"]["id"])
        r = await client.post(
            "/api/v1/knowledge-bases?workspace=personal",
            headers=headers,
            json={"name": "Enterprise-Rank-Diag"},
        )
        kb_id = uuid.UUID(r.json()["id"])

    upload_dir = Path(settings.upload_dir)
    print("入库 acme_*.md …", flush=True)
    docs = await _ingest_acme(kb_id, user_id, upload_dir)
    print(f"入库完成: {docs}", flush=True)

    rows: list[dict] = []
    counts: Counter[str] = Counter()
    trigger_always = 0
    trigger_conditional = 0

    async with SessionLocal() as db:
        corpus = await _load_corpus_texts(db, kb_id)
        print(f"corpus chunks={len(corpus)}", flush=True)
        for i, case in enumerate(scored_cases, start=1):
            needle = (case.get("expect") or {}).get("content_contains") or ""
            query = case["query"]
            in_corpus = _corpus_has_needle(corpus, needle)
            (
                pool,
                n_vec,
                n_fts,
                variants,
                vector_top_ids,
                fts_top_ids,
                fts_rows,
            ) = await _rrf_pool(
                db,
                kb_id,
                query,
                top_n=POOL_K,
                multi_query=args.multi_query,
                mock_variants=args.mock_variants,
                clause_route=use_clause_route,
            )

            rank_rrf, matched_doc = _find_rank(pool, needle)
            rank = rank_rrf
            pool_final = pool
            did_rerank = False
            bucket_always = None
            bucket_conditional = None
            rank_always = None
            rank_conditional = None
            did_always = False
            did_conditional = False

            if use_ab and pool:
                pool_always, did_always = await _policy_rerank(
                    query,
                    pool,
                    policy="always",
                    vector_top_ids=vector_top_ids,
                    fts_top_ids=fts_top_ids,
                    fts_rows=fts_rows,
                )
                pool_cond, did_conditional = await _policy_rerank(
                    query,
                    pool,
                    policy="conditional",
                    vector_top_ids=vector_top_ids,
                    fts_top_ids=fts_top_ids,
                    fts_rows=fts_rows,
                )
                if did_always:
                    trigger_always += 1
                if did_conditional:
                    trigger_conditional += 1
                rank_always, _ = _find_rank(pool_always, needle)
                rank_conditional, matched_doc2 = _find_rank(pool_cond, needle)
                if matched_doc2:
                    matched_doc = matched_doc2
                pool_final = pool_cond
                rank = rank_conditional
                did_rerank = did_conditional
            elif use_rerank and pool:
                if policy in ("always", "conditional"):
                    pool_final, did_rerank = await _policy_rerank(
                        query,
                        pool,
                        policy=policy,
                        vector_top_ids=vector_top_ids,
                        fts_top_ids=fts_top_ids,
                        fts_rows=fts_rows,
                    )
                    if did_rerank and policy == "conditional":
                        trigger_conditional += 1
                    if did_rerank and policy == "always":
                        trigger_always += 1
                else:
                    from app.services.rag.rerank import rerank_chunks

                    prev_enabled = settings.rerank_enabled
                    settings.rerank_enabled = True
                    try:
                        pool_final = await rerank_chunks(query, pool, top_k=len(pool))
                        did_rerank = True
                    finally:
                        settings.rerank_enabled = prev_enabled
                rank, matched_doc2 = _find_rank(pool_final, needle)
                if matched_doc2:
                    matched_doc = matched_doc2

            pool_k = POOL_K
            bucket_rrf = _classify(rank_rrf, in_corpus, pool_k=pool_k)
            bucket = _classify(rank, in_corpus, pool_k=pool_k)
            if use_ab:
                bucket_always = _classify(rank_always, in_corpus, pool_k=pool_k)
                bucket_conditional = bucket
            counts[bucket] += 1
            if use_rerank or use_ab:
                counts[f"RRF_{bucket_rrf}"] += 1
            if use_ab:
                counts[f"ALWAYS_{bucket_always}"] += 1
                counts[f"COND_{bucket_conditional}"] += 1
            route_sub = _is_route_subset(case, query)

            refused = None
            if use_refuse_check:
                from app.services.rag.relevance import should_refuse_answer

                refused = should_refuse_answer(pool_final[:HIT_K], query)

            rows.append(
                {
                    "case_id": case.get("case_id"),
                    "difficulty": case.get("difficulty"),
                    "query": query,
                    "rank": rank,
                    "rank_rrf": rank_rrf if (use_rerank or use_ab) else None,
                    "rank_always": rank_always if use_ab else None,
                    "rank_conditional": rank_conditional if use_ab else None,
                    "bucket": bucket,
                    "bucket_rrf": bucket_rrf if (use_rerank or use_ab) else None,
                    "bucket_always": bucket_always if use_ab else None,
                    "bucket_conditional": bucket_conditional if use_ab else None,
                    "rerank_triggered": did_rerank if (use_rerank or use_ab) else None,
                    "rerank_triggered_always": did_always if use_ab else None,
                    "rerank_triggered_conditional": did_conditional if use_ab else None,
                    "route_subset": route_sub,
                    "needle_in_corpus": in_corpus,
                    "matched_doc": matched_doc,
                    "needle_preview": needle[:80].replace("\n", " "),
                    "vector_hits": n_vec,
                    "fts_hits": n_fts,
                    "variants": variants if args.multi_query else None,
                    "refused": refused,
                    "expect_rejection": False,
                }
            )
            if i % 10 == 0 or i == len(scored_cases):
                extra = ""
                if use_ab:
                    extra = f" always={bucket_always} cond={bucket_conditional}"
                print(
                    f"  [{i}/{len(scored_cases)}] last={case.get('case_id')} "
                    f"→ rrf={bucket_rrf}{extra} rank={rank}",
                    flush=True,
                )

        # A4：拒答题也跑同一检索池 + 拒答门控
        if use_refuse_check and rejection_cases:
            from app.services.rag.relevance import should_refuse_answer

            print(f"refuse-check rejection cases={len(rejection_cases)} …", flush=True)
            for j, case in enumerate(rejection_cases, start=1):
                query = case["query"]
                (
                    pool,
                    n_vec,
                    n_fts,
                    variants,
                    vector_top_ids,
                    fts_top_ids,
                    fts_rows,
                ) = await _rrf_pool(
                    db,
                    kb_id,
                    query,
                    top_n=POOL_K,
                    multi_query=args.multi_query,
                    mock_variants=args.mock_variants,
                    clause_route=use_clause_route,
                )
                pool_final = pool
                if use_ab and pool:
                    pool_final, _ = await _policy_rerank(
                        query,
                        pool,
                        policy="conditional",
                        vector_top_ids=vector_top_ids,
                        fts_top_ids=fts_top_ids,
                        fts_rows=fts_rows,
                    )
                elif use_rerank and pool:
                    if policy in ("always", "conditional"):
                        pool_final, _ = await _policy_rerank(
                            query,
                            pool,
                            policy=policy,
                            vector_top_ids=vector_top_ids,
                            fts_top_ids=fts_top_ids,
                            fts_rows=fts_rows,
                        )
                    else:
                        from app.services.rag.rerank import rerank_chunks

                        prev_enabled = settings.rerank_enabled
                        settings.rerank_enabled = True
                        try:
                            pool_final = await rerank_chunks(query, pool, top_k=len(pool))
                        finally:
                            settings.rerank_enabled = prev_enabled
                refused = should_refuse_answer(pool_final[:HIT_K], query)
                rows.append(
                    {
                        "case_id": case.get("case_id"),
                        "difficulty": case.get("difficulty"),
                        "query": query,
                        "rank": None,
                        "rank_rrf": None,
                        "bucket": "EXPECT_REJECTION",
                        "bucket_rrf": None,
                        "route_subset": False,
                        "needle_in_corpus": False,
                        "matched_doc": None,
                        "needle_preview": "",
                        "vector_hits": n_vec,
                        "fts_hits": n_fts,
                        "variants": variants if args.multi_query else None,
                        "refused": refused,
                        "expect_rejection": True,
                    }
                )
                if j % 5 == 0 or j == len(rejection_cases):
                    print(
                        f"  [rej {j}/{len(rejection_cases)}] "
                        f"last={case.get('case_id')} refused={refused}",
                        flush=True,
                    )

    n = max(1, sum(1 for r in rows if not r.get("expect_rejection")))
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "qa_file": str(qa_path),
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "pool_k": POOL_K,
        "hit_k": HIT_K,
        "multi_query": args.multi_query,
        "mock_variants": args.mock_variants,
        "clause_route": use_clause_route,
        "rerank": use_rerank or use_ab,
        "ab_rerank": use_ab,
        "rerank_policy": "ab" if use_ab else (policy or ("legacy_always" if use_rerank else "off")),
        "rerank_provider": settings.rerank_provider if (use_rerank or use_ab) else None,
        "rrf_vector_weight": settings.rrf_vector_weight,
        "rrf_fts_weight": settings.rrf_fts_weight,
        "refuse_check": use_refuse_check,
        "relevance_similarity_fallback": settings.relevance_similarity_fallback,
        "scored_n": n,
        "counts": {
            k: v
            for k, v in counts.items()
            if not str(k).startswith(("RRF_", "ALWAYS_", "COND_"))
        },
        "rates": {
            k: round(v / n, 4)
            for k, v in counts.items()
            if not str(k).startswith(("RRF_", "ALWAYS_", "COND_"))
        },
        # 决策用：排除 NEEDLE_ABSENT 后的召回/精排占比
        "actionable": {},
        "route_subset": {},
        "rerank_lift": {},
        "ab": {},
        "refuse": {},
    }
    actionable_n = sum(counts[k] for k in ("HIT_AT_3", "RANK_4_20", "MISS_POOL"))
    if actionable_n:
        summary["actionable"] = {
            "n": actionable_n,
            "hit_at_3": round(counts["HIT_AT_3"] / actionable_n, 4),
            "rank_4_20_rerank_gap": round(counts["RANK_4_20"] / actionable_n, 4),
            "miss_pool_recall_gap": round(counts["MISS_POOL"] / actionable_n, 4),
        }

    if use_ab:
        always_counts = {
            k: counts.get(f"ALWAYS_{k}", 0)
            for k in ("HIT_AT_3", "RANK_4_20", "MISS_POOL", "NEEDLE_ABSENT")
        }
        cond_counts = {
            k: counts.get(f"COND_{k}", 0)
            for k in ("HIT_AT_3", "RANK_4_20", "MISS_POOL", "NEEDLE_ABSENT")
        }
        rrf_counts = {
            k: counts.get(f"RRF_{k}", 0)
            for k in ("HIT_AT_3", "RANK_4_20", "MISS_POOL", "NEEDLE_ABSENT")
        }
        summary["ab"] = {
            "rrf": rrf_counts,
            "always": always_counts,
            "conditional": cond_counts,
            "trigger_always": trigger_always,
            "trigger_conditional": trigger_conditional,
            "trigger_rate_always": round(trigger_always / n, 4) if n else 0.0,
            "trigger_rate_conditional": round(trigger_conditional / n, 4) if n else 0.0,
            "lift_always": _lift_stats(rows, post_key="bucket_always"),
            "lift_conditional": _lift_stats(rows, post_key="bucket_conditional"),
        }
        summary["rerank_lift"] = summary["ab"]["lift_conditional"]
        summary["counts"] = rrf_counts
        summary["rates"] = {k: round(v / n, 4) for k, v in rrf_counts.items()}
        actionable_n = sum(rrf_counts[k] for k in ("HIT_AT_3", "RANK_4_20", "MISS_POOL"))
        if actionable_n:
            summary["actionable"] = {
                "n": actionable_n,
                "hit_at_3": round(rrf_counts["HIT_AT_3"] / actionable_n, 4),
                "rank_4_20_rerank_gap": round(rrf_counts["RANK_4_20"] / actionable_n, 4),
                "miss_pool_recall_gap": round(rrf_counts["MISS_POOL"] / actionable_n, 4),
            }
    elif use_rerank:
        summary["rerank_lift"] = _lift_stats(rows, post_key="bucket")
        if policy == "conditional":
            summary["ab"] = {
                "trigger_conditional": trigger_conditional,
                "trigger_rate_conditional": round(trigger_conditional / n, 4) if n else 0.0,
            }

    route_rows = [r for r in rows if r.get("route_subset")]
    if route_rows:
        hit20 = sum(
            1
            for r in route_rows
            if r.get("needle_in_corpus")
            and r.get("rank") is not None
            and r["rank"] <= POOL_K
        )
        summary["route_subset"] = {
            "n": len(route_rows),
            "hit_at_20": hit20,
            "hit_at_20_rate": round(hit20 / len(route_rows), 4),
        }

    if use_refuse_check:
        rej_rows = [r for r in rows if r.get("expect_rejection")]
        hit3_rows = [r for r in rows if r.get("bucket") == "HIT_AT_3"]
        rej_correct = sum(1 for r in rej_rows if r.get("refused") is True)
        false_refuse = sum(1 for r in hit3_rows if r.get("refused") is True)
        summary["refuse"] = {
            "fallback": settings.relevance_similarity_fallback,
            "expect_rejection_n": len(rej_rows),
            "rejection_correct": rej_correct,
            "rejection_accuracy": round(rej_correct / len(rej_rows), 4)
            if rej_rows
            else 0.0,
            "hit_at_3_n": len(hit3_rows),
            "false_refuse": false_refuse,
            "false_refuse_rate": round(false_refuse / len(hit3_rows), 4)
            if hit3_rows
            else 0.0,
        }

    # 建议
    ag = summary["actionable"]
    if use_ab and summary.get("ab"):
        la = summary["ab"]["lift_always"]
        lc = summary["ab"]["lift_conditional"]
        advice = (
            f"I-0 AB：RRF Hit@3={la['rrf_hit_at_3']}；"
            f"always→{la['post_hit_at_3']} (hurt={la['hit_at_3_hurt']}, "
            f"lift={la['rank_4_20_lifted_to_hit3']}/{la['rrf_rank_4_20']}, "
            f"trig={summary['ab']['trigger_rate_always']:.0%})；"
            f"conditional→{lc['post_hit_at_3']} (hurt={lc['hit_at_3_hurt']}, "
            f"lift={lc['rank_4_20_lifted_to_hit3']}/{lc['rrf_rank_4_20']}, "
            f"trig={summary['ab']['trigger_rate_conditional']:.0%})。"
        )
    elif not ag:
        advice = "几乎全是 NEEDLE_ABSENT：先修评测题标/切片，再谈 A1/A2。"
    elif use_rerank and summary.get("rerank_lift"):
        lift = summary["rerank_lift"]
        advice = (
            f"A2 rerank：RRF Hit@3={lift['rrf_hit_at_3']} → post={lift['post_hit_at_3']}；"
            f"RANK_4_20 升入 Hit@3={lift['rank_4_20_lifted_to_hit3']}/{lift['rrf_rank_4_20']}；"
            f"hurt Top-3={lift.get('hit_at_3_hurt', '?')}。"
        )
    elif ag["miss_pool_recall_gap"] >= ag["rank_4_20_rerank_gap"]:
        advice = (
            f"召回失败({ag['miss_pool_recall_gap']:.0%}) ≥ 精排失败({ag['rank_4_20_rerank_gap']:.0%}) "
            "→ 优先 A1 多 query；A2 次之。"
        )
    else:
        advice = (
            f"精排失败({ag['rank_4_20_rerank_gap']:.0%}) > 召回失败({ag['miss_pool_recall_gap']:.0%}) "
            "→ 优先 A2（BGE reranker）；A1 次之。"
        )
    summary["advice"] = advice

    out_path = Path(args.out) if args.out else Path("/tmp/enterprise_rrf_rank_diag.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"summary": summary, "rows": rows}
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 60, flush=True)
    print("Enterprise QA · RRF 名次诊断", flush=True)
    print("=" * 60, flush=True)
    print(f"scored_n={summary['scored_n']} rerank={use_rerank or use_ab} ab={use_ab}", flush=True)
    for k in ("HIT_AT_3", "RANK_4_20", "MISS_POOL", "NEEDLE_ABSENT"):
        v = summary["counts"].get(k, 0)
        print(f"  {k:16s} {v:4d}  ({v / n:.1%})", flush=True)
    print(f"\nactionable: {json.dumps(summary['actionable'], ensure_ascii=False)}", flush=True)
    if summary.get("ab"):
        print(f"ab: {json.dumps(summary['ab'], ensure_ascii=False)}", flush=True)
    elif summary.get("rerank_lift"):
        print(
            f"rerank_lift: {json.dumps(summary['rerank_lift'], ensure_ascii=False)}",
            flush=True,
        )
    if summary.get("route_subset"):
        print(
            f"route_subset: {json.dumps(summary['route_subset'], ensure_ascii=False)}",
            flush=True,
        )
    if summary.get("refuse"):
        print(
            f"refuse: {json.dumps(summary['refuse'], ensure_ascii=False)}",
            flush=True,
        )
    print(f"advice: {advice}", flush=True)
    print(f"wrote: {out_path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
