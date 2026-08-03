"""pytest 共享 fixture（Wave 1.1+：DB 测试 + 认证辅助）。"""

import uuid
from collections.abc import Awaitable, Callable


import pytest
from httpx import ASGITransport, AsyncClient

# 在导入 app.main 之前绕过 API 限流，防止 api 模块在 import 时建立本地引用
import app.services.auth.api_rate_limit as _arl


async def _api_rate_limit_noop(*_args, **_kwargs) -> None:
    """全局限流 noop（既有基线）：在 app.main import 前替换 enforce_api_rate_limit，
    使各 API 模块 by-name 绑定均为 noop。限流用例通过 real_api_rate_limit fixture
    显式恢复真实实现，测试结束再由 fixture 还原本 noop。"""
    return None


_arl.enforce_api_rate_limit = _api_rate_limit_noop  # type: ignore[method-assign]
API_RATE_LIMIT_NOOP = _api_rate_limit_noop
del _arl

# 全局限流 100 req/min/IP（必须在 import app.main 前完成，故这几处导入后置）
from app.core.config import settings as _settings  # noqa: E402
_settings.rate_limit_enabled = False
settings = _settings  # for fixtures that reference conftest.settings
del _settings
from app.core.database import engine  # noqa: E402
from app.main import app  # noqa: E402

# 注册 tests/fixtures/*.py 中的共享 fixture（如 org_iso）
pytest_plugins = ["tests.fixtures.org_isolation"]


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
    """测试环境默认 mock 嵌入，避免依赖通义 API Key。
    设置环境变量 RAG_REAL_EMBEDDING=1 可跳过 mock，使用真实嵌入。"""
    import os
    if os.environ.get("RAG_REAL_EMBEDDING") == "1":
        return
    monkeypatch.setattr(settings, "embedding_provider", "mock")


@pytest.fixture(autouse=True)
def mock_rerank_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """测试默认关闭真 BGE，避免 CI 下载 ONNX；并关 mock 精排以免扰动 golden。
    设置 RAG_REAL_RERANK=1 可走真 BGE 路径。
    单测若需 mock 精排，自行 monkeypatch rerank_enabled=True / policy=always|conditional + provider=mock。"""
    import os
    if os.environ.get("RAG_REAL_RERANK") == "1":
        return
    monkeypatch.setattr(settings, "rerank_enabled", False)
    monkeypatch.setattr(settings, "rerank_policy", "off")
    monkeypatch.setattr(settings, "rerank_provider", "mock")
    monkeypatch.setattr(settings, "query_rewrite_enabled", False)
    monkeypatch.setattr(settings, "query_rewrite_policy", "off")



@pytest.fixture(autouse=True)
async def dispose_db_engine() -> None:
    """每个测试后释放连接池，避免 asyncpg 跨 event loop 报错。"""
    yield
    await engine.dispose()


@pytest.fixture
async def db_session():
    """提供真实 AsyncSession（供集成用例使用，如 ChatEngine 链路）。"""
    from app.core.database import SessionLocal

    async with SessionLocal() as _session:
        yield _session


# 以 by-name 绑定 enforce_api_rate_limit 的 API 模块（conftest import 时均已绑定 noop）
_API_RATE_LIMIT_BOUND_MODULES = (
    "app.api.auth",
    "app.api.chat",
    "app.api.documents",
    "app.api.ask",
    "app.api.search",
    "app.api.kb_threads",
    "app.api.ask_threads",
)


@pytest.fixture
def real_api_rate_limit(monkeypatch: pytest.MonkeyPatch):
    """限流用例专用：恢复真实 enforce_api_rate_limit 并做全量隔离。

    conftest 在 import 时全局 noop 过 enforce_api_rate_limit，本 fixture 通过
    ``importlib.reload`` 取回真实实现，并：
    - 把全部 by-name 绑定模块（auth/chat/documents/ask/search/kb_threads/ask_threads）
      切到真实实现，保证 HTTP 层限流真实生效；
    - 复位内存计数器 / 熔断器 / 降级状态 / 后端缓存，断言不依赖同批文件顺序；
    - teardown 显式还原 noop 全局基线（含模块属性），不残留真实实现状态。
    """
    import importlib

    from app.core.degradation import reset_stabilization
    from app.core.retry import reset_all_breakers
    from app.services.auth import api_rate_limit as _arl
    from app.services.auth.rate_limit_store import reset_rate_limit_backend_cache
    from app.services.observability.metrics_registry import (
        reset_process_counters_for_tests,
    )

    real_module = importlib.reload(_arl)
    for _mod_name in _API_RATE_LIMIT_BOUND_MODULES:
        _mod = importlib.import_module(_mod_name)
        monkeypatch.setattr(
            _mod,
            "enforce_api_rate_limit",
            real_module.enforce_api_rate_limit,
        )

    # 模块属性同样切到真实实现；teardown 显式还原 noop（不能用 monkeypatch，
    # 否则会恢复到 reload 后的真实函数）
    _arl.enforce_api_rate_limit = real_module.enforce_api_rate_limit
    # 钉死降级乘数为 1.0：限流断言只测限流本身，不受同批熔断/降级状态影响
    # （此前 breaker/llm_5xx 同批会因 LLM_DOWN 乘数 0.5 令 invite 等提前 429；
    # 且真实 LLM 失败在本测试内也会触发熔断，中途减半限额）
    monkeypatch.setattr(real_module, "_degradation_multiplier", lambda: 1.0)
    real_module.reset_all_api_rate_limits()
    reset_all_breakers()
    reset_stabilization()
    reset_rate_limit_backend_cache()
    reset_process_counters_for_tests()
    yield real_module
    real_module.reset_all_api_rate_limits()
    reset_all_breakers()
    reset_stabilization()
    reset_rate_limit_backend_cache()
    reset_process_counters_for_tests()
    _arl.enforce_api_rate_limit = API_RATE_LIMIT_NOOP
