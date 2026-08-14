"""/health 系列端点回归测试（M9-P1-1 配套）。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_live(client: AsyncClient) -> None:
    resp = await client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_ready_shape(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.health.check_database",
        AsyncMock(return_value=True),
    )
    from app.core.config import settings

    monkeypatch.setattr(settings, "deepseek_api_key", "ds-key")

    resp = await client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"status", "database", "api_keys_ok"}
    assert body["database"] == "ok"
    assert body["status"] in ("ok", "degraded")


@pytest.mark.asyncio
async def test_health_shape(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.health.check_database",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "app.api.health._check_redis",
        AsyncMock(return_value=True),
    )

    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["database"] == "ok"
    assert body["redis"] == "ok"
    assert body["status"] in ("ok", "degraded")
    assert "degradation" in body
    assert "breakers" in body["degradation"]


@pytest.mark.asyncio
async def test_health_detailed_shape(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.health.check_database",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "app.api.health.probe_embed_readiness",
        AsyncMock(
            return_value={"provider": "mock", "ready": True, "reason": "ok"}
        ),
    )

    resp = await client.get("/health/detailed")
    assert resp.status_code == 200
    body = resp.json()
    assert body["database"] == "ok"
    assert body["status"] in ("ok", "degraded")
    for field in (
        "api_keys",
        "latency",
        "disk",
        "ocr",
        "embed",
        "chat",
        "maintenance",
    ):
        assert field in body
