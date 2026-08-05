"""F1：citation 硬对齐单元测试。"""

from __future__ import annotations

import uuid

from app.services.rag.citation_align import (
    align_citations_to_answer,
    align_chunks_to_answer,
    parse_fragment_indices,
)
from app.services.rag.confidence_reply import PARTIAL_DISCLAIMER_ZH
from app.services.rag.executor import chunk_to_citation
from app.services.rag.types import RetrievedChunk


def _chunk(content: str = "内容", similarity: float = 0.9) -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        doc_name="doc.md",
        content=content,
        page_number=1,
        section_title="§1",
        heading_path=None,
        similarity=similarity,
    )


def test_parse_fragment_indices_dedup_order() -> None:
    assert parse_fragment_indices("见[片段3]与[片段1]，再[片段3]") == [3, 1]


def test_align_over_cite_prune() -> None:
    chunks = [_chunk("a"), _chunk("b"), _chunk("c")]
    aligned = align_chunks_to_answer("年假 10 天[片段1][片段3]", chunks)
    assert [c.content for c in aligned] == ["a", "c"]


def test_align_phantom_index_dropped() -> None:
    chunks = [_chunk("a"), _chunk("b"), _chunk("c")]
    aligned = align_chunks_to_answer("乱标[片段9]但真用[片段2]", chunks)
    assert [c.content for c in aligned] == ["b"]


def test_align_no_markers_keep_all() -> None:
    chunks = [_chunk("a"), _chunk("b"), _chunk("c")]
    aligned = align_chunks_to_answer("年假有 10 天。", chunks)
    assert aligned == chunks


def test_align_empty_chunks() -> None:
    assert align_chunks_to_answer("[片段1]", []) == []


def test_align_strips_e3_disclaimer_prefix() -> None:
    chunks = [_chunk("a"), _chunk("b"), _chunk("c")]
    answer = f"{PARTIAL_DISCLAIMER_ZH}\n\n正式员工年假 10 天[片段2]。"
    aligned = align_chunks_to_answer(
        answer, chunks, strip_prefix=PARTIAL_DISCLAIMER_ZH
    )
    assert [c.content for c in aligned] == ["b"]


def test_align_marker_order_not_pool_order() -> None:
    chunks = [_chunk("a"), _chunk("b"), _chunk("c")]
    aligned = align_chunks_to_answer("先[片段3]后[片段1]", chunks)
    assert [c.content for c in aligned] == ["c", "a"]


def test_align_uses_build_messages_similarity_order() -> None:
    """H1：编号映射与 build_messages 一致（similarity 升序）。

    相似度顺序 ≠ 检索顺序时，[片段N] 必须按 build_messages 的排序解析，
    否则 LLM 正确标注的编号会被错位映射（GQ-47 实测：4.1 → 片段2 被映射到 6.3）。
    """
    chunks = [
        _chunk(content="9.3 绩效", similarity=0.9),
        _chunk(content="4.1 培训", similarity=0.5),
        _chunk(content="5.1 离职通知期", similarity=0.54),
    ]
    # build_messages 排序：0.5 → 片段1，0.54 → 片段2，0.9 → 片段3
    aligned = align_chunks_to_answer(
        "培训费用按比例退还[片段1]；离职需支付代通知金[片段2]。", chunks
    )
    assert [c.content for c in aligned] == ["4.1 培训", "5.1 离职通知期"]


def test_align_citations_to_answer_payload() -> None:
    chunks = [_chunk("a"), _chunk("b"), _chunk("c")]
    cites = align_citations_to_answer(
        "依据[片段2]",
        chunks,
        to_citation=chunk_to_citation,
    )
    assert len(cites) == 1
    assert cites[0]["chunk_id"] == str(chunks[1].chunk_id)
