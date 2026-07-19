"""分两步跑 Enterprise QA：先单独入库文档，再跑检索评测。"""
import asyncio, json, os, uuid
from pathlib import Path

os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"
FIXTURES = Path("/app/tests/fixtures")

async def ingest_all():
    """第1步：创建 KB 并入库所有文档。输出 kb_id。"""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.core.database import SessionLocal
    from app.core.config import settings
    from app.models.document import Document
    from app.models.enums import DocumentStatus
    from app.services.ingestion.pipeline import process_document_ingestion

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"ent-{uuid.uuid4().hex[:8]}@example.com"
        await client.post("/api/v1/auth/register", json={
            "email": email, "username": f"ent{uuid.uuid4().hex[:8]}",
            "password": "JudgePass123!", "account_type": "personal",
        })
        r = await client.post("/api/v1/auth/login", json={"identifier": email, "password": "JudgePass123!"})
        token = r.json()
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        user_id = uuid.UUID(token["user"]["id"])
        r = await client.post("/api/v1/knowledge-bases?workspace=personal", headers=headers, json={"name": "Enterprise-QA"})
        kb_id = uuid.UUID(r.json()["id"])

    up = Path(settings.upload_dir)
    doc_files = sorted(FIXTURES.glob("acme_*.md"))
    print(f"入库 {len(doc_files)} 份文档到 kb_id={kb_id}...")
    async with SessionLocal() as db:
        for f in doc_files:
            doc_id = uuid.uuid4()
            sd = up / str(kb_id) / str(doc_id)
            sd.mkdir(parents=True, exist_ok=True)
            sp = sd / f.name
            sp.write_bytes(f.read_bytes())
            doc = Document(id=doc_id, kb_id=kb_id, filename=f.name,
                file_type="md", file_size=sp.stat().st_size,
                storage_path=str(sp), status=DocumentStatus.queued,
                uploaded_by=user_id)
            db.add(doc)
            await db.commit()
            await process_document_ingestion(doc_id)
            print(f"  {f.name} ✓")
    print(f"入库完成. KB_ID={kb_id}")
    # 保存 kb_id 供第二步使用
    Path("/tmp/ent_kb_id.txt").write_text(str(kb_id))

async def run_queries():
    """第2步：读取 kb_id 并运行所有查询。"""
    kb_id = uuid.UUID(Path("/tmp/ent_kb_id.txt").read_text().strip())
    from app.core.database import SessionLocal
    from app.services.rag.retrieval import retrieve_chunks

    HIT_K = 3
    THRESHOLDS = {"L1": 0.90, "L2": 0.80, "L3": 0.65, "L4": 0.50}

    data = json.loads((FIXTURES / "enterprise_qa.json").read_text(encoding="utf-8"))
    cases = data["cases"]
    print(f"加载 {len(cases)} 题，KB_ID={kb_id}\n")

    by_level = {}
    results = []
    async with SessionLocal() as db:
        for i, case in enumerate(cases):
            level = case.get("difficulty", "L1")
            by_level.setdefault(level, {"total": 0, "hit": 0})
            by_level[level]["total"] += 1

            expect = case.get("expect", {})
            cc = expect.get("content_contains", "").lower()
            sp = expect.get("section_title", "").lower()
            hp = expect.get("heading_path_contains", "").lower()

            chunks = await retrieve_chunks(db, kb_id=kb_id, query=case["query"], top_k=HIT_K)
            hit = False
            if chunks:
                for ck in chunks[:HIT_K]:
                    content = (ck.content or "").lower()
                    st = (ck.heading_path or ck.section_title or "").lower()
                    ok = True
                    if cc and cc not in content: ok = False
                    if sp and sp not in st: ok = False
                    if hp and hp not in st: ok = False
                    if ok: hit = True; break

            if hit: by_level[level]["hit"] += 1
            results.append({"case_id": case["case_id"], "level": level, "query": case["query"][:40], "hit": hit})
            if (i+1) % 25 == 0: print(f"  [{i+1}/{len(cases)}]")

    print(f"\n{'='*60}")
    print(f"Enterprise QA 检索评测 ({len(cases)} 题, Hit@{HIT_K})")
    print(f"{'='*60}")
    all_pass = True
    for level in ["L1", "L2", "L3", "L4"]:
        s = by_level.get(level, {"total": 0, "hit": 0})
        rate = s["hit"] / max(1, s["total"])
        th = THRESHOLDS[level]
        ok = rate >= th
        tag = "PASS" if ok else "FAIL"
        print(f"  {level}: {s['hit']}/{s['total']} = {rate:.0%}  (门禁 >= {th:.0%})  {tag}")
        if not ok: all_pass = False

    total_hits = sum(1 for r in results if r["hit"])
    print(f"  总体: {total_hits}/{len(results)} = {total_hits/max(1,len(results)):.0%}")

    fails = [r for r in results if not r["hit"]]
    if fails:
        print(f"\n  失败 ({len(fails)}):")
        for r in fails: print(f"    [{r['level']}] {r['case_id']}: {r['query']}")
    print(f"\n{'='*60}\nALL {'PASS' if all_pass else 'FAIL'} {'✅' if all_pass else '❌'}")

    summary = {"dataset": "enterprise_qa", "total": len(results), "hit_k": HIT_K,
        "by_level": {l: {"total": s["total"], "hit": s["hit"],
            "rate": round(s["hit"]/max(1,s["total"]),4)} for l,s in sorted(by_level.items())},
        "overall_hit_rate": round(total_hits/max(1,len(results)),4)}
    Path("/app/benchmark_results/enterprise_qa.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

if __name__ == "__main__":
    import sys
    if "ingest" in sys.argv:
        asyncio.run(ingest_all())
    elif "query" in sys.argv:
        asyncio.run(run_queries())
    else:
        print("Usage: python ... ingest | query")
