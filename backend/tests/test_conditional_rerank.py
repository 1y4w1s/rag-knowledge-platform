"""条件精排：should_run_rerank / effective_rerank_policy（Research 序 2）。"""

from __future__ import annotations

import uuid

import pytest

from app.core.config import settings
from app.services.rag.planner import effective_rerank_policy, should_run_rerank
from app.services.rag.types import RetrievedChunk


def _chunk(
    *,
    similarity: float = 0.5,
    rrf_score: float | None = None,
) -> RetrievedChunk:
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
        rrf_score=rrf_score,
    )


def test_effective_policy_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rerank_policy", "off")
    monkeypatch.setattr(settings, "rerank_enabled", False)
    assert effective_rerank_policy() == "off"


def test_effective_policy_bridge_enabled_to_always(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "rerank_policy", "off")
    monkeypatch.setattr(settings, "rerank_enabled", True)
    assert effective_rerank_policy() == "always"


def test_effective_policy_conditional_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "rerank_policy", "conditional")
    monkeypatch.setattr(settings, "rerank_enabled", False)
    assert effective_rerank_policy() == "conditional"


def test_u1_single_candidate_skips() -> None:
    assert should_run_rerank([_chunk(rrf_score=0.03)]) is False


def test_u2_high_similarity_skips() -> None:
    chunks = [
        _chunk(similarity=0.90, rrf_score=0.030),
        _chunk(similarity=0.50, rrf_score=0.029),
        _chunk(similarity=0.40, rrf_score=0.028),
    ]
    assert should_run_rerank(chunks) is False


def test_u3_large_rrf_gap_skips() -> None:
    # (0.040 - 0.020) / 0.040 = 0.50 >= 0.08
    chunks = [
        _chunk(rrf_score=0.040),
        _chunk(rrf_score=0.030),
        _chunk(rrf_score=0.020),
    ]
    assert should_run_rerank(chunks) is False


def test_u4_flat_rrf_runs() -> None:
    # (0.032 - 0.030) / 0.032 = 0.0625 < 0.08
    chunks = [
        _chunk(rrf_score=0.032),
        _chunk(rrf_score=0.031),
        _chunk(rrf_score=0.030),
    ]
    assert should_run_rerank(chunks) is True


def test_u5_low_channel_jaccard_runs() -> None:
    a, b, c, d, e, f = (uuid.uuid4() for _ in range(6))
    flat = [
        _chunk(rrf_score=0.032),
        _chunk(rrf_score=0.031),
        _chunk(rrf_score=0.030),
    ]
    assert (
        should_run_rerank(
            flat,
            vector_top_ids=[a, b, c],
            fts_top_ids=[d, e, f],
        )
        is True
    )


def test_u5b_low_jaccard_with_large_gap_still_skips() -> None:
    """硬排除：RRF 已拉开时，即使两路 Jaccard 低也不精排。"""
    a, b, c, d, e, f = (uuid.uuid4() for _ in range(6))
    chunks = [
        _chunk(rrf_score=0.040),
        _chunk(rrf_score=0.030),
        _chunk(rrf_score=0.020),
    ]
    assert (
        should_run_rerank(
            chunks,
            vector_top_ids=[a, b, c],
            fts_top_ids=[d, e, f],
        )
        is False
    )


def test_u6_high_overlap_and_large_gap_skips() -> None:
    ids = [uuid.uuid4() for _ in range(3)]
    chunks = [
        _chunk(rrf_score=0.040),
        _chunk(rrf_score=0.030),
        _chunk(rrf_score=0.020),
    ]
    assert (
        should_run_rerank(
            chunks,
            vector_top_ids=ids,
            fts_top_ids=list(ids),
        )
        is False
    )


def test_u7_no_rrf_no_channel_ids_skips() -> None:
    chunks = [
        _chunk(similarity=0.5, rrf_score=None),
        _chunk(similarity=0.4, rrf_score=None),
        _chunk(similarity=0.3, rrf_score=None),
    ]
    assert should_run_rerank(chunks) is False


def test_u5c_jaccard_only_when_no_hard_gap() -> None:
    """无 rrf_score 时仅靠两路分歧介入。"""
    a, b, c, d, e, f = (uuid.uuid4() for _ in range(6))
    chunks = [
        _chunk(rrf_score=None),
        _chunk(rrf_score=None),
        _chunk(rrf_score=None),
    ]
    assert (
        should_run_rerank(
            chunks,
            vector_top_ids=[a, b, c],
            fts_top_ids=[d, e, f],
        )
        is True
    )
    assert (
        should_run_rerank(
            chunks,
            vector_top_ids=[a, b, c],
            fts_top_ids=[a, b, c],
        )
        is False
    )
