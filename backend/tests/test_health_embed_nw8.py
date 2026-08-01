"""NW-8：/health/detailed embed readiness；挂掉不误杀整体 status。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_detailed_includes_embed_block(client: AsyncClient) -> None:
    with patch(
        "app.api.health.probe_embed_readiness",
        new=AsyncMock(
            return_value={"provider": "bge", "ready": True, "reason": "ok"}
        ),
    ):
        resp = await client.get("/health/detailed")
    assert resp.status_code == 200
    body = resp.json()
    assert "embed" in body
    assert body["embed"]["provider"] == "bge"
    assert body["embed"]["ready"] is True
    assert body["embed"]["reason"] == "ok"


@pytest.mark.asyncio
async def test_embed_not_ready_does_not_set_status_error(client: AsyncClient) -> None:
    with patch(
        "app.api.health.probe_embed_readiness",
        new=AsyncMock(
            return_value={
                "provider": "tongyi",
                "ready": False,
                "reason": "timeout",
            }
        ),
    ):
        resp = await client.get("/health/detailed")
    assert resp.status_code == 200
    body = resp.json()
    assert body["embed"]["ready"] is False
    assert body["embed"]["reason"] == "timeout"
    assert body["status"] in ("ok", "degraded")
    assert body["status"] != "error"


@pytest.mark.asyncio
async def test_embed_failure_does_not_change_status_vs_ready_ok(
    client: AsyncClient,
) -> None:
    """embed 探测失败不得单独把 ok→degraded（对称 OCR：块内自报）。"""
    with patch(
        "app.api.health.probe_embed_readiness",
        new=AsyncMock(
            return_value={"provider": "bge", "ready": True, "reason": "ok"}
        ),
    ):
        ok_body = (await client.get("/health/detailed")).json()

    with patch(
        "app.api.health.probe_embed_readiness",
        new=AsyncMock(
            return_value={
                "provider": "bge",
                "ready": False,
                "reason": "error",
            }
        ),
    ):
        bad_body = (await client.get("/health/detailed")).json()

    assert ok_body["status"] == bad_body["status"]
    assert bad_body["embed"]["ready"] is False
    assert bad_body["status"] != "error"


@pytest.mark.asyncio
async def test_probe_tongyi_key_missing_without_network() -> None:
    from app.core.config import settings
    from app.services.ingestion.embed_health import probe_embed_readiness

    with patch.object(settings, "embedding_provider", "tongyi"):
        with patch.object(settings, "tongyi_api_key", ""):
            with patch(
                "app.services.ingestion.embedder.try_embed_texts",
                new=AsyncMock(side_effect=AssertionError("must not call embed")),
            ):
                block = await probe_embed_readiness()
    assert block == {
        "provider": "tongyi",
        "ready": False,
        "reason": "key_missing",
    }


@pytest.mark.asyncio
async def test_probe_timeout_maps_reason() -> None:
    from app.core.config import settings
    from app.services.ingestion.embed_health import probe_embed_readiness

    async def _hang(_texts, provider=None):
        await asyncio.sleep(60)
        return [[0.0]]

    with patch.object(settings, "embedding_provider", "bge"):
        with patch(
            "app.services.ingestion.embed_health.EMBED_HEALTH_TIMEOUT_SECONDS",
            0.01,
        ):
            with patch(
                "app.services.ingestion.embedder.try_embed_texts",
                new=_hang,
            ):
                block = await probe_embed_readiness()
    assert block["provider"] == "bge"
    assert block["ready"] is False
    assert block["reason"] == "timeout"
