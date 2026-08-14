"""W1 多语言降级文案：degradation_message language 参数 + 英文组装。"""

from __future__ import annotations

import uuid

from app.core.degradation import (
    DegradationLevel,
    LLM_DOWN_MESSAGE_EN,
    degradation_message,
)
from app.services.rag.confidence_reply import (
    PARTIAL_DISCLAIMER_EN,
    partial_answer_disclaimer_for,
)
from app.services.rag.degraded_answer import build_degraded_fragment_reply
from app.services.rag.generation import NO_CONTEXT_REPLY_EN, no_context_reply_for
from app.services.rag.types import RetrievedChunk


def _chunk(
    *,
    content: str = "正式员工年假 10 天。",
    doc_name: str = "员工手册.md",
    page_number: int | None = 3,
    section_title: str | None = "1.2 年假",
) -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        doc_name=doc_name,
        content=content,
        page_number=page_number,
        section_title=section_title,
        heading_path=section_title,
        similarity=0.92,
        parent_content=None,
    )


def _degradation_text() -> str:
    return degradation_message(DegradationLevel.LLM_DOWN)


def test_build_degraded_fragment_reply_english() -> None:
    """英文 query → 英文说明 + [Fragment N] / Page / Section，正文保持原文。"""
    query = "How many annual leave days do employees get?"
    reply = build_degraded_fragment_reply(query, [_chunk()])

    assert reply.startswith(
        degradation_message(DegradationLevel.LLM_DOWN, language="en")
    )
    assert "[Fragment 1]" in reply
    assert '"员工手册.md"' in reply
    assert "Page 3" in reply
    assert "Section: 1.2 年假" in reply
    assert "正式员工年假 10 天。" in reply
    assert "[片段1]" not in reply
    # 与 R4-2 / E3 对同一 query 的判定保持一致
    assert no_context_reply_for(query) == NO_CONTEXT_REPLY_EN
    assert partial_answer_disclaimer_for(query) == PARTIAL_DISCLAIMER_EN


def test_build_degraded_fragment_reply_chinese_exact() -> None:
    """中文 query → 与现状逐字节一致（说明、[片段1]、《》、页码、章节）。"""
    query = "员工年假有几天？"
    expected = (
        f"{_degradation_text()}\n"
        "[片段1] 《员工手册.md》 · 第3页 · 章节：1.2 年假：正式员工年假 10 天。"
    )
    assert build_degraded_fragment_reply(query, [_chunk()]) == expected
    # 与 R4-2 / E3 对同一 query 的判定保持一致（中文分支）
    assert no_context_reply_for(query) != NO_CONTEXT_REPLY_EN
    assert partial_answer_disclaimer_for(query) != PARTIAL_DISCLAIMER_EN


def test_empty_or_mixed_query_falls_back_zh() -> None:
    """空 / 无法判定 query → 默认中文说明与 meta（与拒答兜底一致）。"""
    for query in ("", "  ", "AI 与年假 Q2 2026"):
        reply = build_degraded_fragment_reply(query, [_chunk()])
        assert reply.startswith(_degradation_text())
        assert "[片段1]" in reply


def test_degradation_message_english_only_for_llm_down() -> None:
    """英文文案仅 LLM_DOWN 预埋；默认中文逐字不变，其他等级不预埋英文。"""
    assert (
        degradation_message(DegradationLevel.LLM_DOWN, language="en")
        == LLM_DOWN_MESSAGE_EN
    )
    assert degradation_message(DegradationLevel.LLM_DOWN) == _degradation_text()
    assert (
        degradation_message(DegradationLevel.LLM_DOWN, language="zh")
        == _degradation_text()
    )
    assert (
        degradation_message(DegradationLevel.ALL_DOWN, language="en")
        == degradation_message(DegradationLevel.ALL_DOWN)
    )
