"""W1 fast 路径 L1 降级：返回原文片段 + 降级说明（无 LLM、不写缓存）。"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.core.degradation import (
    DegradationLevel,
    degradation_message,
    reset_stabilization,
)
from app.services.agent.finalize import AgentGenerationPlan
from app.services.agent.stream import _stream_generation_phase
from app.services.agent.types import AgentRunOutcome
from app.services.agent.working_memory import WindowedPromptHistory
from app.services.rag.citation_align import align_citations_to_answer
from app.services.rag.confidence_reply import AnswerConfidence
from app.services.rag.degraded_answer import build_degraded_fragment_reply
from app.services.rag.engine import ChatEngine
from app.services.rag.retrieval import chunk_to_citation
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


_EN_QUERY = "How many annual leave days do employees get?"


def _en_degradation_text() -> str:
    return degradation_message(DegradationLevel.LLM_DOWN, language="en")


def _assert_english_degraded_tokens(tokens: str, *, chunk_count: int = 1) -> None:
    assert tokens.startswith(_en_degradation_text())
    assert "[Fragment 1]" in tokens
    assert '"员工手册.md"' in tokens
    assert "Page 3" in tokens
    assert "Section: 1.2 年假" in tokens
    assert "正式员工年假 10 天。" in tokens
    assert "[片段1]" not in tokens
    assert _degradation_text() not in tokens
    if chunk_count > 1:
        assert "[Fragment 2]" in tokens
        assert "Page 7" in tokens


@pytest.fixture(autouse=True)
def _reset_degradation() -> None:
    reset_stabilization()


async def _run_engine(
    monkeypatch: pytest.MonkeyPatch,
    *,
    chunks: list[RetrievedChunk],
    level: DegradationLevel,
    query: str = "员工年假有几天？",
) -> tuple[list[dict], dict[str, Any]]:
    """构造隔离的 ChatEngine 并收集 SSE 事件（不依赖 DB）。"""
    engine = ChatEngine(
        MagicMock(),
        user_id=uuid.uuid4(),
        message=query,
        kb_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
    )

    async def _hist() -> None:
        engine.history = []
        engine.retrieval_query = query

    async def _retrieve() -> list:
        engine.chunks = chunks
        return chunks

    saved: dict[str, Any] = {}

    async def _save(content: str, citations: list) -> UUID:
        saved["content"] = content
        saved["citations"] = citations
        return uuid.uuid4()

    monkeypatch.setattr(engine, "_load_history", _hist)
    monkeypatch.setattr(engine, "_retrieve", _retrieve)
    monkeypatch.setattr(engine, "_save", _save)
    monkeypatch.setattr(
        "app.services.rag.engine.classify_answer_confidence",
        lambda chunks_, _q: (
            AnswerConfidence.refuse if not chunks_ else AnswerConfidence.normal
        ),
    )
    monkeypatch.setattr("app.services.rag.engine.assess_degradation", lambda: level)

    events: list[dict] = []
    async for event in engine.stream():
        events.append(event)
    return events, saved


def test_build_degraded_fragment_reply() -> None:
    """L1 组装：降级说明 + [片段N] + 文档名/页码/章节 + 300 字符截断。"""
    long_body = "甲" * 400
    reply = build_degraded_fragment_reply(
        "员工年假有几天？",
        [
            _chunk(),
            _chunk(
                content=long_body,
                doc_name="考勤制度.md",
                page_number=None,
                section_title=None,
            ),
        ],
    )

    assert reply.startswith(_degradation_text())
    assert "[片段1]" in reply
    assert "《员工手册.md》" in reply
    assert "第3页" in reply
    assert "1.2 年假" in reply
    assert "[片段2]" in reply
    assert "考勤制度.md" in reply
    assert "甲" * 300 in reply
    assert "甲" * 301 not in reply


@pytest.mark.asyncio
async def test_fast_precheck_skips_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """前置判定：LLM_DOWN 时不再触发任何 LLM 辅助调用。"""
    llm_calls = 0

    async def _llm(_messages: list) -> AsyncIterator[str]:
        nonlocal llm_calls
        llm_calls += 1
        yield "不应到达"

    monkeypatch.setattr("app.services.rag.engine.stream_deepseek_tokens", _llm)
    compress_calls = 0

    async def _compress(_history: list) -> None:
        nonlocal compress_calls
        compress_calls += 1
        return None

    monkeypatch.setattr("app.services.rag.engine.compress_history", _compress)

    events, saved = await _run_engine(
        monkeypatch,
        chunks=[_chunk()],
        level=DegradationLevel.LLM_DOWN,
    )

    event_names = [e["event"] for e in events]
    assert event_names.index("citation") < event_names.index("token")
    assert event_names[-1] == "done"
    assert llm_calls == 0
    assert compress_calls == 0
    tokens = "".join(e["data"]["text"] for e in events if e["event"] == "token")
    assert _degradation_text() in tokens
    done = next(e["data"] for e in events if e["event"] == "done")
    assert done["citations"]
    assert saved["content"] == tokens
    assert saved["citations"]


@pytest.mark.asyncio
async def test_fast_precheck_skips_llm_english(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """前置判定英文分支：LLM_DOWN + 英文 query → 英文说明与片段 meta。"""
    llm_calls = 0

    async def _llm(_messages: list) -> AsyncIterator[str]:
        nonlocal llm_calls
        llm_calls += 1
        yield "不应到达"

    monkeypatch.setattr("app.services.rag.engine.stream_deepseek_tokens", _llm)
    compress_calls = 0

    async def _compress(_history: list) -> None:
        nonlocal compress_calls
        compress_calls += 1
        return None

    monkeypatch.setattr("app.services.rag.engine.compress_history", _compress)

    events, saved = await _run_engine(
        monkeypatch,
        chunks=[_chunk()],
        level=DegradationLevel.LLM_DOWN,
        query=_EN_QUERY,
    )

    event_names = [e["event"] for e in events]
    assert event_names.index("citation") < event_names.index("token")
    assert event_names[-1] == "done"
    assert llm_calls == 0
    assert compress_calls == 0
    tokens = "".join(e["data"]["text"] for e in events if e["event"] == "token")
    _assert_english_degraded_tokens(tokens)
    done = next(e["data"] for e in events if e["event"] == "done")
    assert done["citations"]
    assert saved["content"] == tokens
    assert saved["citations"]


@pytest.mark.asyncio
async def test_fast_exception_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """异常兜底：前置健康但 LLM 流抛异常 → 切降级流，不向用户裸露异常。"""
    async def _boom(_messages: list) -> AsyncIterator[str]:
        raise RuntimeError("mock: 上游服务不可用 (502)")
        yield  # pragma: no cover

    monkeypatch.setattr("app.services.rag.engine.stream_deepseek_tokens", _boom)
    cache_get = AsyncMock(return_value=None)
    cache_set = AsyncMock()
    monkeypatch.setattr(
        "app.services.rag.engine.llm_response_cache.get",
        cache_get,
    )
    monkeypatch.setattr(
        "app.services.rag.engine.llm_response_cache.set",
        cache_set,
    )

    events, saved = await _run_engine(
        monkeypatch,
        chunks=[_chunk()],
        level=DegradationLevel.NORMAL,
    )

    event_names = [e["event"] for e in events]
    assert event_names.index("citation") < event_names.index("token")
    assert event_names[-1] == "done"
    assert "error" not in event_names
    tokens = "".join(e["data"]["text"] for e in events if e["event"] == "token")
    assert _degradation_text() in tokens
    done = next(e["data"] for e in events if e["event"] == "done")
    assert done["citations"]
    cache_set.assert_not_awaited()


@pytest.mark.asyncio
async def test_fast_refuse_wins_over_degradation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """拒答边界：gate 无依据时 L1 不拦截，仍走固定拒答 + 空 citations。"""
    monkeypatch.setattr(
        "app.services.rag.engine.classify_answer_confidence",
        lambda _chunks, _q: AnswerConfidence.refuse,
    )

    events, saved = await _run_engine(
        monkeypatch,
        chunks=[],
        level=DegradationLevel.LLM_DOWN,
    )

    assert not any(e["event"] == "citation" for e in events)
    tokens = "".join(e["data"]["text"] for e in events if e["event"] == "token")
    assert "未找到" in tokens
    assert _degradation_text() not in tokens
    done = next(e["data"] for e in events if e["event"] == "done")
    assert done["citations"] == []
    assert saved["citations"] == []


@pytest.mark.asyncio
async def test_fast_degradation_skips_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L1 降级回答不读不写 LLM 响应缓存。"""
    llm_calls = 0

    async def _llm(_messages: list) -> AsyncIterator[str]:
        nonlocal llm_calls
        llm_calls += 1
        yield "不应到达"

    monkeypatch.setattr("app.services.rag.engine.stream_deepseek_tokens", _llm)
    cache_get = AsyncMock(return_value=None)
    cache_set = AsyncMock()
    monkeypatch.setattr(
        "app.services.rag.engine.llm_response_cache.get",
        cache_get,
    )
    monkeypatch.setattr(
        "app.services.rag.engine.llm_response_cache.set",
        cache_set,
    )

    events, _saved = await _run_engine(
        monkeypatch,
        chunks=[_chunk()],
        level=DegradationLevel.LLM_DOWN,
    )

    assert events[-1]["event"] == "done"
    assert llm_calls == 0
    cache_get.assert_not_awaited()
    cache_set.assert_not_awaited()


def test_degradation_alignment_keep_all() -> None:
    """降级正文含全部 [片段N]，align_citations_to_answer 候选全保留。"""
    chunks = [_chunk(), _chunk(content="试用期员工年假 5 天。", page_number=7)]
    content = build_degraded_fragment_reply("年假几天？", chunks)
    citations = align_citations_to_answer(
        content,
        chunks,
        to_citation=chunk_to_citation,
    )
    assert len(citations) == 2
    assert {c["chunk_id"] for c in citations} == {
        str(c.chunk_id) for c in chunks
    }


def _thorough_outcome() -> AgentRunOutcome:
    return AgentRunOutcome(
        run_id=uuid.uuid4(),
        steps_used=0,
        max_steps=5,
        capped=False,
        timed_out=False,
        steps=(),
    )


def _thorough_plan(
    chunks: list[RetrievedChunk], *, refusal: bool = False
) -> AgentGenerationPlan:
    return AgentGenerationPlan(
        gated_chunks=tuple(chunks),
        citations=tuple(chunk_to_citation(c) for c in chunks),
        refusal=refusal,
    )


def _parse_thorough_frame(frame: str) -> dict:
    lines = frame.strip().splitlines()
    event = lines[0].removeprefix("event: ").strip()
    data = json.loads(lines[1].removeprefix("data: ").strip())
    return {"event": event, "data": data}


async def _run_thorough_phase(
    monkeypatch: pytest.MonkeyPatch,
    *,
    chunks: list[RetrievedChunk],
    level: DegradationLevel,
    refusal: bool = False,
    message: str = "员工年假有几天？",
    history: list[dict[str, str]] | None = None,
) -> tuple[list[dict], dict[str, Any]]:
    """直调 _stream_generation_phase，隔离 DB 与生成依赖。"""
    from sqlalchemy.ext.asyncio import AsyncSession

    monkeypatch.setattr(
        "app.services.agent.stream.assess_degradation",
        lambda: level,
    )
    monkeypatch.setattr(
        "app.services.agent.stream.classify_answer_confidence",
        lambda _chunks_, _q: AnswerConfidence.normal,
    )
    state: dict[str, Any] = {
        "content": "",
        "citations": [],
        "retrieval_duration_ms": None,
    }
    events: list[dict] = []
    async for frame in _stream_generation_phase(
        AsyncMock(spec=AsyncSession),
        message=message,
        gen_plan=_thorough_plan(chunks, refusal=refusal),
        outcome=_thorough_outcome(),
        user_id=uuid.uuid4(),
        history=history,
        assistant_message_id=uuid.uuid4(),
        state=state,
    ):
        events.append(_parse_thorough_frame(frame))
    return events, state


@pytest.mark.asyncio
async def test_thorough_precheck_skips_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """thorough 前置判定：LLM_DOWN 时不再触发 LLM / 历史压缩辅助调用。"""
    llm_calls = 0

    async def _llm(_messages: list) -> AsyncIterator[str]:
        nonlocal llm_calls
        llm_calls += 1
        yield "不应到达"

    monkeypatch.setattr("app.services.agent.stream.stream_deepseek_tokens", _llm)
    window_calls = 0

    def _window(_history: list, **kwargs) -> WindowedPromptHistory:
        nonlocal window_calls
        window_calls += 1
        return WindowedPromptHistory(history=[], folded=False, placeholders=[])

    monkeypatch.setattr(
        "app.services.agent.stream.build_windowed_prompt_history", _window
    )

    chunks = [_chunk(), _chunk(content="试用期员工年假 5 天。", page_number=7)]
    events, state = await _run_thorough_phase(
        monkeypatch,
        chunks=chunks,
        level=DegradationLevel.LLM_DOWN,
        history=[{"role": "user", "content": "上一轮"}],
    )

    event_names = [e["event"] for e in events]
    assert event_names.index("citation") < event_names.index("token")
    assert event_names[-1] == "done"
    assert llm_calls == 0
    assert window_calls == 0
    tokens = "".join(e["data"]["text"] for e in events if e["event"] == "token")
    assert _degradation_text() in tokens
    done = next(e["data"] for e in events if e["event"] == "done")
    assert len(done["citations"]) == len(chunks)
    assert state["content"] == tokens
    assert state["citations"]


@pytest.mark.asyncio
async def test_thorough_precheck_skips_llm_english(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """thorough 前置判定英文分支：LLM_DOWN + 英文 query → 英文说明与片段 meta。"""
    llm_calls = 0

    async def _llm(_messages: list) -> AsyncIterator[str]:
        nonlocal llm_calls
        llm_calls += 1
        yield "不应到达"

    monkeypatch.setattr("app.services.agent.stream.stream_deepseek_tokens", _llm)
    window_calls = 0

    def _window(_history: list, **kwargs) -> WindowedPromptHistory:
        nonlocal window_calls
        window_calls += 1
        return WindowedPromptHistory(history=[], folded=False, placeholders=[])

    monkeypatch.setattr(
        "app.services.agent.stream.build_windowed_prompt_history", _window
    )

    chunks = [_chunk(), _chunk(content="试用期员工年假 5 天。", page_number=7)]
    events, state = await _run_thorough_phase(
        monkeypatch,
        chunks=chunks,
        level=DegradationLevel.LLM_DOWN,
        message=_EN_QUERY,
        history=[{"role": "user", "content": "上一轮"}],
    )

    event_names = [e["event"] for e in events]
    assert event_names.index("citation") < event_names.index("token")
    assert event_names[-1] == "done"
    assert llm_calls == 0
    assert window_calls == 0
    tokens = "".join(e["data"]["text"] for e in events if e["event"] == "token")
    _assert_english_degraded_tokens(tokens, chunk_count=2)
    done = next(e["data"] for e in events if e["event"] == "done")
    assert len(done["citations"]) == len(chunks)
    assert state["content"] == tokens
    assert state["citations"]


@pytest.mark.asyncio
async def test_thorough_exception_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """thorough 异常兜底：前置健康但 LLM 流抛异常 → 切降级流，不向用户裸露异常。"""

    async def _boom(_messages: list) -> AsyncIterator[str]:
        raise RuntimeError("mock: 上游服务不可用(502)")
        yield  # pragma: no cover

    monkeypatch.setattr("app.services.agent.stream.stream_deepseek_tokens", _boom)

    chunks = [_chunk()]
    events, state = await _run_thorough_phase(
        monkeypatch,
        chunks=chunks,
        level=DegradationLevel.NORMAL,
    )

    event_names = [e["event"] for e in events]
    assert event_names.index("citation") < event_names.index("token")
    assert event_names[-1] == "done"
    assert "error" not in event_names
    tokens = "".join(e["data"]["text"] for e in events if e["event"] == "token")
    assert _degradation_text() in tokens
    done = next(e["data"] for e in events if e["event"] == "done")
    assert len(done["citations"]) == len(chunks)
    assert state["content"] == tokens
    assert state["citations"]


@pytest.mark.asyncio
async def test_thorough_refuse_wins_over_degradation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """拒答边界：refusal 时 L1 不拦截，仍走固定拒答 + 空 citations。"""
    events, state = await _run_thorough_phase(
        monkeypatch,
        chunks=[],
        level=DegradationLevel.LLM_DOWN,
        refusal=True,
    )

    event_names = [e["event"] for e in events]
    assert not any(e["event"] == "citation" for e in events)
    assert event_names.index("token") < event_names.index("done")
    tokens = "".join(e["data"]["text"] for e in events if e["event"] == "token")
    assert "未找到" in tokens
    assert _degradation_text() not in tokens
    done = next(e["data"] for e in events if e["event"] == "done")
    assert done["citations"] == []
    assert state["citations"] == []
