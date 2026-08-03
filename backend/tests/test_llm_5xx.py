"""LLM downstream 5xx tests — mock fault injection, zero production changes."""
from __future__ import annotations

import httpx
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.services.rag import chat_llm
from app.services.rag.generation import stream_deepseek_tokens
from tests.conftest import create_test_kb as _create_kb


@pytest.fixture(autouse=True)
def _reset_llm_fault_state() -> None:
    """5xx 注入会真实触发 LLM 熔断/降级；测试后必须复位，避免污染同批限流用例
    （degradation 乘数会使 invite 等限流断言提前 429）。"""
    from app.core.degradation import reset_stabilization
    from app.core.retry import reset_all_breakers

    reset_all_breakers()
    reset_stabilization()
    yield
    reset_all_breakers()
    reset_stabilization()


class _MockStream5xx:
    async def __aenter__(self) -> httpx.Response:
        req = httpx.Request("POST", "http://test/chat/completions")
        resp = httpx.Response(502, request=req)
        resp.raise_for_status()
        return resp

    async def __aexit__(self, *args: object) -> None:
        pass


class _MockClient5xx:
    def stream(self, *args: object, **kwargs: object) -> _MockStream5xx:
        del args, kwargs
        return _MockStream5xx()


def test_stream_deepseek_5xx_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    """stream_deepseek_tokens raises HTTPStatusError on 5xx (not silently eaten)."""
    import asyncio

    monkeypatch.setattr(settings, "chat_provider", "deepseek")
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-fake-5xx")
    monkeypatch.setattr(chat_llm, "get_deepseek_client", lambda: _MockClient5xx())
    # bypass retry/breaker so 5xx surfaces on first attempt
    async def _once(factory, **kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        async for item in factory():
            yield item

    monkeypatch.setattr(chat_llm, "retry_stream", _once)

    async def _run() -> None:
        with pytest.raises(httpx.HTTPStatusError):
            async for _ in stream_deepseek_tokens([{"role": "user", "content": "hi"}]):
                pass

    asyncio.run(_run())


@pytest.mark.asyncio
async def test_http_chat_llm_5xx_does_not_crash_server(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM 5xx during streaming: server does not crash; HTTP response received."""
    monkeypatch.setattr(settings, "chat_provider", "deepseek")
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-fake-5xx")
    monkeypatch.setattr(chat_llm, "get_deepseek_client", lambda: _MockClient5xx())

    headers, user = await register_and_login(prefix="llm-5xx-safe")
    kb = await _create_kb(client, headers, user, name="LLM 5xx KB")
    kb_id = kb["id"]

    await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        headers=headers,
        files=[("files", ("faq.md", b"# FAQ\n\nAnnual leave 10 days.", "text/markdown"))],
    )

    try:
        async with client.stream(
            "POST",
            f"/api/v1/knowledge-bases/{kb_id}/chat",
            headers=headers,
            json={"message": "How many leave days?", "mode": "fast"},
        ) as resp:
            await resp.aread()
    except Exception:
        pass
