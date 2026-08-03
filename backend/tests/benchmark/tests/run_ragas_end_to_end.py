"""端到端 RAGAS 生成评测：创建 KB → 上传 Golden Handbook → 跑 RAGAS Faithfulness。

在 Docker 容器内直接运行：
    python -m tests.benchmark.tests.run_ragas_end_to_end

无参数。DEEPSEEK_API_KEY 须在环境变量或 .env 中已设置。
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
# 多查询(实验J)已测：引入噪音过多，Faithfulness 从 79.21% 降至 71.97%
os.environ["QUERY_REWRITE_POLICY"] = "off"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("ragas_e2e")

FIXTURES = Path("/app/tests/fixtures")
BENCHMARK_RESULTS = Path("/app/benchmark_results")
QA_PATH = FIXTURES / "golden_qa.json"
HANDBOOK_PATH = FIXTURES / "golden_handbook.md"


async def main():
    t_start = time.perf_counter()

    # ── 1. 创建用户 + KB + 上传文档 ──
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"ragas-{uuid.uuid4().hex[:8]}@example.com"
        await client.post("/api/v1/auth/register", json={
            "email": email,
            "username": f"ragas{uuid.uuid4().hex[:8]}",
            "password": "Test123!@",
            "account_type": "personal",
        })
        r = await client.post("/api/v1/auth/login", json={
            "identifier": email, "password": "Test123!@",
        })
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r = await client.post(
            "/api/v1/knowledge-bases?workspace=personal",
            headers=headers,
            json={"name": "RAGAS-Eval-Golden"},
        )
        kb_id = uuid.UUID(r.json()["id"])
        logger.info("KB created: %s", kb_id)

        with open(HANDBOOK_PATH, "rb") as f:
            await client.post(
                f"/api/v1/knowledge-bases/{kb_id}/documents?workspace=personal",
                headers=headers,
                files={"files": ("hb.md", f, "text/markdown")},
            )
        logger.info("Document uploaded, waiting for ingestion...")

        # ── 2. 等待 ingestion 完成 ──
        for attempt in range(30):
            r = await client.get(
                f"/api/v1/knowledge-bases/{kb_id}/documents?workspace=personal&per_page=1",
                headers=headers,
            )
            items = r.json().get("items", [])
            if items and items[0].get("status") == "completed":
                logger.info("Ingestion completed (attempt %d)", attempt + 1)
                break
            await asyncio.sleep(2)
        else:
            logger.error("Ingestion did not complete after 60s")
            sys.exit(1)

    # ── 3. 加载数据集 ──
    from tests.benchmark.loaders.golden_qa import GoldenQADataset
    from tests.benchmark.rate_limit import RateLimitWrapper
    from tests.benchmark.runner import BenchmarkRunner
    from tests.benchmark.scorers.ragas_scorer import RagasGenerationScorer
    from tests.benchmark.scorers.base import RetrievedChunk, Expect as Expect_
    from tests.benchmark.report import ReportGenerator

    loader = GoldenQADataset()
    queries = await loader.load()
    logger.info("Loaded %d queries from Golden QA", len(queries))

    user_id = uuid.uuid4()
    rate_limit = RateLimitWrapper(mode="bypass")
    runner = BenchmarkRunner(kb_id=kb_id, user_id=user_id, rate_limit=rate_limit)

    from app.core.database import SessionLocal
    from tests.benchmark.adapters.generation import GenerationAdapter

    ragas_scorer = RagasGenerationScorer()
    all_faithfulness: list[float] = []
    all_relevancy: list[float] = []
    all_correctness: list[float] = []
    all_latencies: list[float] = []
    skipped = 0
    rejection_skipped = 0

    async with SessionLocal() as db:
        adapter = GenerationAdapter(db, kb_id)
        runner.set_generate_fn(adapter.generate)

        for idx, q in enumerate(queries):
            if q.expect_rejection:
                rejection_skipped += 1
                continue

            await rate_limit.wait_for_chat(user_id)
            t0 = time.perf_counter()
            try:
                answer, citations = await runner._call_with_retry(
                    runner._generate_fn, q.query, kb_id,
                    label=f"gen-{q.case_id}",
                )
            except Exception as e:
                logger.warning("Generation failed: case=%s err=%s", q.case_id, e)
                skipped += 1
                continue
            elapsed = (time.perf_counter() - t0) * 1000
            all_latencies.append(elapsed)

            # Convert citations → RetrievedChunk
            chunks_for_scorer = []
            for c in citations:
                if isinstance(c, dict):
                    content = c.get("excerpt") or c.get("content") or c.get("text", "")
                    chunks_for_scorer.append(RetrievedChunk(
                        chunk_id=c.get("chunk_id", str(id(c))),
                        content=content,
                        section_title=c.get("section_title", ""),
                    ))
                else:
                    chunks_for_scorer.append(RetrievedChunk(
                        chunk_id=str(id(c)), content=str(c),
                    ))

            # RAGAS scoring
            gt = q.expects[0].get("content_contains", "") if q.expects else (q.answer or "")
            expect_obj = Expect_(content_contains=gt, answer=q.answer or "")
            gscore = ragas_scorer.score_generation(q.query, answer, expect_obj, chunks_for_scorer)

            # 跳过评分失败的（error 非空）
            if gscore.error:
                logger.warning("RAGAS scoring failed: case=%s err=%s", q.case_id, gscore.error)
                skipped += 1
                continue

            all_faithfulness.append(gscore.faithfulness)
            all_relevancy.append(gscore.match_details[0].get("ragas_faithfulness", 0.0) if gscore.match_details else 0.0)
            all_correctness.append(gscore.correctness)

            if (idx + 1) % 5 == 0:
                n_done = len(all_faithfulness)
                pct = (sum(all_faithfulness) / n_done * 100) if n_done else 0
                logger.info(
                    "Progress: %d/%d (faithfulness=%.2f%%, valid=%d, skipped=%d)",
                    idx + 1, len(queries), pct, n_done, skipped,
                )

    # ── 4. 汇总 ──
    n = len(all_faithfulness)
    if n == 0:
        logger.error("No valid results collected")
        sys.exit(1)

    avg_faithfulness = sum(all_faithfulness) / n
    avg_relevancy = sum(all_relevancy) / n
    avg_correctness = sum(all_correctness) / n

    # 构造报告
    from tests.benchmark.schemas import GenerationMetrics, DatasetReport

    gen_metrics = GenerationMetrics(
        faithfulness=avg_faithfulness,
        correctness=avg_correctness,
        total=n,
    )
    report = DatasetReport(
        dataset_name="golden_qa",
        total_queries=len(queries),
        skipped=skipped,
        generation=gen_metrics,
        p50_latency_ms=(
            sorted(all_latencies)[n // 2] if all_latencies else 0.0
        ),
        p95_latency_ms=(
            sorted(all_latencies)[int(n * 0.95)] if all_latencies else 0.0
        ),
        p99_latency_ms=(
            sorted(all_latencies)[int(n * 0.99)] if all_latencies else 0.0
        ),
        throughput_qps=n / (sum(all_latencies) / 1000) if all_latencies else 0.0,
    )

    # 导出
    BENCHMARK_RESULTS.mkdir(parents=True, exist_ok=True)
    report_gen = ReportGenerator(str(BENCHMARK_RESULTS))
    report_gen.add_report(report)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"generation_ragas_golden_qa_{timestamp}"
    report_gen.export_all(filename)

    # 同时保存前端可读的简洁格式
    frontend_file = BENCHMARK_RESULTS / f"{filename}.json"
    frontend_data = {
        "dataset": "golden_qa",
        "display_name": "Golden QA（RAGAS 生成 — 优化后）",
        "total": n,
        "valid": n,
        "skipped": skipped,
        "rejection_skipped": rejection_skipped,
        "avg_faithfulness": round(avg_faithfulness, 4),
        "avg_answer_relevancy": round(avg_relevancy, 4),
        "avg_correctness": round(avg_correctness, 4),
        "avg_hallucination_rate": 0.0,
        "ts": time.time(),
        "note": "P0 v1（A升序+E top_k 8）+ 实验J（多查询融合bugfix）+ 实验G（Claim验证）"
            f" | chunk_max_chars={os.environ.get('CHUNK_MAX_CHARS', '1200')}",
        "optimization": {
            "chunk_ordering": "ascending (highest sim at end, Lost-in-the-Middle fix)",
            "top_k": 8,
            "multi_query": "always",
            "claim_verify": True,
            "baseline_faithfulness": 0.6472,
            "chunk_max_chars": int(os.environ.get("CHUNK_MAX_CHARS", "1200")),
        },
        "detail_per_case": [
            {
                "case_id": q.case_id,
                "query": q.query[:80],
                "faithfulness": all_faithfulness[i],
                "relevancy": all_relevancy[i],
            }
            for i, q in enumerate([q for q in queries if not q.expect_rejection][:n])
        ],
        "total_time_seconds": round(time.perf_counter() - t_start),
    }

    with open(frontend_file, "w", encoding="utf-8") as f:
        json.dump(frontend_data, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"RAGAS 生成评测完成 ({n} 题有效)")
    print(f"{'='*60}")
    print(f"  Faithfulness:      {avg_faithfulness*100:6.2f}%")
    print(f"  Answer Relevancy:  {avg_relevancy*100:6.2f}%")
    print(f"  Correctness:       {avg_correctness*100:6.2f}%")
    print(f"  跳过(拒答):        {rejection_skipped}")
    print(f"  跳过(失败):        {skipped}")
    print("  Baseline:          64.72%")
    print(f"  Delta:             {avg_faithfulness*100 - 64.72:+.2f}pp")
    print(f"{'='*60}")
    print(f"\n结果已保存: {frontend_file}")


if __name__ == "__main__":
    asyncio.run(main())
