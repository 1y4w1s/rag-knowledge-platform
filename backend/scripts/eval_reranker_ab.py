"""Reranker A/B 对比评测：有/无 Qwen3-rerank 对 golden QA 检索质量的影响。

用法：
  docker cp backend/scripts/eval_reranker_ab.py zhiku-api:/tmp/
  docker exec zhiku-api env PYTHONPATH=/app:/tmp python /tmp/eval_reranker_ab.py
"""

from __future__ import annotations

import asyncio
import contextlib
import math
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.ingestion import embedder
from app.services.ingestion.embedder import EMBEDDING_DIM
from app.services.rag.retrieval import retrieve_chunks
from tests.golden_qa_loader import (
    GOLDEN_QA_CASES,
    HIT_K,
    chunk_matches,
    hit_at_k,
    reciprocal_rank,
)

_CJK = re.compile(r"[\u4e00-\u9fff]")
_LATIN = re.compile(r"[a-z0-9]+")


def _lexical_mock_vector(text: str) -> list[float]:
    tokens: set[str] = set(_CJK.findall(text))
    tokens.update(_LATIN.findall(text.lower()))
    vec = [0.0] * EMBEDDING_DIM
    for token in tokens:
        seed = sum(ord(ch) for ch in token)
        for j in range(8):
            idx = (seed * (j + 1) * 17 + j * 31) % EMBEDDING_DIM
            vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


embedder._mock_vector = _lexical_mock_vector

FIXTURES = Path("/tmp/tests/fixtures")


@dataclass
class CaseResult:
    case_id: str
    query: str
    source: str
    hit_with_rerank: bool = False
    rr_with_rerank: float = 0.0
    hit_no_rerank: bool = False
    rr_no_rerank: float = 0.0


async def run_eval(kb_id: uuid.UUID, enable_rerank: bool, db) -> list[dict]:
    """单次 golden QA 评测（共用 db session）。"""
    settings.rerank_enabled = enable_rerank
    results = []
    for case in GOLDEN_QA_CASES:
        t1 = time.time()
        chunks = await retrieve_chunks(db, kb_id=kb_id, query=case.query, top_k=HIT_K)
        latency = time.time() - t1
        passed = hit_at_k(chunks, case, k=HIT_K)
        rr = reciprocal_rank(chunks, case, k=HIT_K)
        results.append({
            "case_id": case.case_id,
            "hit": passed,
            "rr": rr,
            "latency_ms": int(latency * 1000),
        })
    return results


def context_precision(chunks, case) -> float:
    """Top-K 中相关 chunk 的比例。"""
    if not chunks:
        return 0.0
    relevant = sum(1 for c in chunks[:HIT_K] if chunk_matches(case, c))
    return relevant / min(HIT_K, len(chunks))


async def run_context_precision(kb_id: uuid.UUID, enable_rerank: bool, db) -> dict:
    """评估 Context Precision：Top-K 中相关 chunk 的比例。"""
    settings.rerank_enabled = enable_rerank
    total_precision = 0.0
    count = 0
    for case in GOLDEN_QA_CASES:
        if case.expect_rejection:
            continue
        chunks = await retrieve_chunks(db, kb_id=kb_id, query=case.query, top_k=HIT_K)
        total_precision += context_precision(chunks, case)
        count += 1
    return {"context_precision": total_precision / count if count else 0, "count": count}


async def main():
    from httpx import AsyncClient

    async with AsyncClient(base_url="http://localhost:8000") as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"identifier": "demo_admin", "password": "password123"},
        )
        if login.status_code != 200:
            print("Please run seed_enterprise_demo.py first.")
            return
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        kb = await client.post(
            "/api/v1/knowledge-bases?workspace=personal",
            json={"name": f"Reranker AB {uuid.uuid4().hex[:8]}"},
            headers=headers,
        )
        kb_id = uuid.UUID(kb.json()["id"])
        fixture = FIXTURES / "golden_handbook.md"
        with open(fixture, "rb") as f:
            await client.post(
                f"/api/v1/knowledge-bases/{kb_id}/documents",
                files={"files": ("golden_handbook.md", f, "text/markdown")},
                headers=headers,
            )
        print("[setup] KB={} doc=uploaded, waiting ingestion...".format(kb_id))
        await asyncio.sleep(3)

    total = len(GOLDEN_QA_CASES)
    print()
    print("=" * 72)
    print(f"  RERANKER A/B EVALUATION ({total} cases)")
    print("=" * 72)
    print()

    # Use a single DB session for all runs to avoid connection pool issues
    async with SessionLocal() as db:
        # ── A: WITH reranker ──
        print("[A] With reranker...")
        settings.rerank_provider = "mock"
        settings.rerank_enabled = True
        results_with = await run_eval(kb_id, enable_rerank=True, db=db)
        hits_with = sum(1 for r in results_with if r["hit"])
        mrr_with = sum(r["rr"] for r in results_with) / total
        cp_with = await run_context_precision(kb_id, enable_rerank=True, db=db)

        # ── B: WITHOUT reranker ──
        print("[B] Without reranker...")
        results_without = await run_eval(kb_id, enable_rerank=False, db=db)
        hits_without = sum(1 for r in results_without if r["hit"])
        mrr_without = sum(r["rr"] for r in results_without) / total
        cp_without = await run_context_precision(kb_id, enable_rerank=False, db=db)

    # ── Report ──
    print()
    print("=" * 72)
    print("  RESULTS")
    print("=" * 72)
    print()
    header = f"{'Metric':30s} {'With Rerank':>14s} {'No Rerank':>14s} {'Delta':>10s}"
    sep = "-" * 70
    print(header)
    print(sep)

    hit_delta = hits_with - hits_without
    mrr_delta = mrr_with - mrr_without
    cp_delta = cp_with["context_precision"] - cp_without["context_precision"]

    print(f"{'Hit@3':30s} {hits_with:>3d}/{total} ({hits_with/total*100:>5.1f}%)  {hits_without:>3d}/{total} ({hits_without/total*100:>5.1f}%)  {'+' if hit_delta >= 0 else ''}{hit_delta:>+2d}")
    print(f"{'MRR':30s} {mrr_with:>14.4f} {mrr_without:>14.4f} {'+' if mrr_delta >= 0 else ''}{mrr_delta:>+9.4f}")
    print(f"{'Context Precision@3':30s} {cp_with['context_precision']:>14.4f} {cp_without['context_precision']:>14.4f} {'+' if cp_delta >= 0 else ''}{cp_delta:>+9.4f}")

    print()
    print(sep)
    print()

    # Per-case comparison
    print("  PER-CASE COMPARISON")
    print(f"  {'Case':8s} {'Source':8s} {'Rerank':8s} {'NoRerank':8s} {'Match?':8s}")
    print(f"  {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
    for rw, rwo in zip(results_with, results_without):
        if rw["case_id"] != rwo["case_id"]:
            continue
        c = next(c for c in GOLDEN_QA_CASES if c.case_id == rw["case_id"])
        rk = "PASS" if rw["hit"] else "FAIL"
        nrk = "PASS" if rwo["hit"] else "FAIL"
        match = "✓" if rw["hit"] == rwo["hit"] else ("❌ R> NR" if rw["hit"] > rwo["hit"] else "❌ NR> R")
        print(f"  {rw['case_id']:8s} {c.source:8s} {rk:>8s} {nrk:>8s} {match:8s}")

    # Summary
    print()
    print("=" * 72)
    print("  SUMMARY")
    print("=" * 72)
    cases_diff = sum(1 for a, b in zip(results_with, results_without) if a["hit"] != b["hit"])
    print(f"  Cases where rerank changed result: {cases_diff}/{total}")
    print(f"  Hit@3 with rerank:    {hits_with}/{total} ({hits_with/total*100:.1f}%)")
    print(f"  Hit@3 without rerank: {hits_without}/{total} ({hits_without/total*100:.1f}%)")
    print(f"  Context Precision with rerank:    {cp_with['context_precision']:.4f}")
    print(f"  Context Precision without rerank: {cp_without['context_precision']:.4f}")
    print()

    if hits_with > hits_without:
        print("  → Rerank improves Hit@3 by {} cases".format(hits_with - hits_without))
    elif hits_with < hits_without:
        print("  → Rerank hurts Hit@3 by {} cases".format(hits_without - hits_with))
    else:
        print("  → Rerank has no net effect on Hit@3 (identical)")

    # Save report
    report = f"""# Reranker A/B Evaluation Report

> **Date**: 2026-07-15
> **Test set**: {total} golden QA cases (v0.5)
> **Embedding**: Mock lexical (for deterministic comparison)
> **Reranker**: Mock lexical fallback (eval context)

## Comparison

| Metric | With Rerank | No Rerank | Delta |
|--------|------------|-----------|-------|
| Hit@3 | {hits_with}/{total} ({hits_with/total*100:.1f}%) | {hits_without}/{total} ({hits_without/total*100:.1f}%) | {'+' if hit_delta >= 0 else ''}{hit_delta} |
| MRR | {mrr_with:.4f} | {mrr_without:.4f} | {'+' if mrr_delta >= 0 else ''}{mrr_delta:.4f} |
| Context Precision@3 | {cp_with['context_precision']:.4f} | {cp_without['context_precision']:.4f} | {'+' if cp_delta >= 0 else ''}{cp_delta:.4f} |
| Cases changed | — | — | {cases_diff}/{total} |

## Per-Case

| Case | Source | With Rerank | No Rerank |
|------|--------|------------|-----------|
"""
    for rw, rwo in zip(results_with, results_without):
        c = next(c for c in GOLDEN_QA_CASES if c.case_id == rw["case_id"])
        report += f"| {rw['case_id']} | {c.source} | {'PASS' if rw['hit'] else 'FAIL'} | {'PASS' if rwo['hit'] else 'FAIL'} |\n"

    report += f"""
## Conclusion

In mock embedding mode, the reranker shows {'improvement' if hits_with >= hits_without else 'degradation'} of {abs(hit_delta)} cases.
Note: This test uses **mock** lexical reranking since eval runs with mock embeddings.
For production validation with real embeddings, use the live Qwen3-rerank API by running outside eval context.
"""
    out_path = "/tmp/reranker_ab_report.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report saved to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
