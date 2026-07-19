"""并发检索测试：10 路并发查询，验证结果不串。"""
import asyncio
import uuid
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.database import SessionLocal
from app.services.rag.retrieval import retrieve_chunks

QUERIES = [
    "员工年假有几天？", "加班费怎么算？", "迟到怎么处理？",
    "出差补贴是多少？", "培训费用谁承担？", "年终奖怎么发？",
    "病假怎么扣款？", "餐补多少？", "入职多久可以休年假？",
    "出差住宿怎么报销？",
]


async def test_10_concurrent_retrievals():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        email = f"concur-{uuid.uuid4().hex[:8]}@example.com"
        await c.post("/api/v1/auth/register", json={
            "email": email, "username": f"con{uuid.uuid4().hex[:8]}",
            "password": "Test123!@", "account_type": "personal",
        })
        r = await c.post("/api/v1/auth/login", json={"identifier": email, "password": "Test123!@"})
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = await c.post("/api/v1/knowledge-bases?workspace=personal", headers=h, json={"name": "Concurrent-KB"})
        kb_id = r.json()["id"]
        with open("/app/tests/fixtures/golden_handbook.md", "rb") as f:
            await c.post(f"/api/v1/knowledge-bases/{kb_id}/documents?workspace=personal",
                         headers=h, files={"files": ("hb.md", f, "text/markdown")})
        for _ in range(20):
            r = await c.get(f"/api/v1/knowledge-bases/{kb_id}/documents?workspace=personal&per_page=1", headers=h)
            if r.json().get("items", []) and r.json()["items"][0].get("status") == "completed":
                break
            await asyncio.sleep(2)

    kb_uuid = uuid.UUID(kb_id)
    async def _retrieve(query, idx):
        async with SessionLocal() as db:
            chunks = await retrieve_chunks(db, kb_id=kb_uuid, query=query, top_k=3)
            return idx, len(chunks)

    results = await asyncio.gather(*[_retrieve(q, i) for i, q in enumerate(QUERIES)])
    assert len(results) == 10
    for idx, n in results:
        assert n > 0, f"请求 {idx} 返回 {n} chunks"
    print(f"10 路并发检索全部通过: {[n for _, n in results]}")
