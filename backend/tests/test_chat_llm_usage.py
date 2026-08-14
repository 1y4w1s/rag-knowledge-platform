"""G2-usage W1: chat_llm usage contract / event stream / global metrics."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import pytest

from app.core.config import settings
from app.services.observability.metrics_registry import (
    inc_llm_chat_usage,
    llm_chat_usage_counter_lines,
    llm_chat_usage_snapshot,
    reset_process_counters_for_tests,
)
from app.services.rag import chat_llm
from app.services.rag.chat_llm import (
    ChatUsage,
    complete_chat,
    complete_chat_with_usage,
    parse_chat_usage,
    stream_chat_tokens,
)


class _FakeStreamResp:
    def __init__(self, lines: list[str], *, fail: bool = False) -> None:
        self._lines = lines
        self._fail = fail

    def raise_for_status(self) -> None:
        if self._fail:
            raise RuntimeError("mock: upstream unavailable (502)")

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self._lines:
            yield line

    async def __aenter__(self) -> _FakeStreamResp:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


class _CapturingClient:
    def __init__(self, lines: list[str]) -> None:
        self.calls: list[dict[str, Any]] = []
        self.lines = lines

    def stream(
        self, method: str, url: str, *, headers: dict, json: dict
    ) -> _FakeStreamResp:
        self.calls.append(
            {"method": method, "url": url, "headers": headers, "json": json}
        )
        return _FakeStreamResp(self.lines)


class _FailClient:
    def stream(self, *args: object, **kwargs: object) -> _FakeStreamResp:
        del args, kwargs
        return _FakeStreamResp([], fail=True)


def _sse_lines(*chunks: dict, done: bool = True) -> list[str]:
    lines = [f"data: {json.dumps(chunk)}" for chunk in chunks]
    if done:
        lines.append("data: [DONE]")
    return lines


def _usage_chunk(prompt: int, completion: int, **extra: object) -> dict:
    usage = {"prompt_tokens": prompt, "completion_tokens": completion, **extra}
    return {"choices": [], "usage": usage}


async def _text(stream: AsyncIterator[str]) -> str:
    return "".join([t async for t in stream])


async def _passthrough_retry(factory, **kwargs):  # type: ignore[no-untyped-def]
    del kwargs
    async for item in factory():
        yield item


def _assert_usage(holder: list[ChatUsage | None], **fields: object) -> None:
    assert len(holder) == 1
    usage = holder[0]
    assert usage is not None
    for key, value in fields.items():
        assert getattr(usage, key) == value


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_process_counters_for_tests()
    monkeypatch.setattr(settings, "chat_provider", "deepseek")
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    monkeypatch.setattr(settings, "tongyi_api_key", "")
    monkeypatch.setattr(settings, "deepseek_base_url", "https://api.deepseek.com")
    monkeypatch.setattr(settings, "deepseek_model", "deepseek-chat")
    monkeypatch.setattr(
        settings,
        "tongyi_chat_base_url",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    monkeypatch.setattr(settings, "tongyi_chat_model", "qwen-plus")
    monkeypatch.setattr(settings, "llm_usage_collection_enabled", True)
    yield


def test_parse_chat_usage_deepseek_full() -> None:
    payload = {"usage": {"prompt_tokens": 100, "completion_tokens": 30}}
    payload["usage"]["total_tokens"] = 130
    payload["usage"]["prompt_cache_hit_tokens"] = 20
    payload["usage"]["prompt_cache_miss_tokens"] = 80
    usage = parse_chat_usage(payload, "deepseek")
    assert usage is not None
    assert usage.prompt_tokens == 100
    assert usage.completion_tokens == 30
    assert usage.total_tokens == 130
    assert usage.prompt_cache_hit_tokens == 20
    assert usage.prompt_cache_miss_tokens == 80
    assert usage.provider == "deepseek"
    assert usage.has_value


def test_parse_chat_usage_tongyi_cached() -> None:
    payload = {
        "usage": {
            "prompt_tokens": 120,
            "completion_tokens": 25,
            "total_tokens": 145,
            "prompt_tokens_details": {"cached_tokens": 70},
        }
    }
    usage = parse_chat_usage(payload, "tongyi")
    assert usage is not None
    assert usage.prompt_cache_hit_tokens == 70
    assert usage.prompt_cache_miss_tokens == 50
    assert usage.provider == "tongyi"


def test_parse_chat_usage_missing_total_and_cache() -> None:
    usage = parse_chat_usage(
        {"usage": {"prompt_tokens": 8, "completion_tokens": 4}}, "deepseek"
    )
    assert usage is not None
    assert usage.total_tokens == 12
    assert usage.prompt_cache_hit_tokens == 0
    assert usage.prompt_cache_miss_tokens == 8


def test_parse_chat_usage_invalid_ignored() -> None:
    assert parse_chat_usage({}, "deepseek") is None
    assert parse_chat_usage({"usage": []}, "deepseek") is None
    neg = {"usage": {"prompt_tokens": -3, "completion_tokens": "x"}}
    assert parse_chat_usage(neg, "deepseek") is None
    cache_only = {"usage": {"prompt_tokens": 0, "completion_tokens": 0}}
    cache_only["usage"]["prompt_cache_hit_tokens"] = 5
    assert parse_chat_usage(cache_only, "deepseek") is None
    usage = parse_chat_usage(
        {"usage": {"prompt_tokens": -3, "completion_tokens": 5}}, "deepseek"
    )
    assert usage is not None
    assert usage.prompt_tokens == 0
    assert usage.completion_tokens == 5


@pytest.mark.asyncio
async def test_stream_text_behavior_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-ds")
    client = _CapturingClient(
        lines=_sse_lines(
            {"choices": [{"delta": {"content": "hello"}}]},
            {"choices": [{"delta": {"content": "world"}}]},
        )
    )
    monkeypatch.setattr(chat_llm, "get_deepseek_client", lambda: client)
    monkeypatch.setattr(chat_llm, "retry_stream", _passthrough_retry)
    parts = [
        t
        async for t in stream_chat_tokens([{"role": "user", "content": "hi"}])
    ]
    assert parts == ["hello", "world"]


@pytest.mark.asyncio
async def test_stream_usage_chunk_consumed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-ds")
    chunk = _usage_chunk(10, 5, prompt_cache_hit_tokens=3, prompt_cache_miss_tokens=7)
    client = _CapturingClient(
        lines=_sse_lines(
            {"choices": [{"delta": {"content": "ok"}}]},
            chunk,
        )
    )
    monkeypatch.setattr(chat_llm, "get_deepseek_client", lambda: client)
    monkeypatch.setattr(chat_llm, "retry_stream", _passthrough_retry)
    holder: list[ChatUsage | None] = []
    text = await _text(
        stream_chat_tokens([{"role": "user", "content": "hi"}], usage_holder=holder)
    )
    assert text == "ok"
    _assert_usage(
        holder,
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        prompt_cache_hit_tokens=3,
        prompt_cache_miss_tokens=7,
        provider="deepseek",
    )
    assert client.calls[0]["json"]["stream_options"] == {"include_usage": True}


@pytest.mark.asyncio
async def test_stream_no_usage_holder_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-ds")
    client = _CapturingClient(
        lines=_sse_lines({"choices": [{"delta": {"content": "ok"}}]})
    )
    monkeypatch.setattr(chat_llm, "get_deepseek_client", lambda: client)
    monkeypatch.setattr(chat_llm, "retry_stream", _passthrough_retry)
    holder: list[ChatUsage | None] = []
    await _text(
        stream_chat_tokens([{"role": "user", "content": "hi"}], usage_holder=holder)
    )
    assert holder == [None]


@pytest.mark.asyncio
async def test_stream_mock_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    monkeypatch.setattr(settings, "tongyi_api_key", "")
    holder: list[ChatUsage | None] = []
    text = await _text(
        stream_chat_tokens([{"role": "user", "content": "hi"}], usage_holder=holder)
    )
    assert text == "根据知识库内容回答"
    assert holder == [None]


@pytest.mark.asyncio
async def test_stream_fallback_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-ds")
    monkeypatch.setattr(settings, "tongyi_api_key", "sk-ty")
    chunk = _usage_chunk(4, 6, prompt_tokens_details={"cached_tokens": 2})
    ok_client = _CapturingClient(
        lines=_sse_lines(
            {"choices": [{"delta": {"content": "fallback-ok"}}]},
            chunk,
        )
    )
    monkeypatch.setattr(chat_llm, "get_deepseek_client", lambda: _FailClient())
    monkeypatch.setattr(chat_llm, "get_tongyi_client", lambda: ok_client)
    monkeypatch.setattr(chat_llm, "retry_stream", _passthrough_retry)
    holder: list[ChatUsage | None] = []
    text = await _text(
        stream_chat_tokens([{"role": "user", "content": "hi"}], usage_holder=holder)
    )
    assert text == "fallback-ok"
    _assert_usage(
        holder,
        prompt_tokens=4,
        completion_tokens=6,
        total_tokens=10,
        prompt_cache_hit_tokens=2,
        prompt_cache_miss_tokens=2,
        provider="tongyi",
    )


@pytest.mark.asyncio
async def test_complete_chat_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_stream(messages, *, usage_holder=None):  # type: ignore[no-untyped-def]
        del messages, usage_holder
        yield "he"
        yield "llo"
    monkeypatch.setattr(chat_llm, "stream_chat_tokens", _fake_stream)
    result = await complete_chat([{"role": "user", "content": "hi"}])
    assert isinstance(result, str)
    assert result == "hello"


@pytest.mark.asyncio
async def test_complete_chat_with_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = ChatUsage(
        prompt_tokens=3,
        completion_tokens=2,
        total_tokens=5,
        provider="deepseek",
    )
    async def _fake_stream(messages, *, usage_holder=None):  # type: ignore[no-untyped-def]
        del messages
        assert usage_holder is not None
        yield "answer"
        usage_holder.append(expected)
    monkeypatch.setattr(chat_llm, "stream_chat_tokens", _fake_stream)
    text, usage = await complete_chat_with_usage(
        [{"role": "user", "content": "hi"}]
    )
    assert text == "answer"
    assert usage == expected
    async def _fake_stream_none(messages, *, usage_holder=None):  # type: ignore[no-untyped-def]
        del messages
        assert usage_holder is not None
        yield "no-usage"
        usage_holder.append(None)
    monkeypatch.setattr(chat_llm, "stream_chat_tokens", _fake_stream_none)
    text2, usage2 = await complete_chat_with_usage(
        [{"role": "user", "content": "hi"}]
    )
    assert text2 == "no-usage"
    assert usage2 is None


@pytest.mark.asyncio
async def test_global_usage_metric_wired(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-ds")
    chunk = _usage_chunk(10, 5, prompt_cache_hit_tokens=3, prompt_cache_miss_tokens=7)
    client = _CapturingClient(
        lines=_sse_lines(
            {"choices": [{"delta": {"content": "ok"}}]},
            chunk,
        )
    )
    monkeypatch.setattr(chat_llm, "get_deepseek_client", lambda: client)
    monkeypatch.setattr(chat_llm, "retry_stream", _passthrough_retry)
    with caplog.at_level(logging.INFO, logger="app.services.rag.chat_llm"):
        await _text(stream_chat_tokens([{"role": "user", "content": "needle-query-xyz"}]))
    snap = llm_chat_usage_snapshot()
    assert snap[("deepseek", "prompt")] == 10
    assert snap[("deepseek", "completion")] == 5
    assert snap[("deepseek", "cache_hit")] == 3
    assert snap[("deepseek", "cache_miss")] == 7
    lines = llm_chat_usage_counter_lines()
    assert (
        'ruige_llm_chat_usage_tokens_total{provider="deepseek",kind="prompt"} 10'
        in lines
    )
    assert (
        'ruige_llm_chat_usage_tokens_total{provider="deepseek",kind="completion"} 5'
        in lines
    )
    usage_records = [
        r.getMessage() for r in caplog.records if "llm_usage" in r.getMessage()
    ]
    assert usage_records
    assert "needle-query-xyz" not in usage_records[0]


@pytest.mark.asyncio
async def test_usage_collection_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-ds")
    monkeypatch.setattr(settings, "llm_usage_collection_enabled", False)
    client = _CapturingClient(
        lines=_sse_lines(
            {"choices": [{"delta": {"content": "ok"}}]},
            _usage_chunk(10, 5),
        )
    )
    monkeypatch.setattr(chat_llm, "get_deepseek_client", lambda: client)
    monkeypatch.setattr(chat_llm, "retry_stream", _passthrough_retry)
    text = await _text(stream_chat_tokens([{"role": "user", "content": "hi"}]))
    assert text == "ok"
    assert "stream_options" not in client.calls[0]["json"]
    assert llm_chat_usage_snapshot() == {}


def test_reset_clears_usage_metrics() -> None:
    usage = ChatUsage(
        prompt_tokens=1,
        completion_tokens=2,
        prompt_cache_miss_tokens=1,
        provider="deepseek",
    )
    inc_llm_chat_usage("deepseek", usage)
    assert llm_chat_usage_snapshot() != {}
    reset_process_counters_for_tests()
    assert llm_chat_usage_snapshot() == {}
