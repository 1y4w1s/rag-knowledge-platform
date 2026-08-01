"""D1 GraphRAG — Query NER：从用户提问中实时抽取实体名。

对齐 extract_entities_sync 范式：httpx.Client + get_breaker + inc_llm_*。
区别：
- 只返回实体名列表（list[str]），不做类型/关系抽取
- 超时 8s（热路径，非 ingestion 的 60s）
- 接受可选 context 用于代词解析
"""

from __future__ import annotations

import json
import logging

import httpx

from app.core.config import settings
from app.core.retry import get_breaker
from app.services.observability.metrics_registry import inc_llm_failure, inc_llm_success

logger = logging.getLogger(__name__)

_QUERY_NER_PROMPT = """从以下用户问题中识别出知识库中的实体名称。
注意：实体可能是人名、组织名、项目名、合同号、金额、日期、产品名。
如果是代词（它、他、她、他们、这个、那个等），结合对话历史推断所指的实体名。
仅返回实体名称列表的 JSON 格式：
{{"entities": ["名称1", "名称2"]}}
不要包含任何其他文本。

用户问题：{query}"""

_CONTEXT_HINT = """
对话历史：
{context}"""

_MAX_RETRIES = 1  # 热路径，只重试 1 次


def _build_prompt(query: str, context: list[dict[str, str]] | None) -> str:
    """构造 prompt。有 context 时追加对话历史以支持代词解析。

    context 元素 schema：{"role": "user"|"assistant", "content": str}
    用 .get() 访问以防御 KeyError。
    """
    prompt = _QUERY_NER_PROMPT.format(query=query)
    if context:
        # 取最近 4 条消息（约 2 轮 user+assistant），避免 token 浪费
        recent = context[-4:]
        ctx_text = "\n".join(
            f'{m.get("role", "unknown")}: {m.get("content", "")[:500]}' for m in recent
        )
        prompt += _CONTEXT_HINT.format(context=ctx_text)
    return prompt


def query_ner_sync(
    query: str,
    context: list[dict[str, str]] | None = None,
) -> list[str]:
    """同步调用 DeepSeek JSON mode 抽取实体名。

    纯同步函数（内部用 httpx.Client），必须通过
    await asyncio.to_thread(query_ner_sync, query, context) 调用。
    超时 8s。

    返回实体名称列表，失败/超时返回 []（降级为纯词法匹配）。
    """
    api_key = settings.deepseek_api_key
    if not api_key:
        logger.warning("query_ner_sync: DEEPSEEK_API_KEY 未配置")
        return []

    base_url = (settings.deepseek_base_url or "").rstrip("/")
    url = f"{base_url}/chat/completions"
    model = settings.deepseek_model or "deepseek-chat"

    prompt = _build_prompt(query, context)
    messages = [
        {"role": "system", "content": prompt},
    ]
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 256,  # NER 只需少量 token
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    breaker = get_breaker("deepseek_llm")
    for attempt in range(_MAX_RETRIES):
        try:
            with httpx.Client(timeout=8) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                raw = resp.json()["choices"][0]["message"]["content"] or ""
                breaker.record_success()
                inc_llm_success()
                parsed = _try_parse_name_list(raw)
                logger.debug(
                    "query_ner_sync: query=%.40s entities=%s",
                    query, parsed,
                )
                return parsed
        except Exception as e:
            breaker.record_failure()
            inc_llm_failure()
            logger.warning(
                "query_ner_sync 尝试 %d/%d 失败: %s",
                attempt + 1, _MAX_RETRIES, e,
            )
            if attempt == _MAX_RETRIES - 1:
                return []
    return []


def _try_parse_name_list(raw: str) -> list[str]:
    """尝试解析 JSON 响应为实体名列表。"""
    try:
        data = json.loads(raw)
        entities = data.get("entities", [])
        if isinstance(entities, list):
            return [str(e).strip() for e in entities if e]
    except (json.JSONDecodeError, ValueError):
        pass
    # 兜底：截取第一个 [...] 再试
    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end > start:
        candidate = raw[start : end + 1]
        try:
            data = json.loads(candidate)
            if isinstance(data, list):
                return [str(e).strip() for e in data if e]
        except (json.JSONDecodeError, ValueError):
            pass
    logger.warning("query_ner_sync: 畸形响应，返回空列表. raw=%.200s", raw)
    return []
