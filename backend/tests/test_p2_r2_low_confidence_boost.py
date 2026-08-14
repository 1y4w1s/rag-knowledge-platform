"""P2-R2：低置信判断传带分结果（_RecallRow → RetrievedChunk），变体提权不再静默失效。"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.services.rag.types import RetrievedChunk, _RecallRow


def _fake_chunk(cid: uuid.UUID, kb_id: uuid.UUID):
    return SimpleNamespace(
        id=cid,
        kb_id=kb_id,
        document_id=uuid.uuid4(),
        content="员工年假十天。",
        page_number=1,
        section_title="1.1 年假",
        heading_path=None,
        parent_chunk_id=None,
    )


def _recall_rows(kb_id: uuid.UUID, similarities: list[float]) -> list[_RecallRow]:
    return [
        _RecallRow(
            chunk=_fake_chunk(uuid.uuid4(), kb_id),
            filename="handbook.md",
            vector_similarity=sim,
        )
        for sim in similarities
    ]


def _fake_route():
    async def _route(query: str, **kwargs):
        return SimpleNamespace(
            provider=None,
            embedding_col=None,
            query_vec=[0.1] * 8,
        )

    return _route


def _make_fake_fuse(captured: dict):
    def _fake_fuse(ranked_lists, *, weights, top_n, newcomer_slots=5):
        captured["weights"] = weights
        return []

    return _fake_fuse


def test_confidence_rows_map_vector_similarity() -> None:
    from app.services.rag.multi_query import _recall_rows_to_confidence_chunks

    kb_id = uuid.uuid4()
    rows = _recall_rows(kb_id, [0.32])
    rows.append(
        _RecallRow(
            chunk=_fake_chunk(uuid.uuid4(), kb_id),
            filename="handbook.md",
            fts_rank=1.0,
        )
    )
    chunks = _recall_rows_to_confidence_chunks(rows)
    assert isinstance(chunks[0], RetrievedChunk)
    assert chunks[0].similarity == pytest.approx(0.32)
    assert chunks[1].similarity == 0.0  # 纯 FTS 无向量分


@pytest.mark.asyncio
async def test_kb_low_confidence_boosts_variant(monkeypatch: pytest.MonkeyPatch) -> None:
    """原问 ≥3 条弱向量分 → 变体权重 1.0（此前无分分支会漏提权）。"""
    from app.services.rag import multi_query as mq

    captured = {}
    monkeypatch.setattr(settings, "query_rewrite_variant_weight", 0.7)
    monkeypatch.setattr(mq, "resolve_query_embed", _fake_route())
    monkeypatch.setattr(
        mq,
        "vector_recall_en_empty_fallback",
        AsyncMock(side_effect=lambda **kwargs: _recall_rows(uuid.uuid4(), [0.30, 0.28, 0.25])),
    )
    monkeypatch.setattr(mq, "fts_recall", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        mq, "_additive_fuse_original_priority", _make_fake_fuse(captured)
    )

    await mq.multi_query_kb_recall(
        AsyncMock(),
        kb_id=uuid.uuid4(),
        query="年假有几天",
        vector_limit=10,
        fts_limit=10,
        top_n=8,
        injected_variants=["变体"],
    )
    assert captured["weights"][2] == 1.0


@pytest.mark.asyncio
async def test_kb_strong_similarity_keeps_default_weight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """原问强向量分（≥0.5）→ 变体维持 query_rewrite_variant_weight，不提权。"""
    from app.services.rag import multi_query as mq

    captured = {}
    monkeypatch.setattr(settings, "query_rewrite_variant_weight", 0.7)
    monkeypatch.setattr(mq, "resolve_query_embed", _fake_route())
    monkeypatch.setattr(
        mq,
        "vector_recall_en_empty_fallback",
        AsyncMock(side_effect=lambda **kwargs: _recall_rows(uuid.uuid4(), [0.90, 0.88, 0.85])),
    )
    monkeypatch.setattr(mq, "fts_recall", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        mq, "_additive_fuse_original_priority", _make_fake_fuse(captured)
    )

    await mq.multi_query_kb_recall(
        AsyncMock(),
        kb_id=uuid.uuid4(),
        query="年假有几天",
        vector_limit=10,
        fts_limit=10,
        top_n=8,
        injected_variants=["变体"],
    )
    assert captured["weights"][2] == pytest.approx(0.7)


@pytest.mark.asyncio
async def test_workspace_low_confidence_boosts_variant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """workspace 路径同样按带分结果提权变体。"""
    from app.services.rag import multi_query as mq

    captured = {}
    monkeypatch.setattr(settings, "query_rewrite_variant_weight", 0.7)
    monkeypatch.setattr(mq, "resolve_query_embed", _fake_route())
    monkeypatch.setattr(
        mq,
        "_vector_recall_workspace",
        AsyncMock(side_effect=lambda *a, **kwargs: _recall_rows(uuid.uuid4(), [0.24, 0.22, 0.20])),
    )
    monkeypatch.setattr(mq, "_fts_recall_workspace", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        mq, "_additive_fuse_original_priority", _make_fake_fuse(captured)
    )

    await mq.multi_query_workspace_recall(
        AsyncMock(),
        query="年假有几天",
        scope=None,
        org_scope=None,
        vector_limit=10,
        fts_limit=10,
        top_n=8,
        scope_clause=None,
        injected_variants=["变体"],
    )
    assert captured["weights"][2] == 1.0


@pytest.mark.asyncio
async def test_workspace_strong_similarity_keeps_default_weight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.rag import multi_query as mq

    captured = {}
    monkeypatch.setattr(settings, "query_rewrite_variant_weight", 0.7)
    monkeypatch.setattr(mq, "resolve_query_embed", _fake_route())
    monkeypatch.setattr(
        mq,
        "_vector_recall_workspace",
        AsyncMock(side_effect=lambda *a, **kwargs: _recall_rows(uuid.uuid4(), [0.91, 0.87, 0.84])),
    )
    monkeypatch.setattr(mq, "_fts_recall_workspace", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        mq, "_additive_fuse_original_priority", _make_fake_fuse(captured)
    )

    await mq.multi_query_workspace_recall(
        AsyncMock(),
        query="年假有几天",
        scope=None,
        org_scope=None,
        vector_limit=10,
        fts_limit=10,
        top_n=8,
        scope_clause=None,
        injected_variants=["变体"],
    )
    assert captured["weights"][2] == pytest.approx(0.7)
