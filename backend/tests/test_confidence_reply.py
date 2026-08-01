"""E3：低置信度三档与确定性话术。"""

from uuid import uuid4

from app.services.rag.confidence_reply import (
    PARTIAL_DISCLAIMER_EN,
    PARTIAL_DISCLAIMER_ZH,
    AnswerConfidence,
    classify_answer_confidence,
    is_low_confidence,
    partial_answer_disclaimer_for,
    with_partial_disclaimer,
)
from app.services.rag.generation import NO_CONTEXT_REPLY, build_messages
from app.services.rag.types import RetrievedChunk


def _chunk(
    *,
    content: str,
    similarity: float = 0.1,
    section_title: str | None = "1.1 年假",
) -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=uuid4(),
        chunk_id=uuid4(),
        document_id=uuid4(),
        doc_name="handbook.md",
        content=content,
        page_number=None,
        section_title=section_title,
        heading_path=None,
        similarity=similarity,
    )


def test_classify_refuse_when_no_relevant_context() -> None:
    """与 engine 一致：filter 后空列表 → refuse。"""
    assert classify_answer_confidence([], "年假有几天？") is AnswerConfidence.refuse


def test_classify_normal_when_strong_similarity_even_if_two_chunks() -> None:
    """adaptive_top_k 高置信常只给 2 条，不得误标 low。"""
    chunks = [
        _chunk(content="员工年满一年后可享受年假10天。", similarity=0.88),
        _chunk(content="年假须提前申请。", similarity=0.86),
    ]
    assert classify_answer_confidence(chunks, "年假有几天？") is AnswerConfidence.normal
    assert is_low_confidence(chunks) is False


def test_classify_low_when_weak_similarity_with_overlap() -> None:
    chunks = [_chunk(content="员工年满一年后可享受年假10天。", similarity=0.32)]
    assert classify_answer_confidence(chunks, "年假有几天？") is AnswerConfidence.low


def test_classify_low_when_fts_only_sparse() -> None:
    chunks = [_chunk(content="员工年满一年后可享受年假10天。", similarity=0.0)]
    assert classify_answer_confidence(chunks, "年假有几天？") is AnswerConfidence.low


def test_classify_low_s3_universally_weak_vectors() -> None:
    chunks = [
        _chunk(content="员工年假10天。", similarity=0.20),
        _chunk(content="年假须书面申请。", similarity=0.22),
        _chunk(content="年假不可跨年。", similarity=0.18),
    ]
    assert is_low_confidence(chunks) is True
    assert classify_answer_confidence(chunks, "年假几天") is AnswerConfidence.low


def test_disclaimer_zh_en() -> None:
    assert partial_answer_disclaimer_for("年假几天？") == PARTIAL_DISCLAIMER_ZH
    assert partial_answer_disclaimer_for("How many leave days?") == PARTIAL_DISCLAIMER_EN


def test_with_partial_disclaimer_idempotent() -> None:
    body = "正式员工年假 10 天。"
    once = with_partial_disclaimer("年假几天？", body)
    assert once.startswith(PARTIAL_DISCLAIMER_ZH)
    assert "年假 10 天" in once
    assert with_partial_disclaimer("年假几天？", once) == once


def test_low_not_equal_to_full_refusal_copy() -> None:
    assert PARTIAL_DISCLAIMER_ZH != NO_CONTEXT_REPLY
    assert PARTIAL_DISCLAIMER_ZH not in NO_CONTEXT_REPLY


def test_build_messages_low_adds_partial_prompt_note() -> None:
    chunks = [_chunk(content="员工年满一年后可享受年假10天。", similarity=0.30)]
    messages = build_messages(
        "年假有几天？",
        chunks,
        answer_confidence=AnswerConfidence.low,
    )
    blob = "\n".join(m["content"] for m in messages)
    assert "低置信度约束" in blob
    assert "禁止推测或编造" in blob
