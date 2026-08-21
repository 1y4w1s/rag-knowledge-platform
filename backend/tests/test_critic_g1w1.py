"""G1-W1 / G1-W1b：Critic 规则 claim + chat/agent 挂点（默认关）。"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.core.degradation import DegradationLevel
from app.services.agent.stream import _stream_generation_phase
from app.services.rag.confidence_reply import AnswerConfidence
from app.services.rag.critic import (
    METHOD_RULES_V1,
    METHOD_SKIPPED,
    critique_answer_rules,
    run_critic,
)
from app.services.rag.feedback_attribution import (
    LABEL_GENERATION_BAD,
    LABEL_UNKNOWN,
)
from app.services.rag.generation import no_context_reply_for
from app.services.rag.retrieval import chunk_to_citation
from app.services.rag.types import RetrievedChunk


def _chunk(content: str, *, similarity: float = 0.9) -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        doc_name="制度.md",
        content=content,
        page_number=1,
        section_title="4.1 培训",
        heading_path="4.1 培训",
        similarity=similarity,
        parent_content=None,
    )


def test_defaults_remain_off() -> None:
    assert settings.rag_critic_enabled is False
    assert settings.self_verify_enabled is False
    assert settings.rag_critic_mode == "rules"
    assert settings.rag_critic_on_fail == "fail_closed"


# ── G1-W3：小数点 / 节号句切护栏 ─────────────────────────────────────────


def test_decimal_multiplier_with_citation_passes() -> None:
    """T1：含 1.5 + 句末 [片段1] → rules ok=True（勿把小数点当句号）。"""
    chunks = [_chunk("工作日加班按基本工资1.5倍计算加班费。")]
    answer = "工作日加班按基本工资 1.5 倍计算加班费[片段1]。"
    result = critique_answer_rules(answer, chunks)
    assert result.ok is True
    assert result.metadata["critic.failed_claim_count"] == 0


def test_section_number_with_citation_passes() -> None:
    """T2：含章节 1.1 + [片段1] → ok=True。"""
    chunks = [_chunk("见第1.1节考勤规定，迟到三次记旷工半天。")]
    answer = "见第 1.1 节考勤规定，迟到三次记旷工半天[片段1]。"
    result = critique_answer_rules(answer, chunks)
    assert result.ok is True
    assert result.metadata["critic.failed_claim_count"] == 0


def test_filename_extension_dot_not_sentence_split() -> None:
    """文件名 .md 中的点不分句（GQ-4 类：handbook.md + 1.1 + 引用）。"""
    chunk = RetrievedChunk(
        kb_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        doc_name="golden_handbook.md",
        content="员工年满一年后可享受年假10天。年假须提前两周申请。",
        page_number=1,
        section_title="1.1 年假",
        heading_path="1.1 年假",
        similarity=1.0,
        parent_content=None,
    )
    answer = "年假10天在 golden_handbook.md 的 1.1 年假 章节[片段1]。"
    result = critique_answer_rules(answer, [chunk])
    assert result.ok is True
    assert result.metadata["critic.failed_claim_count"] == 0


def test_true_missing_citation_still_fails_without_decimal() -> None:
    """T3：真缺引用断言句（无小数干扰）→ 仍 ok=False / missing cite。"""
    chunks = [_chunk("正式员工每月餐补为300元。")]
    answer = "正式员工每月餐补为300元。"
    result = critique_answer_rules(answer, chunks)
    assert result.ok is False
    assert result.label == LABEL_GENERATION_BAD
    assert "missing" in (result.rationale or "")


def test_ascii_sentence_end_dot_still_splits() -> None:
    """真句末 ASCII . 仍分句：前半无引用须拦，后半有引用可通过校验链。"""
    chunks = [_chunk("Training fee must be refunded proportionally after early resignation.")]
    answer = (
        "Training fee is fully waived. "
        "Training fee must be refunded proportionally[片段1]."
    )
    result = critique_answer_rules(answer, chunks)
    assert result.ok is False
    assert "missing" in (result.rationale or "")


def test_valid_citation_with_evidence_passes() -> None:
    chunks = [_chunk("员工参加培训后提前离职，需按比例退还培训费用。")]
    answer = "培训费需按比例退还[片段1]。"
    result = critique_answer_rules(answer, chunks)
    assert result.ok is True
    assert result.method == METHOD_RULES_V1
    assert result.label == LABEL_UNKNOWN
    assert result.metadata["critic.failed_claim_count"] == 0


def test_out_of_range_citation_fails_generation_bad() -> None:
    chunks = [_chunk("员工参加培训后提前离职，需按比例退还培训费用。")]
    answer = "培训费全额退还[片段9]。"
    result = critique_answer_rules(answer, chunks)
    assert result.ok is False
    assert result.label == LABEL_GENERATION_BAD
    assert result.method == METHOD_RULES_V1
    assert any(not c.ok for c in result.claims)
    assert "out of range" in (result.rationale or "")


def test_missing_citation_on_assertive_claim_fails() -> None:
    chunks = [_chunk("正式员工每月餐补为300元。")]
    answer = "正式员工每月餐补为300元。"
    result = critique_answer_rules(answer, chunks)
    assert result.ok is False
    assert result.label == LABEL_GENERATION_BAD
    assert "missing" in (result.rationale or "")


def test_shallow_evidence_miss_fails() -> None:
    chunks = [_chunk("会议室预约需提前一天申请。")]
    answer = "年假每年15天且可拆分使用[片段1]。"
    result = critique_answer_rules(answer, chunks)
    assert result.ok is False
    assert result.label == LABEL_GENERATION_BAD
    assert "evidence" in (result.rationale or "")


def test_refusal_is_skipped() -> None:
    chunks = [_chunk("无关内容。")]
    answer = "知识库中未找到相关内容。"
    result = critique_answer_rules(answer, chunks)
    assert result.ok is True
    assert result.claims == ()
    assert result.label == LABEL_UNKNOWN


@pytest.mark.asyncio
async def test_run_critic_disabled_is_noop() -> None:
    chunks = [_chunk("员工参加培训后提前离职，需按比例退还培训费用。")]
    # 默认关：非法引用也不应改答语义（ok=True skipped）
    result = await run_critic("胡说内容[片段99]。", chunks, "培训费？")
    assert result.ok is True
    assert result.method == METHOD_SKIPPED
    assert result.metadata["critic.enabled"] is False


@pytest.mark.asyncio
async def test_run_critic_enabled_rules_catches_bad_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "rag_critic_enabled", True)
    monkeypatch.setattr(settings, "rag_critic_mode", "rules")
    chunks = [_chunk("员工参加培训后提前离职，需按比例退还培训费用。")]
    result = await run_critic("培训费全额退还[片段9]。", chunks, "培训费？")
    assert result.ok is False
    assert result.label == LABEL_GENERATION_BAD
    assert result.method == METHOD_RULES_V1


# ── G1-W1b：agent stream 薄挂 ─────────────────────────────────────────────


def _agent_plan(chunk: RetrievedChunk) -> SimpleNamespace:
    return SimpleNamespace(
        citations=tuple(chunk_to_citation(chunk)),
        refusal=False,
        gated_chunks=(chunk,),
        external_context="",
    )


def _parse_sse(frame: str) -> dict[str, Any]:
    lines = frame.strip().splitlines()
    return {
        "event": lines[0].removeprefix("event: ").strip(),
        "data": json.loads(lines[1].removeprefix("data: ").strip()),
    }


async def _collect_generation(
    monkeypatch: pytest.MonkeyPatch,
    *,
    answer_text: str,
    chunk: RetrievedChunk,
    state: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from sqlalchemy.ext.asyncio import AsyncSession

    async def _llm(_messages: list) -> AsyncIterator[str]:
        yield answer_text

    monkeypatch.setattr(
        "app.services.agent.stream.assess_degradation",
        lambda: DegradationLevel.NORMAL,
    )
    monkeypatch.setattr(
        "app.services.agent.stream.classify_answer_confidence",
        lambda _chunks, _q: AnswerConfidence.normal,
    )
    monkeypatch.setattr(
        "app.services.agent.stream.has_available_chat_provider_key",
        lambda: True,
    )
    monkeypatch.setattr("app.services.agent.stream.stream_deepseek_tokens", _llm)

    out_state = state or {
        "content": "",
        "citations": [],
        "retrieval_duration_ms": None,
    }
    events: list[dict[str, Any]] = []
    async for frame in _stream_generation_phase(
        AsyncMock(spec=AsyncSession),
        message="培训费怎么退？",
        gen_plan=_agent_plan(chunk),
        outcome=SimpleNamespace(run_id=uuid.uuid4(), steps=()),
        user_id=uuid.uuid4(),
        history=None,
        assistant_message_id=uuid.uuid4(),
        state=out_state,
    ):
        events.append(_parse_sse(frame))
    return events, out_state


@pytest.mark.asyncio
async def test_agent_stream_critic_disabled_is_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """默认关：非法引用仍原样落 state，无 correction 事件。"""
    assert settings.rag_critic_enabled is False
    chunk = _chunk("员工参加培训后提前离职，需按比例退还培训费用。")
    events, state = await _collect_generation(
        monkeypatch,
        answer_text="培训费全额退还[片段9]。",
        chunk=chunk,
    )
    assert not any(e["event"] == "correction" for e in events)
    assert state["content"] == "培训费全额退还[片段9]。"
    assert events[-1]["event"] == "done"


@pytest.mark.asyncio
async def test_agent_stream_critic_fail_closed_emits_correction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """显式开 rules：越界引用 → fail_closed 拒答 + correction + 清空引用。"""
    monkeypatch.setattr(settings, "rag_critic_enabled", True)
    monkeypatch.setattr(settings, "rag_critic_mode", "rules")
    monkeypatch.setattr(settings, "rag_critic_on_fail", "fail_closed")
    chunk = _chunk("员工参加培训后提前离职，需按比例退还培训费用。")
    refuse = no_context_reply_for("培训费怎么退？")
    events, state = await _collect_generation(
        monkeypatch,
        answer_text="培训费全额退还[片段9]。",
        chunk=chunk,
    )
    corrections = [e["data"]["text"] for e in events if e["event"] == "correction"]
    assert corrections == [refuse]
    assert state["content"] == refuse
    assert state["citations"] == []
    done = events[-1]
    assert done["event"] == "done"
    assert done["data"]["citations"] == []


@pytest.mark.asyncio
async def test_agent_stream_critic_passes_valid_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """显式开 rules：合法引用 + 浅层证据 → 无 correction，正文保留。"""
    monkeypatch.setattr(settings, "rag_critic_enabled", True)
    monkeypatch.setattr(settings, "rag_critic_mode", "rules")
    chunk = _chunk("员工参加培训后提前离职，需按比例退还培训费用。")
    answer = "培训费需按比例退还[片段1]。"
    events, state = await _collect_generation(
        monkeypatch,
        answer_text=answer,
        chunk=chunk,
    )
    assert not any(e["event"] == "correction" for e in events)
    assert state["content"] == answer
