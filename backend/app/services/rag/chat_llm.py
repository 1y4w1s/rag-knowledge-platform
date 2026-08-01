"""对话 LLM 流式客户端（NW-9：env 可切换 DeepSeek / 通义 chat；熔断后自动切备用）。"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from app.core.config import settings
from app.core.http_client import get_deepseek_client, get_tongyi_client
from app.core.retry import retry_stream

logger = logging.getLogger(__name__)

TEMP_DETERMINISTIC: float = 0.0

_VALID_CHAT_PROVIDERS = frozenset({"deepseek", "tongyi"})


def resolve_chat_provider() -> str:
    """规范化 CHAT_PROVIDER；非法值回退 deepseek 并打 warning。"""
    raw = (settings.chat_provider or "deepseek").strip().lower()
    if raw in _VALID_CHAT_PROVIDERS:
        return raw
    logger.warning("非法 CHAT_PROVIDER=%r，回退 deepseek", settings.chat_provider)
    return "deepseek"


def active_chat_endpoint() -> tuple[str, str, str, str]:
    """返回 (base_url, api_key, model, breaker_name)。"""
    provider = resolve_chat_provider()
    return _endpoint_for(provider)


def _endpoint_for(provider: str) -> tuple[str, str, str, str]:
    """按 provider 返回 (base_url, api_key, model, breaker_name)。"""
    if provider == "tongyi":
        return (
            settings.tongyi_chat_base_url.rstrip("/"),
            settings.tongyi_api_key,
            settings.tongyi_chat_model,
            "tongyi_llm",
        )
    return (
        settings.deepseek_base_url.rstrip("/"),
        settings.deepseek_api_key,
        settings.deepseek_model,
        "deepseek_llm",
    )


def active_chat_api_key_configured() -> bool:
    return bool(active_chat_endpoint()[1])


def _make_stream_factory(
    provider: str,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
) -> callable:  # type: ignore[type-arg]
    """为指定 provider 创建流式工厂（闭包捕获按值，避免循环变量引用）。"""
    client_getter = get_tongyi_client if provider == "tongyi" else get_deepseek_client

    async def _make_stream() -> AsyncIterator[str]:
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": 0.3,
        }
        client = client_getter()
        async with client.stream("POST", url, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line.removeprefix("data: ").strip()
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                choices = data.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                text = delta.get("content")
                if text:
                    yield text

    return _make_stream


def _build_chat_provider_chain(primary: str) -> list[str]:
    """构造 provider 链：主 + 备用（有 key 时才加入链）。

    返回的列表中至少含主 provider；备用若未配置 key 则不加入。
    """
    alt = "tongyi" if primary == "deepseek" else "deepseek"
    alt_key = settings.tongyi_api_key if alt == "tongyi" else settings.deepseek_api_key

    chain = [primary]
    if alt_key:
        chain.append(alt)
    return chain


async def stream_chat_tokens(messages: list[dict[str, str]]) -> AsyncIterator[str]:
    """流式调用 chat provider，熔断/失败后自动切备用 provider。

    行为：
    1. 先尝试主 provider（env CHAT_PROVIDER 指定）。
    2. 若主 provider 失败且备用 provider 已配置 API key，自动切备用。
    3. 两个 provider 均失败 / 均无 key → 抛异常 / 回退 mock。

    Yields:
        文本 token。
    """
    primary = resolve_chat_provider()
    chain = _build_chat_provider_chain(primary)

    from app.services.observability.metrics_registry import inc_llm_failure, inc_llm_success

    # ── 均无 key → mock ──────────────────────────────────────────────
    endpoints_with_key = [(p, _endpoint_for(p)) for p in chain if _endpoint_for(p)[1]]
    if not endpoints_with_key:
        yield "根据"
        yield "知识库"
        yield "内容"
        yield "回答"
        return

    last_exc: Exception | None = None

    for idx, (prov, (base_url, api_key, model, breaker_name)) in enumerate(
        endpoints_with_key
    ):
        if idx > 0:
            logger.warning(
                "LLM provider 自动切换: %s → %s（主 provider 失败后 fallback）",
                endpoints_with_key[0][0],
                prov,
            )

        stream_factory = _make_stream_factory(prov, base_url, api_key, model, messages)

        try:
            async for token in retry_stream(
                stream_factory,
                max_retries=settings.retry_max_attempts,
                base_delay=settings.retry_base_delay,
                max_delay=settings.retry_max_delay,
                breaker_name=breaker_name,
            ):
                yield token
            inc_llm_success()
            return
        except Exception as exc:
            last_exc = exc
            inc_llm_failure()
            logger.warning(
                "LLM provider %s 失败（链中第 %d/%d）: %s",
                prov,
                idx + 1,
                len(endpoints_with_key),
                exc,
            )

    # 所有 provider 均失败
    if last_exc is not None:
        raise last_exc
    # 不应到达此处，但兜底
    yield "根据"
    yield "知识库"
    yield "内容"
    yield "回答"


# 兼容旧调用点（engine / agent / 测试）
stream_deepseek_tokens = stream_chat_tokens


async def complete_chat(messages: list[dict[str, str]]) -> str:
    """完整非流式 chat 调用，委托 stream_chat_tokens 返回拼接结果。"""
    return "".join([tok async for tok in stream_chat_tokens(messages)])
