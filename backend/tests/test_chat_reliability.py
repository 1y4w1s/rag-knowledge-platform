"""可靠性测试：LLM provider 熔断后自动切换（指数退避重试 + 备用 provider fallback）。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Self

import pytest

from app.core.config import settings
from app.services.rag import chat_llm
from app.services.rag.chat_llm import stream_chat_tokens


class _FakeStreamOk:
    """模拟成功响应的流。"""

    def __init__(self, token: str = "ok") -> None:
        self._token = token

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self) -> AsyncIterator[str]:
        import json
        payload = {"choices": [{"delta": {"content": self._token}}]}
        yield f"data: {json.dumps(payload)}"
        yield "data: [DONE]"

    async def __aenter__(self) -> _FakeStreamOk:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


class _FakeStreamError:
    """模拟失败的流（HTTP 级别抛异常）。"""

    class _RaiseOnEnter:
        def raise_for_status(self) -> None:
            raise RuntimeError("mock: 上游服务不可用 (502)")

        async def aiter_lines(self) -> AsyncIterator[str]:
            return
            yield  # type: ignore[unreachable]

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

    def stream(self, *args: object, **kwargs: object) -> _RaiseOnEnter:
        del args, kwargs
        return self._RaiseOnEnter()


class _OkClient:
    """总是返回成功的 mock 客户端。"""
    def __init__(self, token: str = "ok") -> None:
        self.token = token

    def stream(self, method: str, url: str, *, headers: dict, json: dict) -> _FakeStreamOk:
        del method, url, headers, json
        return _FakeStreamOk(self.token)


class _FailClient:
    """总是返回失败的 mock 客户端。"""
    def stream(self, *args: object, **kwargs: object) -> _FakeStreamError._RaiseOnEnter:
        del args, kwargs
        return _FakeStreamError._RaiseOnEnter()


async def _passthrough_retry(factory, **kwargs):  # type: ignore[no-untyped-def]
    """绕过重试/熔断器，直接调工厂。"""
    del kwargs
    async for item in factory():
        yield item


@pytest.fixture(autouse=True)
def _reset_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """每个测试前重置为 deepseek 主 + tongyi 备用。"""
    monkeypatch.setattr(settings, "chat_provider", "deepseek")
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-ds-primary")
    monkeypatch.setattr(settings, "tongyi_api_key", "sk-ty-fallback")
    monkeypatch.setattr(settings, "deepseek_base_url", "https://api.deepseek.com")
    monkeypatch.setattr(settings, "deepseek_model", "deepseek-chat")
    monkeypatch.setattr(
        settings,
        "tongyi_chat_base_url",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    monkeypatch.setattr(settings, "tongyi_chat_model", "qwen-plus")


# ── 主 provider 成功，不触发 fallback ────────────────────────────────


@pytest.mark.asyncio
async def test_primary_succeeds_no_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """主 provider (deepseek) 成功 → 只调一次，不用 fallback。"""
    client = _OkClient()
    monkeypatch.setattr(chat_llm, "get_deepseek_client", lambda: client)
    monkeypatch.setattr(chat_llm, "retry_stream", _passthrough_retry)

    parts: list[str] = []
    async for t in stream_chat_tokens([{"role": "user", "content": "hi"}]):
        parts.append(t)
    assert "".join(parts) == "ok"


# ── 主 provider 失败 → fallback 成功 ────────────────────────────────


@pytest.mark.asyncio
async def test_primary_fails_fallback_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """主 provider (deepseek) 失败 → 自动切备用 (tongyi) → 成功。"""
    fail_client = _FailClient()
    ok_client = _OkClient(token="tongyi-answer")
    monkeypatch.setattr(chat_llm, "get_deepseek_client", lambda: fail_client)
    monkeypatch.setattr(chat_llm, "get_tongyi_client", lambda: ok_client)
    monkeypatch.setattr(chat_llm, "retry_stream", _passthrough_retry)

    parts: list[str] = []
    async for t in stream_chat_tokens([{"role": "user", "content": "hi"}]):
        parts.append(t)
    # 收到备用 provider 的回答
    assert "".join(parts) == "tongyi-answer"


# ── 两个 provider 都失败 ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_both_providers_fail_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """主 + 备用均失败 → 抛异常。"""
    fail_client = _FailClient()
    monkeypatch.setattr(chat_llm, "get_deepseek_client", lambda: fail_client)
    monkeypatch.setattr(chat_llm, "get_tongyi_client", lambda: fail_client)
    monkeypatch.setattr(chat_llm, "retry_stream", _passthrough_retry)

    with pytest.raises(RuntimeError, match="上游服务不可用"):
        async for _ in stream_chat_tokens([{"role": "user", "content": "hi"}]):
            pass


# ── 无备用 key → 只试主 provider ───────────────────────────────────


@pytest.mark.asyncio
async def test_no_fallback_key_only_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    """备用 provider 无 key → 链中只有主 provider，失败即抛。"""
    monkeypatch.setattr(settings, "tongyi_api_key", "")
    fail_client = _FailClient()
    monkeypatch.setattr(chat_llm, "get_deepseek_client", lambda: fail_client)
    # tongyi 不会被调用，所以不需 patch get_tongyi_client
    monkeypatch.setattr(chat_llm, "retry_stream", _passthrough_retry)

    with pytest.raises(RuntimeError, match="上游服务不可用"):
        async for _ in stream_chat_tokens([{"role": "user", "content": "hi"}]):
            pass


# ── 均无 key → mock ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_keys_both_providers_returns_mock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """两个 provider 均无 key → 回退 mock。"""
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    monkeypatch.setattr(settings, "tongyi_api_key", "")

    parts: list[str] = []
    async for t in stream_chat_tokens([{"role": "user", "content": "hi"}]):
        parts.append(t)
    assert "".join(parts) == "根据知识库内容回答"


# ── 备用无 key 但主有 key → 有 mock client → 走主 provider ────────


@pytest.mark.asyncio
async def test_fallback_no_key_primary_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """仅主 provider 有 key → 只走主 provider 成功。"""
    monkeypatch.setattr(settings, "tongyi_api_key", "")
    client = _OkClient()
    monkeypatch.setattr(chat_llm, "get_deepseek_client", lambda: client)
    monkeypatch.setattr(chat_llm, "retry_stream", _passthrough_retry)

    parts: list[str] = []
    async for t in stream_chat_tokens([{"role": "user", "content": "hi"}]):
        parts.append(t)
    assert "".join(parts) == "ok"
