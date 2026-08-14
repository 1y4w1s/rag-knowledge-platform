"""M9-P1-1（P1-31）：/health/ready 按当前 chat provider 判定 API Key。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.core.config import settings


async def _get_ready(client: AsyncClient) -> dict:
    resp = await client.get("/health/ready")
    assert resp.status_code == 200
    return resp.json()


@pytest.fixture(autouse=True)
def _db_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.health.check_database",
        AsyncMock(return_value=True),
    )


@pytest.mark.asyncio
async def test_ready_ok_with_only_current_provider_key_deepseek(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "chat_provider", "deepseek")
    monkeypatch.setattr(settings, "deepseek_api_key", "ds-key")
    monkeypatch.setattr(settings, "tongyi_api_key", "")

    body = await _get_ready(client)

    assert body["status"] == "ok"
    assert body["api_keys_ok"] is True


@pytest.mark.asyncio
async def test_ready_degraded_when_current_provider_key_missing(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "chat_provider", "deepseek")
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    monkeypatch.setattr(settings, "tongyi_api_key", "qwen-key")

    body = await _get_ready(client)

    assert body["status"] == "degraded"
    assert body["api_keys_ok"] is False


@pytest.mark.asyncio
async def test_ready_ok_with_only_current_provider_key_tongyi(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "chat_provider", "tongyi")
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    monkeypatch.setattr(settings, "tongyi_api_key", "qwen-key")

    body = await _get_ready(client)

    assert body["status"] == "ok"
    assert body["api_keys_ok"] is True


@pytest.mark.asyncio
async def test_ready_degraded_when_tongyi_key_missing(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "chat_provider", "tongyi")
    monkeypatch.setattr(settings, "deepseek_api_key", "ds-key")
    monkeypatch.setattr(settings, "tongyi_api_key", "")

    body = await _get_ready(client)

    assert body["status"] == "degraded"
    assert body["api_keys_ok"] is False


@pytest.mark.asyncio
async def test_ready_degraded_without_any_key(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "chat_provider", "deepseek")
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    monkeypatch.setattr(settings, "tongyi_api_key", "")

    body = await _get_ready(client)

    assert body["status"] == "degraded"
    assert body["api_keys_ok"] is False
