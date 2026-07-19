"""Citation Accuracy 评测：验证对话模式下的 [片段N] 引用准确性。"""
import asyncio, json, os, re, uuid
from pathlib import Path

os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"
FIXTURES = Path("/app/tests/fixtures")

async def main():
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.core.database import SessionLocal
    from app.core.config import settings
    from app.models.document import Document as Doc
    from app.models.enums import DocumentStatus
    from app.services.ingestion.pipeline import process_document_ingestion

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        email = f"cite2-{uuid.uuid4().hex[:8]}@e.com"
        await c.post("/api/v1/auth/register", json={
            "email": email, "username": f"cite2{uuid.uuid4().hex[:8]}",
            "password": "JudgePass123!", "account_type": "personal",
        })
        resp = await c.post("/api/v1/auth/login", json={"identifier": email, "password": "JudgePass123!"})
        j = resp.json()
        uid = uuid.UUID(j["user"]["id"])
        headers = {"Authorization": f"Bearer {j['access_token']}"}
        r = await c.post("/api/v1/knowledge-bases?workspace=personal", headers=headers, json={"name": "CiteEval2"})
        kb_id = uuid.UUID(r.json()["id"])

    up = Path(settings.upload_dir)
    src = FIXTURES / "golden_handbook.md"
    did = uuid.uuid4()
    sd = up / str(kb_id) / str(did)
    sd.mkdir(parents=True, exist_ok=True)
    sp = sd / src.name
    sp.write_bytes(src.read_bytes())
    async with SessionLocal() as db:
        doc = Doc(id=did, kb_id=kb_id, filename=src.name,
            file_type="md", file_size=sp.stat().st_size,
            storage_path=str(sp), status=DocumentStatus.queued, uploaded_by=uid)
        db.add(doc)
        await db.commit()
        await process_document_ingestion(did)
    print("Ingestion done")

    queries = ["年假有多少天？", "加班费怎么算？", "餐补每月多少钱？",
               "迟到怎么处理？", "出差住宿标准是多少？"]
    results = []

    for q in queries:
        # Use chat API via HTTP to get proper SSE parsing
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            async with client.stream(
                "POST",
                f"/api/v1/knowledge-bases/{kb_id}/chat",
                headers=headers,
                json={"message": q, "mode": "fast"},
            ) as resp:
                answer = ""
                citations = []
                current_event = ""
                async for line in resp.aiter_lines():
                    if line.startswith("event: "):
                        current_event = line[7:].strip()
                    elif line.startswith("data: "):
                        raw = line[6:]
                        try:
                            d = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        if current_event == "token" and isinstance(d, dict) and "text" in d:
                            answer += d["text"]
                        elif current_event == "citation":
                            citations.append(d)
                        elif current_event == "done":
                            pass

            refs = re.findall(r'\[片段(\d+)\]', answer)
            # Also count citation events from SSE
            citation_event_count = len(citations)
            has_citations = bool(refs) or citation_event_count > 0
            valid = sum(1 for r in refs if 1 <= int(r) <= citation_event_count) if refs else citation_event_count
            has_refs = bool(refs)
            results.append({
                "query": q[:30],
                "has_citations": has_citations,
                "has_inline_refs": has_refs,
                "valid": valid,
                "total": len(refs) or citation_event_count,
                "citation_event_count": citation_event_count,
                "answer_len": len(answer),
            })
            status = "OK" if has_citations else "NO_REF"
            print(f"  [{status}] {q[:20]}: inline={has_refs}, events={citation_event_count}")

    n = len(results)
    has_cite = sum(1 for r in results if r["has_citations"])
    has_inline = sum(1 for r in results if r["has_inline_refs"])
    total_refs = sum(r["total"] for r in results)
    valid_refs = sum(r["valid"] for r in results)
    total_events = sum(r["citation_event_count"] for r in results)

    print(f"\n{'='*60}")
    print(f"Citation Accuracy 评测 ({n} 次对话)")
    print(f"{'='*60}")
    print(f"  有引用的对话: {has_cite}/{n} = {has_cite/max(1,n):.0%}")
    print(f"  行内 [片段N]: {has_inline}/{n} = {has_inline/max(1,n):.0%}")
    print(f"  引用 SSE 事件总数: {total_events}")
    for r in results:
        print(f"    {r['query']}: inline={r['has_inline_refs']}, events={r['citation_event_count']}, valid={r['valid']}/{r['total']}")

asyncio.run(main())
