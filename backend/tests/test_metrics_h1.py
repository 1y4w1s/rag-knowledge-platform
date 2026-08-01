"""H1：Prometheus /metrics 延迟 · 拒答 · 积压（手写 exposition）。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.latency import get_tracker
from app.services.observability.metrics_registry import (
    inc_chat_answer,
    inc_chats_total,
    reset_process_counters_for_tests,
)

METRICS_TOKEN = "test-metrics-token"


@pytest.fixture(autouse=True)
def _auth_metrics(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """P0-3 修复后 /metrics 需携带 METRICS_BEARER_TOKEN；本模块自动带上以保住既有断言。"""
    monkeypatch.setenv("METRICS_BEARER_TOKEN", METRICS_TOKEN)
    client.headers["Authorization"] = f"Bearer {METRICS_TOKEN}"
    yield


@pytest.fixture(autouse=True)
def _reset_metrics():
    reset_process_counters_for_tests()
    get_tracker("retrieval.embed").clear()
    yield
    reset_process_counters_for_tests()
    get_tracker("retrieval.embed").clear()


@pytest.mark.asyncio
async def test_metrics_exposition_skeleton(client: AsyncClient) -> None:
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    ct = resp.headers.get("content-type", "")
    assert "text/plain" in ct
    assert "version=0.0.4" in ct
    body = resp.text
    assert "ruige_uptime_seconds" in body
    assert "ruige_chats_total" in body
    assert "ruige_chat_answers_total" in body
    assert "ruige_rate_limit_rejected_total" in body
    assert "ruige_documents_backlog" in body
    assert "ruige_degradation_level" in body
    assert 'ruige_documents_backlog{status="queued"}' in body
    assert 'ruige_documents_backlog{status="processing"}' in body


@pytest.mark.asyncio
async def test_metrics_latency_matches_tracker(client: AsyncClient) -> None:
    tracker = get_tracker("retrieval.embed")
    for ms in (10.0, 20.0, 30.0, 40.0, 50.0):
        tracker.record(ms)

    from app.core.latency import all_tracker_stats

    stats = all_tracker_stats(min_count=5)["retrieval.embed"]
    assert "p50" in stats

    resp = await client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    assert f'ruige_latency_ms{{stage="embed",quantile="p50"}} {stats["p50"]}' in body
    assert f'ruige_latency_ms{{stage="embed",quantile="p95"}} {stats["p95"]}' in body


@pytest.mark.asyncio
async def test_metrics_refuse_counter_increments(client: AsyncClient) -> None:
    before = await client.get("/metrics")
    assert 'ruige_chat_answers_total{confidence="refuse",mode="fast"} 0' in before.text

    inc_chat_answer("refuse", "fast")
    inc_chat_answer("refuse", "fast")

    after = await client.get("/metrics")
    assert 'ruige_chat_answers_total{confidence="refuse",mode="fast"} 2' in after.text


@pytest.mark.asyncio
async def test_metrics_chats_total_increments(client: AsyncClient) -> None:
    inc_chats_total()
    resp = await client.get("/metrics")
    assert "ruige_chats_total 1" in resp.text


@pytest.mark.asyncio
async def test_metrics_backlog_gauge(client: AsyncClient) -> None:
    with patch(
        "app.services.observability.metrics_registry.documents_backlog_counts",
        new_callable=AsyncMock,
        return_value={"queued": 3, "processing": 1},
    ):
        # patch the function used inside metrics route — call via registry path
        # metrics.py imports documents_backlog_counts at module level; patch there too
        with patch(
            "app.api.metrics.documents_backlog_counts",
            new_callable=AsyncMock,
            return_value={"queued": 3, "processing": 1},
        ):
            resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert 'ruige_documents_backlog{status="queued"} 3' in resp.text
    assert 'ruige_documents_backlog{status="processing"} 1' in resp.text


@pytest.mark.asyncio
async def test_metrics_requires_token(client: AsyncClient) -> None:
    """P0-3 回归：匿名（无令牌）读取 /metrics 必须被拒。"""
    client.headers.pop("Authorization", None)
    resp = await client.get("/metrics")
    assert resp.status_code == 401
