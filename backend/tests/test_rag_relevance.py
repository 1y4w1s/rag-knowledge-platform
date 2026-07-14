"""Wave 3.3 + Plan-RAG R4-2 检索相关性 gate 单元测试。"""

from uuid import uuid4

import pytest

from app.core.config import settings
from app.services.rag.generation import (
    NO_CONTEXT_REPLY,
    NO_CONTEXT_REPLY_EN,
    no_context_reply_for,
)
from app.services.rag.relevance import (
    _vector_scores_universally_weak,
    filter_relevant_chunks,
    has_relevant_context,
    query_overlaps_chunk,
    should_refuse_answer,
)
from app.services.rag.types import RetrievedChunk


def _chunk(
    *,
    content: str,
    section_title: str | None = None,
    similarity: float = 0.1,
    kb_id=None,
) -> RetrievedChunk:
    kid = kb_id if kb_id is not None else uuid4()
    return RetrievedChunk(
        kb_id=kid,
        chunk_id=uuid4(),
        document_id=uuid4(),
        doc_name="golden_handbook.md",
        content=content,
        page_number=None,
        section_title=section_title,
        heading_path=None,
        similarity=similarity,
    )


def test_query_overlaps_chunk_on_shared_chinese_term() -> None:
    chunk = _chunk(content="员工年满一年后可享受年假10天。", section_title="1.1 年假")
    assert query_overlaps_chunk("员工年假有几天？", chunk)


def test_query_overlaps_chunk_false_for_unrelated_topic() -> None:
    chunk = _chunk(content="员工年满一年后可享受年假10天。", section_title="1.1 年假")
    assert not query_overlaps_chunk("火星殖民计划是什么？", chunk)


def test_has_relevant_context_by_lexical_overlap_when_similarity_low() -> None:
    chunks = [_chunk(content="员工年满一年后可享受年假10天。", similarity=0.05)]
    assert has_relevant_context(chunks, "员工年假有几天？")


def test_filter_relevant_chunks_empty_for_irrelevant_query() -> None:
    chunks = [_chunk(content="员工年满一年后可享受年假10天。", similarity=0.05)]
    assert filter_relevant_chunks(chunks, "量子计算机怎么造？") == []


def test_filter_relevant_chunks_rejects_high_similarity_without_overlap() -> None:
    """R3-P1-1：向量分高但无词面重叠仍须拒绝（AC-4 无关题）。"""
    chunks = [_chunk(content="无关正文", similarity=0.9)]
    assert filter_relevant_chunks(chunks, "火星殖民计划") == []


def test_should_refuse_answer_true_when_empty() -> None:
    assert should_refuse_answer([], "年假几天？") is True


def test_should_refuse_answer_false_with_overlap() -> None:
    chunks = [_chunk(content="员工年满一年后可享受年假10天。", similarity=0.05)]
    assert should_refuse_answer(chunks, "员工年假有几天？") is False


def test_vector_scores_universally_weak_uses_settings_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "retrieval_min_top1_similarity", 0.5)
    weak = [_chunk(content="a", similarity=0.2), _chunk(content="b", similarity=0.3)]
    strong = [_chunk(content="a", similarity=0.6)]
    fts_only = [_chunk(content="a", similarity=0.0)]

    assert _vector_scores_universally_weak(weak) is True
    assert _vector_scores_universally_weak(strong) is False
    assert _vector_scores_universally_weak(fts_only) is False


def test_weak_vector_scores_still_pass_when_overlap_exists() -> None:
    """R4-2 H5：mock/FTS 低分但有词面重叠 → 仍有依据。"""
    chunks = [_chunk(content="员工年满一年后可享受年假10天。", similarity=0.1)]
    assert _vector_scores_universally_weak(chunks) is True
    assert has_relevant_context(chunks, "员工年假有几天？") is True


def test_no_context_reply_for_chinese_question() -> None:
    assert no_context_reply_for("公司上市计划是什么？") == NO_CONTEXT_REPLY


def test_no_context_reply_for_english_question() -> None:
    assert (
        no_context_reply_for("What is the company IPO plan?")
        == NO_CONTEXT_REPLY_EN
    )
