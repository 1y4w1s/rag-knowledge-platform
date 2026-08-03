"""快速对比：有检索 vs 无检索（前 10 题，RAGAS 评分）。
在 Docker 容器内运行：
    python -m tests.benchmark.tests.run_ragas_ablation
"""
import asyncio
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path

os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", stream=sys.stdout)
logger = logging.getLogger("ragas_ablation")

FIXTURES = Path("/app/tests/fixtures")
BENCHMARK_RESULTS = Path("/app/benchmark_results")
QA_PATH = FIXTURES / "golden_qa.json"
HANDBOOK_PATH = FIXTURES / "golden_handbook.md"
N_SAMPLE = 10  # 10 题抽样

async def main():
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"ablation-{uuid.uuid4().hex[:8]}@example.com"
        await client.post("/api/v1/auth/register", json={"email": email, "username": f"ablation{uuid.uuid4().hex[:8]}", "password": "Test123!@", "account_type": "personal"})
        r = await client.post("/api/v1/auth/login", json={"identifier": email, "password": "Test123!@"})
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        r = await client.post("/api/v1/knowledge-bases?workspace=personal", headers=headers, json={"name": "Ablation-Golden"})
        kb_id = uuid.UUID(r.json()["id"])
        with open(HANDBOOK_PATH, "rb") as f:
            await client.post(f"/api/v1/knowledge-bases/{kb_id}/documents?workspace=personal", headers=headers, files={"files": ("hb.md", f, "text/markdown")})
        for attempt in range(30):
            r = await client.get(f"/api/v1/knowledge-bases/{kb_id}/documents?workspace=personal&per_page=1", headers=headers)
            items = r.json().get("items", [])
            if items and items[0].get("status") == "completed":
                break
            await asyncio.sleep(2)
        else:
            logger.error("Ingestion timeout")
            sys.exit(1)

    from tests.benchmark.loaders.golden_qa import GoldenQADataset
    from tests.benchmark.rate_limit import RateLimitWrapper
    from tests.benchmark.runner import BenchmarkRunner
    from tests.benchmark.scorers.ragas_scorer import RagasGenerationScorer
    from tests.benchmark.scorers.base import RetrievedChunk, Expect
    from tests.benchmark.adapters.generation import GenerationAdapter
    from app.core.database import SessionLocal
    from app.services.rag.generation import stream_deepseek_tokens

    loader = GoldenQADataset()
    queries = await loader.load()
    non_rejection = [q for q in queries if not q.expect_rejection][:N_SAMPLE]
    logger.info("抽样 %d 题", len(non_rejection))

    user_id = uuid.uuid4()
    rate_limit = RateLimitWrapper(mode="bypass")
    runner = BenchmarkRunner(kb_id=kb_id, user_id=user_id, rate_limit=rate_limit)
    ragas_scorer = RagasGenerationScorer()

    results = []
    async with SessionLocal() as db:
        adapter = GenerationAdapter(db, kb_id)
        runner.set_generate_fn(adapter.generate)

        for q in non_rejection:
            # ── 有检索 ──
            await rate_limit.wait_for_chat(user_id)
            ans_rag, citations = await runner._call_with_retry(runner._generate_fn, q.query, kb_id, label=f"rag-{q.case_id}")
            chunks_rag = []
            for c in citations:
                if isinstance(c, dict):
                    chunks_rag.append(RetrievedChunk(chunk_id=c.get("chunk_id", str(id(c))), content=c.get("excerpt") or c.get("content", ""), section_title=c.get("section_title", "")))
                else:
                    chunks_rag.append(RetrievedChunk(chunk_id=str(id(c)), content=str(c)))
            gt = q.expects[0].get("content_contains", "") if q.expects else (q.answer or "")
            score_rag = ragas_scorer.score_generation(q.query, ans_rag, Expect(content_contains=gt, answer=q.answer or ""), chunks_rag)

            # ── 无检索 ──
            await rate_limit.wait_for_chat(user_id)
            ans_raw_parts = []
            async for token in stream_deepseek_tokens([{"role": "user", "content": q.query}]):
                ans_raw_parts.append(token)
            ans_raw = "".join(ans_raw_parts)
            score_raw = ragas_scorer.score_generation(q.query, ans_raw, Expect(content_contains=gt, answer=q.answer or ""), [])

            results.append({
                "case_id": q.case_id,
                "query": q.query[:50],
                "rag_faithfulness": score_rag.faithfulness if not score_rag.error else 0.0,
                "rag_error": score_rag.error or "",
                "raw_faithfulness": score_raw.faithfulness if not score_raw.error else 0.0,
                "raw_error": score_raw.error or "",
                "rag_answer": ans_rag[:200],
                "raw_answer": ans_raw[:200],
            })
            logger.info("%s: rag=%.2f  raw=%.2f", q.case_id, results[-1]["rag_faithfulness"], results[-1]["raw_faithfulness"])

    # 输出
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = BENCHMARK_RESULTS / f"ablation_{ts}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    n = len(results)
    rag_avg = sum(r["rag_faithfulness"] for r in results) / n
    raw_avg = sum(r["raw_faithfulness"] for r in results) / n
    print(f"\n{'='*60}")
    print(f"Ablation 对比完成 ({n} 题)")
    print(f"{'='*60}")
    print(f"  有检索 Faithfulness:  {rag_avg*100:6.2f}%")
    print(f"  无检索 Faithfulness:  {raw_avg*100:6.2f}%")
    print(f"  Delta:                {rag_avg*100 - raw_avg*100:+.2f}pp")
    print(f"  对数差(log-odds):    {_log_odds(rag_avg) - _log_odds(raw_avg):+.4f}")
    print(f"{'='*60}")
    print(f"结果: {out}")

def _log_odds(p: float) -> float:
    import math
    p = max(min(p, 0.999), 0.001)
    return math.log(p / (1 - p))

if __name__ == "__main__":
    asyncio.run(main())
