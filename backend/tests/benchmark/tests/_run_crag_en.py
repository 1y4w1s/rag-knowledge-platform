"""运行 CRAG 英文 5 题检索测试"""
import asyncio, json, os, uuid, base64
from pathlib import Path
os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"
PW = base64.b64decode("SnVkZ2VQYXNzMTIzIQ==").decode()

async def main():
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.core.database import SessionLocal
    from app.core.config import settings
    from app.models.document import Document as Doc
    from app.models.enums import DocumentStatus
    from app.services.ingestion.pipeline import process_document_ingestion
    from app.services.rag.retrieval import retrieve_chunks

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        email = f"en2-{uuid.uuid4().hex[:8]}@e.com"
        await c.post("/api/v1/auth/register", json={"email": email, "username": f"en2{uuid.uuid4().hex[:8]}", "password": PW, "account_type": "personal"})
        resp = await c.post("/api/v1/auth/login", json={"identifier": email, "password": PW})
        j = resp.json(); uid = uuid.UUID(j["user"]["id"])
        headers = {"Authorization": f"Bearer {j['access_token']}"}
        r = await c.post("/api/v1/knowledge-bases?workspace=personal", headers=headers, json={"name": "EnglishTest2"})
        kb_id = uuid.UUID(r.json()["id"])

    up = Path(settings.upload_dir)
    for f in sorted(Path("/app/tests/fixtures/crag_en").glob("*.md")):
        did = uuid.uuid4(); sd = up / str(kb_id) / str(did); sd.mkdir(parents=True, exist_ok=True)
        sp = sd / f.name; sp.write_bytes(f.read_bytes())
        async with SessionLocal() as db:
            doc = Doc(id=did, kb_id=kb_id, filename=f.name, file_type="md", file_size=sp.stat().st_size, storage_path=str(sp), status=DocumentStatus.queued, uploaded_by=uid)
            db.add(doc); await db.commit(); await process_document_ingestion(did)

    data = json.loads((Path("/app/tests/fixtures/crag_en_qa.json")).read_text(encoding="utf-8"))
    hits = 0
    async with SessionLocal() as db:
        for case in data["cases"]:
            cc = case["expect"]["content_contains"].lower()
            chunks = await retrieve_chunks(db, kb_id=kb_id, query=case["query"], top_k=3)
            hit = False
            if chunks:
                for ck in chunks[:3]:
                    if cc in (ck.content or "").lower():
                        hit = True; break
            if hit: hits += 1
            print(f'  {case["case_id"]}: {"HIT" if hit else "MISS"} [{case["query"][:40]}]')

    n = len(data["cases"])
    print(f"\nCRAG English ({n}): {hits}/{n} = {hits/max(1,n):.0%}")

asyncio.run(main())
