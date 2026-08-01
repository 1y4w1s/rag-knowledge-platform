"""NW-9：CHAT_PROVIDER 在 DeepSeek / 通义 chat 间分派（mock，不打外网）。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest

from app.core.config import settings
from app.services.rag import chat_llm
from app.services.rag.chat_llm import resolve_chat_provider, stream_chat_tokens, stream_deepseek_tokens

json_mod = json


class _FakeStreamResp:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self._lines:
            yield line

    async def __aenter__(self) -> _FakeStreamResp:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


class _CapturingClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def stream(
        self,
        method: str,
        url: str,
        *,
        headers: dict,
        json: dict,  # httpx keyword; do not shadow module
    ) -> _FakeStreamResp:
        body = json
        self.calls.append({"method": method, "url": url, "headers": headers, "json": body})
        payload = {"choices": [{"delta": {"content": "ok"}}]}
        lines = [f"data: {json_mod.dumps(payload)}", "data: [DONE]"]
        return _FakeStreamResp(lines)


async def _passthrough_retry(factory, **kwargs):  # type: ignore[no-untyped-def]
    del kwargs
    async for item in factory():
        yield item


@pytest.fixture(autouse=True)
def _reset_provider(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_resolve_chat_provider_default_and_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    assert resolve_chat_provider() == "deepseek"
    monkeypatch.setattr(settings, "chat_provider", "tongyi")
    assert resolve_chat_provider() == "tongyi"
    monkeypatch.setattr(settings, "chat_provider", "GPT-NEO")
    assert resolve_chat_provider() == "deepseek"


@pytest.mark.asyncio
async def test_no_key_returns_mock_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "chat_provider", "tongyi")
    monkeypatch.setattr(settings, "tongyi_api_key", "")
    parts: list[str] = []
    async for t in stream_chat_tokens([{"role": "user", "content": "hi"}]):
        parts.append(t)
    assert "".join(parts) == "根据知识库内容回答"


@pytest.mark.asyncio
async def test_deepseek_provider_hits_deepseek_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _CapturingClient()
    monkeypatch.setattr(settings, "chat_provider", "deepseek")
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-ds")
    monkeypatch.setattr(chat_llm, "get_deepseek_client", lambda: client)
    monkeypatch.setattr(chat_llm, "retry_stream", _passthrough_retry)

    parts: list[str] = []
    async for t in stream_deepseek_tokens([{"role": "user", "content": "hi"}]):
        parts.append(t)

    assert "".join(parts) == "ok"
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["url"] == "https://api.deepseek.com/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer sk-ds"
    assert call["json"]["model"] == "deepseek-chat"


@pytest.mark.asyncio
async def test_tongyi_provider_hits_dashscope_compatible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _CapturingClient()
    monkeypatch.setattr(settings, "chat_provider", "tongyi")
    monkeypatch.setattr(settings, "tongyi_api_key", "sk-ty")
    monkeypatch.setattr(chat_llm, "get_tongyi_client", lambda: client)
    monkeypatch.setattr(chat_llm, "retry_stream", _passthrough_retry)

    parts: list[str] = []
    async for t in stream_chat_tokens([{"role": "user", "content": "hi"}]):
        parts.append(t)

    assert "".join(parts) == "ok"
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["url"] == (
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    )
    assert call["headers"]["Authorization"] == "Bearer sk-ty"
    assert call["json"]["model"] == "qwen-plus"
    assert call["json"]["stream"] is True


@pytest.mark.asyncio
async def test_health_detailed_reports_chat_provider(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "chat_provider", "tongyi")
    resp = await client.get("/health/detailed")
    assert resp.status_code == 200
    body = resp.json()
    assert body["chat"]["provider"] == "tongyi"
    # chat 块不参与整体 status 公式
    assert "status" in body
