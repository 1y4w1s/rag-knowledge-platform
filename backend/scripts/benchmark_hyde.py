"""Baseline vs Multi-Query 对比基准测试（HyDE 已移除，睿阁不启用）。

用法：
  docker cp backend/scripts/benchmark_hyde.py zhiku-api:/tmp/
  docker exec zhiku-api env PYTHONPATH=/app:/tmp python /tmp/benchmark_hyde.py
"""

from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.rag.generation import expand_queries
from app.services.rag.retrieval import retrieve_chunks
from app.services.rag.types import RetrievedChunk
from tests.golden_qa_loader import GOLDEN_QA_CASES, HIT_K, GoldenQACase, chunk_matches
from app.services.ingestion import embedder
from app.services.ingestion.embedder import EMBEDDING_DIM
import math
import re

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




def score(chunks: list[RetrievedChunk], case: GoldenQACase) -> tuple[bool, float]:
    for rank, c in enumerate(chunks[:HIT_K], start=1):
        if chunk_matches(case, c):
            return True, 1.0 / rank
    return False, 0.0


async def run_baseline(db, kb_id) -> tuple[list, float, int]:
    """单次检索（baseline）。"""
    results, total_rr, hits = [], 0.0, 0
    for case in GOLDEN_QA_CASES:
        chunks = await retrieve_chunks(db, kb_id=kb_id, query=case.query, top_k=HIT_K)
        hit, rr = score(chunks, case)
        results.append({"case": case.case_id, "hit": hit, "rr": rr})
        if hit:
            hits += 1
        total_rr += rr
    return results, total_rr / len(GOLDEN_QA_CASES), hits


async def run_multi_query(db, kb_id) -> tuple[list, float, int, int]:
    """多查询扩展：3 路检索合并。"""
    results, total_rr, hits, total_llm_calls = [], 0.0, 0, 0
    for case in GOLDEN_QA_CASES:
        queries = await expand_queries(case.query)
        total_llm_calls += 1
        seen: set[uuid.UUID] = set()
        merged: list[RetrievedChunk] = []
        for q in queries:
            chunks = await retrieve_chunks(db, kb_id=kb_id, query=q, top_k=HIT_K)
            for c in chunks:
                if c.chunk_id not in seen:
                    seen.add(c.chunk_id)
                    merged.append(c)
        merged = merged[:HIT_K]
        hit, rr = score(merged, case)
        results.append({"case": case.case_id, "hit": hit, "rr": rr})
        if hit:
            hits += 1
        total_rr += rr
    return results, total_rr / len(GOLDEN_QA_CASES), hits, total_llm_calls


# HyDE 已移除（睿阁不启用）


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
            json={"name": f"HyDE Bench {uuid.uuid4().hex[:8]}"},
            headers=headers,
        )
        kb_id = uuid.UUID(kb.json()["id"])
        fixture = Path("/tmp/tests/fixtures/golden_handbook.md")
        with open(fixture, "rb") as f:
            await client.post(
                f"/api/v1/knowledge-bases/{kb_id}/documents",
                files={"files": ("golden_handbook.md", f, "text/markdown")},
                headers=headers,
            )
        print("Ingesting...")
        await asyncio.sleep(3)

    print()
    print(f"{'Method':20s} {'Hit@3':>10s} {'MRR':>8s} {'LLM calls':>12s} {'Emb calls':>12s} {'Latency':>10s}")
    print("-" * 75)

    async with SessionLocal() as db:
        # Baseline
        t0 = time.time()
        _, mrr_b, hits_b = await run_baseline(db, kb_id)
        t_b = time.time() - t0
        print(f"{'Baseline (single)':20s} {f'{hits_b}/25 ({hits_b/25*100:.0f}%)':>10s} {mrr_b:>8.4f} {'0':>12s} {'25':>12s} {t_b:>8.1f}s")

        # Multi-query
        t0 = time.time()
        _, mrr_m, hits_m, llm_m = await run_multi_query(db, kb_id)
        t_m = time.time() - t0
        print(f"{'Multi-Query (3x)':20s} {f'{hits_m}/25 ({hits_m/25*100:.0f}%)':>10s} {mrr_m:>8.4f} {str(llm_m):>12s} {'75':>12s} {t_m:>8.1f}s")

        # HyDE 已移除（睿阁不启用）

    print()
    print("=" * 75)
    print("  COST ESTIMATION (per 1000 queries)")
    print("=" * 75)
    print(f"  {'Method':20s} {'LLM input':>12s} {'LLM output':>12s} {'Emb':>10s} {'Total est.':>12s}")
    print(f"  {'-'*20} {'-'*12} {'-'*12} {'-'*10} {'-'*12}")
    # Rough cost: LLM input ~0.1元/1K tokens, output ~0.3元/1K tokens, embedding ~0.001元/call
    # Per 1000 queries
    c_b = 0 + 0 + 25 * 1000 * 0.001  # 25 emb per query * 1000 queries
    c_m = (500 * 0.1 + 200 * 0.3) * 1000 / 1000 + 75 * 1000 * 0.001  # 500 input + 200 output tokens per LLM call
    print(f"  {'Baseline':20s} {'0':>12s} {'0':>12s} {'25k':>10s} {'~25':>11s}元")
    print(f"  {'Multi-Query':20s} {'500k':>12s} {'200k':>12s} {'75k':>10s} {'~210':>11s}元")
    print()
    print(f"  Notes:")
    print(f"  - LLM: DeepSeek ~0.5元/1M input, ~2元/1M output")
    print(f"  - Embedding: 通义 ~0.003元/次")
    print(f"  - 实际成本因模型和 token 量而异")
    print(f"  - Multi-query 成本约为 Baseline 的 8 倍")


if __name__ == "__main__":
    asyncio.run(main())
