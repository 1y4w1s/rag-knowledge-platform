#!/usr/bin/env python
"""从已保存的 Faithfulness 结果重新运行 RAGAS 对比（仅 faithfulness）"""
import asyncio
import json
import logging
import os
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RESULTS_PATH = Path("/app/benchmark_results/faithfulness_enterprise_qa.json")

async def main():
    data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    results = data.get("results", [])
    logger.info("加载 %d 条结果", len(results))

    # Collect RAGAS data
    case_ids, answers, contexts_list = [], [], []
    for r in results:
        if r.get("faithfulness") is not None and not r.get("skipped") and r.get("answer"):
            case_ids.append(r["case_id"])
            answers.append(r["answer"])
            contexts_list.append(r.get("contexts", []))

    logger.info("RAGAS 评估: %d 题", len(case_ids))
    if not case_ids:
        logger.warning("无有效数据")
        return

    # Load questions from enterprise_qa.json
    qa_raw = json.loads(Path("/app/tests/fixtures/enterprise_qa.json").read_text(encoding="utf-8"))
    cases = qa_raw.get("cases", qa_raw)
    qa_map = {c["case_id"]: c["query"] for c in cases}
    questions = [qa_map.get(cid, "") for cid in case_ids]

    # RAGAS imports
    try:
        from datasets import Dataset as HFDataset
        from langchain_openai import ChatOpenAI
        from ragas import evaluate
        from ragas.metrics import faithfulness
    except ImportError as e:
        logger.error("RAGAS 依赖未安装: %s", e)
        return

    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    deepseek_base = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    if not deepseek_key:
        logger.error("DEEPSEEK_API_KEY 未设置")
        return

    os.environ["OPENAI_API_KEY"] = deepseek_key
    os.environ["OPENAI_API_BASE"] = deepseek_base

    deepseek_llm = ChatOpenAI(
        model="deepseek-chat",
        openai_api_key=deepseek_key,
        openai_api_base=deepseek_base,
    )

    data_hf = HFDataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts_list,
    })

    logger.info("RAGAS evaluate (judge=deepseek-chat, metric=faithfulness)...")
    t0 = time.time()
    try:
        result = evaluate(data_hf, metrics=[faithfulness], llm=deepseek_llm)
    except Exception as e:
        logger.error("RAGAS evaluate 失败: %s", e)
        import traceback
        traceback.print_exc()
        return
    elapsed = time.time() - t0
    logger.info("RAGAS 完成 (%.1fs)", elapsed)

    ragas_scores = {}
    for i, cid in enumerate(case_ids):
        ragas_scores[cid] = round(float(result["faithfulness"][i]), 4)

    # Compare
    total, f_own_sum, f_rag_sum = 0, 0.0, 0.0
    detailed = []
    for r in results:
        cid = r["case_id"]
        if r.get("faithfulness") is not None and cid in ragas_scores:
            total += 1
            f_own_sum += r["faithfulness"]
            f_rag_sum += ragas_scores[cid]
            detailed.append({
                "case_id": cid,
                "faithfulness_own": r["faithfulness"],
                "faithfulness_ragas": ragas_scores[cid],
            })

    if total == 0:
        logger.warning("无法对比")
        return

    avg_f_own = round(f_own_sum / total, 4)
    avg_f_rag = round(f_rag_sum / total, 4)

    logger.info("")
    logger.info("=" * 50)
    logger.info("RAGAS 对比结果（%d 题）", total)
    logger.info("=" * 50)
    logger.info("  FaithfulnessJudge (DeepSeek): %.2f%%", avg_f_own * 100)
    logger.info("  RAGAS faithfulness (DeepSeek): %.2f%%", avg_f_rag * 100)
    logger.info("  差值:                         %+.2f%%", (avg_f_own - avg_f_rag) * 100)

    summary = {
        "total": total,
        "faithfulness_own_avg": avg_f_own,
        "faithfulness_ragas_avg": avg_f_rag,
        "faithfulness_delta": round(avg_f_own - avg_f_rag, 4),
        "detailed": detailed,
    }

    # Update original file
    data["ragas"] = summary
    data["config"]["ragas"] = True
    RESULTS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    logger.info("结果已更新: %s", RESULTS_PATH)

asyncio.run(main())
