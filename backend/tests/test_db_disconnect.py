"""Database disconnect tests — mock fault injection, zero production changes.

With exception_handler for sqlalchemy.exc.OperationalError → 503.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_kb as _create_kb


@pytest.mark.asyncio
async def test_health_db_down(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """/health returns degraded when DB is unreachable."""
    async def _check() -> bool:
        return False

    monkeypatch.setattr("app.api.health.check_database", _check)

    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "degraded"
    assert resp.json()["database"] == "error"


async def _patch_db_and_call(client, url, headers, json_data=None, method="post"):
    """Mock SessionLocal to fail, call endpoint, assert 503."""
    from app.core.database import SessionLocal as orig

    class _FakeSession:
        async def __aenter__(self):
            import sqlalchemy
            raise sqlalchemy.exc.OperationalError(
                "could not connect to server", None, None
            )
        async def __aexit__(self, *args):
            pass

    import app.core.database as db_mod
    db_mod.SessionLocal = lambda: _FakeSession()  # type: ignore[method-assign]

    try:
        if method == "post":
            if json_data:
                resp = await client.post(url, headers=headers, json=json_data)
            else:
                resp = await client.post(url, headers=headers)
        else:
            resp = await client.get(url, headers=headers)
        assert resp.status_code == 503
    finally:
        db_mod.SessionLocal = orig


@pytest.mark.asyncio
async def test_chat_db_unavailable_returns_503(
    client: AsyncClient,
    register_and_login,
) -> None:
    """Chat API: DB failure -> 503."""
    headers, user = await register_and_login(prefix="db-down-chat")
    kb = await _create_kb(client, headers, user, name="DB Down Chat KB")
    await _patch_db_and_call(
        client,
        f"/api/v1/knowledge-bases/{kb['id']}/chat",
        headers,
        json_data={"message": "test"},
    )


@pytest.mark.asyncio
async def test_document_list_db_down_returns_503(
    client: AsyncClient,
    register_and_login,
) -> None:
    """Document list: DB failure -> 503."""
    headers, user = await register_and_login(prefix="db-down-doc-list")
    kb = await _create_kb(client, headers, user, name="DB Down Doc KB")
    await _patch_db_and_call(
        client,
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers,
        method="get",
    )


@pytest.mark.asyncio
async def test_create_kb_db_down_returns_503(
    client: AsyncClient,
    register_and_login,
) -> None:
    """Create KB: DB failure -> 503."""
    headers, user = await register_and_login(prefix="db-down-create-kb")
    await _patch_db_and_call(
        client,
        "/api/v1/knowledge-bases",
        headers,
        json_data={"name": "DB Down Create KB"},
    )
