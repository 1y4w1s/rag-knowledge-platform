"""P1-14: bound retrieval LLM calls with asyncio.wait_for.

Multi-query expansion and HyDE generation must be truncated when the LLM
hangs, and the retrieval chain must fall back to the original query instead
of surfacing a raw timeout error.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.core.config import settings
from app.services.rag.hyde import generate_hypothetical_document
from app.services.rag.multi_query import build_query_variants


@pytest.fixture(autouse=True)
def _reset_hyde_cache():
    """Reset the HyDE env cache so tests do not leak state."""
    import app.services.rag.hyde as hyde_mod

    hyde_mod._HYDE_ENABLED = None
    yield
    hyde_mod._HYDE_ENABLED = None


async def _hang_forever(*args, **kwargs):
    await asyncio.sleep(3600)
    return []


@pytest.mark.asyncio
async def test_multi_query_llm_hang_truncated_and_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """expand_queries hanging past the timeout falls back to [original query]."""
    monkeypatch.setattr(settings, "llm_timeout_seconds", 0.05)
    monkeypatch.setattr(
        "app.services.rag.generation.expand_queries", _hang_forever
    )

    started = time.monotonic()
    variants = await build_query_variants("annual leave days")
    elapsed = time.monotonic() - started

    assert variants == ["annual leave days"]
    assert elapsed < 2.0


@pytest.mark.asyncio
async def test_hyde_llm_hang_truncated_and_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """complete_chat hanging past the timeout returns None for HyDE."""
    import app.services.rag.hyde as hyde_mod

    monkeypatch.setattr(settings, "llm_timeout_seconds", 0.05)
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    monkeypatch.setattr(settings, "tongyi_api_key", "")
    monkeypatch.setattr("app.services.rag.hyde.complete_chat", _hang_forever)
    hyde_mod._HYDE_ENABLED = True

    started = time.monotonic()
    result = await generate_hypothetical_document("annual leave days")
    elapsed = time.monotonic() - started

    assert result is None
    assert elapsed < 2.0
