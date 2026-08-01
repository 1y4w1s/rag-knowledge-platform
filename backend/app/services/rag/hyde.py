"""HyDE（Hypothetical Document Embedding）检索增强。

原理：query → LLM 生成假设文档 → 用假设文档做 embedding → 检索。
假设文档的向量比 query 向量更贴近文档分布，提升召回。

闸门：HYDE_ENABLED=true 环境变量（默认关闭）。
LLM：复用 complete_chat()（熔断链 + provider 回退 + 无 key mock）。
"""

from __future__ import annotations

import logging
import os

from app.services.rag.chat_llm import complete_chat

logger = logging.getLogger(__name__)

# ── 判断是否启用 ──

_HYDE_ENABLED: bool | None = None


def is_hyde_enabled() -> bool:
    """运行时判断 HyDE 是否启用（缓存环境变量结果）。"""
    global _HYDE_ENABLED
    if _HYDE_ENABLED is None:
        val = os.environ.get("HYDE_ENABLED", "false").strip().lower()
        _HYDE_ENABLED = val in ("true", "1", "yes")
    return _HYDE_ENABLED


# ── Prompt 模板 ──

HYDE_SYSTEM_PROMPT = (
    "你是一名检索专家。请根据用户的问题，撰写一段详细的文档段落，"
    "这段文档应当能完美回答该问题。"
)

HYDE_USER_PROMPT = """\
要求：
1. 用中文回答
2. 包含具体细节、数据、例子
3. 以陈述语气写，不要出现"根据问题""针对这个问题"等元描述
4. 长度 100-300 字

问题：{query}

假设文档："""


# ── 核心函数 ──

async def generate_hypothetical_document(query: str) -> str | None:
    """根据 query 生成假设文档。

    复用 complete_chat()（包了熔断链 + provider 回退 + 无 key mock），
    不自建 LLM client。

    Args:
        query: 用户原始查询。

    Returns:
        生成的假设文档文本；如果生成失败返回 None（调用方回退到原始 query）。
    """
    if not query or not query.strip():
        logger.warning("hyde: 空 query，跳过生成")
        return None

    if not is_hyde_enabled():
        return None

    messages: list[dict[str, str]] = [
        {"role": "system", "content": HYDE_SYSTEM_PROMPT},
        {"role": "user", "content": HYDE_USER_PROMPT.format(query=query.strip())},
    ]

    try:
        result = await complete_chat(messages)
        result = result.strip()
        if not result:
            logger.warning("hyde: complete_chat 返回空，降级")
            return None
        logger.info(
            "hyde: 生成成功 query_len=%d hyde_len=%d preview=%.60s",
            len(query), len(result), result,
        )
        return result
    except Exception as e:
        logger.warning("hyde: complete_chat 失败: %s，降级到原始 query", e)
        return None
