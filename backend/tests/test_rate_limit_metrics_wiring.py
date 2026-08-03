"""T6-O-7 · 限流指标接线验收：HTTP 层 429 → ``ruige_rate_limit_rejected_total`` 递增。

审计发现 O-7（docs/audit/T6-infrastructure-audit.md §4）的两个缺口：
1. ``ApiRateLimitKind.register`` 不在 ``RATE_LIMIT_REJECT_KINDS`` 白名单——注册/邀请码
   校验复用桶（register + invites/validate 同 IP 10 次/小时）的 429 被静默丢弃；
2. 全局限流中间件（RateLimitMiddleware，100 req/min/IP）直接返回 429 时不调
   ``inc_rate_limit_rejected``。

修复：
- ``metrics_registry.RATE_LIMIT_REJECT_KINDS`` 增补 ``register`` / ``global``；
- ``api/middleware/rate_limit.py`` 的 429 分支调 ``inc_rate_limit_rejected("global")``。

测试说明：conftest 在导入 app.main 前把 ``enforce_api_rate_limit`` 全局替换为 no-op
（既有基线问题，9 条记录在案）。修复后全部限流用例通过共享 ``real_api_rate_limit``
fixture 恢复真实实现（reload + 全部 API 模块接线 + 降级/熔断隔离），无需再避开
同批文件，在 HTTP 层证明真实接线（memory / redis 双后端）。
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.api.middleware import rate_limit as rate_limit_mw
from app.core.config import settings
from app.services.auth import api_rate_limit as api_rl
from app.services.auth.rate_limit_store import reset_rate_limit_backend_cache
from app.services.observability.metrics_registry import RATE_LIMIT_REJECT_KINDS

METRICS_TOKEN = "test-metrics-token-t6o7"

# 恢复真实限流实现（含计数器/后端缓存/降级/熔断复位），HTTP 层断言真实 429
pytestmark = pytest.mark.usefixtures("real_api_rate_limit")


@pytest.fixture(autouse=True)
def _auth_metrics(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """/metrics 需携带 METRICS_BEARER_TOKEN；本模块自动带上。"""
    monkeypatch.setattr(settings, "metrics_bearer_token", METRICS_TOKEN)
    client.headers["Authorization"] = f"Bearer {METRICS_TOKEN}"
    yield


class _FakeRedis:
    """最小 zset 假 Redis：仅覆盖 ``redis_sliding_allow`` 用到的 ``eval``。"""

    def __init__(self) -> None:
        self.zsets: dict[str, dict[str, float]] = {}

    async def eval(self, script: str, numkeys: int, *keys_and_args: str) -> int:
        key = keys_and_args[0]
        now = float(keys_and_args[1])
        window_start = float(keys_and_args[2])
        max_req = int(keys_and_args[3])
        member = keys_and_args[5]
        kept = {m: s for m, s in self.zsets.get(key, {}).items() if s > window_start}
        if len(kept) >= max_req:
            self.zsets[key] = kept
            return 0
        kept[member] = now
        self.zsets[key] = kept
        return 1


async def _validate(client: AsyncClient, code: str = "NO-SUCH-CODE"):
    return await client.post(
        "/api/v1/auth/invites/validate",
        json={"code": code},
    )


@pytest.mark.asyncio
async def test_metrics_skeleton_includes_register_and_global(
    client: AsyncClient,
) -> None:
    """固定 scrape：全部 7 档 kind 恒有输出（含新增 register / global）。"""
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "register" in RATE_LIMIT_REJECT_KINDS
    assert "global" in RATE_LIMIT_REJECT_KINDS
    for kind in RATE_LIMIT_REJECT_KINDS:
        assert f'ruige_rate_limit_rejected_total{{kind="{kind}"}} 0' in resp.text


@pytest.mark.asyncio
async def test_http_register_429_increments_metric_memory(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP 层（memory 后端）：invites/validate 复用 register 桶撞限 → 429 → kind=register 递增。"""
    monkeypatch.setattr(api_rl, "REGISTER_MAX_REQUESTS", 3)

    for _ in range(3):
        resp = await _validate(client)
        assert resp.status_code == 422, resp.text

    blocked = await _validate(client)
    assert blocked.status_code == 429, blocked.text

    body = (await client.get("/metrics")).text
    assert 'ruige_rate_limit_rejected_total{kind="register"} 1' in body


@pytest.mark.asyncio
async def test_http_register_429_increments_metric_redis(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP 层（redis 后端）：同一 register 桶撞限 → 429 → kind=register 递增。"""
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    reset_rate_limit_backend_cache()
    fake = _FakeRedis()

    async def _get():
        return fake

    monkeypatch.setattr("app.core.redis.get_redis", _get)
    monkeypatch.setattr(api_rl, "REGISTER_MAX_REQUESTS", 3)

    for _ in range(3):
        resp = await _validate(client)
        assert resp.status_code == 422, resp.text

    blocked = await _validate(client)
    assert blocked.status_code == 429, blocked.text

    body = (await client.get("/metrics")).text
    assert 'ruige_rate_limit_rejected_total{kind="register"} 1' in body


@pytest.mark.asyncio
async def test_http_middleware_429_increments_global_metric(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP 层：全局限流中间件直接返回 429 → kind=global 递增。"""
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    state = {"limited": True}
    monkeypatch.setattr(
        rate_limit_mw,
        "is_rate_limited",
        lambda ip, **kw: state["limited"],
    )
    monkeypatch.setattr(
        rate_limit_mw,
        "window_reset_seconds",
        lambda ip, **kw: 60,
    )

    resp = await client.get("/api/v1/knowledge-bases")
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") == "60"

    state["limited"] = False
    body = (await client.get("/metrics")).text
    assert 'ruige_rate_limit_rejected_total{kind="global"} 1' in body
