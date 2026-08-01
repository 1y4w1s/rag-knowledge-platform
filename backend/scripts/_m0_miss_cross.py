"""M0 · L2 后企业池：run_benchmark content Hit@3 miss × diagnose 四桶（同一次入库）。

评测侧脚本，不改检索默认。产出 docs/tasks/_m0_cross_out.{json,txt}
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import re
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"

# Container: /app ; host: backend/
_BACKEND_CANDIDATES = [
    Path("/app"),
    Path(__file__).resolve().parents[1],
]
ROOT = next((p for p in _BACKEND_CANDIDATES if (p / "app").is_dir()), _BACKEND_CANDIDATES[0])
FIX = ROOT / "tests" / "fixtures"
# Prefer writable /tmp in container; host falls back next to repo docs/tasks
_OUT_CANDIDATES = [
    Path("/tmp/m0_cross_out.json"),
    ROOT.parent / "docs" / "tasks" / "_m0_cross_out.json",
]
OUT_JSON = _OUT_CANDIDATES[0] if Path("/tmp").is_dir() and os.access("/tmp", os.W_OK) else _OUT_CANDIDATES[1]
OUT_TXT = OUT_JSON.with_suffix(".txt")

sys.path.insert(0, str(ROOT))

# Load diagnose helpers without running its CLI
_DIAG_CANDIDATES = [
    Path(__file__).resolve().parent / "diagnose_enterprise_rank.py",
    Path("/tmp/diagnose_enterprise_rank.py"),
    ROOT / "scripts" / "diagnose_enterprise_rank.py",
]
_DIAG_PATH = next((p for p in _DIAG_CANDIDATES if p.exists()), _DIAG_CANDIDATES[0])
_spec = importlib.util.spec_from_file_location("diagnose_enterprise_rank", _DIAG_PATH)
_diag = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_diag)

HIT_K = 3
POOL_K = 20

# Heuristic tags for miss shape (readability only; not gate)
_TABLE_Q = re.compile(r"收入|毛利率|费用|人数|占比|Q1|产品线|总收入|净利润|现金流")
_CLAUSE_Q = re.compile(r"第\s*\d+\s*条|条款|SLA|违约|保密|服务期限|可用性")
_CROSS_HINT = re.compile(r"分别|对比|哪个.*最高|哪个.*最低|和.*分别")


def _bm_hit(chunks, expect: dict) -> bool:
    cc = (expect.get("content_contains") or "").lower()
    sp = (expect.get("section_title") or "").lower()
    hp = (expect.get("heading_path_contains") or "").lower()
    for ck in (chunks or [])[:HIT_K]:
        content = (ck.content or "").lower()
        st = (ck.heading_path or ck.section_title or "").lower()
        ok = True
        if cc and cc not in content:
            ok = False
        if sp and sp not in st:
            ok = False
        if hp and hp not in st:
            ok = False
        if ok:
            return True
    return False


def _shape_tag(query: str, source_docs: list | None, bucket: str) -> str:
    q = query or ""
    if bucket == "NEEDLE_ABSENT":
        return "needle_absent"
    if bucket == "MISS_POOL":
        return "out_of_pool"
    if bucket == "RANK_4_20":
        return "mid_rank"
    # HIT_AT_3 on diagnose but miss on run_benchmark → ruler fork / label / chunk surface
    docs = source_docs or []
    if len(docs) >= 2 or _CROSS_HINT.search(q):
        return "cross_doc_suspect"
    if _TABLE_Q.search(q):
        return "table_metric"
    if _CLAUSE_Q.search(q):
        return "clause_contract"
    return "other_content_miss"


async def main() -> None:
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.services.rag.retrieval import retrieve_chunks

    qa = json.loads((FIX / "enterprise_qa.json").read_text(encoding="utf-8"))
    all_cases = qa["cases"]
    scored = [c for c in all_cases if not c.get("expect_rejection")]
    print(f"non_rejection={len(scored)} fixture={FIX / 'enterprise_qa.json'}", flush=True)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"m0-{uuid.uuid4().hex[:8]}@e.com"
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "username": f"m0{uuid.uuid4().hex[:8]}",
                "password": "M0Pass123!",
                "account_type": "personal",
            },
        )
        r = await client.post(
            "/api/v1/auth/login",
            json={"identifier": email, "password": "M0Pass123!"},
        )
        token_data = r.json()
        headers = {"Authorization": f"Bearer {token_data['access_token']}"}
        user_id = uuid.UUID(token_data["user"]["id"])
        r = await client.post(
            "/api/v1/knowledge-bases?workspace=personal",
            headers=headers,
            json={"name": "M0-Miss-Cross"},
        )
        kb_id = uuid.UUID(r.json()["id"])

    print("ingest acme_*.md …", flush=True)
    docs = await _diag._ingest_acme(kb_id, user_id, Path(settings.upload_dir))
    print(f"ingested: {docs}", flush=True)

    rows: list[dict] = []
    diag_counts: Counter[str] = Counter()
    bm_hit_n = 0

    async with SessionLocal() as db:
        corpus = await _diag._load_corpus_texts(db, kb_id)
        print(f"corpus_chunks={len(corpus)}", flush=True)
        for i, case in enumerate(scored, start=1):
            expect = case.get("expect") or {}
            needle = expect.get("content_contains") or ""
            query = case["query"]
            in_corpus = _diag._corpus_has_needle(corpus, needle)

            pool, n_vec, n_fts, *_rest = await _diag._rrf_pool(
                db,
                kb_id,
                query,
                top_n=POOL_K,
                multi_query=False,
                mock_variants=False,
                clause_route=True,
            )
            rank, matched_doc = _diag._find_rank(pool, needle)
            bucket = _diag._classify(rank, in_corpus, pool_k=POOL_K)
            diag_counts[bucket] += 1

            # run_benchmark lens: production retrieve_chunks Top-3, content-only
            chunks = await retrieve_chunks(db, kb_id=kb_id, query=query, top_k=HIT_K)
            bm_ok = _bm_hit(chunks, expect)
            if bm_ok:
                bm_hit_n += 1

            shape = _shape_tag(query, case.get("source_docs"), bucket)
            rows.append(
                {
                    "case_id": case.get("case_id"),
                    "query": query,
                    "difficulty": case.get("difficulty"),
                    "source_docs": case.get("source_docs"),
                    "bm_hit": bm_ok,
                    "diag_bucket": bucket,
                    "diag_rank": rank,
                    "needle_in_corpus": in_corpus,
                    "matched_doc": matched_doc,
                    "shape": shape if not bm_ok else None,
                    "needle_preview": needle[:80].replace("\n", " "),
                    "vector_hits": n_vec,
                    "fts_hits": n_fts,
                }
            )
            if i % 10 == 0 or i == len(scored):
                print(
                    f"  [{i}/{len(scored)}] {case.get('case_id')} "
                    f"bm={'H' if bm_ok else 'M'} diag={bucket} rank={rank}",
                    flush=True,
                )

    n = len(scored)
    misses = [r for r in rows if not r["bm_hit"]]
    cross = Counter((r["diag_bucket"], r["shape"]) for r in misses)
    by_bucket = Counter(r["diag_bucket"] for r in misses)
    by_shape = Counter(r["shape"] for r in misses)

    # Among BM misses that diagnose says HIT_AT_3: ruler fork / mid-surface
    fork = [r for r in misses if r["diag_bucket"] == "HIT_AT_3"]
    mid = [r for r in misses if r["diag_bucket"] == "RANK_4_20"]
    pool_miss = [r for r in misses if r["diag_bucket"] == "MISS_POOL"]
    absent = [r for r in misses if r["diag_bucket"] == "NEEDLE_ABSENT"]

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fixture": "enterprise_qa.json",
        "note": "L2-after fixture; clause_route=true; RERANK off path via _rrf_pool",
        "non_rejection_n": n,
        "run_benchmark_hit_at_3": round(bm_hit_n / max(1, n), 4),
        "run_benchmark_hits": bm_hit_n,
        "run_benchmark_misses": len(misses),
        "diagnose_counts": dict(diag_counts),
        "diagnose_hit_at_3_rate": round(diag_counts["HIT_AT_3"] / max(1, n), 4),
        "miss_by_diag_bucket": dict(by_bucket),
        "miss_by_shape": dict(by_shape),
        "miss_cross_bucket_x_shape": {
            f"{a}|{b}": c for (a, b), c in cross.most_common()
        },
        "fork_diag_hit_bm_miss_n": len(fork),
        "mid_rank_n": len(mid),
        "out_of_pool_n": len(pool_miss),
        "needle_absent_n": len(absent),
    }

    payload = {"summary": summary, "misses": misses, "all_rows": rows}
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"generated_at={summary['generated_at']}",
        f"non_rejection={n}",
        f"run_benchmark Hit@3={bm_hit_n}/{n}={summary['run_benchmark_hit_at_3']:.1%}",
        f"diagnose HIT_AT_3={diag_counts['HIT_AT_3']}/{n}={summary['diagnose_hit_at_3_rate']:.1%}",
        "--- diagnose four buckets (full scored pool) ---",
    ]
    for k in ("HIT_AT_3", "RANK_4_20", "MISS_POOL", "NEEDLE_ABSENT"):
        lines.append(f"{k}\t{diag_counts[k]}\t{diag_counts[k]/n:.1%}")
    lines.append("--- run_benchmark misses × diagnose bucket ---")
    for k in ("HIT_AT_3", "RANK_4_20", "MISS_POOL", "NEEDLE_ABSENT"):
        lines.append(f"BM_MISS∩{k}\t{by_bucket[k]}")
    lines.append("--- BM miss shape counts ---")
    for k, v in by_shape.most_common():
        lines.append(f"{k}\t{v}")
    lines.append("--- cross bucket×shape (BM misses) ---")
    for (a, b), c in cross.most_common():
        lines.append(f"{a}\t{b}\t{c}")
    lines.append("--- BM miss samples (up to 15 per bucket) ---")
    for bucket in ("HIT_AT_3", "RANK_4_20", "MISS_POOL", "NEEDLE_ABSENT"):
        subset = [r for r in misses if r["diag_bucket"] == bucket][:15]
        lines.append(f"[{bucket}] n={by_bucket[bucket]}")
        for r in subset:
            lines.append(
                f"  {r['case_id']}|rank={r['diag_rank']}|shape={r['shape']}|"
                f"q={r['query'][:40]}"
            )

    OUT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)
    print(f"wrote {OUT_JSON}", flush=True)
    print(f"wrote {OUT_TXT}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
