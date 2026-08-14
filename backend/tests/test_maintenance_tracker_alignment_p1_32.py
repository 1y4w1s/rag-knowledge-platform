"""M9-P1-2（P1-32）：维护白名单与脚本调用点对齐。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.services.ops import maintenance_tracker

SCRIPT_CALL_SITES = ("dedup_documents", "reindex_pgvector")


@pytest.fixture(autouse=True)
def _clean_maintenance_history(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(maintenance_tracker, "_MAINTENANCE_HISTORY", {})


def test_whitelist_contains_script_call_sites() -> None:
    for kind in SCRIPT_CALL_SITES:
        assert kind in maintenance_tracker.MAINTENANCE_TASKS


def test_record_maintenance_updates_status_for_script_call_sites() -> None:
    for kind in SCRIPT_CALL_SITES:
        maintenance_tracker.record_maintenance(kind)

        status = maintenance_tracker.get_maintenance_status()[kind]
        assert status["status"] == "ok"
        assert status["days_since"] == 0


def test_record_maintenance_ignores_unknown_kind() -> None:
    maintenance_tracker.record_maintenance("not_a_task")

    assert "not_a_task" not in maintenance_tracker.get_maintenance_status()


@pytest.mark.asyncio
async def test_health_detailed_maintenance_no_longer_all_never(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.health.check_database",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "app.api.health.probe_embed_readiness",
        AsyncMock(return_value={"provider": "mock", "ready": True, "reason": "ok"}),
    )

    for kind in SCRIPT_CALL_SITES:
        maintenance_tracker.record_maintenance(kind)

    resp = await client.get("/health/detailed")
    assert resp.status_code == 200

    maintenance = resp.json()["maintenance"]
    for kind in SCRIPT_CALL_SITES:
        assert maintenance[kind]["status"] != "never"
