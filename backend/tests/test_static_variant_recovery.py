"""M5.3: static deterministic variants recover 5.1 when LLM is degraded."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.degradation import DegradationLevel
from app.services.rag.retrieval import (
    _expand_if_low_confidence,
    static_query_variants,
)
from app.services.rag.types import RetrievedChunk, _RecallRow


def test_static_query_variants_hits_compensation_anchor() -> None:
    variants = static_query_variants("什么情况下要赔公司钱？")
    assert "离职 代通知金 赔偿" in variants
    assert "培训费 按比例 退还" in variants


def test_static_query_variants_ignores_unrelated_query() -> None:
    assert static_query_variants("年假有多少天？") == []


@pytest.mark.asyncio
async def test_expand_low_confidence_uses_static_variants_when_llm_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.rag.retrieval as retrieval_mod

    llm_called = False

    async def _llm_expand(query: str) -> list[str]:
        nonlocal llm_called
        llm_called = True
        return [query]

    monkeypatch.setattr("app.services.rag.generation.expand_queries", _llm_expand)
    monkeypatch.setattr(
        retrieval_mod, "assess_degradation", lambda: DegradationLevel.LLM_DOWN
    )

    embed_mock = AsyncMock(return_value=[[0.0] * 512])
    monkeypatch.setattr(retrieval_mod, "try_embed_texts", embed_mock)

    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    extra_chunk = SimpleNamespace(
        id=uuid.uuid4(),
        kb_id=kb_id,
        document_id=doc_id,
        content="离职通知期及代通知金赔偿规定",
        page_number=1,
        section_title="5.1 离职通知期",
        heading_path="5.1 离职通知期",
    )
    row = _RecallRow(
        chunk=extra_chunk,
        filename="员工手册.md",
        vector_similarity=0.55,
    )
    monkeypatch.setattr(retrieval_mod, "vector_recall", AsyncMock(return_value=[row]))

    base = RetrievedChunk(
        kb_id=kb_id,
        chunk_id=uuid.uuid4(),
        document_id=doc_id,
        doc_name="员工手册.md",
        content="培训费退还",
        page_number=1,
        section_title="4.1 培训",
        heading_path="4.1 培训",
        similarity=0.3,
    )

    result = await _expand_if_low_confidence(
        db=None,
        result=[base],
        query="什么情况下要赔公司钱？",
        kb_id=kb_id,
        visible_kb_ids=None,
        hide_admin_only=False,
        top_k=8,
    )

    assert not llm_called
    assert embed_mock.call_count == 2
    assert any(c.section_title == "5.1 离职通知期" for c in result)


@pytest.mark.asyncio
async def test_expand_low_confidence_keeps_llm_path_when_normal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.rag.retrieval as retrieval_mod

    llm_called = False

    async def _llm_expand(query: str) -> list[str]:
        nonlocal llm_called
        llm_called = True
        return [query]

    monkeypatch.setattr("app.services.rag.generation.expand_queries", _llm_expand)
    monkeypatch.setattr(
        retrieval_mod, "assess_degradation", lambda: DegradationLevel.NORMAL
    )

    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    base = RetrievedChunk(
        kb_id=kb_id,
        chunk_id=uuid.uuid4(),
        document_id=doc_id,
        doc_name="员工手册.md",
        content="培训费退还",
        page_number=1,
        section_title="4.1 培训",
        heading_path="4.1 培训",
        similarity=0.3,
    )

    result = await _expand_if_low_confidence(
        db=None,
        result=[base],
        query="什么情况下要赔公司钱？",
        kb_id=kb_id,
        visible_kb_ids=None,
        hide_admin_only=False,
        top_k=8,
    )

    assert llm_called
    assert len(result) == 1