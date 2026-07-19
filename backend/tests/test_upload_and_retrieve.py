"""大上传+检索测试：上传多份文档后并发检索。"""
import asyncio
import uuid
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.database import SessionLocal
from app.services.rag.retrieval import retrieve_chunks


async def test_upload_multiple_and_retrieve():
    """上传 5 份文档后检索。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        email = f"bulk-{uuid.uuid4().hex[:8]}@example.com"
        await c.post("/api/v1/auth/register", json={
            "email": email, "username": f"bulk{uuid.uuid4().hex[:8]}",
            "password": "Test123!@", "account_type": "personal",
        })
        r = await c.post("/api/v1/auth/login", json={"identifier": email, "password": "Test123!@"})
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = await c.post("/api/v1/knowledge-bases?workspace=personal", headers=h, json={"name": "Bulk-KB"})
        kb_id = r.json()["id"]

        # 上传 5 次同样的文档
        for i in range(5):
            with open("/app/tests/fixtures/golden_handbook.md", "rb") as f:
                r2 = await c.post(f"/api/v1/knowledge-bases/{kb_id}/documents?workspace=personal",
                                  headers=h, files={"files": (f"hb_{i}.md", f, "text/markdown")})
            assert r2.status_code == 201, f"上传 {i} 失败"

        # 等待 ingestion
        for _ in range(30):
            r2 = await c.get(f"/api/v1/knowledge-bases/{kb_id}/documents?workspace=personal&per_page=10", headers=h)
            items = r2.json().get("items", [])
            if len(items) >= 5 and all(d.get("status") == "completed" for d in items):
                break
            await asyncio.sleep(2)

        # 并发检索
        kb_uuid = uuid.UUID(kb_id)
        queries = ["年假", "加班费", "出差", "培训", "餐补"]
        async def _search(query):
            async with SessionLocal() as db:
                return len(await retrieve_chunks(db, kb_id=kb_uuid, query=query, top_k=3))

        results = await asyncio.gather(*[_search(q) for q in queries])
        assert all(n > 0 for n in results), f"部分检索返回 0: {results}"
        print(f"5 文档上传 + 5 检索全部成功: {results}")
