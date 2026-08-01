"""RAGAS 快速验证：用 DeepSeek judge 替代 GPT-4。

用法（容器内）：
    cd /app && PYTHONPATH=/app:/app/tests GIT_PYTHON_REFRESH=quiet \
        python scripts/run_ragas_smoke.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

GOLDEN_PATH = Path("/app/tests/fixtures/golden_qa.json")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")


def load_golden(n: int = 5) -> list[dict]:
    data = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    cases = data.get("cases", data) if isinstance(data, dict) else data
    result = []
    for c in cases:
        if len(result) >= n:
            break
        if c.get("expect_rejection"):
            continue
        expect = c.get("expect", {}) or {}
        if "content_contains" not in expect:
            continue
        result.append({
            "case_id": c.get("case_id", ""),
            "question": c.get("query", ""),
            "ground_truth": expect["content_contains"],
        })
    return result


async def run_ragas(qa_list: list[dict]) -> dict | None:
    try:
        from datasets import Dataset as HFDataset
        from langchain_openai import ChatOpenAI
        from ragas import evaluate
        from ragas.metrics import faithfulness
    except ImportError as e:
        logger.error("RAGAS 依赖未安装: %s", e)
        return None

    if not DEEPSEEK_API_KEY:
        logger.error("DEEPSEEK_API_KEY 未设置")
        return None

    questions = [q["question"] for q in qa_list]
    answers = [q["ground_truth"][:200] for q in qa_list]
    contexts = [[q["ground_truth"][:200]] for q in qa_list]
    ground_truths = [q["ground_truth"] for q in qa_list]

    # 用 ChatOpenAI 指向 DeepSeek，覆盖 RAGAS 默认的 gpt-4o-mini
    deepseek_llm = ChatOpenAI(
        model="deepseek-v4-flash",
        openai_api_key=DEEPSEEK_API_KEY,
        openai_api_base=DEEPSEEK_BASE_URL,
    )
    faithfulness.llm = deepseek_llm

    dataset = HFDataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths,
    })

    logger.info("RAGAS evaluate（%d 题, judge=deepseek-v4-flash）...", len(questions))
    t0 = time.time()
    result = evaluate(dataset, metrics=[faithfulness])
    elapsed = time.time() - t0
    logger.info("RAGAS 完成 (%.1fs)", elapsed)

    scores = []
    for i in range(len(questions)):
        scores.append({
            "case_id": qa_list[i]["case_id"],
            "faithfulness": float(result["faithfulness"][i]),
        })

    avg_f = sum(s["faithfulness"] for s in scores) / len(scores) if scores else 0

    return {
        "total": len(scores),
        "faithfulness_avg": round(avg_f, 4),
        "detailed": scores,
        "elapsed_s": round(elapsed, 1),
        "judge": "deepseek-v4-flash",
    }


async def main() -> None:
    qa_list = load_golden(n=5)
    logger.info("加载 %d 条 golden QA", len(qa_list))

    logger.info("=== 运行 RAGAS ===")
    result = await run_ragas(qa_list)

    if result:
        logger.info("")
        logger.info("=" * 50)
        logger.info("RAGAS 验证结果")
        logger.info("=" * 50)
        logger.info("  Judge:              %s", result["judge"])
        logger.info("  题数:               %d", result["total"])
        logger.info("  Faithfulness:       %.2f%%", result["faithfulness_avg"] * 100)
        logger.info("  耗时:               %.1fs", result["elapsed_s"])
        logger.info("")
        for s in result["detailed"]:
            logger.info("  %s: faith=%.2f%%",
                       s["case_id"], s["faithfulness"] * 100)

        out = Path("/app/benchmark_results/ragas_smoke.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        logger.info("结果已保存: %s", out)
    else:
        logger.error("RAGAS 运行失败")


if __name__ == "__main__":
    asyncio.run(main())
