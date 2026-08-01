"""A4：一次入库，扫 RRF 权重 + 拒答语义兜底阈值，输出掉分题前后对比。

用法（容器内）：
  PYTHONPATH=/app python scripts/sweep_a4_rrf_refuse.py \\
    --out /tmp/enterprise_a4_sweep.json --clause-route
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"

# 允许从 /tmp 或 scripts/ 运行
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from diagnose_enterprise_rank import (  # noqa: E402
    FIXTURES,
    HIT_K,
    POOL_K,
    _classify,
    _corpus_has_needle,
    _find_rank,
    _ingest_acme,
    _load_corpus_texts,
    _rrf_pool,
)

FTS_GRID = (0.8, 1.0, 1.2, 1.5, 2.0)
VECTOR_GRID = (0.8, 1.0, 1.2)
FALLBACK_GRID = (0.35, 0.40, 0.45, 0.50, 0.55)
BASE_VECTOR = 1.0
BASE_FTS = 1.2
BASE_FALLBACK = 0.45


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A4 RRF weight + refuse fallback sweep")
    p.add_argument("--qa", default="enterprise_qa.json")
    p.add_argument("--out", default="/tmp/enterprise_a4_sweep.json")
    p.add_argument("--clause-route", action="store_true", default=True)
    p.add_argument("--no-clause-route", action="store_true")
    p.add_argument("--limit", type=int, default=0)
    return p.parse_args()


def _pick_best_weight(grid: list[dict]) -> dict:
    """Hit@3 最大；并列 miss_pool 更低；再 rank_4_20 更低。"""

    def key(g: dict) -> tuple:
        a = g["actionable"]
        return (
            a["hit_at_3"],
            -a["miss_pool_recall_gap"],
            -a["rank_4_20_rerank_gap"],
        )

    return max(grid, key=key)


def _pick_best_refuse(grid: list[dict], baseline_false_refuse: int) -> dict:
    """拒答正确率↑且假拒答不高于基线；否则保持 baseline fallback。"""
    eligible = [
        g
        for g in grid
        if g["false_refuse"] <= baseline_false_refuse
    ]
    if not eligible:
        return next(g for g in grid if g["fallback"] == BASE_FALLBACK)
    best = max(
        eligible,
        key=lambda g: (g["rejection_accuracy"], -g["false_refuse"], -abs(g["fallback"] - BASE_FALLBACK)),
    )
    return best


def _bucket_compare(base_rows: list[dict], new_rows: list[dict]) -> list[dict]:
    by_new = {r["case_id"]: r for r in new_rows}
    out: list[dict] = []
    for br in base_rows:
        nr = by_new.get(br["case_id"])
        if nr is None:
            continue
        if br.get("bucket") == nr.get("bucket") and br.get("rank") == nr.get("rank"):
            continue
        out.append(
            {
                "case_id": br["case_id"],
                "query": br.get("query", "")[:60],
                "old_bucket": br.get("bucket"),
                "old_rank": br.get("rank"),
                "new_bucket": nr.get("bucket"),
                "new_rank": nr.get("rank"),
            }
        )
    return out


async def _eval_weights(
    db,
    kb_id: uuid.UUID,
    scored_cases: list[dict],
    corpus: list[str],
    *,
    vector_w: float,
    fts_w: float,
    clause_route: bool,
) -> tuple[dict, list[dict]]:
    from app.core.config import settings

    prev_v, prev_f = settings.rrf_vector_weight, settings.rrf_fts_weight
    settings.rrf_vector_weight = vector_w
    settings.rrf_fts_weight = fts_w
    try:
        rows: list[dict] = []
        counts: Counter[str] = Counter()
        for case in scored_cases:
            needle = (case.get("expect") or {}).get("content_contains") or ""
            query = case["query"]
            in_corpus = _corpus_has_needle(corpus, needle)
            pool, n_vec, n_fts, _variants = await _rrf_pool(
                db,
                kb_id,
                query,
                top_n=POOL_K,
                multi_query=False,
                mock_variants=False,
                clause_route=clause_route,
            )
            rank, matched_doc = _find_rank(pool, needle)
            bucket = _classify(rank, in_corpus, pool_k=POOL_K)
            counts[bucket] += 1
            rows.append(
                {
                    "case_id": case.get("case_id"),
                    "query": query,
                    "rank": rank,
                    "bucket": bucket,
                    "matched_doc": matched_doc,
                    "vector_hits": n_vec,
                    "fts_hits": n_fts,
                    "top3_sims": [float(c.similarity or 0.0) for c in pool[:HIT_K]],
                    "pool_top3": pool[:HIT_K],
                }
            )
        n = max(1, len(rows))
        actionable_n = sum(counts[k] for k in ("HIT_AT_3", "RANK_4_20", "MISS_POOL"))
        summary = {
            "rrf_vector_weight": vector_w,
            "rrf_fts_weight": fts_w,
            "counts": dict(counts),
            "actionable": {
                "n": actionable_n,
                "hit_at_3": round(counts["HIT_AT_3"] / actionable_n, 4)
                if actionable_n
                else 0.0,
                "rank_4_20_rerank_gap": round(counts["RANK_4_20"] / actionable_n, 4)
                if actionable_n
                else 0.0,
                "miss_pool_recall_gap": round(counts["MISS_POOL"] / actionable_n, 4)
                if actionable_n
                else 0.0,
                "hit_at_3_n": counts["HIT_AT_3"],
                "rank_4_20_n": counts["RANK_4_20"],
                "miss_pool_n": counts["MISS_POOL"],
            },
            "rates": {k: round(v / n, 4) for k, v in counts.items()},
        }
        return summary, rows
    finally:
        settings.rrf_vector_weight = prev_v
        settings.rrf_fts_weight = prev_f


async def _eval_refuse(
    weight_rows: list[dict],
    rejection_cases: list[dict],
    db,
    kb_id: uuid.UUID,
    *,
    fallback: float,
    clause_route: bool,
    vector_w: float,
    fts_w: float,
) -> dict:
    from app.core.config import settings
    from app.services.rag.relevance import should_refuse_answer

    prev_fb = settings.relevance_similarity_fallback
    prev_v, prev_f = settings.rrf_vector_weight, settings.rrf_fts_weight
    settings.relevance_similarity_fallback = fallback
    settings.rrf_vector_weight = vector_w
    settings.rrf_fts_weight = fts_w
    try:
        hit3 = [r for r in weight_rows if r["bucket"] == "HIT_AT_3"]
        false_refuse = 0
        for r in hit3:
            pool = r.get("pool_top3") or []
            if should_refuse_answer(pool, r["query"]):
                false_refuse += 1

        rej_correct = 0
        for case in rejection_cases:
            query = case["query"]
            pool, _, _, _ = await _rrf_pool(
                db,
                kb_id,
                query,
                top_n=POOL_K,
                multi_query=False,
                mock_variants=False,
                clause_route=clause_route,
            )
            if should_refuse_answer(pool[:HIT_K], query):
                rej_correct += 1

        rej_n = max(1, len(rejection_cases))
        hit_n = max(1, len(hit3))
        return {
            "fallback": fallback,
            "expect_rejection_n": len(rejection_cases),
            "rejection_correct": rej_correct,
            "rejection_accuracy": round(rej_correct / rej_n, 4),
            "hit_at_3_n": len(hit3),
            "false_refuse": false_refuse,
            "false_refuse_rate": round(false_refuse / hit_n, 4),
        }
    finally:
        settings.relevance_similarity_fallback = prev_fb
        settings.rrf_vector_weight = prev_v
        settings.rrf_fts_weight = prev_f


async def main() -> None:
    args = parse_args()
    qa_path = FIXTURES / args.qa
    if not qa_path.exists():
        raise SystemExit(f"QA 文件不存在: {qa_path}")

    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.core.config import settings
    from app.core.database import SessionLocal

    use_clause_route = not bool(args.no_clause_route)
    settings.clause_route_enabled = use_clause_route
    settings.rerank_enabled = False
    settings.query_rewrite_enabled = False

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
    rejection_source = str(qa_path)
    # enterprise_qa.json 当前无 expect_rejection：用 golden 拒答题作「应拒答」代理（同 acme 库）
    if not rejection_cases:
        golden_path = FIXTURES / "golden_qa.json"
        if golden_path.exists():
            gdata = json.loads(golden_path.read_text(encoding="utf-8"))
            rejection_cases = [
                c for c in gdata.get("cases", []) if c.get("expect_rejection")
            ]
            rejection_source = f"{golden_path} (proxy; enterprise QA has 0)"

    print(
        f"A4 sweep fixtures={FIXTURES} scored={len(scored_cases)} "
        f"rejection={len(rejection_cases)} source={rejection_source} "
        f"clause_route={use_clause_route}",
        flush=True,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"a4-{uuid.uuid4().hex[:8]}@e.com"
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "username": f"a4{uuid.uuid4().hex[:8]}",
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
            json={"name": "Enterprise-A4-Sweep"},
        )
        kb_id = uuid.UUID(r.json()["id"])

    upload_dir = Path(settings.upload_dir)
    print("入库 acme_*.md …", flush=True)
    docs = await _ingest_acme(kb_id, user_id, upload_dir)
    print(f"入库完成: {docs}", flush=True)

    weight_grid: list[dict] = []
    rows_by_key: dict[str, list[dict]] = {}

    async with SessionLocal() as db:
        corpus = await _load_corpus_texts(db, kb_id)
        print(f"corpus chunks={len(corpus)}", flush=True)

        # Phase 1: vector=1.0 × fts grid
        for fts_w in FTS_GRID:
            print(f"  weight sweep vector={BASE_VECTOR} fts={fts_w} …", flush=True)
            summary, rows = await _eval_weights(
                db,
                kb_id,
                scored_cases,
                corpus,
                vector_w=BASE_VECTOR,
                fts_w=fts_w,
                clause_route=use_clause_route,
            )
            key = f"v{BASE_VECTOR}_f{fts_w}"
            weight_grid.append(summary)
            rows_by_key[key] = rows
            a = summary["actionable"]
            print(
                f"    Hit@3={a['hit_at_3_n']} RANK_4_20={a['rank_4_20_n']} "
                f"MISS={a['miss_pool_n']}",
                flush=True,
            )

        best_fts_phase = _pick_best_weight(weight_grid)
        best_fts = best_fts_phase["rrf_fts_weight"]

        # Phase 2: best fts × vector grid (skip already-run BASE_VECTOR)
        for vec_w in VECTOR_GRID:
            if vec_w == BASE_VECTOR:
                continue
            print(f"  weight sweep vector={vec_w} fts={best_fts} …", flush=True)
            summary, rows = await _eval_weights(
                db,
                kb_id,
                scored_cases,
                corpus,
                vector_w=vec_w,
                fts_w=best_fts,
                clause_route=use_clause_route,
            )
            key = f"v{vec_w}_f{best_fts}"
            weight_grid.append(summary)
            rows_by_key[key] = rows
            a = summary["actionable"]
            print(
                f"    Hit@3={a['hit_at_3_n']} RANK_4_20={a['rank_4_20_n']} "
                f"MISS={a['miss_pool_n']}",
                flush=True,
            )

        best_w = _pick_best_weight(weight_grid)
        worst_w = min(
            weight_grid,
            key=lambda g: (
                g["actionable"]["hit_at_3"],
                -g["actionable"]["miss_pool_recall_gap"],
            ),
        )
        best_key = f"v{best_w['rrf_vector_weight']}_f{best_w['rrf_fts_weight']}"
        worst_key = f"v{worst_w['rrf_vector_weight']}_f{worst_w['rrf_fts_weight']}"
        base_key = f"v{BASE_VECTOR}_f{BASE_FTS}"
        base_rows = rows_by_key[base_key]
        best_rows = rows_by_key[best_key]
        worst_rows = rows_by_key[worst_key]
        drop_compare = _bucket_compare(base_rows, best_rows)
        # 即使 best==baseline，也用 worst 对照记录掉分题前后（证明默认优于弱权重）
        drop_vs_worst = _bucket_compare(worst_rows, base_rows)
        drop_snapshot = [
            {
                "case_id": r["case_id"],
                "query": (r.get("query") or "")[:80],
                "bucket": r["bucket"],
                "rank": r["rank"],
            }
            for r in base_rows
            if r.get("bucket") in ("RANK_4_20", "MISS_POOL")
        ]

        # Phase 3: refuse fallback on best weights
        refuse_grid: list[dict] = []
        for fb in FALLBACK_GRID:
            print(f"  refuse sweep fallback={fb} …", flush=True)
            # 复用 best_rows 的 Top-3 pool（假拒答）；拒答题重新召回
            # pool_top3 在 rows 里仍是 RetrievedChunk — 需清掉不可 JSON 化字段前先用
            refuse_stat = await _eval_refuse(
                best_rows,
                rejection_cases,
                db,
                kb_id,
                fallback=fb,
                clause_route=use_clause_route,
                vector_w=best_w["rrf_vector_weight"],
                fts_w=best_w["rrf_fts_weight"],
            )
            refuse_grid.append(refuse_stat)
            print(
                f"    rej_acc={refuse_stat['rejection_accuracy']} "
                f"false_refuse={refuse_stat['false_refuse']}",
                flush=True,
            )

        base_refuse = next(g for g in refuse_grid if g["fallback"] == BASE_FALLBACK)
        best_refuse = _pick_best_refuse(refuse_grid, base_refuse["false_refuse"])

    # 序列化：去掉 RetrievedChunk
    def _strip_pools(rows: list[dict]) -> list[dict]:
        out = []
        for r in rows:
            item = {k: v for k, v in r.items() if k != "pool_top3"}
            out.append(item)
        return out

    baseline_summary = next(
        g
        for g in weight_grid
        if g["rrf_vector_weight"] == BASE_VECTOR and g["rrf_fts_weight"] == BASE_FTS
    )
    keep_weights = (
        best_w["rrf_vector_weight"] == BASE_VECTOR
        and best_w["rrf_fts_weight"] == BASE_FTS
    )
    keep_fallback = best_refuse["fallback"] == BASE_FALLBACK

    payload = {
        "summary": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "qa_file": str(qa_path),
            "clause_route": use_clause_route,
            "scored_n": len(scored_cases),
            "rejection_n": len(rejection_cases),
            "baseline_weights": {
                "rrf_vector_weight": BASE_VECTOR,
                "rrf_fts_weight": BASE_FTS,
                "actionable": baseline_summary["actionable"],
            },
            "best_weights": {
                **{k: best_w[k] for k in ("rrf_vector_weight", "rrf_fts_weight", "actionable", "counts")},
                "keep_defaults": keep_weights,
            },
            "weight_grid": [
                {
                    "rrf_vector_weight": g["rrf_vector_weight"],
                    "rrf_fts_weight": g["rrf_fts_weight"],
                    "actionable": g["actionable"],
                }
                for g in weight_grid
            ],
            "baseline_refuse": base_refuse,
            "best_refuse": {**best_refuse, "keep_defaults": keep_fallback},
            "refuse_grid": refuse_grid,
            "rejection_source": rejection_source,
            "drop_score_snapshot": drop_snapshot,
            "drop_score_bucket_changes_vs_best": drop_compare,
            "drop_score_change_n": len(drop_compare),
            "worst_weights": {
                "rrf_vector_weight": worst_w["rrf_vector_weight"],
                "rrf_fts_weight": worst_w["rrf_fts_weight"],
                "actionable": worst_w["actionable"],
            },
            "drop_score_bucket_changes_worst_to_baseline": drop_vs_worst,
            "recommendation": {
                "rrf_vector_weight": best_w["rrf_vector_weight"],
                "rrf_fts_weight": best_w["rrf_fts_weight"],
                "relevance_similarity_fallback": best_refuse["fallback"],
                "change_weights": not keep_weights,
                "change_fallback": not keep_fallback,
            },
        },
        "baseline_rows": _strip_pools(base_rows),
        "best_rows": _strip_pools(best_rows),
        "worst_rows": _strip_pools(worst_rows),
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 60, flush=True)
    print("A4 RRF + refuse sweep", flush=True)
    print("=" * 60, flush=True)
    print(
        f"baseline Hit@3={baseline_summary['actionable']['hit_at_3_n']} "
        f"→ best Hit@3={best_w['actionable']['hit_at_3_n']} "
        f"(v={best_w['rrf_vector_weight']} f={best_w['rrf_fts_weight']}) "
        f"keep_weights={keep_weights}",
        flush=True,
    )
    print(
        f"refuse baseline fallback={BASE_FALLBACK} "
        f"acc={base_refuse['rejection_accuracy']} false={base_refuse['false_refuse']} "
        f"→ best fallback={best_refuse['fallback']} "
        f"acc={best_refuse['rejection_accuracy']} false={best_refuse['false_refuse']} "
        f"keep_fallback={keep_fallback}",
        flush=True,
    )
    print(f"drop_score snapshot (baseline RANK_4_20|MISS): {len(drop_snapshot)}", flush=True)
    for row in drop_snapshot:
        print(
            f"  {row['case_id']}: {row['bucket']}@{row['rank']} | {row['query'][:40]}",
            flush=True,
        )
    print(
        f"worst→baseline bucket changes: {len(drop_vs_worst)} "
        f"(worst v={worst_w['rrf_vector_weight']} f={worst_w['rrf_fts_weight']})",
        flush=True,
    )
    for row in drop_vs_worst[:20]:
        print(
            f"  {row['case_id']}: {row['old_bucket']}@{row['old_rank']} "
            f"→ {row['new_bucket']}@{row['new_rank']}",
            flush=True,
        )
    print(f"wrote: {out_path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
