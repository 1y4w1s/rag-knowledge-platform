"""Golden QA 真实嵌入评测：用通义 embedding + DeepSeek 做全链路评估。

用法：
  1. 确保 RESEND_API_KEY / TONGYI_API_KEY / DEEPSEEK_API_KEY 在 .env 中已配置
  2. 先跑 seed 确保 demo_admin 存在
  3. 运行本脚本

输出：检索质量指标 + 生成质量评分。
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path

from app.core.database import SessionLocal
from app.services.rag.retrieval import retrieve_chunks
from app.services.rag.generation import build_messages, stream_deepseek_tokens
from tests.golden_qa_loader import GOLDEN_QA_CASES, HIT_K, GoldenQACase

CASE_COST_WARN = 25 * 2  # 25 retrievals + ~25 LLM calls
print(f"  [warn] This will consume approximately {CASE_COST_WARN} API calls.")
print()

FIXTURES = Path("/tmp/tests/fixtures")


def _chunk_matches(case: GoldenQACase, chunk) -> bool:
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


JUDGE_PROMPT = """你是一个 RAG 评测助手。请评估以下回答的质量。

【用户问题】
{query}

【检索片段】
{context}

【系统回答】
{answer}

请从以下三个维度评分（1-5分），并简要说明理由：

1. 正确性（Correctness）：回答是否准确、完整？
2. 忠实度（Faithfulness）：回答是否基于检索片段，没有编造？
3. 相关性（Relevance）：回答是否切题？

输出格式（JSON）：
{{"correctness": <1-5>, "faithfulness": <1-5>, "relevance": <1-5>, "reason": "<一句话说明>"}}"""


async def judge_answer(query: str, context: str, answer: str) -> dict | None:
    prompt = JUDGE_PROMPT.format(query=query, context=context[:1500], answer=answer[:1000])
    try:
        parts: list[str] = []
        async for token in stream_deepseek_tokens([{"role": "user", "content": prompt}]):
            parts.append(token)
        text = "".join(parts).strip()
        # Extract JSON from response
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        return None
    except Exception as e:
        print(f"    [judge error] {e}")
        return None


async def run_retrieval_only():
    """Phase 1: Retrieval quality with real embeddings."""
    print("=" * 72)
    print("  PHASE 1: RETRIEVAL QUALITY (Real Embeddings)")
    print("=" * 72)
    print()

    from httpx import AsyncClient

    async with AsyncClient(base_url="http://localhost:8000") as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"identifier": "demo_admin", "password": "password123"},
        )
        if login.status_code != 200:
            print("  [ERROR] Cannot login as demo_admin.")
            return None, [], 0
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        kb = await client.post(
            "/api/v1/knowledge-bases?workspace=personal",
            json={"name": f"Golden QA Real {uuid.uuid4().hex[:8]}"},
            headers=headers,
        )
        if kb.status_code != 201:
            print(f"  [ERROR] Cannot create KB: {kb.text}")
            return None, [], 0
        kb_id = uuid.UUID(kb.json()["id"])
        print(f"  [OK] KB created: {kb_id}")

        fixture = FIXTURES / "golden_handbook.md"
        if not fixture.exists():
            print(f"  [ERROR] Fixture not found: {fixture}")
            return None, [], 0

        with open(fixture, "rb") as f:
            upload = await client.post(
                f"/api/v1/knowledge-bases/{kb_id}/documents",
                files={"files": ("golden_handbook.md", f, "text/markdown")},
                headers=headers,
            )
        if upload.status_code != 201:
            print(f"  [ERROR] Upload failed: {upload.text}")
            return None, [], 0
        print(f"  [OK] Document uploaded. Waiting for ingestion...")
        await asyncio.sleep(3)

    print("  Running 25 retrievals with real embeddings...")
    results = []
    t0 = time.time()

    async with SessionLocal() as db:
        for i, case in enumerate(GOLDEN_QA_CASES):
            t1 = time.time()
            chunks = await retrieve_chunks(db, kb_id=kb_id, query=case.query, top_k=HIT_K)
            t2 = time.time()
            passed, hit_rank = False, None
            for rank, chunk in enumerate(chunks[:HIT_K], start=1):
                if _chunk_matches(case, chunk):
                    passed = True
                    hit_rank = rank
                    break
            rr = 1.0 / hit_rank if hit_rank else 0.0
            results.append({
                "case_id": case.case_id,
                "query": case.query,
                "source": case.source,
                "hit": passed,
                "hit_rank": hit_rank,
                "rr": rr,
                "latency_ms": int((t2 - t1) * 1000),
            })
            print(f"    [{i+1}/25] {case.case_id}: {'PASS' if passed else 'FAIL'} (rank={hit_rank}, {int((t2-t1)*1000)}ms)")

    elapsed = time.time() - t0
    total = len(results)
    hits = sum(1 for r in results if r["hit"])
    mrr = sum(r["rr"] for r in results) / total
    avg_latency = sum(r["latency_ms"] for r in results) / total

    print()
    print("-" * 72)
    print("  RETRIEVAL RESULTS (Real Embeddings)")
    print("-" * 72)
    print(f"  Hit@{HIT_K}:  {hits}/{total} ({hits/total*100:.1f}%)")
    print(f"  MRR:       {mrr:.4f}")
    print(f"  Avg latency: {avg_latency:.0f}ms")
    print(f"  Duration:  {elapsed:.1f}s")
    print()

    return kb_id, results, hits


async def run_generation_eval(kb_id, results):
    """Phase 2: Generation quality with DeepSeek + LLM-as-judge."""
    print()
    print("=" * 72)
    print("  PHASE 2: GENERATION QUALITY (DeepSeek + LLM-as-judge)")
    print("=" * 72)
    print("  [warn] This will call DeepSeek ~50 times (answer + judge per case)")
    print()

    judge_results = []
    async with SessionLocal() as db:
        for i, (case, r) in enumerate(zip(GOLDEN_QA_CASES, results)):
            chunks = await retrieve_chunks(db, kb_id=kb_id, query=case.query, top_k=3)
            context = "\n\n".join(
                c.parent_content or c.content for c in chunks[:3]
            )
            if not context:
                print(f"    [{i+1}/25] {case.case_id}: SKIP (no context)")
                judge_results.append(None)
                continue

            # Generate answer
            messages = build_messages(case.query, list(chunks)[:3])
            answer_parts = []
            async for token in stream_deepseek_tokens(messages):
                answer_parts.append(token)
            answer = "".join(answer_parts).strip()

            # Judge
            score = await judge_answer(case.query, context[:1500], answer[:1000])
            judge_results.append(score)
            status = f"c={score['correctness']}/f={score['faithfulness']}/r={score['relevance']}" if score else "judge failed"
            print(f"    [{i+1}/25] {case.case_id}: {status}")

    # Aggregate
    valid = [s for s in judge_results if s]
    if valid:
        avg_c = sum(s["correctness"] for s in valid) / len(valid)
        avg_f = sum(s["faithfulness"] for s in valid) / len(valid)
        avg_r = sum(s["relevance"] for s in valid) / len(valid)
        print()
        print("-" * 72)
        print("  GENERATION QUALITY (LLM-as-Judge)")
        print("-" * 72)
        print(f"  Correctness:  {avg_c:.2f}/5.0")
        print(f"  Faithfulness: {avg_f:.2f}/5.0")
        print(f"  Relevance:    {avg_r:.2f}/5.0")
        print(f"  Average:      {(avg_c+avg_f+avg_r)/3:.2f}/5.0")
        print(f"  Judged cases: {len(valid)}/{len(judge_results)}")
        print()

    return judge_results


async def main():
    kb_id, results, hits = await run_retrieval_only()

    if kb_id is None:
        return

    # Ask user if they want phase 2
    print()
    print("  Phase 2 (Generation Quality) requires ~50 DeepSeek API calls.")
    print("  Run it? (y/n) [will auto-run in 5s]")
    # We'll check if the user typed something, or proceed automatically
    # Since we're in Docker with no stdin, we'll prompt via output and let the user decide
    print()
    import os
    if os.environ.get("RUN_GENERATION") == "1":
        await run_generation_eval(kb_id, results)
    else:
        print("  [skip] Set RUN_GENERATION=1 to enable generation eval")
    print()

    # Phase 2 requires a separate flag since it costs API credits
    # For now, report retrieval-only results
    print()
    print("=" * 72)
    print("  SUMMARY: Real-Embedding Evaluation")
    print("=" * 72)
    missed = [r for r in results if not r["hit"]]
    print(f"  Hit@{HIT_K}:  {sum(1 for r in results if r['hit'])}/25 ({sum(1 for r in results if r['hit'])/25*100:.1f}%)")
    print(f"  MRR:       {sum(r['rr'] for r in results)/25:.4f}")
    print(f"  Avg latency: {sum(r['latency_ms'] for r in results)/25:.0f}ms")
    if missed:
        print(f"  Missed:    {', '.join(r['case_id'] for r in missed)}")
    print()
    print("  Compare with mock: Hit@3 92.0% vs real ___%")
    print()

    # Compare with mock results
    mock_hits = 23
    mock_mrr = 0.9000
    real_hits = sum(1 for r in results if r["hit"])
    real_mrr = sum(r["rr"] for r in results) / 25
    print("-" * 72)
    print("  MOCK vs REAL EMBEDDING COMPARISON")
    print("-" * 72)
    print(f"  {'Metric':20s} {'Mock':12s} {'Real':12s} {'Delta':12s}")
    print(f"  {'-'*20} {'-'*12} {'-'*12} {'-'*12}")
    print(f"  {'Hit@3':20s} {mock_hits:>5}/25 ({mock_hits/25*100:.1f}%)  {real_hits:>5}/25 ({real_hits/25*100:.1f}%)  {'+' if real_hits > mock_hits else ''}{(real_hits - mock_hits)/25*100:.1f}%")
    print(f"  {'MRR':20s} {mock_mrr:<12.4f} {real_mrr:<12.4f} {'+' if real_mrr > mock_mrr else ''}{real_mrr - mock_mrr:.4f}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
