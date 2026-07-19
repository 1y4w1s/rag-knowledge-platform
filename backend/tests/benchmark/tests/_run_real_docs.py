"""真实文档测试集基线"""
import asyncio, json, os, uuid
from pathlib import Path
import base64

os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"
F = Path("/app/tests/fixtures")
Q = F / "real_docs_qa.json"
D = F / "real_docs"
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
        email = f"rd2-{uuid.uuid4().hex[:8]}@e.com"
        await c.post("/api/v1/auth/register", json={"email": email, "username": f"rd2{uuid.uuid4().hex[:8]}", "password": PW, "account_type": "personal"})
        resp = await c.post("/api/v1/auth/login", json={"identifier": email, "password": PW})
        j = resp.json(); uid = uuid.UUID(j["user"]["id"])
        headers = {"Authorization": f"Bearer {j['access_token']}"}
        r = await c.post("/api/v1/knowledge-bases?workspace=personal", headers=headers, json={"name": "RealDocs2"})
        kb_id = uuid.UUID(r.json()["id"])

    up = Path(settings.upload_dir)
    for f in sorted(D.glob("*.md")):
        did = uuid.uuid4(); sd = up / str(kb_id) / str(did); sd.mkdir(parents=True, exist_ok=True)
        sp = sd / f.name; sp.write_bytes(f.read_bytes())
        async with SessionLocal() as db:
            doc = Doc(id=did, kb_id=kb_id, filename=f.name, file_type="md", file_size=sp.stat().st_size, storage_path=str(sp), status=DocumentStatus.queued, uploaded_by=uid)
            db.add(doc); await db.commit(); await process_document_ingestion(did)
    print("Ingestion done")

    data = json.loads(Q.read_text(encoding="utf-8"))
    cases = data["cases"]
    hits = 0
    async with SessionLocal() as db:
        for i, case in enumerate(cases):
            e = case.get("expect", {}); cc = e.get("content_contains", "").lower(); sp = e.get("section_title", "").lower(); hp = e.get("heading_path_contains", "").lower()
            ch = await retrieve_chunks(db, kb_id=kb_id, query=case["query"], top_k=3)
            hit = False
            if ch:
                for ck in ch[:3]:
                    c = (ck.content or "").lower(); s = (ck.heading_path or ck.section_title or "").lower(); ok = True
                    if cc and cc not in c: ok = False
                    if sp and sp not in s: ok = False
                    if hp and hp not in s: ok = False
                    if ok: hit = True; break
            if hit: hits += 1

    print(f"\n{'='*60}")
    print(f"Real Docs Test ({len(cases)} cases)")
    print(f"{'='*60}")
    print(f"Hit@3: {hits}/{len(cases)} = {hits/max(1,len(cases)):.0%}")

asyncio.run(main())
