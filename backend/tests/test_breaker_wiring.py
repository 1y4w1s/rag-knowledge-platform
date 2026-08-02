"""P1-10 熔断接线测试：OPEN 后快速失败（不发起上游调用、无超时放大）+ 半开探活。"""

from __future__ import annotations

import time

import pytest

from app.core.retry import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    async_retry,
    get_breaker,
    reset_all_breakers,
    retry_stream,
)
from app.core import retry as retry_mod


@pytest.fixture(autouse=True)
def _reset_breakers() -> None:
    reset_all_breakers()
    yield
    reset_all_breakers()


def _failing_factory(calls: dict[str, int]):
    """总是失败的流工厂（同步计数）。"""
    async def _factory():
        calls["n"] += 1
        raise RuntimeError("mock: 上游服务不可用 (502)")
        yield  # type: ignore[unreachable]

    return _factory


def _ok_factory(calls: dict[str, int], token: str = "ok"):
    async def _factory():
        calls["n"] += 1
        yield token

    return _factory


def _fresh_breaker(name: str, *, threshold: int, recovery_timeout: float) -> CircuitBreaker:
    """强制以指定阈值重建熔断器（get_breaker 对已存在实例会忽略参数）。"""
    retry_mod._breakers.pop(name, None)
    return get_breaker(name, failure_threshold=threshold, recovery_timeout=recovery_timeout)


@pytest.mark.asyncio
async def test_retry_stream_fast_fails_when_breaker_open() -> None:
    """连续失败达到阈值 → 熔断器 OPEN；下一次调用快速失败且不碰上游。"""
    calls = {"n": 0}
    _fresh_breaker("test_stream", threshold=2, recovery_timeout=30)

    for _ in range(2):
        with pytest.raises(RuntimeError, match="上游服务不可用"):
            async for _ in retry_stream(
                _failing_factory(calls), max_retries=0, breaker_name="test_stream"
            ):
                pass

    breaker = get_breaker("test_stream")
    assert breaker.state == "open"

    n_before = calls["n"]
    start = time.monotonic()
    with pytest.raises(CircuitBreakerOpenError, match="快速失败"):
        async for _ in retry_stream(
            _failing_factory(calls), max_retries=2, breaker_name="test_stream"
        ):
            pass
    elapsed = time.monotonic() - start

    assert calls["n"] == n_before, "熔断 OPEN 后不应再发起上游调用"
    assert elapsed < 0.5, f"快速失败应无退避/超时放大，实际耗时 {elapsed:.2f}s"


@pytest.mark.asyncio
async def test_retry_stream_half_open_probe_recovers() -> None:
    """recovery 超时后进入半开：探活成功 → 熔断器恢复 CLOSED。"""
    fail_calls = {"n": 0}
    ok_calls = {"n": 0}
    _fresh_breaker("test_halfopen", threshold=1, recovery_timeout=0.05)

    with pytest.raises(RuntimeError):
        async for _ in retry_stream(
            _failing_factory(fail_calls), max_retries=0, breaker_name="test_halfopen"
        ):
            pass
    assert get_breaker("test_halfopen").state == "open"

    # 等 recovery 窗口过 → 半开 → 探活成功 → CLOSED
    await _sleep(0.08)
    parts: list[str] = []
    async for t in retry_stream(
        _ok_factory(ok_calls, token="recovered"), max_retries=0, breaker_name="test_halfopen"
    ):
        parts.append(t)

    assert "".join(parts) == "recovered"
    assert get_breaker("test_halfopen").state == "closed"
    assert ok_calls["n"] == 1


@pytest.mark.asyncio
async def test_async_retry_fast_fails_when_breaker_open() -> None:
    """async_retry 同样受熔断闸门约束：OPEN 快速失败。"""
    calls = {"n": 0}
    _fresh_breaker("test_retry", threshold=1, recovery_timeout=30)

    async def _work() -> str:
        calls["n"] += 1
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await async_retry(_work, max_retries=0, breaker_name="test_retry")
    assert get_breaker("test_retry").state == "open"

    n_before = calls["n"]
    start = time.monotonic()
    with pytest.raises(CircuitBreakerOpenError):
        await async_retry(_work, max_retries=3, breaker_name="test_retry")
    elapsed = time.monotonic() - start

    assert calls["n"] == n_before
    assert elapsed < 0.5


async def _sleep(seconds: float) -> None:
    """测试内小睡（避免直接依赖 asyncio.sleep 的调用点噪音）。"""
    import asyncio

    await asyncio.sleep(seconds)


# ── chat 主链路：主 provider 熔断 → 快速切备用（无超时放大）──────────


@pytest.mark.asyncio
async def test_chat_llm_breaker_open_switches_fallback_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings
    from app.services.rag import chat_llm

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

    ds_calls = {"n": 0}

    class _OkClient:
        def __init__(self, token: str) -> None:
            self._token = token

        def stream(self, *args: object, **kwargs: object):
            del args, kwargs
            import json

            class _Stream:
                def __init__(self, token: str) -> None:
                    self._token = token

                def raise_for_status(self) -> None:
                    return None

                async def aiter_lines(self):
                    payload = {"choices": [{"delta": {"content": self._token}}]}
                    yield f"data: {json.dumps(payload)}"
                    yield "data: [DONE]"

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args: object) -> None:
                    return None

            return _Stream(self._token)

    def _counted_deepseek_client():
        ds_calls["n"] += 1
        raise AssertionError("熔断 OPEN 后主 provider 不应被调用")

    monkeypatch.setattr(chat_llm, "get_deepseek_client", _counted_deepseek_client)
    monkeypatch.setattr(chat_llm, "get_tongyi_client", lambda: _OkClient("fallback-ok"))
    # 使用真实 retry_stream（不 bypass），验证熔断闸门在 chat 链路生效

    # 先让 deepseek_llm 熔断器 OPEN（阈值 1）
    _fresh_breaker("deepseek_llm", threshold=1, recovery_timeout=30).record_failure()

    start = time.monotonic()
    parts: list[str] = []
    async for t in chat_llm.stream_chat_tokens([{"role": "user", "content": "hi"}]):
        parts.append(t)
    elapsed = time.monotonic() - start

    assert "".join(parts) == "fallback-ok"
    assert ds_calls["n"] == 0, "主 provider 熔断时应快速切备用，不发起上游调用"
    assert elapsed < 1.0, f"熔断快速失败应无明显耗时，实际 {elapsed:.2f}s"


@pytest.mark.asyncio
async def test_chat_llm_both_breakers_open_fails_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """主 + 备用均熔断 → 快速抛错（无超时放大）。"""
    from app.core.config import settings
    from app.services.rag import chat_llm

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

    def _should_not_call():
        raise AssertionError("熔断 OPEN 后不应发起任何上游调用")

    monkeypatch.setattr(chat_llm, "get_deepseek_client", _should_not_call)
    monkeypatch.setattr(chat_llm, "get_tongyi_client", _should_not_call)

    _fresh_breaker("deepseek_llm", threshold=1, recovery_timeout=30).record_failure()
    _fresh_breaker("tongyi_llm", threshold=1, recovery_timeout=30).record_failure()

    start = time.monotonic()
    with pytest.raises(CircuitBreakerOpenError, match="快速失败"):
        async for _ in chat_llm.stream_chat_tokens([{"role": "user", "content": "hi"}]):
            pass
    elapsed = time.monotonic() - start

    assert elapsed < 1.0, f"双熔断快速失败应无耗时，实际 {elapsed:.2f}s"
