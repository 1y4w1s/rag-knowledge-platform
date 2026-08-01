"""快速抽样评测：固定 30 题（10 曾受益 + 10 曾下降 + 10 随机），约 15 分钟。
在 Docker 容器内运行：
    python -m tests.benchmark.tests.run_ragas_sampled
"""
import asyncio, json, logging, os, sys, time, uuid
from pathlib import Path

os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"
logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", stream=sys.stdout)
logger = logging.getLogger("ragas_sampled")

FIXTURES = Path("/app/tests/fixtures")
SAMPLE_SIZE = 30

# 固定抽样：从评测结果中挑题（首轮用启发式，后续可固化）
# 曾受益（实验L 从 <0.7 升到 1.0）+ 曾下降（从 1.0 降到 <1.0）+ 高分稳定
_PRIORITY_BENEFIT = ["GQ-22", "GQ-46", "GQ-10", "GQ-13", "GQ-21", "GQ-29", "GQ-44", "GQ-51", "GQ-67", "GQ-99"]
_PRIORITY_DECLINE = ["GQ-31", "GQ-24", "GQ-52", "GQ-61", "GQ-65", "GQ-76", "GQ-100", "GQ-104", "GQ-3", "GQ-79"]
_RANDOM_FILL = ["GQ-1", "GQ-2", "GQ-5", "GQ-6", "GQ-8", "GQ-11", "GQ-14", "GQ-19", "GQ-30", "GQ-41"]

TARGET_IDS = _PRIORITY_BENEFIT + _PRIORITY_DECLINE + _RANDOM_FILL  # 30 题

async def main():
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"sampled-{uuid.uuid4().hex[:8]}@example.com"
        await client.post("/api/v1/auth/register", json={"email": email, "username": f"sampled{uuid.uuid4().hex[:8]}", "password": "Test123!@", "account_type": "personal"})
        r = await client.post("/api/v1/auth/login", json={"identifier": email, "password": "Test123!@"})
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        r = await client.post("/api/v1/knowledge-bases?workspace=personal", headers=headers, json={"name": "Sampled-Eval"})
        kb_id = uuid.UUID(r.json()["id"])
        with open(FIXTURES / "golden_handbook.md", "rb") as f:
            await client.post(f"/api/v1/knowledge-bases/{kb_id}/documents?workspace=personal", headers=headers, files={"files": ("hb.md", f, "text/markdown")})
        for attempt in range(30):
            r = await client.get(f"/api/v1/knowledge-bases/{kb_id}/documents?workspace=personal&per_page=1", headers=headers)
            items = r.json().get("items", [])
            if items and items[0].get("status") == "completed":
                break
            await asyncio.sleep(2)

    from tests.benchmark.loaders.golden_qa import GoldenQADataset
    from tests.benchmark.rate_limit import RateLimitWrapper
    from tests.benchmark.runner import BenchmarkRunner
    from tests.benchmark.scorers.ragas_scorer import RagasGenerationScorer
    from tests.benchmark.scorers.base import RetrievedChunk, Expect as Expect_
    from tests.benchmark.adapters.generation import GenerationAdapter
    from app.core.database import SessionLocal

    loader = GoldenQADataset()
    queries = await loader.load()
    target = [q for q in queries if q.case_id in TARGET_IDS and not q.expect_rejection]
    logger.warning("抽样 %d 题", len(target))

    user_id = uuid.uuid4()
    rate_limit = RateLimitWrapper(mode="bypass")
    runner = BenchmarkRunner(kb_id=kb_id, user_id=user_id, rate_limit=rate_limit)
    ragas_scorer = RagasGenerationScorer()

    scores = []
    async with SessionLocal() as db:
        adapter = GenerationAdapter(db, kb_id)
        runner.set_generate_fn(adapter.generate)
        for q in target:
            await rate_limit.wait_for_chat(user_id)
            try:
                answer, citations = await runner._call_with_retry(runner._generate_fn, q.query, kb_id, label=f"gen-{q.case_id}")
            except Exception as e:
                logger.warning("skip gen %s: %s", q.case_id, str(e)[:80])
                continue
            chunks_for_scorer = []
            for c in citations:
                if isinstance(c, dict):
                    chunks_for_scorer.append(RetrievedChunk(chunk_id=c.get("chunk_id", str(id(c))), content=c.get("excerpt") or c.get("content", ""), section_title=c.get("section_title", "")))
                else:
                    chunks_for_scorer.append(RetrievedChunk(chunk_id=str(id(c)), content=str(c)))
            gt = q.expects[0].get("content_contains", "") if q.expects else (q.answer or "")
            gscore = ragas_scorer.score_generation(q.query, answer, Expect_(content_contains=gt, answer=q.answer or ""), chunks_for_scorer)
            if gscore.error:
                logger.warning("skip score %s: %s", q.case_id, gscore.error)
                continue
            scores.append({"case_id": q.case_id, "faithfulness": gscore.faithfulness})
            logger.warning("%s: %.2f", q.case_id, gscore.faithfulness)

    avg = sum(s["faithfulness"] for s in scores) / len(scores) if scores else 0
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = Path("/app/benchmark_results") / f"sampled_{ts}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"sample_size": len(scores), "avg_faithfulness": avg, "note": "快速抽样集 30 题", "detail": scores}, f, ensure_ascii=False, indent=2)
    print(f"\n抽样评测完成: {len(scores)} 题, Faithfulness={avg*100:.2f}%")
    print(f"结果: {out}")

if __name__ == "__main__":
    asyncio.run(main())
