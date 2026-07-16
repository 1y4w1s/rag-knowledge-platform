"""含噪鲁棒性评测：通过含噪查询 + 混合检索，测试 Context Precision 保持能力。

核心方法：
1. 基线 Context Precision@3 = 自然检索 Top-3 中相关 chunk 的比例
2. 混合查询测试：将特定查询与噪声关键词拼接，模拟真实场景中检索混入无关结果
3. 相关性门控有效性：对比通过/未通过 gate 的 Context Precision

用法：
  docker cp backend/scripts/eval_noise_robustness.py zhiku-api:/tmp/
  docker exec zhiku-api env PYTHONPATH=/app:/tmp python /tmp/eval_noise_robustness.py
"""

from __future__ import annotations

import asyncio
import math
import re
import time
import uuid
from pathlib import Path

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.ingestion import embedder
from app.services.ingestion.embedder import EMBEDDING_DIM
from app.services.rag.retrieval import retrieve_chunks
from app.services.rag.relevance import filter_relevant_chunks
from app.services.rag.types import RetrievedChunk
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

NOISE_SUFFIXES = [
    " 财务报告",       # "financial report"
    " 企业文化",       # "corporate culture"
    " 招聘流程",       # "recruitment process"
    " 数据安全政策",   # "data security policy"
    " 办公室管理规定", # "office management"
]


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
            json={"name": f"Noise Eval {uuid.uuid4().hex[:8]}"},
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
    print("  NOISE ROBUSTNESS EVALUATION")
    print("=" * 72)

    results = []  # {case_id, baseline_cp, noisy_cp, gated_cp, passed_gate}

    async with SessionLocal() as db:
        for idx, case in enumerate(GOLDEN_QA_CASES):
            if case.expect_rejection:
                continue

            # ── Baseline: clean query ──
            clean_chunks = await retrieve_chunks(db, kb_id=kb_id, query=case.query, top_k=HIT_K * 2)
            baseline_cp = 0.0
            if clean_chunks:
                rel_clean = sum(1 for c in clean_chunks[:HIT_K] if chunk_matches(case, c))
                baseline_cp = rel_clean / min(HIT_K, len(clean_chunks[:HIT_K]))

            # ── Noisy query: append irrelevant suffix ──
            noise_suffix = NOISE_SUFFIXES[idx % len(NOISE_SUFFIXES)]
            noisy_query = case.query + noise_suffix
            noisy_chunks = await retrieve_chunks(db, kb_id=kb_id, query=noisy_query, top_k=HIT_K * 2)
            noisy_cp = 0.0
            if noisy_chunks:
                rel_noisy = sum(1 for c in noisy_chunks[:HIT_K] if chunk_matches(case, c))
                noisy_cp = rel_noisy / min(HIT_K, len(noisy_chunks[:HIT_K]))

            # ── With relevance gate ──
            gated = filter_relevant_chunks(noisy_chunks, noisy_query)
            gated_cp = 0.0
            if gated:
                rel_gated = sum(1 for c in gated[:HIT_K] if chunk_matches(case, c))
                gated_cp = rel_gated / min(HIT_K, len(gated[:HIT_K]))

            passed_gate = hit_at_k(noisy_chunks, case, k=HIT_K)

            results.append({
                "case_id": case.case_id,
                "query": case.query[:30],
                "baseline_cp": baseline_cp,
                "noisy_cp": noisy_cp,
                "gated_cp": gated_cp,
                "passed": passed_gate,
                "clean_count": len(clean_chunks),
                "noisy_count": len(noisy_chunks),
                "gated_count": len(gated),
            })

            if (idx + 1) % 10 == 0:
                print(f"    [{idx+1}/{total}] processed...")

    # ── Aggregate ──
    n = len(results)
    avg_baseline_cp = sum(r["baseline_cp"] for r in results) / n
    avg_noisy_cp = sum(r["noisy_cp"] for r in results) / n
    avg_gated_cp = sum(r["gated_cp"] for r in results) / n
    noise_degradation = avg_baseline_cp - avg_noisy_cp
    gate_improvement = avg_gated_cp - avg_noisy_cp

    print()
    print("=" * 72)
    print("  RESULTS")
    print("=" * 72)
    print()
    print(f"  {'Metric':45s} {'Value':>15s}")
    print(f"  {'-'*45} {'-'*15}")
    print(f"  {'Baseline Context Precision@3':45s} {avg_baseline_cp:>15.4f}")
    print(f"  {'Noisy Query CP@3 (w/o gate)':45s} {avg_noisy_cp:>15.4f}")
    print(f"  {'Gated CP@3 (with relevance gate)':45s} {avg_gated_cp:>15.4f}")
    print(f"  {'Noise degradation':45s} {noise_degradation:>15.4f}")
    print(f"  {'Gate improvement':45s} {gate_improvement:>15.4f}")
    print(f"  {'Average clean chunks retrieved':45s} {sum(r['clean_count'] for r in results)/n:>15.1f}")
    print(f"  {'Average noisy chunks retrieved':45s} {sum(r['noisy_count'] for r in results)/n:>15.1f}")
    print(f"  {'Average gated chunks (after filter)':45s} {sum(r['gated_count'] for r in results)/n:>15.1f}")

    # ── Robustness Grade ──
    if noise_degradation < 0.05:
        grade = "⭐⭐⭐⭐⭐ (Excellent — noise has minimal impact)"
    elif noise_degradation < 0.15:
        grade = "⭐⭐⭐⭐ (Good — slight impact)"
    elif noise_degradation < 0.30:
        grade = "⭐⭐⭐ (Fair — noticeable impact)"
    else:
        grade = "⭐⭐ (Poor — significant impact)"

    print()
    print(f"  Robustness Grade: {grade}")

    if gate_improvement > 0:
        gate_grade = "⭐⭐⭐⭐⭐" if gate_improvement > 0.1 else "⭐⭐⭐⭐"
        print(f"  Relevance Gate Effectiveness: {gate_grade}")
        print(f"    (improves CP by {gate_improvement:.4f} on noisy queries)")

    print()

    # ── Per-case detail (top drops) ──
    sorted_by_degradation = sorted(results, key=lambda r: r["baseline_cp"] - r["noisy_cp"], reverse=True)
    worst_5 = [r for r in sorted_by_degradation if r["baseline_cp"] - r["noisy_cp"] > 0][:5]
    if worst_5:
        print("  Top-5 most degraded cases:")
        print(f"  {'Case':8s} {'Query':30s} {'Baseline':>10s} {'Noisy':>10s} {'Gate':>10s}")
        print(f"  {'-'*8} {'-'*30} {'-'*10} {'-'*10} {'-'*10}")
        for r in worst_5:
            print(f"  {r['case_id']:8s} {r['query']:30s} {r['baseline_cp']:>10.2f} {r['noisy_cp']:>10.2f} {r['gated_cp']:>10.2f}")

    # ── Save report ──
    report = f"""# Noise Robustness Evaluation Report

> **Date**: 2026-07-15
> **Test set**: {n} non-rejection golden QA cases (v0.5)
> **Embedding**: Mock lexical
> **Noise injection**: Query suffix concatenation (irrelevant topic appended)

## Core Metrics

| Metric | Value |
|--------|-------|
| Baseline Context Precision@3 | {avg_baseline_cp:.4f} |
| Noisy Query CP@3 (wo/ gate) | {avg_noisy_cp:.4f} |
| Gated CP@3 (with relevance gate) | {avg_gated_cp:.4f} |
| Noise degradation | {noise_degradation:.4f} |
| Gate improvement | {gate_improvement:.4f} |
| Avg chunks before gate | {sum(r['clean_count'] for r in results)/n:.1f} |
| Avg chunks after gate | {sum(r['gated_count'] for r in results)/n:.1f} |

## Robustness Grade

**{grade}**

Relevance Gate Effectiveness: {'Effective' if gate_improvement > 0.05 else 'Limited'}

## Top-5 Most Degraded Cases

| Case | Query | Baseline CP | Noisy CP | Gated CP |
|------|-------|------------|----------|----------|
"""
    for r in worst_5:
        report += f"| {r['case_id']} | {r['query']} | {r['baseline_cp']:.2f} | {r['noisy_cp']:.2f} | {r['gated_cp']:.2f} |\n"

    report += """
## Interpretation

- **Baseline CP** measures how many of top-3 chunks are relevant in a clean query
- **Noisy CP** shows degradation when query contains irrelevant noise terms
- **Gated CP** shows how much the relevance gate recovers from noise
- A high gate improvement (>0.05) means the gate effectively filters noise
"""
    out_path = "/tmp/noise_robustness_report.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report saved to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
