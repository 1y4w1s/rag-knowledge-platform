"""T6 长周期记忆分层 · W7 会话折叠摘要生成阶段接线（mock 集成测试）。"""

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
from app.services.agent.working_memory import WindowedPromptHistory
from app.services.rag.confidence_reply import AnswerConfidence
from app.services.rag.retrieval import chunk_to_citation
from app.services.rag.types import RetrievedChunk


def _history(count: int = 14) -> list[dict[str, str]]:
    return [
        {
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"消息{i}",
        }
        for i in range(count)
    ]


def _plan() -> SimpleNamespace:
    chunk = RetrievedChunk(
        kb_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        doc_name="员工手册.md",
        content="正式员工年假 10 天。",
        page_number=3,
        section_title="1.2 年假",
        heading_path="1.2 年假",
        similarity=0.92,
    )
    return SimpleNamespace(
        citations=tuple(chunk_to_citation(chunk)),
        refusal=False,
        gated_chunks=(chunk,),
        external_context="",
    )


def _outcome() -> SimpleNamespace:
    return SimpleNamespace(run_id=uuid.uuid4(), steps=())


def _parse_frame(frame: str) -> dict:
    lines = frame.strip().splitlines()
    return {
        "event": lines[0].removeprefix("event: ").strip(),
        "data": json.loads(lines[1].removeprefix("data: ").strip()),
    }


async def _collect(
    monkeypatch: pytest.MonkeyPatch,
    *,
    level: DegradationLevel,
    history: list[dict[str, str]] | None,
) -> list[dict]:
    from sqlalchemy.ext.asyncio import AsyncSession

    monkeypatch.setattr(
        "app.services.agent.stream.assess_degradation", lambda: level
    )
    monkeypatch.setattr(
        "app.services.agent.stream.classify_answer_confidence",
        lambda _chunks, _q: AnswerConfidence.normal,
    )
    monkeypatch.setattr(
        "app.services.agent.stream.has_available_chat_provider_key", lambda: True
    )
    state: dict[str, Any] = {
        "content": "",
        "citations": [],
        "retrieval_duration_ms": None,
    }
    events: list[dict] = []
    async for frame in _stream_generation_phase(
        AsyncMock(spec=AsyncSession),
        message="员工年假几天？",
        gen_plan=_plan(),
        outcome=_outcome(),
        user_id=uuid.uuid4(),
        history=history,
        assistant_message_id=uuid.uuid4(),
        state=state,
    ):
        events.append(_parse_frame(frame))
    return events


@pytest.mark.asyncio
async def test_generation_phase_wires_windowed_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """正常 LLM 分支：适配器消费 history，窗口化结果进入 build_messages，compress_history 已移除。"""
    captured: dict[str, Any] = {}
    source_history = _history()

    async def _llm(messages: list) -> AsyncIterator[str]:
        captured["messages"] = messages
        yield "正常回答"

    def _window(source: list, **kwargs) -> WindowedPromptHistory:
        captured["source"] = source
        captured["kwargs"] = kwargs
        return WindowedPromptHistory(
            history=[{"role": "system", "content": "【对话摘要】\n[会话折叠摘要]"}],
            folded=True,
            placeholders=[],
        )

    monkeypatch.setattr("app.services.agent.stream.stream_deepseek_tokens", _llm)
    monkeypatch.setattr(
        "app.services.agent.stream.build_windowed_prompt_history", _window
    )

    events = await _collect(
        monkeypatch,
        level=DegradationLevel.NORMAL,
        history=source_history,
    )

    assert captured["source"] == source_history
    assert captured["kwargs"]["max_messages"] == settings.agent_memory_window_max_messages
    assert captured["kwargs"]["token_budget"] == settings.agent_memory_window_token_budget
    assert captured["kwargs"]["min_keep"] == settings.agent_memory_window_min_keep
    assert captured["kwargs"]["summary_prefix"] == settings.agent_memory_window_summary_prefix
    assert captured["kwargs"]["summary_max"] == settings.agent_memory_window_summary_max
    assert captured["messages"][1] == {
        "role": "system",
        "content": "【对话摘要】\n[会话折叠摘要]",
    }
    names = [event["event"] for event in events]
    assert names.index("citation") < names.index("token")
    assert names[-1] == "done"

    import app.services.agent.stream as stream_module

    assert not hasattr(stream_module, "compress_history")


@pytest.mark.asyncio
async def test_generation_phase_l1_skips_window_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L1 降级分支：不调用适配器、不调用 LLM，SSE 事件序不变。"""
    window_calls = 0
    llm_calls = 0

    async def _llm(messages: list) -> AsyncIterator[str]:
        nonlocal llm_calls
        llm_calls += 1
        yield "不应到达"

    def _window(source: list, **kwargs) -> WindowedPromptHistory:
        nonlocal window_calls
        window_calls += 1
        return WindowedPromptHistory(history=[], folded=False, placeholders=[])

    monkeypatch.setattr("app.services.agent.stream.stream_deepseek_tokens", _llm)
    monkeypatch.setattr(
        "app.services.agent.stream.build_windowed_prompt_history", _window
    )

    events = await _collect(
        monkeypatch,
        level=DegradationLevel.LLM_DOWN,
        history=_history(4),
    )

    names = [event["event"] for event in events]
    assert names.index("citation") < names.index("token")
    assert names[-1] == "done"
    assert llm_calls == 0
    assert window_calls == 0
