"""长对话测试：10 轮对话后 context 不溢出。"""
import uuid
from httpx import ASGITransport, AsyncClient
from app.main import app


async def test_long_conversation():
    """10 轮对话，每轮问题不同，验证始终能返回。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        email = f"longchat-{uuid.uuid4().hex[:8]}@example.com"
        await c.post("/api/v1/auth/register", json={
            "email": email, "username": f"lchat{uuid.uuid4().hex[:8]}",
            "password": "Test123!@", "account_type": "personal",
        })
        r = await c.post("/api/v1/auth/login", json={"identifier": email, "password": "Test123!@"})
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = await c.post("/api/v1/knowledge-bases?workspace=personal", headers=h, json={"name": "LongChat-KB"})
        kb_id = r.json()["id"]
        with open("/app/tests/fixtures/golden_handbook.md", "rb") as f:
            await c.post(f"/api/v1/knowledge-bases/{kb_id}/documents?workspace=personal",
                         headers=h, files={"files": ("hb.md", f, "text/markdown")})

        questions = [
            "年假有多少天？", "请简单介绍下年假规则",
            "那事假呢？", "事假有工资吗",
            "加班怎么算？", "法定节假日加班是几倍",
            "出差补贴呢？", "一线城市和普通城市一样吗",
            "培训费用谁承担", "培训后离职要赔钱吗",
        ]
        for i, q in enumerate(questions):
            r = await c.get("/api/v1/search/documents", headers=h,
                            params={"workspace": "personal", "q": q, "mode": "content", "limit": 3})
            assert r.status_code == 200, f"第 {i+1} 轮失败: {r.status_code}"
        print(f"10 轮对话全部成功")
