"""入库6份文档（新切片策略）并跑 Enterprise QA。复用已有 KB。"""
import asyncio, json, os, uuid
from pathlib import Path
os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"
FIXTURES = Path("/app/tests/fixtures")

async def ingest():
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.core.database import SessionLocal
    from app.core.config import settings
    from app.models.document import Document
    from app.models.enums import DocumentStatus
    from app.services.ingestion.pipeline import process_document_ingestion

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        email = f"ent2-{uuid.uuid4().hex[:8]}@e.com"
        await c.post("/api/v1/auth/register", json={
            "email": email, "username": f"ent2{uuid.uuid4().hex[:8]}",
            "password": "JudgePass123!", "account_type": "personal",
        })
        resp = await c.post("/api/v1/auth/login", json={"identifier": email, "password": "JudgePass123!"})
        j = resp.json()
        uid = uuid.UUID(j["user"]["id"])
        headers = {"Authorization": f"Bearer {j['access_token']}"}
        r = await c.post("/api/v1/knowledge-bases?workspace=personal", headers=headers, json={"name": "EntQA-v2"})
        kb_id = uuid.UUID(r.json()["id"])

    up = Path(settings.upload_dir)
    for f in sorted(FIXTURES.glob("acme_*.md")):
        did = uuid.uuid4()
        sd = up / str(kb_id) / str(did); sd.mkdir(parents=True, exist_ok=True)
        sp = sd / f.name; sp.write_bytes(f.read_bytes())
        async with SessionLocal() as db:
            doc = Document(id=did, kb_id=kb_id, filename=f.name,
                file_type="md", file_size=sp.stat().st_size,
                storage_path=str(sp), status=DocumentStatus.queued, uploaded_by=uid)
            db.add(doc); await db.commit()
            await process_document_ingestion(did)
        print(f"  {f.name} ✓")
    print(f"KB_ID={kb_id}")
    Path("/tmp/ent2_kb.txt").write_text(str(kb_id))

async def query():
    import asyncio
    from app.core.database import SessionLocal
    from app.services.rag.retrieval import retrieve_chunks
    from app.models.document_chunk import DocumentChunk
    from app.models.document import Document
    from sqlalchemy import select
    
    kb_id = uuid.UUID(Path("/tmp/ent2_kb.txt").read_text().strip())
    data = json.loads((FIXTURES / "enterprise_qa.json").read_text(encoding="utf-8"))
    cases = data["cases"]
    HIT_K = 3

    # Check chunk distribution first
    async with SessionLocal() as db:
        r = await db.execute(select(Document).where(Document.kb_id == kb_id))
        docs = r.scalars().all()
        print(f"\nChunk stats:")
        for d in docs:
            r2 = await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == d.id))
            chunks = r2.scalars().all()
            sizes = [len(c.content or "") for c in chunks]
            small = sum(1 for s in sizes if s < 200)
            avg = sum(sizes)/max(1,len(sizes))
            print(f"  {d.filename}: {len(chunks)} chunks, avg={avg:.0f}, small(<200)={small}")

    # Query
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
            results.append(hit)
            if (i+1) % 25 == 0: print(f"  [{i+1}/{len(cases)}]")

    n = len(results); hits = sum(results); hit3 = hits/max(1,n)
    print(f"\n{'='*60}")
    print(f"Enterprise QA v2 ({n} 题, Hit@{HIT_K})")
    print(f"{'='*60}")
    for level in ["L1","L2","L3","L4"]:
        s = by_level.get(level, {"total":0,"hit":0})
        r = s["hit"]/max(1,s["total"])
        print(f"  {level}: {s['hit']}/{s['total']} = {r:.0%}")
    print(f"  总体: {hits}/{n} = {hit3:.0%}")
    print(f"{'='*60}")

if __name__ == "__main__":
    import sys
    if "ingest" in sys.argv:
        asyncio.run(ingest())
    elif "query" in sys.argv:
        asyncio.run(query())
