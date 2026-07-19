"""Golden QA 全量检索评测（在 Docker 内直接调用 retrieve_chunks）"""
import asyncio
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path

os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("golden_qa")

QA_PATH = Path("/app/tests/fixtures/golden_qa.json")
KB_ID = None  # 运行时创建


def _query_content_overlap(query: str, chunk) -> bool:
    """检查 query 关键词是否出现在 chunk 的内容/标题字段中（用于拒答题评估）。"""
    import re as _re
    cjk = _re.findall(r"[\u4e00-\u9fff]{2,}", query)
    latin = _re.findall(r"[A-Za-z0-9_]{4,}", query)
    terms = cjk + latin
    if not terms:
        return False
    haystack = " ".join(
        str(v) for v in (chunk.content, chunk.heading_path, chunk.section_title) if v
    ).lower()
    return any(t.lower() in haystack for t in terms)


async def main():
    t_start = time.perf_counter()
    data = json.loads(QA_PATH.read_text(encoding="utf-8"))
    cases = data["cases"]
    hit_k = data.get("hit_k", 3)
    logger.info(f"加载 {len(cases)} 题, Hit@{hit_k}")

    from app.core.database import SessionLocal
    from app.services.rag.retrieval import retrieve_chunks
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 创建用户 + KB
        email = f"gqa-{uuid.uuid4().hex[:8]}@example.com"
        await client.post("/api/v1/auth/register", json={
            "email": email, "username": f"gqa{uuid.uuid4().hex[:8]}",
            "password": "Test123!@", "account_type": "personal",
        })
        r = await client.post("/api/v1/auth/login", json={"identifier": email, "password": "Test123!@"})
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

        r = await client.post("/api/v1/knowledge-bases?workspace=personal", headers=headers, json={"name": "GoldenQA-Full"})
        kb_id = uuid.UUID(r.json()["id"])
        logger.info(f"KB: {kb_id}")

        with open("/app/tests/fixtures/golden_handbook.md", "rb") as f:
            await client.post(f"/api/v1/knowledge-bases/{kb_id}/documents?workspace=personal", headers=headers, files={"files": ("hb.md", f, "text/markdown")})

        for _ in range(30):
            r = await client.get(f"/api/v1/knowledge-bases/{kb_id}/documents?workspace=personal&per_page=1", headers=headers)
            items = r.json().get("items", [])
            if items and items[0].get("status") == "completed":
                logger.info(f"Ingestion 完成")
                break
            await asyncio.sleep(2)

    # 用 retrieve_chunks 直接检索
    async with SessionLocal() as db:
        results = []
        by_tag = {}
        rejection = {"correct": 0, "total": 0}

        for i, case in enumerate(cases):
            expect = case.get("expect", {})
            tags = case.get("tags", [])
            is_rej = case.get("expect_rejection", False)

            t0 = time.perf_counter()
            chunks = await retrieve_chunks(db, kb_id=kb_id, query=case["query"], top_k=hit_k)
            elapsed_ms = (time.perf_counter() - t0) * 1000

            match_pos = []
            for pos, chunk in enumerate(chunks[:hit_k]):
                content = (chunk.content or "").lower()
                st = (chunk.heading_path or chunk.section_title or "").lower()
                cc = expect.get("content_contains", "").lower()
                sp = expect.get("section_title", "").lower()
                hp = expect.get("heading_path_contains", "").lower()
                ok = True
                if cc and cc not in content: ok = False
                if sp and sp not in st: ok = False
                if hp and hp not in st: ok = False
                if ok: match_pos.append(pos); break

            hit = len(match_pos) > 0 and not is_rej
            mrr = 1.0 / (match_pos[0] + 1) if match_pos else 0.0

            if is_rej:
                rejection["total"] += 1
                if not expect:
                    # 无 expect 字段的拒答题：检查 query 关键词是否出现在 chunks 中
                    has_overlap = any(_query_content_overlap(case["query"], c) for c in chunks[:hit_k])
                    if not has_overlap:
                        rejection["correct"] += 1
                elif not match_pos:
                    rejection["correct"] += 1

            results.append({"case_id": case["case_id"], "hit": hit, "mrr": mrr, "is_rej": is_rej, "tags": tags, "ms": round(elapsed_ms)})
            for tag in tags: by_tag.setdefault(tag, []).append(hit)

            if (i + 1) % 50 == 0:
                h = sum(1 for r2 in results if r2["hit"])
                logger.info(f"  [{i+1:3d}] Hit@{hit_k}={h}/{i+1}={h/(i+1)*100:.1f}% MRR={sum(r2['mrr'] for r2 in results)/len(results):.4f}")

        # 汇总
        n = len(results)
        total_hits = sum(1 for r2 in results if r2["hit"])
        avg_mrr = sum(r2["mrr"] for r2 in results) / n
        rej_acc = rejection["correct"] / max(1, rejection["total"])
        latencies = sorted([r2["ms"] for r2 in results])

        print(f"\n{'='*60}")
        print(f"Golden QA 检索评测 ({n} 题)")
        print(f"{'='*60}")
        print(f"  Hit@{hit_k}: {total_hits}/{n} = {total_hits/n*100:.1f}%")
        print(f"  MRR:        {avg_mrr:.4f}")
        print(f"  拒答正确率: {rejection['correct']}/{rejection['total']} = {rej_acc:.0%}")
        print(f"  延迟:       P50={latencies[n//2]:.0f}ms P95={latencies[int(n*0.95)]:.0f}ms")

        print(f"\n按章节拆解:")
        for tag, h in sorted(by_tag.items()):
            print(f"  {tag:20s} {sum(h):3d}/{len(h):3d} = {sum(h)/len(h):.0%}")

        # 保存
        summary = {
            "dataset": "golden_qa", "total": n, "hit_k": hit_k,
            "hit_at_k": total_hits / n, "mrr": round(avg_mrr, 4),
            "rejection_correct": rejection["correct"],
            "rejection_total": rejection["total"],
            "rejection_accuracy": round(rej_acc, 4),
            "latency_ms": {
                "p50": round(latencies[n // 2], 0),
                "p95": round(latencies[int(n * 0.95)], 0) if n > 1 else 0,
            },
            "by_tag": {tag: {"total": len(h), "hit": sum(h), "rate": round(sum(h)/len(h), 4)}
                       for tag, h in sorted(by_tag.items())},
            "total_time_seconds": round(time.perf_counter() - t_start),
        }
        out = Path("/app/benchmark_results/golden_qa_full.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"\n--- RAW DATA ---")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"\n结果已保存: {out}")


asyncio.run(main())
