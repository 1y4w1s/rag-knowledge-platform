"""RRF 权重 Grid Search：找最优 vector_weight + fts_weight 组合。

用法：
  docker cp backend/scripts/rrf_grid_search.py zhiku-api:/tmp/
  docker exec zhiku-api mkdir -p /tmp/tests/fixtures
  docker exec zhiku-api env PYTHONPATH=/app:/tmp python /tmp/rrf_grid_search.py
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
from app.services.rag.types import RetrievedChunk
from tests.golden_qa_loader import GOLDEN_QA_CASES, HIT_K, GoldenQACase

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


def _chunk_matches(case: GoldenQACase, chunk: RetrievedChunk) -> bool:
    if case.section_title and chunk.section_title != case.section_title:
        return False
    if case.heading_path_contains and (
        not chunk.heading_path or case.heading_path_contains not in chunk.heading_path
    ):
        return False
    if case.content_contains and case.content_contains.lower() not in (chunk.content or "").lower():
        return False
    if case.page_number is not None and chunk.page_number != case.page_number:
        return False
    return True


async def run_golden(kb_id: uuid.UUID, v_w: float, f_w: float) -> tuple[float, float, int]:
    settings.rrf_vector_weight = v_w
    settings.rrf_fts_weight = f_w

    results: list[float] = []
    hits = 0
    async with SessionLocal() as db:
        for case in GOLDEN_QA_CASES:
            chunks = await retrieve_chunks(db, kb_id=kb_id, query=case.query, top_k=HIT_K)
            passed = False
            for rank, chunk in enumerate(chunks[:HIT_K], start=1):
                if _chunk_matches(case, chunk):
                    passed = True
                    results.append(1.0 / rank)
                    break
            if not passed:
                results.append(0.0)
            if passed:
                hits += 1
    mrr = sum(results) / len(results)
    return mrr, hits / len(results), hits


async def main():
    # Login + create KB + upload doc + ingest
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
            json={"name": f"RRF Grid {uuid.uuid4().hex[:8]}"},
            headers=headers,
        )
        if kb.status_code != 201:
            print(f"Cannot create KB: {kb.text}")
            return
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

    # Grid search
    candidates = [(v, f) for v in [0.5, 0.75, 1.0, 1.25, 1.5] for f in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]]
    results: list[tuple[float, float, float, int]] = []

    print(f"{'v_weight':>10s} {'f_weight':>10s} {'MRR':>8s} {'Hit%':>8s} {'Hits':>6s}")
    print("-" * 45)

    for v_w, f_w in candidates:
        t0 = time.time()
        mrr, hit_rate, hits = await run_golden(kb_id, v_w, f_w)
        elapsed = time.time() - t0
        mark = " <-- BEST" if mrr >= 0.99 else ""
        print(f"{v_w:>10.2f} {f_w:>10.2f} {mrr:>8.4f} {hit_rate*100:>7.1f}% {hits:>4d}/{len(GOLDEN_QA_CASES)} {mark}")
        results.append((mrr, v_w, f_w, hits))

    print()
    results.sort(key=lambda r: (-r[0], -r[3]))
    best = results[0]
    print(f"BEST: v={best[1]:.2f} f={best[2]:.2f} MRR={best[0]:.4f} Hits={best[3]}/{len(GOLDEN_QA_CASES)}")
    print(f"Current: v={settings.rrf_vector_weight:.2f} f={settings.rrf_fts_weight:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
