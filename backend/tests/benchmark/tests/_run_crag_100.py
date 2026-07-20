"""CRAG 100 题外部检索基线（已弃用，请用 scripts/run_crag.py --sample 100）。
从 CRAG 数据提取 100 条 query + page_snippet 作为文档，入库后跑 Hit@3。
"""
import asyncio, bz2, json, os, uuid
from pathlib import Path

os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"
CRAG_PATH = Path("/app/data/benchmark/crag/crag_task_1_and_2_dev_v4.jsonl.bz2")
SAMPLE_N = 100

async def main():
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.core.database import SessionLocal
    from app.core.config import settings
    from app.models.document import Document as Doc
    from app.models.enums import DocumentStatus
    from app.services.ingestion.pipeline import process_document_ingestion
    from app.services.rag.retrieval import retrieve_chunks
    import base64; PW = base64.b64decode("SnVkZ2VQYXNzMTIzIQ==").decode()

    # 1. 从 CRAG 读取 100 条
    print("Loading 100 CRAG samples...")
    samples = []
    with bz2.open(CRAG_PATH, "rt", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= SAMPLE_N:
                break
            raw = json.loads(line)
            snippets = []
            for sr in raw.get("search_results", [])[:3]:
                snip = sr.get("page_snippet", "")[:600]
                if snip:
                    snippets.append(f"[{sr.get('page_name','Source')}]\n{snip}")
            doc_content = "\n\n---\n\n".join(snippets) if snippets else raw.get("query", "")
            samples.append({
                "query": raw["query"],
                "answer": raw.get("answer", ""),
                "doc_content": doc_content,
            })
    print(f"Loaded {len(samples)} samples")

    # 2. 建 KB + 逐条入库（每 query 对应一个 doc）
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        email = f"crag100-{uuid.uuid4().hex[:8]}@e.com"
        await c.post("/api/v1/auth/register", json={"email": email, "username": f"crag100{uuid.uuid4().hex[:8]}", "password": PW, "account_type": "personal"})
        resp = await c.post("/api/v1/auth/login", json={"identifier": email, "password": PW})
        j = resp.json(); uid = uuid.UUID(j["user"]["id"])
        headers = {"Authorization": f"Bearer {j['access_token']}"}
        r = await c.post("/api/v1/knowledge-bases?workspace=personal", headers=headers, json={"name": "CRAG100"})
        kb_id = uuid.UUID(r.json()["id"])

    up = Path(settings.upload_dir)
    qa_cases = []
    for i, s in enumerate(samples):
        content = s["doc_content"].encode()
        if len(content) < 20:
            continue
        did = uuid.uuid4(); sd = up / str(kb_id) / str(did); sd.mkdir(parents=True, exist_ok=True)
        sp = sd / f"crag_{i}.md"; sp.write_bytes(content)
        async with SessionLocal() as db:
            doc = Doc(id=did, kb_id=kb_id, filename=f"crag_{i}.md", file_type="md", file_size=len(content), storage_path=str(sp), status=DocumentStatus.queued, uploaded_by=uid)
            db.add(doc); await db.commit()
            await process_document_ingestion(did)
        # 每 20 条打印
        if (i+1) % 20 == 0:
            print(f"  Ingested {i+1}/{len(samples)}")
        qa_cases.append(s)
    print(f"Ingestion done: {len(qa_cases)} docs")

    # 3. 检索
    hits = 0
    async with SessionLocal() as db:
        for i, s in enumerate(qa_cases):
            chunks = await retrieve_chunks(db, kb_id=kb_id, query=s["query"], top_k=3)
            hit = False
            if chunks:
                answer_key = s.get("answer", "").lower().strip()[:40]
                if answer_key:
                    for ck in chunks[:3]:
                        if answer_key in (ck.content or "").lower():
                            hit = True; break
            if hit: hits += 1
            if (i+1) % 20 == 0:
                print(f"  [{i+1}/{len(qa_cases)}] {hits}/{i+1}={hits/max(1,i+1):.0%}")

    n = len(qa_cases)
    print(f"\n{'='*60}")
    print(f"CRAG 英文检索 ({n} 条)")
    print(f"{'='*60}")
    print(f"  Hit@3: {hits}/{n} = {hits/max(1,n):.0%}")

asyncio.run(main())
