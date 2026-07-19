"""BGE 纯向量检索对比（内存余弦相似度，绕过 pgvector 维度限制）。
"""
import argparse
import asyncio
import json
import math
import os
import time
from pathlib import Path

os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"

QA_PATH = Path("/app/tests/fixtures/golden_qa.json")


def _hit_at_k(chunk_scores, case, k=3):
    """与 golden_qa_loader.hit_at_k 一致的命中判定。"""
    from tests.golden_qa_loader import chunk_matches
    top = chunk_scores[:k]
    match_count = sum(1 for c in top if chunk_matches(case, c))
    if case.expect_rejection:
        return match_count == 0
    return match_count >= case.min_match


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="bge", choices=["bge", "tongyi"])
    parser.add_argument("--model", default="bge-small-zh-v1.5", help="用于输出文件名标识")
    args = parser.parse_args()

    MODEL_DIR = f"/app/models/{args.model}"

    from app.core.config import settings
    settings.embedding_provider = args.provider
    settings.bge_model_path = MODEL_DIR

    from app.services.ingestion.embedder import embed_texts

    # 加载 golden QA 数据
    data = json.loads(QA_PATH.read_text(encoding="utf-8"))
    cases = data["cases"]
    hit_k = data.get("hit_k", 3)

    # 先用通义入库（不要提前改 embedding_dim，表结构是 VECTOR(1536)）
    settings.embedding_provider = "tongyi"

    # 构建 chunk 库：上传黄金文档 → 获取所有 chunk 原文
    from app.core.database import SessionLocal
    from app.models.document_chunk import DocumentChunk
    from app.models.document import Document
    from sqlalchemy import select
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.models.enums import DocumentStatus
    import uuid

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"eval-{uuid.uuid4().hex[:8]}@example.com"
        await client.post("/api/v1/auth/register", json={
            "email": email, "username": f"eval{uuid.uuid4().hex[:8]}",
            "password": "TestPass123!", "account_type": "personal",
        })
        r = await client.post("/api/v1/auth/login", json={"identifier": email, "password": "TestPass123!"})
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

        r = await client.post("/api/v1/knowledge-bases?workspace=personal", headers=headers, json={"name": "Eval-KB"})
        kb_id = uuid.UUID(r.json()["id"])

        with open("/app/tests/fixtures/golden_handbook.md", "rb") as f:
            await client.post(f"/api/v1/knowledge-bases/{kb_id}/documents?workspace=personal", headers=headers, files={"files": ("hb.md", f, "text/markdown")})

        for _ in range(30):
            r = await client.get(f"/api/v1/knowledge-bases/{kb_id}/documents?workspace=personal&per_page=1", headers=headers)
            items = r.json().get("items", [])
            if items and items[0].get("status") == "completed":
                break
            await asyncio.sleep(2)

    # 获取所有 chunk 原文
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(DocumentChunk).join(Document, DocumentChunk.document_id == Document.id)
            .where(Document.kb_id == kb_id)
            .where(DocumentChunk.chunk_kind != "parent")
        )).scalars().all()
        chunk_texts = [r.content for r in rows]

    if not chunk_texts:
        print("❌ 没有找到 chunks")
        return

    print(f"  Chunks: {len(chunk_texts)} 条")
    print(f"  Cases:  {len(cases)} 题")

    # 从 golden_qa.json 解析 GoldenQACase
    from tests.golden_qa_loader import load_golden_qa_cases, GoldenQACase
    gqa_cases, _ = load_golden_qa_cases(QA_PATH)

    # 切回 BGE 做推理对比
    settings.embedding_provider = args.provider
    if args.provider == "bge":
        settings.embedding_dim = 1024 if "large" in args.model else 512

    # 用当前 provider 批量生成所有 chunk 的向量
    t0 = time.perf_counter()
    print(f"  正在生成 {len(chunk_texts)} 条 chunk 向量...")
    chunk_vecs = await embed_texts(chunk_texts)
    embed_ms = (time.perf_counter() - t0) * 1000
    print(f"  chunk 向量生成完成: {len(chunk_vecs)}条, 维度={len(chunk_vecs[0])}, 耗时={embed_ms:.0f}ms")

    # 逐题评测（使用 golden_qa_loader.chunk_matches）
    from tests.golden_qa_loader import chunk_matches

    results = []
    latencies = []
    by_tag = {}
    rejection = {"correct": 0, "total": 0}

    for i, case in enumerate(gqa_cases):
        t0 = time.perf_counter()
        q_vec = (await embed_texts([case.query]))[0]
        q_norm = math.sqrt(sum(v*v for v in q_vec))
        scored: list[tuple[float, object]] = []
        for c_vec, c_row in zip(chunk_vecs, rows):
            dot = sum(qv*cv for qv, cv in zip(q_vec, c_vec))
            c_norm = math.sqrt(sum(v*v for v in c_vec))
            sim = dot / (q_norm * c_norm) if q_norm * c_norm > 0 else 0
            scored.append((sim, c_row))
        scored.sort(key=lambda x: -x[0])
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)

        match_count = sum(1 for _, c in scored[:hit_k] if chunk_matches(case, c))
        hit = match_count == 0 if case.expect_rejection else match_count >= case.min_match

        if case.expect_rejection:
            rejection["total"] += 1
            if match_count == 0:
                rejection["correct"] += 1

        results.append({"case_id": case.case_id, "hit": hit, "mrr": 1.0 if hit else 0.0, "ms": round(elapsed_ms)})
        for tag in case.tags:
            by_tag.setdefault(tag, []).append(hit)

    # 汇总
    n = len(results)
    total_hits = sum(1 for r2 in results if r2["hit"])
    avg_mrr = sum(r2["mrr"] for r2 in results) / n
    rej_acc = rejection["correct"] / max(1, rejection["total"])
    latencies.sort()
    p50 = latencies[n // 2]

    summary = {
        "provider": args.provider,
        "model": args.model,
        "dim": len(chunk_vecs[0]) if chunk_vecs else 0,
        "total": n, "hit_k": hit_k,
        "hit_at_k": round(total_hits / n, 4),
        "mrr": round(avg_mrr, 4),
        "rejection_accuracy": round(rej_acc, 4),
        "latency_ms": {"p50": round(p50, 0)},
        "by_tag": {tag: {"total": len(h), "hit": sum(h), "rate": round(sum(h)/len(h), 4)}
                   for tag, h in sorted(by_tag.items())},
    }

    out = Path(f"/app/benchmark_results/embed_compare_{args.model}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"Embedding 对比: {args.model}")
    print(f"{'='*60}")
    print(f"  向量维度:   {summary['dim']}")
    print(f"  Hit@{hit_k}: {total_hits}/{n} = {total_hits/n*100:.1f}%")
    print(f"  MRR:        {avg_mrr:.4f}")
    print(f"  拒答准确率: {rej_acc:.0%}")
    print(f"  P50 延迟:   {p50:.0f}ms")
    print(f"  结果已保存: {out}")
    print(f"\n  对比通义基线: Hit@3 = 86.49%(50题) / 93.6%(12题门禁)")


asyncio.run(main())
