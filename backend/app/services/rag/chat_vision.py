"""C1 多模态 RAG — 同步版 Vision LLM 调用（Qwen-VL via DashScope）。

用于 ingestion 线程（asyncio.to_thread 内，无事件循环）。
熔断由 get_breaker("tongyi_llm").record_success/failure 手工标记。
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.core.retry import get_breaker
from app.services.observability.metrics_registry import inc_llm_failure, inc_llm_success

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2


def complete_chat_vision_sync(
    messages: list[dict[str, object]],
    max_tokens: int = 2048,
) -> str:
    """同步版多模态 chat 调用（Qwen-VL via DashScope /chat/completions）。

    Args:
        messages: OpenAI 格式 messages，支持多模态 content（text + image_url）。
        max_tokens: 最大生成 token 数。

    Returns:
        模型返回文本；失败或未配置时返回空字符串。
    """
    api_key = settings.tongyi_api_key
    if not api_key:
        logger.warning("complete_chat_vision_sync: TONGYI_API_KEY 未配置")
        return ""

    vl_model = settings.tongyi_vl_model or "qwen-vl-plus"
    base_url = (settings.tongyi_chat_base_url or "").rstrip("/")
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": vl_model,
        "messages": messages,
        "max_tokens": max_tokens,
    }

    breaker = get_breaker("tongyi_llm")
    for attempt in range(_MAX_RETRIES):
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"] or ""
                breaker.record_success()
                inc_llm_success()
                return content
        except Exception as e:
            breaker.record_failure()
            inc_llm_failure()
            logger.warning(
                "complete_chat_vision_sync 尝试 %d/%d 失败: %s",
                attempt + 1, _MAX_RETRIES, e,
            )
            if attempt == _MAX_RETRIES - 1:
                return ""
    return ""
