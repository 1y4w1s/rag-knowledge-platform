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


async def _join_team(client: AsyncClient, headers: dict[str, str]):
    return await client.post(
        "/api/v1/settings/account/join-team",
        headers=headers,
        json={"invite_code": "NO-SUCH-CODE"},
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


@pytest.mark.asyncio
async def test_join_team_429_after_threshold(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P2-P3：同 IP 连打阈值后 join-team → 429（复用 register 桶防枚举）。"""
    monkeypatch.setattr(api_rl, "REGISTER_MAX_REQUESTS", 3)
    headers, _user = await register_and_login(
        prefix="join-rate",
        account_type="personal",
    )

    # 注册已计 1 次（同一 register 桶）；再打 2 次未超限，第 3 次触发 429
    for _ in range(2):
        resp = await _join_team(client, headers)
        # 未超限：业务层正常响应（无效码 422，证明限流未误伤）
        assert resp.status_code == 422

    blocked = await _join_team(client, headers)
    assert blocked.status_code == 429
    assert "频繁" in blocked.json()["detail"]


@pytest.mark.asyncio
async def test_join_team_rate_limits_are_per_ip(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P2-P3：同一登录用户在不同 IP 独立计数，A 打满 429、B 正常放行。"""
    monkeypatch.setattr(api_rl, "REGISTER_MAX_REQUESTS", 2)
    headers, _user = await register_and_login(
        prefix="join-rate-ip",
        account_type="personal",
    )

    client_a = AsyncClient(
        transport=ASGITransport(app=app, client=("203.0.113.30", 10001)),
        base_url="http://test",
    )
    client_b = AsyncClient(
        transport=ASGITransport(app=app, client=("203.0.113.40", 10002)),
        base_url="http://test",
    )
    async with client_a, client_b:
        for _ in range(2):
            resp = await _join_team(client_a, headers)
            assert resp.status_code == 422

        blocked = await _join_team(client_a, headers)
        assert blocked.status_code == 429

        # 异 IP 不受影响：仍是正常业务响应
        ok = await _join_team(client_b, headers)
        assert ok.status_code == 422
