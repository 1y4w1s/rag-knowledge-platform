"""M9-P2-1（P2-04）：verify 失败且无纠正稿时 fail-closed，不再保留未验证正文。"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.services.rag.confidence_reply import AnswerConfidence
from app.services.rag.engine import ChatEngine
from app.services.rag.generation import no_context_reply_for
from app.services.rag.types import RetrievedChunk


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        doc_name="培训制度.md",
        content="员工参加培训后提前离职，需按比例退还培训费用。",
        page_number=3,
        section_title="4.1 培训",
        heading_path="4.1 培训",
        similarity=0.92,
        parent_content=None,
    )


async def _run_engine(
    monkeypatch: pytest.MonkeyPatch,
    *,
    verify_result: tuple[bool, str | None],
    density_check: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    query = "培训费怎么退？"
    engine = ChatEngine(
        MagicMock(),
        user_id=uuid.uuid4(),
        message=query,
        kb_id=uuid.uuid4(),
    )

    async def _hist() -> None:
        engine.history = None
        engine.retrieval_query = query

    async def _retrieve() -> list[RetrievedChunk]:
        engine.chunks = [_chunk()]
        return engine.chunks

    saved: dict[str, Any] = {}
    cache_calls: dict[str, int] = {"set": 0}

    async def _save(content: str, citations: list) -> uuid.UUID:
        saved["content"] = content
        saved["citations"] = citations
        return uuid.uuid4()

    async def _cache_get(*args: object, **kwargs: object) -> None:
        return None

    async def _cache_set(*args: object, **kwargs: object) -> None:
        cache_calls["set"] += 1

    async def _no_compress(_history: list) -> None:
        return None

    async def _verify(
        answer: str, chunks: list, query: str
    ) -> tuple[bool, str | None]:
        return verify_result

    async def _tokens(_messages: list) -> object:
        for char in "培训费按比例退还[片段1]。":
            yield char

    monkeypatch.setattr(engine, "_load_history", _hist)
    monkeypatch.setattr(engine, "_retrieve", _retrieve)
    monkeypatch.setattr(engine, "_save", _save)
    monkeypatch.setattr(
        "app.services.rag.engine.classify_answer_confidence",
        lambda chunks_, _q: AnswerConfidence.normal,
    )
    monkeypatch.setattr(
        "app.services.rag.engine.degradation_requires_llm", lambda _level: True
    )
    monkeypatch.setattr("app.services.rag.engine.compress_history", _no_compress)
    monkeypatch.setattr(
        "app.services.rag.engine.stream_deepseek_tokens", _tokens
    )
    monkeypatch.setattr(
        "app.services.rag.engine.output_safety_check",
        lambda text: (True, []),
    )
    monkeypatch.setattr(
        "app.services.rag.generation.verify_answer", _verify
    )
    monkeypatch.setattr(
        "app.services.rag.engine.llm_response_cache.get", _cache_get
    )
    monkeypatch.setattr(
        "app.services.rag.engine.llm_response_cache.set", _cache_set
    )
    monkeypatch.setattr(settings, "self_verify_enabled", True)
    monkeypatch.setattr(settings, "citation_density_check_enabled", density_check)
    monkeypatch.setattr(settings, "citation_density_regenerate_limit", 1)

    events: list[dict[str, Any]] = []
    async for event in engine.stream():
        events.append(event)
    return events, saved, cache_calls


@pytest.mark.asyncio
async def test_verify_fail_without_corrected_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """verify 失败且无纠正稿：保存/结束事件均为 R4-2 拒答话术，无未验证正文。"""
    events, saved, cache_calls = await _run_engine(
        monkeypatch, verify_result=(False, None)
    )

    refuse_text = no_context_reply_for("培训费怎么退？")
    assert saved["content"] == refuse_text
    assert saved["citations"] == []
    assert "培训费按比例退还" not in saved["content"]

    corrections = [
        e["data"].get("text", "")
        for e in events
        if e["event"] == "correction"
    ]
    assert corrections == [refuse_text]

    done = next(e["data"] for e in events if e["event"] == "done")
    assert done["citations"] == []
    assert done.get("message_id")

    # fail-closed 后不应再触发引用密度重生成，也不应写 LLM 响应缓存
    assert not any(e["event"] == "regenerating" for e in events)
    assert cache_calls["set"] == 0


@pytest.mark.asyncio
async def test_verify_fail_with_corrected_still_applies_correction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """回归：verify 失败但有纠正稿时仍走原 corrected 分支。"""
    corrected = "按比例退还培训费[片段1]。"
    events, saved, cache_calls = await _run_engine(
        monkeypatch, verify_result=(False, corrected), density_check=False
    )

    assert saved["content"] == corrected
    corrections = [
        e["data"].get("text", "")
        for e in events
        if e["event"] == "correction"
    ]
    assert corrections == [corrected]
    done = next(e["data"] for e in events if e["event"] == "done")
    assert "citations" in done
    assert cache_calls["set"] == 1
