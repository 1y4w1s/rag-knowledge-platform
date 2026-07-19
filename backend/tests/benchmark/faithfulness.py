"""Faithfulness Judge：答案忠实度评估器（Decompose-then-Verify）。

企业评测体系 Phase 2 — 生成质量全维度评估。

方法：
1. Decompose: 用 LLM 将生成答案拆解为原子断言（atomic claims）
2. Verify: 逐一验证每个断言是否被检索到的 chunks 支持
3. Score: 被支持的 claims / 总 claims = 忠实度分数

用法:
    judge = FaithfulnessJudge()
    score, halluc_rate = await judge.evaluate(answer, citations)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.http_client import get_deepseek_client
from app.services.rag.generation import stream_deepseek_tokens

logger = logging.getLogger(__name__)

DECOMPOSE_PROMPT = """你是一个答案分解专家。请将下面的 AI 回答分解为若干"原子断言"（atomic claims）。

原子断言的定义：
- 每个断言是回答中一个不可再分的事实性陈述
- 每个断言必须能被单独验证为"真"或"假"
- 不包含逻辑连接词（如"而且"、"但是"、"因为"——应拆开）
- 不包含主观判断或建议

【回答】
{answer}

请将输出格式化为 JSON 数组：
["断言1", "断言2", ...]

只输出 JSON，不要额外内容。"""

VERIFY_PROMPT = """你是一个事实核查专家。请判断下面的断言是否能从给定的上下文片段中得到支持。

【断言】
{claim}

【上下文片段】
{context}

判断标准：
- SUPPORTED: 上下文明确包含或直接支持该断言，无矛盾
- NOT_SUPPORTED: 上下文中找不到该断言的信息，或存在矛盾
- PARTIAL: 上下文部分支持该断言，但缺少一些细节

请仅输出 JSON：{{"verdict": "SUPPORTED" | "NOT_SUPPORTED" | "PARTIAL", "evidence": "<引用文本片段或'无'>"}}"""


class FaithfulnessJudge:
    """答案忠实度评估器。

    使用 DeepSeek 对生成答案做 Decompose-then-Verify 忠实度评估。
    """

    def __init__(self) -> None:
        self._total_calls = 0

    async def evaluate(
        self,
        answer: str,
        citations: list[dict[str, Any]],
    ) -> tuple[float, float]:
        """评估答案忠实度。

        Args:
            answer: 系统生成的回答
            citations: 引用的 chunks 列表（含 content）

        Returns:
            (faithfulness_score 0.0-1.0, hallucination_rate 0.0-1.0)
        """
        if not answer or not answer.strip():
            return 1.0, 0.0

        # Step 1: Decompose
        claims = await self._decompose(answer)
        if not claims:
            return 1.0, 0.0

        # Step 2: Build context from citations
        context_parts = []
        for c in citations:
            content = c.get("content", c.get("excerpt", ""))
            doc_name = c.get("doc_name", c.get("document_name", ""))
            if content:
                context_parts.append("[%s] %s" % (doc_name, content[:500]))
        context = "\n\n".join(context_parts) if context_parts else "(无引用上下文)"

        # Step 3: Verify each claim
        supported = 0
        partial = 0
        not_supported = 0

        for claim in claims:
            verdict = await self._verify(claim, context)
            if verdict == "SUPPORTED":
                supported += 1
            elif verdict == "PARTIAL":
                partial += 1
            else:
                not_supported += 1

        total = len(claims)
        faithfulness = (supported + 0.5 * partial) / max(1, total)
        hallucination = (not_supported + 0.5 * partial) / max(1, total)

        logger.debug("Faithfulness: %d/%d supported, %d partial, %d not (score=%.2f, hallu=%.2f)",
                      supported, total, partial, not_supported, faithfulness, hallucination)
        return faithfulness, hallucination

    async def _decompose(self, answer: str) -> list[str]:
        """将答案分解为原子断言列表。"""
        self._total_calls += 1
        prompt = DECOMPOSE_PROMPT.format(answer=answer[:2000])
        result = await self._call_llm(prompt)
        try:
            # 提取 JSON 数组
            start = result.index("[")
            end = result.rindex("]") + 1
            claims = json.loads(result[start:end])
            if isinstance(claims, list):
                return [str(c).strip() for c in claims if str(c).strip()]
        except (ValueError, json.JSONDecodeError):
            # Fallback: 按句子拆分
            return [s.strip() for s in re.split(r"[。！？\n]", answer) if len(s.strip()) > 4]
        return []

    async def _verify(self, claim: str, context: str) -> str:
        """验证单个断言是否被上下文支持。"""
        self._total_calls += 1
        prompt = VERIFY_PROMPT.format(claim=claim[:300], context=context[:2000])
        result = await self._call_llm(prompt)
        try:
            start = result.index("{")
            end = result.rindex("}") + 1
            data = json.loads(result[start:end])
            return str(data.get("verdict", "NOT_SUPPORTED"))
        except (ValueError, json.JSONDecodeError):
            if "supported" in result.lower():
                return "SUPPORTED"
            return "NOT_SUPPORTED"

    async def _call_llm(self, prompt: str) -> str:
        """调用 DeepSeek。"""
        messages = [
            {"role": "system", "content": "你是严谨的分析专家。只输出要求的格式。"},
            {"role": "user", "content": prompt},
        ]
        parts: list[str] = []
        async for token in stream_deepseek_tokens(messages):
            parts.append(token)
        return "".join(parts)

    @property
    def stats(self) -> dict[str, int]:
        return {"faithfulness_calls": self._total_calls}
