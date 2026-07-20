#!/usr/bin/env python3
"""CI 中运行新评分引擎对比旧引擎输出。"""
import asyncio, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

async def main():
    from tests.benchmark.scorers.content_match import ContentMatchScorer
    from tests.benchmark.scorers.base import Expect, RetrievedChunk

    # 读取 benchmark 输出（旧引擎结果）
    # 重新跑一次检索并用新引擎评分
    from app.core.database import SessionLocal
    from app.services.rag.retrieval import retrieve_chunks
    from sqlalchemy import text

    # 找最近的 KB
    async with SessionLocal() as db:
        r = await db.execute(text(
            "SELECT id, name FROM knowledge_bases ORDER BY created_at DESC LIMIT 1"
        ))
        row = r.fetchone()
        if not row:
            print("No KB found, skipping new scorer comparison")
            return
        kb_id = row[0]

    # 读 Golden QA cases
    cases_path = os.path.join(os.path.dirname(__file__), "..", "tests",
                              "fixtures", "golden_qa", "v1.0", "cases.json")
    with open(cases_path, encoding="utf-8") as f:
        data = json.load(f)

    cases = [c for c in data["cases"] if not c.get("expect_rejection")]
    scorer = ContentMatchScorer()
    new_hits = 0

    async with SessionLocal() as db:
        for i, c in enumerate(cases):
            chunks = await retrieve_chunks(db, kb_id=kb_id, query=c["query"], top_k=3)
            if not chunks:
                continue
            rchunks = [RetrievedChunk.from_raw(ck) for ck in chunks]
            result = scorer.score_retrieval(c["query"], rchunks, Expect.from_case(c))
            if result.hit_at_3:
                new_hits += 1

    n = len(cases)
    print(f"New scorer (ContentMatch): {new_hits}/{n} = {new_hits/n*100:.1f}%")
    print(f"Note: Compare with old engine's 95.5% baseline")

if __name__ == "__main__":
    asyncio.run(main())
