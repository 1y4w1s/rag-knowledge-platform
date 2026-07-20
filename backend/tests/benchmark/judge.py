"""LLM-as-judge 评估器（v1.0 加固版：few-shot + 引用评估 + 完整统计）。

企业评测体系 Phase 2 — 生成质量全维度评估。

评估维度：
1. 正确性（Correctness）：与 golden answer 一致性（few-shot 校准）
2. 引用准确性（Citation Accuracy）：LLM 评估引用是否真实支撑答案
3. 拒答正确性（Rejection Correctness）：无依据时是否正确拒答

用法:
    judge = LLMJudge()
    score, reason = await judge.evaluate_correctness(query, answer, golden)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.rag.generation import stream_deepseek_tokens

logger = logging.getLogger(__name__)

# ———— Correctness Judge（含 few-shot）————

CORRECTNESS_SYSTEM = """你是一个严谨的 RAG 答案质量评估专家。你负责评估 AI 助手的回答是否正确地回答了用户的问题。

评估标准（满分 1.0）：
- 1.0：完全正确，与黄金答案一致，包含所有关键信息，无错误
- 0.8：大部分正确，关键信息完整，但缺少次要细节
- 0.6：部分正确，包含一些关键信息，但也有明显遗漏或少量错误
- 0.4：少量正确，大部分内容错误或与黄金答案不符
- 0.2：几乎完全错误，仅有一小部分相关
- 0.0：完全错误、拒绝回答（当黄金答案存在时）、或编造信息

请严格评分，不要有偏袒倾向。只输出 JSON。"""

CORRECTNESS_FEW_SHOT = """
以下是一些评分示例：

示例 1：
用户问题：年假有多少天？
黄金答案：正式员工每年有10天年假。
AI回答：正式员工每年有10天年假，需提前两周申请。
评分：{"score": 1.0, "reason": "完全正确，且额外提供了申请时限信息（不扣分）"}

示例 2：
用户问题：年假有多少天？
黄金答案：正式员工每年有10天年假。
AI回答：年假有5天。
评分：{"score": 0.0, "reason": "答案错误，与黄金答案矛盾"}

示例 3：
用户问题：出差到一线城市每天补贴多少？
黄金答案：一线城市每天200元。
AI回答：出差补贴因城市而异，一线城市标准较高。
评分：{"score": 0.4, "reason": "方向正确但未给出具体金额"}

--- 现在请评估以下内容 ---"""

CORRECTNESS_PROMPT = """【用户问题】
{query}

【黄金标准答案】
{golden_answer}

【AI 助手的回答】
{generated_answer}

请仅输出 JSON：{{"score": <0.0-1.0>, "reason": "<简短理由（中文）>"}}"""

# ———— Rejection Judge ————

REJECTION_SYSTEM = """你是一个 RAG 拒答行为评估专家。评估 AI 助手是否在应该拒答时正确拒答。

评分标准：
- 1.0：正确拒答 — AI 明确表示"知识库中未找到相关内容"、"手册中没有"、"无法从提供的信息中回答"等，且没有编造答案
- 0.0：错误 — AI 编造了答案、给出了具体信息（即使语气不确定也算）

注意：如果 AI 说"根据员工手册..."或引用具体条款，即使说"没有找到"，只要后面跟了具体内容就是编造。
只输出 JSON。"""

REJECTION_PROMPT = """【用户问题】
{query}

【AI 助手的回答】
{generated_answer}

请仅输出 JSON：{{"score": <0.0 or 1.0>, "reason": "<简短理由>"}}"""

# ———— Citation Accuracy Judge ————

CITATION_SYSTEM = """你是一个引用准确性评估专家。检查 AI 回答中的引用是否真实来自其引用的文档片段。

评估每一条引用：
1. 引用内容是否在提供的文档片段中出现
2. 引用是否与答案中声称的内容一致
3. 是否有编造不存在的引用

输出 JSON 格式。"""

CITATION_PROMPT = """【AI 回答】
{answer}

【引用列表】
{citations}

评估标准：
- 1.0：所有引用都真实有效，内容与文档片段一致
- 0.7：大部分引用有效，少数引用略有偏差
- 0.4：部分引用有效，但存在编造或不一致
- 0.0：引用完全编造或大部分无效

请仅输出 JSON：{{"score": <0.0-1.0>, "reason": "<简短理由>"}}"""


class LLMJudge:
    """LLM-as-judge 评估器（v1.0 加固版）。"""

    def __init__(self) -> None:
        self._total_calls = 0
        self._total_est_tokens = 0

    @property
    def stats(self) -> dict[str, int]:
        return {"judge_calls": self._total_calls, "judge_est_tokens": self._total_est_tokens}

    async def evaluate_correctness(
        self,
        query: str,
        generated_answer: str,
        golden_answer: str | None,
    ) -> tuple[float, str]:
        """评估答案正确性。"""
        if not golden_answer or not golden_answer.strip():
            return 0.0, "no golden answer available"

        prompt = CORRECTNESS_SYSTEM + CORRECTNESS_FEW_SHOT + CORRECTNESS_PROMPT.format(
            query=str(query)[:500],
            golden_answer=str(golden_answer)[:1000],
            generated_answer=str(generated_answer)[:2000],
        )
        result = await self._call_llm(prompt)
        return self._parse_score(result, default=0.0)

    async def evaluate_rejection(
        self,
        query: str,
        generated_answer: str,
    ) -> tuple[float, str]:
        """评估拒答正确性。"""
        prompt = REJECTION_SYSTEM + REJECTION_PROMPT.format(
            query=str(query)[:500],
            generated_answer=str(generated_answer)[:1000],
        )
        result = await self._call_llm(prompt)
        return self._parse_score(result, default=0.0)

    async def evaluate_citation_accuracy(
        self,
        generated_answer: str,
        citations: list[dict[str, Any]],
    ) -> tuple[float, str]:
        """评估引用准确性（LLM 评估）。"""
        if not citations:
            return 0.0, "no citations provided"

        cites_str = "\n".join(
            "- 文档「%s」: %s" % (c.get("doc_name", "?"), str(c.get("content", c.get("excerpt", "")))[:200])
            for c in citations[:10]
        )
        prompt = CITATION_SYSTEM + CITATION_PROMPT.format(
            answer=str(generated_answer)[:1000],
            citations=cites_str,
        )
        result = await self._call_llm(prompt)
        return self._parse_score(result, default=0.0)

    async def verify_calibration(self, calibration_path: str | None = None) -> dict:
        """用预标注校准集验证评分一致性。"""
        import json, os
        path = calibration_path or os.path.join(
            os.path.dirname(__file__), "..", "fixtures", "judge_calibration.json"
        )
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return {"status": "SKIP", "reason": f"calibration file not found: {path}"}

        results = []
        for item in data.get("items", []):
            query = item["query"]
            golden = item.get("golden_answer", "")

            # 用 golden 自身作为 generated_answer 测试 -> 应得高分
            score, reason = await self.evaluate_correctness(query, golden, golden)
            results.append({
                "case_id": item["case_id"],
                "score": score,
                "expected_ge": 0.8,  # self-match 应 >= 0.8
                "pass": score >= 0.8,
            })

        passed = sum(1 for r in results if r["pass"])
        total = len(results)
        pass_rate = passed / total if total > 0 else 0
        return {
            "status": "PASS" if pass_rate >= 0.8 else "WARN",
            "passed": passed,
            "total": total,
            "pass_rate": round(pass_rate, 2),
            "failures": [r for r in results if not r["pass"]],
        }

    async def _call_llm(self, prompt: str) -> str:
        """调用 DeepSeek。"""
        self._total_calls += 1
        messages = [
            {"role": "system", "content": "你是严谨的 AI 评估专家。只输出要求的 JSON 格式。"},
            {"role": "user", "content": prompt},
        ]
        parts: list[str] = []
        async for token in stream_deepseek_tokens(messages):
            parts.append(token)
        result = "".join(parts)
        self._total_est_tokens += len(result) // 4
        return result

    @staticmethod
    def _parse_score(result: str, default: float = 0.0) -> tuple[float, str]:
        """从 DeepSeek 输出中解析 JSON 分数。"""
        try:
            start = result.index("{")
            end = result.rindex("}") + 1
            data = json.loads(result[start:end])
            score = float(data.get("score", default))
            reason = str(data.get("reason", ""))
            return max(0.0, min(1.0, score)), reason
        except (ValueError, json.JSONDecodeError, TypeError):
            logger.warning("Judge parse failed: %s", str(result)[:100])
            return default, "parse failed"
