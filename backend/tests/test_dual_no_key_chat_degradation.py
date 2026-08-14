"""W1 双无 key 对话降级：LLM / 嵌入 key 均缺失时 fast / thorough 生成走 L1 降级流。"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.core.config import settings
from app.core.degradation import (
    DegradationLevel,
    degradation_message,
    reset_stabilization,
)
from app.services.agent.finalize import AgentGenerationPlan
from app.services.agent.stream import _stream_generation_phase
from app.services.agent.types import AgentRunOutcome
from app.services.agent.working_memory import WindowedPromptHistory
from app.services.rag.chat_llm import (
    has_available_chat_provider_key,
    stream_chat_tokens,
)
from app.services.rag.confidence_reply import AnswerConfidence
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


def _set_dual_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "chat_provider", "deepseek")
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    monkeypatch.setattr(settings, "tongyi_api_key", "")


def _set_fallback_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "chat_provider", "deepseek")
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    monkeypatch.setattr(settings, "tongyi_api_key", "sk-ty-fallback")


@pytest.fixture(autouse=True)
def _reset_degradation() -> None:
    reset_stabilization()


async def _run_engine(
    monkeypatch: pytest.MonkeyPatch,
    *,
    chunks: list[RetrievedChunk],
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
    # 熔断器健康（NORMAL），是否降级完全由 chat provider key 判定驱动
    monkeypatch.setattr(
        "app.services.rag.engine.assess_degradation",
        lambda: DegradationLevel.NORMAL,
    )

    events: list[dict] = []
    async for event in engine.stream():
        events.append(event)
    return events, saved


@pytest.mark.asyncio
async def test_fast_dual_no_key_goes_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """双无 key + 有依据 → fast 走 L1 降级流，stream_deepseek_tokens 零调用。"""
    _set_dual_no_key(monkeypatch)
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

    events, saved = await _run_engine(monkeypatch, chunks=[_chunk()])

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
async def test_fast_dual_no_key_english_goes_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """双无 key + 英文 query → fast 走 L1 英文降级说明与片段 meta。"""
    _set_dual_no_key(monkeypatch)
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
    refusal: bool = False,
    message: str = "员工年假有几天？",
    history: list[dict[str, str]] | None = None,
) -> tuple[list[dict], dict[str, Any]]:
    """直调 _stream_generation_phase，隔离 DB 与生成依赖。"""
    from sqlalchemy.ext.asyncio import AsyncSession

    monkeypatch.setattr(
        "app.services.agent.stream.assess_degradation",
        lambda: DegradationLevel.NORMAL,
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
async def test_thorough_dual_no_key_goes_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """双无 key + 有依据 → thorough 生成阶段走 L1 降级流，LLM 零调用。"""
    _set_dual_no_key(monkeypatch)
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
async def test_thorough_dual_no_key_english_goes_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """双无 key + 英文 query → thorough 生成阶段走 L1 英文降级说明与片段 meta。"""
    _set_dual_no_key(monkeypatch)
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
async def test_dual_no_key_refuse_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """拒答 gate 优先：双无 key + 无依据仍走固定拒答，不出降级说明与 citations。"""
    _set_dual_no_key(monkeypatch)

    events, saved = await _run_engine(monkeypatch, chunks=[])

    assert not any(e["event"] == "citation" for e in events)
    tokens = "".join(e["data"]["text"] for e in events if e["event"] == "token")
    assert "未找到" in tokens
    assert _degradation_text() not in tokens
    done = next(e["data"] for e in events if e["event"] == "done")
    assert done["citations"] == []
    assert saved["citations"] == []


@pytest.mark.asyncio
async def test_thorough_dual_no_key_refuse_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """thorough 拒答 gate 优先：双无 key + refusal 不出降级说明与 citations。"""
    _set_dual_no_key(monkeypatch)

    events, state = await _run_thorough_phase(
        monkeypatch,
        chunks=[],
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


@pytest.mark.asyncio
async def test_dual_no_key_skips_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """双无 key 降级分支不读不写 LLM 响应缓存。"""
    _set_dual_no_key(monkeypatch)
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

    events, _saved = await _run_engine(monkeypatch, chunks=[_chunk()])

    assert events[-1]["event"] == "done"
    assert llm_calls == 0
    cache_get.assert_not_awaited()
    cache_set.assert_not_awaited()


@pytest.mark.asyncio
async def test_any_provider_key_normal_path_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """主无 key 备有 key → fast 仍走正常 LLM 路径，不回退降级。"""
    _set_fallback_key(monkeypatch)
    llm_calls = 0

    async def _llm(_messages: list) -> AsyncIterator[str]:
        nonlocal llm_calls
        llm_calls += 1
        yield "正常回答内容"

    monkeypatch.setattr("app.services.rag.engine.stream_deepseek_tokens", _llm)

    async def _compress(_history: list) -> None:
        return None

    monkeypatch.setattr("app.services.rag.engine.compress_history", _compress)
    monkeypatch.setattr(settings, "citation_density_check_enabled", False)
    monkeypatch.setattr(
        "app.services.rag.engine.llm_response_cache.get",
        AsyncMock(return_value=None),
    )

    events, saved = await _run_engine(monkeypatch, chunks=[_chunk()])

    assert llm_calls == 1
    tokens = "".join(e["data"]["text"] for e in events if e["event"] == "token")
    assert "正常回答内容" in tokens
    assert _degradation_text() not in tokens
    assert events[-1]["event"] == "done"
    assert saved["content"] == tokens


@pytest.mark.asyncio
async def test_any_provider_key_normal_path_thorough(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """主无 key 备有 key → thorough 生成阶段仍走正常 LLM 路径。"""
    _set_fallback_key(monkeypatch)
    llm_calls = 0

    async def _llm(_messages: list) -> AsyncIterator[str]:
        nonlocal llm_calls
        llm_calls += 1
        yield "正常回答内容"

    monkeypatch.setattr("app.services.agent.stream.stream_deepseek_tokens", _llm)

    def _window(_history: list, **kwargs) -> WindowedPromptHistory:
        return WindowedPromptHistory(
            history=list(_history), folded=False, placeholders=[]
        )

    monkeypatch.setattr(
        "app.services.agent.stream.build_windowed_prompt_history", _window
    )

    events, state = await _run_thorough_phase(monkeypatch, chunks=[_chunk()])

    assert llm_calls == 1
    tokens = "".join(e["data"]["text"] for e in events if e["event"] == "token")
    assert "正常回答内容" in tokens
    assert _degradation_text() not in tokens
    assert events[-1]["event"] == "done"
    assert state["content"] == tokens


@pytest.mark.asyncio
async def test_chat_llm_mock_contract_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """chat_llm mock 分支保持：双无 key 仍产出占位文案，判定助手同口径。"""
    _set_dual_no_key(monkeypatch)
    assert has_available_chat_provider_key() is False

    parts: list[str] = []
    async for tok in stream_chat_tokens([{"role": "user", "content": "hi"}]):
        parts.append(tok)
    assert "".join(parts) == "根据知识库内容回答"

    monkeypatch.setattr(settings, "deepseek_api_key", "sk-ds-primary")
    monkeypatch.setattr(settings, "tongyi_api_key", "")
    assert has_available_chat_provider_key() is True

    monkeypatch.setattr(settings, "deepseek_api_key", "")
    monkeypatch.setattr(settings, "tongyi_api_key", "sk-ty-fallback")
    assert has_available_chat_provider_key() is True
