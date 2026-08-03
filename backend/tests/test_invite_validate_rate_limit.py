"""P1-21 · 邀请码 validate 限流接线测试（H4 窗）。

conftest 在导入 app.main 前把 ``enforce_api_rate_limit`` 全局替换为 no-op。
本模块通过共享 ``real_api_rate_limit`` fixture 恢复真实实现（reload + 全部 API
模块接线 + 计数器/熔断/降级隔离），从而在 HTTP 层证明：同 IP 连打阈值后
``POST /api/v1/auth/invites/validate`` → 429（真实限流，非 no-op），且 429
时序不依赖同批文件顺序（fixture 已复位降级乘数与熔断器）。

复用 ``ApiRateLimitKind.register`` 桶：匿名注册流（register + invites/validate）
同 IP 合计 10 次/小时，防邀请码枚举。
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.auth import api_rate_limit as api_rl


# 恢复真实限流实现（含降级/熔断复位），HTTP 层断言真实 429
pytestmark = pytest.mark.usefixtures("real_api_rate_limit")


async def _validate(client: AsyncClient, code: str = "NO-SUCH-CODE"):
    return await client.post(
        "/api/v1/auth/invites/validate",
        json={"code": code},
    )


@pytest.mark.asyncio
async def test_invite_validate_429_after_threshold(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同 IP 连打阈值后 invites/validate → 429（限流先于邀请码查询）。"""
    monkeypatch.setattr(api_rl, "REGISTER_MAX_REQUESTS", 3)

    for _ in range(3):
        resp = await _validate(client)
        # 未超限：正常业务响应（无效码 422，证明限流未误伤）
        assert resp.status_code == 422

    blocked = await _validate(client)
    assert blocked.status_code == 429
    assert "频繁" in blocked.json()["detail"]


@pytest.mark.asyncio
async def test_invite_validate_limits_are_per_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同 IP 打满后 429；另一客户端 IP 独立计数，正常放行。"""
    monkeypatch.setattr(api_rl, "REGISTER_MAX_REQUESTS", 2)

    client_a = AsyncClient(
        transport=ASGITransport(app=app, client=("203.0.113.10", 10001)),
        base_url="http://test",
    )
    client_b = AsyncClient(
        transport=ASGITransport(app=app, client=("203.0.113.20", 10002)),
        base_url="http://test",
    )
    async with client_a, client_b:
        for _ in range(2):
            resp = await _validate(client_a)
            assert resp.status_code == 422

        blocked = await _validate(client_a)
        assert blocked.status_code == 429

        # 异 IP 不受影响：仍是正常业务响应
        ok = await _validate(client_b)
        assert ok.status_code == 422
