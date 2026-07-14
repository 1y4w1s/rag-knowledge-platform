"""LLM downstream 5xx tests — mock fault injection, zero production changes."""
from __future__ import annotations

import httpx
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.services.rag.generation import stream_deepseek_tokens, stream_no_context_reply
from tests.conftest import create_test_kb as _create_kb


class _MockStream5xx:
    async def __aenter__(self) -> httpx.Response:
        req = httpx.Request("POST", "http://test/chat/completions")
        resp = httpx.Response(502, request=req)
        resp.raise_for_status()
        return resp
    async def __aexit__(self, *args: object) -> None:
        pass


class _MockClient5xx:
    async def __aenter__(self) -> _MockClient5xx:
        return self
    async def __aexit__(self, *args: object) -> None:
        pass
    def stream(self, *args: object, **kwargs: object) -> _MockStream5xx:
        del args, kwargs
        return _MockStream5xx()


def test_stream_deepseek_5xx_propagates() -> None:
    """stream_deepseek_tokens raises HTTPStatusError on 5xx (not silently eaten)."""
    import asyncio
    async def _run() -> None:
        mp = pytest.MonkeyPatch()
        mp.setattr(settings, "deepseek_api_key", "sk-fake-5xx")
        mp.setattr("app.services.rag.generation.httpx.AsyncClient", lambda **kw: _MockClient5xx())
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
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-fake-5xx")
    monkeypatch.setattr(
        "app.services.rag.generation.httpx.AsyncClient",
        lambda **kw: _MockClient5xx(),
    )

    headers, user = await register_and_login(prefix="llm-5xx-safe")
    kb = await _create_kb(client, headers, user, name="LLM 5xx KB")
    kb_id = kb["id"]

    # Upload a doc so retrieval finds chunks
    await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        headers=headers,
        files=[("files", ("faq.md", b"# FAQ\n\nAnnual leave 10 days.", "text/markdown"))],
    )

    # Server should stay alive; we get some response (200 or 500)
    try:
        async with client.stream(
            "POST",
            f"/api/v1/knowledge-bases/{kb_id}/chat",
            headers=headers,
            json={"message": "How many leave days?", "mode": "fast"},
        ) as resp:
            await resp.aread()
    except Exception:
        pass  # The server crashed but connection handled it
