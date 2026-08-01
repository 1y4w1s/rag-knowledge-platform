"""条件多查询：effective_query_rewrite_policy / should_expand_queries / 短问。"""

from __future__ import annotations

import uuid

import pytest

from app.core.config import settings
from app.services.rag.planner import (
    effective_query_rewrite_policy,
    is_short_query_for_rewrite,
    should_expand_queries,
)
from app.services.rag.types import RetrievedChunk


def _chunk(*, similarity: float = 0.5) -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        doc_name="doc.md",
        content="内容",
        page_number=1,
        section_title=None,
        heading_path=None,
        similarity=similarity,
    )


def test_effective_policy_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "query_rewrite_policy", "off")
    monkeypatch.setattr(settings, "query_rewrite_enabled", False)
    assert effective_query_rewrite_policy() == "off"


def test_effective_policy_bridge_enabled_to_always(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "query_rewrite_policy", "off")
    monkeypatch.setattr(settings, "query_rewrite_enabled", True)
    assert effective_query_rewrite_policy() == "always"


def test_effective_policy_conditional_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "query_rewrite_policy", "conditional")
    monkeypatch.setattr(settings, "query_rewrite_enabled", False)
    assert effective_query_rewrite_policy() == "conditional"


def test_short_query_boundary() -> None:
    assert is_short_query_for_rewrite("年假") is True  # 2
    assert is_short_query_for_rewrite("年假？") is True  # 去标点 → 2
    assert is_short_query_for_rewrite("年假天") is True  # 3
    assert is_short_query_for_rewrite("年假有多少天？") is False  # 去标点 → 6
    assert is_short_query_for_rewrite("迟到怎么处理？") is False


def test_empty_pool_expands() -> None:
    assert should_expand_queries("任意足够长的问句内容", []) is True


def test_single_candidate_expands() -> None:
    assert should_expand_queries("任意足够长的问句内容", [_chunk()]) is True


def test_two_candidates_with_fts_skips() -> None:
    chunks = [_chunk(), _chunk()]
    assert (
        should_expand_queries(
            "任意足够长的问句内容", chunks, has_effective_fts=True
        )
        is False
    )


def test_two_candidates_without_fts_expands() -> None:
    chunks = [_chunk(), _chunk()]
    assert (
        should_expand_queries(
            "任意足够长的问句内容", chunks, has_effective_fts=False
        )
        is True
    )


def test_three_candidates_without_fts_skips() -> None:
    """≥3 候选且无 FTS 也不扩（避免 mock 低 sim 误伤）。"""
    chunks = [_chunk(), _chunk(), _chunk()]
    assert (
        should_expand_queries(
            "任意足够长的问句内容", chunks, has_effective_fts=False
        )
        is False
    )


@pytest.mark.asyncio
async def test_conditional_short_query_calls_multi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """conditional + 超短问 → 直扩 multi_query，不走单问探针。"""
    from unittest.mock import AsyncMock

    from app.services.rag import retrieval as retrieval_mod
    from app.services.rag.types import RetrievedChunk, _RecallRow

    monkeypatch.setattr(settings, "query_rewrite_policy", "conditional")
    monkeypatch.setattr(settings, "query_rewrite_enabled", False)
    monkeypatch.setattr(retrieval_mod, "query_cache_enabled", lambda: False)
    monkeypatch.setattr(settings, "clause_route_enabled", False)

    kb_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    fake_chunk = type(
        "C",
        (),
        {
            "id": chunk_id,
            "document_id": uuid.uuid4(),
            "content": "年假五天",
            "page_number": 1,
            "section_title": None,
            "heading_path": None,
            "parent_chunk_id": None,
            "kb_id": kb_id,
        },
    )()
    row = _RecallRow(
        chunk=fake_chunk, filename="x.md", vector_similarity=0.9, fts_rank=0.1
    )
    fused = [(chunk_id, 1.0)]
    merged = {chunk_id: row}
    mq_calls = {"n": 0}
    single_calls = {"n": 0}

    async def _fake_mq(db, **kwargs):
        mq_calls["n"] += 1
        return fused, merged, ["年假"]

    async def _fake_single(*a, **k):
        single_calls["n"] += 1
        return fused, merged, None, None, [row]

    monkeypatch.setattr(
        "app.services.rag.multi_query.multi_query_kb_recall", _fake_mq
    )
    monkeypatch.setattr(retrieval_mod, "_kb_single_hybrid", _fake_single)
    monkeypatch.setattr(
        retrieval_mod, "load_parent_contents", AsyncMock(return_value={})
    )

    result = await retrieval_mod.retrieve_chunks(
        AsyncMock(), kb_id=kb_id, query="年假", top_k=3
    )
    assert mq_calls["n"] == 1
    assert single_calls["n"] == 0
    assert len(result) == 1
    assert isinstance(result[0], RetrievedChunk)


@pytest.mark.asyncio
async def test_conditional_strong_pool_skips_multi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """conditional + 长问 + ≥3 候选有 FTS → 不扩。"""
    from unittest.mock import AsyncMock

    from app.services.rag import retrieval as retrieval_mod
    from app.services.rag.types import _RecallRow

    monkeypatch.setattr(settings, "query_rewrite_policy", "conditional")
    monkeypatch.setattr(settings, "query_rewrite_enabled", False)
    monkeypatch.setattr(retrieval_mod, "query_cache_enabled", lambda: False)
    monkeypatch.setattr(settings, "clause_route_enabled", False)

    kb_id = uuid.uuid4()
    ids = [uuid.uuid4() for _ in range(3)]
    rows = {}
    fused = []
    for i, cid in enumerate(ids):
        fake = type(
            "C",
            (),
            {
                "id": cid,
                "document_id": uuid.uuid4(),
                "content": f"内容{i}",
                "page_number": 1,
                "section_title": None,
                "heading_path": None,
                "parent_chunk_id": None,
                "kb_id": kb_id,
            },
        )()
        rows[cid] = _RecallRow(
            chunk=fake, filename="x.md", vector_similarity=0.75 - i * 0.05, fts_rank=0.2
        )
        fused.append((cid, 0.03 - i * 0.001))

    mq_calls = {"n": 0}

    async def _fake_mq(db, **kwargs):
        mq_calls["n"] += 1
        return fused, rows, ["q"]

    async def _fake_single(*a, **k):
        return fused, rows, ids[:3], ids[:3], list(rows.values())

    monkeypatch.setattr(
        "app.services.rag.multi_query.multi_query_kb_recall", _fake_mq
    )
    monkeypatch.setattr(retrieval_mod, "_kb_single_hybrid", _fake_single)
    monkeypatch.setattr(
        retrieval_mod, "load_parent_contents", AsyncMock(return_value={})
    )

    await retrieval_mod.retrieve_chunks(
        AsyncMock(),
        kb_id=kb_id,
        query="员工入职满一年后年假有多少天可以申请",
        top_k=3,
    )
    assert mq_calls["n"] == 0
