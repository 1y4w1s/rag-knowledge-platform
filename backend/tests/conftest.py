"""pytest 共享 fixture（Wave 1.1+：DB 测试 + 认证辅助）。"""

import uuid
from collections.abc import Awaitable, Callable

import pytest
from httpx import ASGITransport, AsyncClient


from app.core.config import settings
from app.core.database import engine
from app.main import app


def unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


def unique_username(prefix: str) -> str:
    import re

    base = re.sub(r"[^a-z0-9]", "", prefix.lower()) or "user"
    return f"{base}{uuid.uuid4().hex[:8]}"[:32]


def workspace_query(user: dict, *, kind: str = "default") -> dict[str, str]:
    """list/stats/create 所需的 ``?workspace=`` 查询参数。

    kind:
      ``default`` — 个人用户 personal；企业用户默认团队 org_id
      ``personal`` — 强制 personal
      ``organization`` — 强制 user[\"org_id\"]
    """
    if kind == "personal":
        return {"workspace": "personal"}
    if kind == "organization":
        org_id = user.get("org_id")
        assert org_id is not None, "organization workspace requires org_id on user"
        return {"workspace": org_id}
    if user.get("org_id"):
        return {"workspace": user["org_id"]}
    return {"workspace": "personal"}


def kb_list_items(body: dict) -> list:
    """Paginated GET /knowledge-bases response → items."""
    return body["items"]


@pytest.fixture
async def client() -> AsyncClient:
    """FastAPI ASGI 测试客户端（不启动真实 HTTP 端口）。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


RegisterAndLogin = Callable[..., Awaitable[tuple[dict[str, str], dict]]]


async def create_test_kb(
    client: AsyncClient,
    headers: dict[str, str],
    user: dict,
    *,
    name: str = "测试库",
    description: str | None = None,
    workspace_kind: str = "default",
) -> dict:
    """创建测试用资料库（自动带 ``?workspace=``）。

    团队空间默认 ``org_unit_id=null``（公司公共库），与 ORG 迁移前测试基线一致；
    ORG-4.1 归属用例请显式传 ``org_unit_id``。
    """
    params = workspace_query(user, kind=workspace_kind)
    payload: dict = {"name": name}
    if description is not None:
        payload["description"] = description
    if params.get("workspace") != "personal" and user.get("org_id"):
        payload["org_unit_id"] = None
    resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=params,
        json=payload,
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
def register_and_login(client: AsyncClient) -> RegisterAndLogin:
    """注册并登录，返回 (Authorization headers, user dict)。"""

    async def _register_and_login(
        *,
        prefix: str = "user",
        account_type: str = "personal",
        org_name: str | None = None,
        password: str = "Test123!@",
    ) -> tuple[dict[str, str], dict]:
        email = unique_email(prefix)
        username = unique_username(prefix)
        payload: dict = {
            "email": email,
            "username": username,
            "password": password,
            "account_type": account_type,
        }
        if org_name is not None:
            payload["org_name"] = org_name

        reg = await client.post("/api/v1/auth/register", json=payload)
        assert reg.status_code == 201

        login = await client.post(
            "/api/v1/auth/login",
            json={"identifier": email, "password": password},
        )
        assert login.status_code == 200
        data = login.json()
        headers = {"Authorization": f"Bearer {data['access_token']}"}
        return headers, data["user"]

    return _register_and_login


@pytest.fixture(autouse=True)
def mock_embedding_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """测试环境默认 mock 嵌入，避免依赖通义 API Key。"""
    monkeypatch.setattr(settings, "embedding_provider", "mock")


@pytest.fixture(autouse=True)
async def dispose_db_engine() -> None:
    """每个测试后释放连接池，避免 asyncpg 跨 event loop 报错。"""
    yield
    await engine.dispose()
