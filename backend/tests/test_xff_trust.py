"""P0-05 XFF 信任链测试：可信代理解析 + 伪造校验（限流不得被 XFF 绕过）。"""

from __future__ import annotations

import pytest
from fastapi import Request
from httpx import AsyncClient

from app.core.config import settings
from app.core.request_ip import resolve_client_ip


def _make_request(
    *,
    headers: dict[str, str] | None = None,
    client: tuple[str, int] | None = ("10.0.0.9", 12345),
) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (k.lower().encode("ascii"), v.encode("ascii"))
            for k, v in (headers or {}).items()
        ],
        "client": client,
        "server": ("test", 80),
    }
    return Request(scope)


# ── 单元：可信代理链解析 ─────────────────────────────────────────────


def test_direct_mode_ignores_xff(monkeypatch: pytest.MonkeyPatch) -> None:
    """trusted_proxy_count=0（API 直连）：忽略 XFF，使用 TCP peer——伪造无效。"""
    monkeypatch.setattr(settings, "trusted_proxy_count", 0)
    req = _make_request(headers={"X-Forwarded-For": "6.6.6.6"})
    assert resolve_client_ip(req) == "10.0.0.9"


def test_single_proxy_takes_xff(monkeypatch: pytest.MonkeyPatch) -> None:
    """trusted_proxy_count=1（nginx 覆写场景）：取 XFF 唯一/最右段。"""
    monkeypatch.setattr(settings, "trusted_proxy_count", 1)
    assert resolve_client_ip(_make_request(headers={"X-Forwarded-For": "6.6.6.6"})) == "6.6.6.6"
    # 即使客户端伪造前段，nginx 覆写后最右段仍是真实客户端 IP
    assert (
        resolve_client_ip(
            _make_request(headers={"X-Forwarded-For": "1.2.3.4, 6.6.6.6"})
        )
        == "6.6.6.6"
    )


def test_multi_proxy_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    """trusted_proxy_count=2：取右数第 2 段（跳过最近两级可信代理）。"""
    monkeypatch.setattr(settings, "trusted_proxy_count", 2)
    req = _make_request(headers={"X-Forwarded-For": "1.2.3.4, 6.6.6.6, 10.0.0.1"})
    assert resolve_client_ip(req) == "6.6.6.6"


def test_malformed_xff_falls_back_to_peer(monkeypatch: pytest.MonkeyPatch) -> None:
    """XFF 为空 / 段数不足 / 无 client 时安全回退，不信任伪造段。"""
    monkeypatch.setattr(settings, "trusted_proxy_count", 1)
    assert resolve_client_ip(_make_request(headers={"X-Forwarded-For": " "})) == "10.0.0.9"
    # 段数少于信任层数 → 无法确定客户端 → 用 TCP peer（防伪）
    monkeypatch.setattr(settings, "trusted_proxy_count", 2)
    assert (
        resolve_client_ip(_make_request(headers={"X-Forwarded-For": "1.2.3.4"}))
        == "10.0.0.9"
    )
    # 无 client 且无 XFF → None
    monkeypatch.setattr(settings, "trusted_proxy_count", 0)
    assert resolve_client_ip(_make_request(client=None)) is None


# ── 集成：XFF 正确参与全局限流（含伪造校验）─────────────────────────


@pytest.mark.asyncio
async def test_rate_limit_not_bypassed_by_forged_xff(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """直连模式（trust=0）：伪造 XFF 换 IP 无法绕过限流——桶键仍是 TCP peer。"""
    from app.services import rate_limit as rl

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "trusted_proxy_count", 0)
    monkeypatch.setattr(rl, "MAX_REQUESTS", 2)
    monkeypatch.setattr(rl, "WINDOW_SECONDS", 60)
    rl.reset_all_rate_limits()
    try:
        for i in range(2):
            resp = await client.get(
                "/openapi.json",
                headers={"X-Forwarded-For": f"6.6.6.{i}"},
            )
            assert resp.status_code == 200, resp.text

        # 第三个请求换一个伪造 IP——仍应 429（peer 桶已满，伪造无效）
        blocked = await client.get(
            "/openapi.json",
            headers={"X-Forwarded-For": "7.7.7.7"},
        )
        assert blocked.status_code == 429
        assert "请求过于频繁" in blocked.json()["detail"]
    finally:
        rl.reset_all_rate_limits()


@pytest.mark.asyncio
async def test_rate_limit_uses_trusted_xff(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """代理模式（trust=1）：XFF 参与限流键——同 XFF 打满，异 XFF 独立计数。"""
    from app.services import rate_limit as rl

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "trusted_proxy_count", 1)
    monkeypatch.setattr(rl, "MAX_REQUESTS", 2)
    monkeypatch.setattr(rl, "WINDOW_SECONDS", 60)
    rl.reset_all_rate_limits()
    try:
        for _ in range(2):
            resp = await client.get(
                "/openapi.json",
                headers={"X-Forwarded-For": "6.6.6.6"},
            )
            assert resp.status_code == 200, resp.text

        # 同一 XFF 第三次 → 429
        blocked = await client.get(
            "/openapi.json",
            headers={"X-Forwarded-For": "6.6.6.6"},
        )
        assert blocked.status_code == 429

        # 不同 XFF → 独立桶，放行（证明限流键确实来自 XFF）
        other = await client.get(
            "/openapi.json",
            headers={"X-Forwarded-For": "8.8.8.8"},
        )
        assert other.status_code == 200
    finally:
        rl.reset_all_rate_limits()
