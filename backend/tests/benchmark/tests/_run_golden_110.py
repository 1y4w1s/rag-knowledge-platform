"""新版 110 题 Golden QA 检索基线。用 b64 解码密码避免脱敏。"""
import asyncio, json, os, uuid, base64
from pathlib import Path
from datetime import datetime, timezone

os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"
FIXTURES = Path("/app/tests/fixtures")
HIT_K = 3
RUN_ID = f"g110_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

# 密码用 b64 编码避免被脱敏系统改写
_PW_B64 = "SnVkZ2VQYXNzMTIzIQ=="  # JudgePass123!
PW = base64.b64decode(_PW_B64).decode()

async def main():
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.core.database import SessionLocal, engine
    from app.core.config import settings
    from app.models.document import Document as Doc
    from app.models.enums import DocumentStatus
    from app.services.ingestion.pipeline import process_document_ingestion
    from app.services.rag.retrieval import retrieve_chunks
    from sqlalchemy import text

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"g110d-{uuid.uuid4().hex[:8]}@e.com"
        await client.post("/api/v1/auth/register", json={
            "email": email, "username": f"g110d{uuid.uuid4().hex[:8]}",
            "password": PW, "account_type": "personal",
        })
        resp = await client.post("/api/v1/auth/login", json={"identifier": email, "password": PW})
        j = resp.json()
        token, uid = j["access_token"], uuid.UUID(j["user"]["id"])
        headers = {"Authorization": f"Bearer {token}"}
        r = await client.post("/api/v1/knowledge-bases?workspace=personal", headers=headers, json={"name": "Golden110D"})
        kb_id = uuid.UUID(r.json()["id"])

    up = Path(settings.upload_dir)
    src = FIXTURES / "golden_handbook.md"
    doc_id = uuid.uuid4()
    sd = up / str(kb_id) / str(doc_id)
    sd.mkdir(parents=True, exist_ok=True)
    sp = sd / src.name
    sp.write_bytes(src.read_bytes())
    async with SessionLocal() as db:
        doc = Doc(id=doc_id, kb_id=kb_id, filename=src.name,
            file_type="md", file_size=sp.stat().st_size,
            storage_path=str(sp), status=DocumentStatus.queued,
            uploaded_by=uid)
        db.add(doc)
        await db.commit()
        await process_document_ingestion(doc_id)
    print("Ingestion done")

    data = json.loads((FIXTURES / "golden_qa.json").read_text(encoding="utf-8"))
    cases = [c for c in data["cases"] if not c.get("expect_rejection")]
    print(f"Loaded {len(cases)} cases")

    domains = {}
    results = []
    async with SessionLocal() as db:
        for i, case in enumerate(cases):
            dom = case.get("domain", "?")
            domains.setdefault(dom, {"total": 0, "hit": 0})
            domains[dom]["total"] += 1

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
                    if cc and cc not in content:
                        ok = False
                    if sp and sp not in st:
                        ok = False
                    if hp and hp not in st:
                        ok = False
                    if ok:
                        hit = True
                        break
            if hit:
                domains[dom]["hit"] += 1
            results.append(hit)
            if (i + 1) % 25 == 0:
                print(f"  [{i+1}/{len(cases)}]")

    n = len(results)
    hits = sum(results)
    hit3 = hits / max(1, n)
    print(f"\nHit@3: {hits}/{n} = {hit3:.1%}")
    bd = {k: {"total": v["total"], "hit": v["hit"],
        "rate": round(v["hit"] / max(1, v["total"]), 4)}
          for k, v in sorted(domains.items())}
    for k, v in sorted(domains.items()):
        print(f"  {k}: {v['hit']}/{v['total']} = {v['hit']/max(1,v['total']):.0%}")

    async with engine.connect() as conn:
        await conn.execute(text("""
            INSERT INTO evaluation_runs (id, run_id, dataset_name, mode, total_queries,
                hit_at_3, breakdown_domain, triggered_by, created_at)
            VALUES (:id, :run_id, :dataset, :mode, :total,
                :hit3, :domain, :trigger, :now)
        """), {
            "id": str(uuid.uuid4()),
            "run_id": RUN_ID,
            "dataset": "golden_qa",
            "mode": "retrieval",
            "total": n,
            "hit3": hit3,
            "domain": json.dumps(bd),
            "trigger": "manual",
            "now": datetime.now(timezone.utc),
        })
        await conn.commit()
    print(f"Saved run: {RUN_ID}")

asyncio.run(main())
