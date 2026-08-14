"""对话 LLM 流式客户端（NW-9：env 可切换 DeepSeek / 通义 chat；熔断后自动切备用）。"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

from app.core.config import settings
from app.core.http_client import get_deepseek_client, get_tongyi_client
from app.core.retry import retry_stream

logger = logging.getLogger(__name__)

CHAT_TEMPERATURE: float = 0.3

_VALID_CHAT_PROVIDERS = frozenset({"deepseek", "tongyi"})


@dataclass(frozen=True, slots=True)
class ChatUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    prompt_cache_hit_tokens: int = 0
    prompt_cache_miss_tokens: int = 0
    provider: str = ""

    @property
    def has_value(self) -> bool:
        return self.prompt_tokens > 0 or self.completion_tokens > 0


def _non_negative_int(value: object) -> int:
    """非负整数；负数 / 非数字 / 缺失一律按 0 忽略（防上游脏数据）。"""
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(value, 0)


def parse_chat_usage(payload: dict, provider: str) -> ChatUsage | None:
    """从非流式/流式末尾 chunk 的 usage 归一化；无 usage 或全 0 返回 None。"""
    raw_usage = payload.get("usage")
    if not isinstance(raw_usage, dict):
        return None

    prompt_tokens = _non_negative_int(raw_usage.get("prompt_tokens"))
    completion_tokens = _non_negative_int(raw_usage.get("completion_tokens"))
    if "total_tokens" in raw_usage:
        total_tokens = _non_negative_int(raw_usage.get("total_tokens"))
    else:
        total_tokens = prompt_tokens + completion_tokens

    cache_hit = _non_negative_int(raw_usage.get("prompt_cache_hit_tokens"))
    if cache_hit <= 0:
        details = raw_usage.get("prompt_tokens_details")
        if isinstance(details, dict):
            cache_hit = _non_negative_int(details.get("cached_tokens"))
    cache_miss = _non_negative_int(raw_usage.get("prompt_cache_miss_tokens"))
    if cache_miss <= 0:
        cache_miss = max(0, prompt_tokens - cache_hit)

    usage = ChatUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        prompt_cache_hit_tokens=cache_hit,
        prompt_cache_miss_tokens=cache_miss,
        provider=provider,
    )
    return usage if usage.has_value else None


@dataclass(frozen=True, slots=True)
class _ChatStreamEvent:
    text: str = ""
    usage: ChatUsage | None = None


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


def has_available_chat_provider_key() -> bool:
    """任一 chat provider（主/备）已配置 API key（与 stream_chat_tokens mock 分支同口径）。"""
    primary = resolve_chat_provider()
    return any(
        _endpoint_for(provider)[1]
        for provider in _build_chat_provider_chain(primary)
    )


def _make_stream_factory(
    provider: str,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    *,
    include_usage: bool,
) -> Callable[[], AsyncIterator[_ChatStreamEvent]]:
    """为指定 provider 创建流式工厂（闭包捕获按值，避免循环变量引用）。"""
    client_getter = get_tongyi_client if provider == "tongyi" else get_deepseek_client

    async def _make_stream() -> AsyncIterator[_ChatStreamEvent]:
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": CHAT_TEMPERATURE,
        }
        if include_usage:
            payload["stream_options"] = {"include_usage": True}
        client = client_getter()
        last_usage: ChatUsage | None = None
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
                if choices:
                    delta = choices[0].get("delta") or {}
                    text = delta.get("content")
                    if text:
                        yield _ChatStreamEvent(text=text)
                else:
                    usage = parse_chat_usage(data, provider)
                    if usage is not None:
                        last_usage = usage
        if last_usage is not None:
            yield _ChatStreamEvent(usage=last_usage)

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


async def stream_chat_tokens(
    messages: list[dict[str, str]],
    *,
    usage_holder: list[ChatUsage | None] | None = None,
) -> AsyncIterator[str]:
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
    include_usage = settings.llm_usage_collection_enabled or usage_holder is not None

    from app.services.observability.metrics_registry import (
        inc_llm_chat_usage,
        inc_llm_failure,
        inc_llm_success,
    )

    # ── 均无 key → mock ──────────────────────────────────────────────
    endpoints_with_key = [(p, _endpoint_for(p)) for p in chain if _endpoint_for(p)[1]]
    if not endpoints_with_key:
        yield "根据"
        yield "知识库"
        yield "内容"
        yield "回答"
        if usage_holder is not None:
            usage_holder.append(None)
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

        stream_factory = _make_stream_factory(
            prov,
            base_url,
            api_key,
            model,
            messages,
            include_usage=include_usage,
        )

        try:
            last_usage: ChatUsage | None = None
            async for event in retry_stream(
                stream_factory,
                max_retries=settings.retry_max_attempts,
                base_delay=settings.retry_base_delay,
                max_delay=settings.retry_max_delay,
                breaker_name=breaker_name,
            ):
                if event.usage is not None:
                    last_usage = event.usage
                elif event.text:
                    yield event.text
            if last_usage is not None and settings.llm_usage_collection_enabled:
                inc_llm_chat_usage(last_usage.provider, last_usage)
                logger.info(
                    '{"event_type":"llm_usage","provider":"%s","prompt_tokens":%d,'
                    '"completion_tokens":%d,"cache_hit_tokens":%d,"cache_miss_tokens":%d}',
                    last_usage.provider,
                    last_usage.prompt_tokens,
                    last_usage.completion_tokens,
                    last_usage.prompt_cache_hit_tokens,
                    last_usage.prompt_cache_miss_tokens,
                )
            inc_llm_success()
            if usage_holder is not None:
                usage_holder.append(last_usage)
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


async def complete_chat_with_usage(
    messages: list[dict[str, str]],
) -> tuple[str, ChatUsage | None]:
    """完整非流式 chat 调用，额外返回 provider 真实 usage（无则 None）。"""
    holder: list[ChatUsage | None] = []
    text = "".join(
        [tok async for tok in stream_chat_tokens(messages, usage_holder=holder)]
    )
    return text, holder[0] if holder else None
