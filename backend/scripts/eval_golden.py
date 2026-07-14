"""Golden QA 评估：Hit@K + MRR 专业报告。

用法：
  docker exec zhiku-api sh -c 'mkdir -p /tmp/tests/fixtures
    && docker cp D:\\MyPrograms\\rag-knowledge-platform\\backend\\scripts\\eval_golden.py zhiku-api:/tmp/eval_golden.py
    && docker cp D:\\MyPrograms\\rag-knowledge-platform\\backend\\tests\\golden_qa_loader.py zhiku-api:/tmp/tests/golden_qa_loader.py
    && docker cp D:\\MyPrograms\\rag-knowledge-platform\\backend\\tests\\fixtures\\golden_*.md zhiku-api:/tmp/tests/fixtures/
    && docker cp D:\\MyPrograms\\rag-knowledge-platform\\backend\\tests\\fixtures\\golden_qa.json zhiku-api:/tmp/tests/fixtures/
    && docker exec zhiku-api env PYTHONPATH=/app:/tmp python /tmp/eval_golden.py'

输出格式化报告，包含逐题明细和聚合指标。
"""

from __future__ import annotations

import asyncio
import math
import re
import time
import uuid
from pathlib import Path

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
    if case.content_contains and case.content_contains not in (chunk.parent_content or chunk.content):
        return False
    if case.page_number is not None and chunk.page_number != case.page_number:
        return False
    return True


def hit_at_k(chunks: list[RetrievedChunk], case: GoldenQACase, k: int = HIT_K) -> tuple[bool, int | None]:
    for rank, chunk in enumerate(chunks[:k], start=1):
        if _chunk_matches(case, chunk):
            return True, rank
    return False, None


async def main():
    print("=" * 72)
    print("  Golden QA Evaluation Report")
    print("  Retrieval Quality Benchmark — Hit@K + MRR")
    print("=" * 72)
    print()

    from httpx import AsyncClient

    async with AsyncClient(base_url="http://localhost:8000") as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"identifier": "demo_admin", "password": "password123"},
        )
        if login.status_code != 200:
            print("  [ERROR] Cannot login as demo_admin. Run seed_enterprise_demo.py first.")
            return
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        print("  [setup] Creating KB...")
        kb = await client.post(
            "/api/v1/knowledge-bases?workspace=personal",
            json={"name": f"Golden QA Eval {uuid.uuid4().hex[:8]}"},
            headers=headers,
        )
        if kb.status_code != 201:
            print(f"  [ERROR] Cannot create KB: {kb.text}")
            return
        kb_id = uuid.UUID(kb.json()["id"])

        fixture = Path("/tmp/tests/fixtures/golden_handbook.md")
        if not fixture.exists():
            print(f"  [ERROR] Golden fixture not found: {fixture}")
            return

        with open(fixture, "rb") as f:
            upload = await client.post(
                f"/api/v1/knowledge-bases/{kb_id}/documents",
                files={"files": ("golden_handbook.md", f, "text/markdown")},
                headers=headers,
            )
        if upload.status_code != 201:
            print(f"  [ERROR] Upload failed: {upload.text}")
            return
        print(f"  [OK] KB={kb_id} Document={upload.json()['documents'][0]['id']}")
        print("  [wait] Ingestion...")
        await asyncio.sleep(3)

    print()
    print("  Running QA cases...")
    print()

    results: list[dict] = []
    t0 = time.time()

    async with SessionLocal() as db:
        for case in GOLDEN_QA_CASES:
            chunks = await retrieve_chunks(db, kb_id=kb_id, query=case.query, top_k=HIT_K)
            passed, hit_rank = hit_at_k(chunks, case, k=HIT_K)
            rr = 1.0 / hit_rank if hit_rank else 0.0
            results.append({
                "case_id": case.case_id,
                "query": case.query,
                "source": case.source,
                "hit": passed,
                "hit_rank": hit_rank,
                "rr": rr,
            })

    elapsed = time.time() - t0
    total = len(results)
    hits = sum(1 for r in results if r["hit"])
    mrr = sum(r["rr"] for r in results) / total

    print()
    print("-" * 72)
    print("  AGGREGATE RESULTS")
    print("-" * 72)
    print(f"  Hit@{HIT_K}:  {hits}/{total} ({hits/total*100:.1f}%)")
    print(f"  MRR:       {mrr:.4f}")
    print(f"  Duration:  {elapsed:.1f}s")
    print()

    print("-" * 72)
    print("  PER-CASE BREAKDOWN")
    print("-" * 72)
    header = f"  {'Case':8s} {'Src':4s} {'Hit':5s} {'Rank':5s} {'RR':6s}  Query"
    print(header)
    print(f"  {'-'*8} {'-'*4} {'-'*5} {'-'*5} {'-'*6}  {'-'*30}")
    for r in results:
        rank = str(r["hit_rank"]) if r["hit_rank"] else "-"
        mark = "PASS" if r["hit"] else "FAIL"
        print(f"  {r['case_id']:8s} {r['source']:4s} {mark:5s} {rank:5s} {r['rr']:.4f}  {r['query'][:40]}")
    print()

    missed = [r for r in results if not r["hit"]]
    if missed:
        print("-" * 72)
        print("  MISSED CASES")
        print("-" * 72)
        for r in missed:
            print(f"  {r['case_id']}: {r['query']}")
        print()

    print("=" * 72)
    report = f"""## Golden QA Evaluation

| Metric | Value |
|--------|-------|
| Hit@{HIT_K} | {hits}/{total} ({hits/total*100:.1f}%) |
| MRR | {mrr:.4f} |
| Cases | {total} |
| Duration | {elapsed:.1f}s |

```
{header}
{''.join(f"  {r['case_id']:8s} {r['source']:4s} {'PASS' if r['hit'] else 'FAIL':5s} {str(r['hit_rank']) if r['hit_rank'] else '-':5s} {r['rr']:.4f}  {r['query'][:40]}" for r in results)}
```"""
    print()
    print(report)
    print()
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
