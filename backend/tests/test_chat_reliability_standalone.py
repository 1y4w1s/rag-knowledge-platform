"""可靠性测试 — 仅测 chat_llm 模块（不依赖 DB / LLM 外部服务）。

用法：
  cd backend
  python tests/test_chat_reliability_standalone.py              # 直接运行（自动注入 mock metrics_registry）
  python -m pytest tests/test_chat_reliability_standalone.py -x -v  # pytest 模式（走 conftest）

注意：mock metrics_registry 只允许在 __main__ 里注入。放在模块顶层会污染
sys.modules，导致全量收集时 3 个 metrics 测试 ImportError（CI collect 门禁会红）。
"""
from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from typing import Self

# 确保能找到 app 模块
_BACKEND_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.core.config import settings  # noqa: E402
from app.services.rag import chat_llm  # noqa: E402
from app.services.rag.chat_llm import _build_chat_provider_chain, _endpoint_for  # noqa: E402


# ── Mock 辅助类 ───────────────────────────────────────────────────


class _FakeStreamOk:
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


class _FakeStreamErr:
    class _RaiseOnEnter:
        """httpx 错误响应 mock — raise_for_status 是 sync。"""
        def raise_for_status(self) -> None:
            raise RuntimeError("mock: 上游服务不可用 (502)")

        async def aiter_lines(self) -> AsyncIterator[str]:
            return
            yield

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

    def stream(self, *args, **kwargs) -> _RaiseOnEnter:
        del args, kwargs
        return self._RaiseOnEnter()


class _OkClient:
    def __init__(self, token: str = "ok"):
        self.token = token

    def stream(self, method: str, url: str, *, headers: dict, json: dict) -> _FakeStreamOk:
        del method, url, headers, json
        return _FakeStreamOk(self.token)


class _FailClient:
    def stream(self, *args, **kwargs) -> _FakeStreamErr._RaiseOnEnter:
        del args, kwargs
        return _FakeStreamErr._RaiseOnEnter()


async def _passthrough_retry(factory, **kwargs):
    del kwargs
    async for item in factory():
        yield item


# ── 测试前重置 ────────────────────────────────────────────────────


def _reset():
    settings.chat_provider = "deepseek"
    settings.deepseek_api_key = "sk-ds-primary"
    settings.tongyi_api_key = "sk-ty-fallback"
    settings.deepseek_base_url = "https://api.deepseek.com"
    settings.deepseek_model = "deepseek-chat"
    settings.tongyi_chat_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    settings.tongyi_chat_model = "qwen-plus"


# ═══════════════════════════════════════════════════════════════════
#  测试用例
# ═══════════════════════════════════════════════════════════════════


def test_build_chain_both_keys():
    """两个 provider 都有 key → 链长 2。"""
    _reset()
    chain = _build_chat_provider_chain("deepseek")
    assert chain == ["deepseek", "tongyi"], f"期望 [deepseek, tongyi], 得到 {chain}"

    chain = _build_chat_provider_chain("tongyi")
    assert chain == ["tongyi", "deepseek"], f"期望 [tongyi, deepseek], 得到 {chain}"


def test_build_chain_fallback_no_key():
    """备用无 key → 链长 1。"""
    _reset()
    settings.tongyi_api_key = ""
    chain = _build_chat_provider_chain("deepseek")
    assert chain == ["deepseek"], f"期望 [deepseek], 得到 {chain}"


def test_build_chain_primary_no_key_but_fallback_has():
    """主无 key 但备用有 → 链含主（无 key 调用方过滤）。"""
    _reset()
    settings.deepseek_api_key = ""
    chain = _build_chat_provider_chain("deepseek")
    assert chain == ["deepseek", "tongyi"], f"期望 [deepseek, tongyi], 得到 {chain}"


def test_endpoint_for_deepseek():
    _reset()
    ep = _endpoint_for("deepseek")
    assert ep[0] == "https://api.deepseek.com"
    assert ep[1] == "sk-ds-primary"
    assert ep[2] == "deepseek-chat"
    assert ep[3] == "deepseek_llm"


def test_endpoint_for_tongyi():
    _reset()
    ep = _endpoint_for("tongyi")
    assert ep[0] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert ep[1] == "sk-ty-fallback"
    assert ep[2] == "qwen-plus"
    assert ep[3] == "tongyi_llm"


async def _run_stream(primary_ok=True, fallback_ok=True, fallback_key=True):
    """运行 stream_chat_tokens 并返回收集的文本。"""
    _reset()
    if not fallback_key:
        settings.tongyi_api_key = ""

    old_ds = chat_llm.get_deepseek_client
    old_ty = chat_llm.get_tongyi_client
    old_retry = chat_llm.retry_stream

    chat_llm.get_deepseek_client = lambda: _OkClient() if primary_ok else _FailClient()
    chat_llm.get_tongyi_client = lambda: _OkClient(token="fallback-ok") if fallback_ok else _FailClient()
    chat_llm.retry_stream = _passthrough_retry

    try:
        parts = []
        async for t in chat_llm.stream_chat_tokens([{"role": "user", "content": "hi"}]):
            parts.append(t)
        return "".join(parts)
    finally:
        chat_llm.get_deepseek_client = old_ds
        chat_llm.get_tongyi_client = old_ty
        chat_llm.retry_stream = old_retry


async def _run_stream_raises(primary_ok=False, fallback_ok=False, fallback_key=True):
    """运行 stream_chat_tokens，期望抛异常，返回异常消息。"""
    _reset()
    if not fallback_key:
        settings.tongyi_api_key = ""

    old_ds = chat_llm.get_deepseek_client
    old_ty = chat_llm.get_tongyi_client
    old_retry = chat_llm.retry_stream

    chat_llm.get_deepseek_client = lambda: _OkClient() if primary_ok else _FailClient()
    chat_llm.get_tongyi_client = lambda: _OkClient(token="fallback-ok") if fallback_ok else _FailClient()
    chat_llm.retry_stream = _passthrough_retry

    try:
        async for _ in chat_llm.stream_chat_tokens([{"role": "user", "content": "hi"}]):
            pass
        return None  # should not reach
    except Exception as e:
        return str(e)
    finally:
        chat_llm.get_deepseek_client = old_ds
        chat_llm.get_tongyi_client = old_ty
        chat_llm.retry_stream = old_retry


# ── async 测试 ────────────────────────────────────────────────────


def test_primary_succeeds():
    """主 provider 成功 → 返回主 provider 的回答。"""
    result = asyncio.run(_run_stream(primary_ok=True, fallback_ok=True))
    assert result == "ok", f"期望 'ok', 得到 {result!r}"


def test_primary_fails_fallback_succeeds():
    """主失败 → fallback 成功 → 返回 fallback 回答。"""
    result = asyncio.run(_run_stream(primary_ok=False, fallback_ok=True))
    assert result == "fallback-ok", f"期望 'fallback-ok', 得到 {result!r}"


def test_both_fail():
    """主 + fallback 均失败 → 抛异常。"""
    err = asyncio.run(_run_stream_raises(primary_ok=False, fallback_ok=False))
    assert err is not None, "期望异常，但未抛出"
    assert "上游服务不可用" in err, f"异常消息不匹配: {err}"


def test_no_fallback_key_primary_fails():
    """备用无 key + 主失败 → 抛异常（不尝试备用）。"""
    err = asyncio.run(_run_stream_raises(primary_ok=False, fallback_ok=True, fallback_key=False))
    assert err is not None, "期望异常，但未抛出"
    assert "上游服务不可用" in err, f"异常消息不匹配: {err}"


def test_no_keys_mock():
    """两个 provider 均无 key → 返回 mock。"""
    _reset()
    settings.deepseek_api_key = ""
    settings.tongyi_api_key = ""

    old_ds = chat_llm.get_deepseek_client
    old_ty = chat_llm.get_tongyi_client
    old_retry = chat_llm.retry_stream

    chat_llm.get_deepseek_client = lambda: _FailClient()
    chat_llm.get_tongyi_client = lambda: _FailClient()
    chat_llm.retry_stream = _passthrough_retry

    try:
        result = asyncio.run(_collect_stream())
        assert result == "根据知识库内容回答", f"期望 mock, 得到 {result!r}"
    finally:
        chat_llm.get_deepseek_client = old_ds
        chat_llm.get_tongyi_client = old_ty
        chat_llm.retry_stream = old_retry


async def _collect_stream():
    parts = []
    async for t in chat_llm.stream_chat_tokens([{"role": "user", "content": "hi"}]):
        parts.append(t)
    return "".join(parts)


# ═══════════════════════════════════════════════════════════════════
#  入口
# ═══════════════════════════════════════════════════════════════════

tests = [
    ("test_build_chain_both_keys", test_build_chain_both_keys),
    ("test_build_chain_fallback_no_key", test_build_chain_fallback_no_key),
    ("test_build_chain_primary_no_key_but_fallback_has", test_build_chain_primary_no_key_but_fallback_has),
    ("test_endpoint_for_deepseek", test_endpoint_for_deepseek),
    ("test_endpoint_for_tongyi", test_endpoint_for_tongyi),
    ("test_primary_succeeds", test_primary_succeeds),
    ("test_primary_fails_fallback_succeeds", test_primary_fails_fallback_succeeds),
    ("test_both_fail", test_both_fail),
    ("test_no_fallback_key_primary_fails", test_no_fallback_key_primary_fails),
    ("test_no_keys_mock", test_no_keys_mock),
]

if __name__ == "__main__":
    # 仅直接运行时注入 mock metrics_registry（绕过真实模块的 Document 模型导入链）。
    # 禁止上移到模块顶层：会污染 sys.modules，使 pytest 全量收集时 3 个 metrics 测试 ImportError。
    import types

    _mock_metrics = types.ModuleType("app.services.observability.metrics_registry")
    _mock_metrics.inc_llm_success = lambda: None
    _mock_metrics.inc_llm_failure = lambda: None
    sys.modules["app.services.observability.metrics_registry"] = _mock_metrics

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  OK  {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL {name}: {e}")
            failed += 1

    print(f"\n{'=' * 40}")
    print(f"{passed}/{passed + failed} 通过")
    if failed:
        print(f"失败: {failed}")
        exit(1)
    else:
        print("全部通过")
