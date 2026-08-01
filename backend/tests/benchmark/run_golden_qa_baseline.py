"""Golden QA RAGAS 生成基线运行器。

用法：
    # 小样本验证（5 题，mock 模式）
    python -m tests.benchmark.run_golden_qa_baseline --sample 5 --skip-llm

    # 全量 Faithfulness 基线（需 DEEPSEEK_API_KEY）
    python -m tests.benchmark.run_golden_qa_baseline

    # 仅检索基线（不跑生成）
    python -m tests.benchmark.run_golden_qa_baseline --retrieval-only

依赖：
    - RAGAS scorer（DEEPSEEK_API_KEY，skip-llm 模式不需要）
    - RagasAdapter（需要 DB + KB）
    - 嵌入模型（xinference / bge_embed）

注意：
    - 嵌入模型不可用时系统降级为 FTS-only，基线数据将不反映完整检索能力。
    - 基线结果保存到 docs/baseline-ragas.json。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_golden_qa_baseline")

# 输出目录
DOCS_DIR = Path(__file__).resolve().parents[3] / "docs"
DEFAULT_OUTPUT = DOCS_DIR / "baseline-ragas.json"


def _safe_float(val: float) -> float | None:
    """将 NaN/Inf 转为 None，确保 JSON 序列化安全。"""
    import math
    if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
        return None
    return round(val, 4)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Golden QA RAGAS 生成基线")
    p.add_argument("--sample", type=int, default=None, help="抽样题数（默认全量 109 题）")
    p.add_argument("--skip-llm", action="store_true", help="跳过 LLM 调用（mock 模式，仅验证结构）")
    p.add_argument("--retrieval-only", action="store_true", help="仅跑检索模式（不生成 answer）")
    p.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT), help="基线输出路径")
    p.add_argument("--kb-id", type=str, default=None, help="知识库 ID（默认自动创建）")
    return p.parse_args()


async def main() -> None:
    args = parse_args()

    # 设置环境
    os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"
    # ChatOpenAI 新版本需要 OPENAI_API_KEY
    if "DEEPSEEK_API_KEY" in os.environ and "OPENAI_API_KEY" not in os.environ:
        os.environ["OPENAI_API_KEY"] = os.environ["DEEPSEEK_API_KEY"]

    from app.core.database import SessionLocal
    from tests.benchmark.loaders.ragas_adapter import RagasAdapter
    from tests.benchmark.scorers.ragas_scorer import RagasGenerationScorer, _get_llm
    from uuid import UUID

    # 初始化 KB
    kb_id: UUID | None = None
    if args.kb_id:
        kb_id = UUID(args.kb_id)
    elif not args.skip_llm:
        # 非 mock 模式需要实际 KB
        logger.info("自动创建 KB 用于基线评测...")
        from httpx import ASGITransport, AsyncClient
        import uuid as _uuid
        from app.main import app

        # 定位 golden_handbook.md
        # run_golden_qa_baseline.py → parents[1]=tests/ → fixtures/
        hb_dir = Path(__file__).resolve().parents[1] / "fixtures"
        hb_path = hb_dir / "golden_handbook.md"

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            email = f"bl-{_uuid.uuid4().hex[:8]}@example.com"
            await client.post("/api/v1/auth/register", json={
                "email": email, "username": f"bl{_uuid.uuid4().hex[:8]}",
                "password": "Test123!@", "account_type": "personal",
            })
            r = await client.post("/api/v1/auth/login", json={
                "identifier": email, "password": "Test123!@",
            })
            headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
            r = await client.post(
                "/api/v1/knowledge-bases?workspace=personal",
                headers=headers,
                json={"name": "GoldenQA-Baseline"},
            )
            kb_id = UUID(r.json()["id"])
            logger.info("KB created: %s", kb_id)

            # 上传 golden_handbook.md
            with open(hb_path, "rb") as f:
                await client.post(
                    f"/api/v1/knowledge-bases/{kb_id}/documents?workspace=personal",
                    headers=headers,
                    files={"files": ("hb.md", f, "text/markdown")},
                )

            # 等待文档入库完成
            for _ in range(30):
                r = await client.get(
                    f"/api/v1/knowledge-bases/{kb_id}/documents?workspace=personal&per_page=1",
                    headers=headers,
                )
                items = r.json().get("items", [])
                if items and items[0].get("status") == "completed":
                    logger.info("Ingestion completed")
                    break
                await asyncio.sleep(2)

    async with SessionLocal() as db:
        adapter = RagasAdapter(db, kb_id, skip_llm=args.skip_llm)

        t0 = time.perf_counter()

        if args.retrieval_only:
            logger.info("检索模式: Golden QA (sample=%s)", args.sample or "full")
            dataset = await adapter.to_ragas_retrieval_dataset(
                "golden_qa", top_k=3, sample=args.sample,
            )
            mode = "retrieval"
        else:
            logger.info("生成模式: Golden QA (sample=%s, skip_llm=%s)",
                         args.sample or "full", args.skip_llm)
            dataset = await adapter.to_ragas_dataset(
                "golden_qa", top_k=3, sample=args.sample,
            )
            mode = "generation"

        elapsed = time.perf_counter() - t0
        n = len(dataset["question"])
        logger.info("Adapter 完成: %d 题, 耗时 %.1fs", n, elapsed)

        # RAGAS 评分（非 mock 模式）
        ragas_scores = {}
        if not args.skip_llm and not args.retrieval_only:
            logger.info("开始 RAGAS Faithfulness 评分...")
            try:
                llm = _get_llm()
                scorer = RagasGenerationScorer()

                faithfulness_list: list[float] = []
                relevancy_list: list[float] = []
                correctness_list: list[float] = []

                for i in range(n):
                    try:
                        scores = scorer._single_evaluate(
                            query=dataset["question"][i],
                            answer=dataset["answer"][i],
                            chunks_text=dataset["contexts"][i],
                            llm=llm,
                            ground_truth=dataset["ground_truth"][i] or None,
                            # N13-1：默认 faithfulness_only=True 导致 correctness 恒 0。
                            # 有 ground_truth 时计算 relevancy + correctness。
                            faithfulness_only=not (dataset["ground_truth"][i] or None),
                        )
                        val = scores.get("faithfulness", 0.0)
                        if isinstance(val, float) and math.isnan(val):
                            val = 0.0
                        faithfulness_list.append(val)
                        val2 = scores.get("answer_relevancy", 0.0)
                        if isinstance(val2, float) and math.isnan(val2):
                            val2 = 0.0
                        relevancy_list.append(val2)
                        val3 = scores.get("answer_correctness", 0.0)
                        if isinstance(val3, float) and math.isnan(val3):
                            val3 = 0.0
                        correctness_list.append(val3)
                    except Exception as e:
                        logger.warning("RAGAS eval 失败 idx=%d: %s", i, e)
                        faithfulness_list.append(0.0)
                        relevancy_list.append(0.0)
                        correctness_list.append(0.0)

                    if (i + 1) % 10 == 0:
                        logger.info("  RAGAS: %d/%d 完成", i + 1, n)

                ragas_scores = {
                    "faithfulness_avg": sum(faithfulness_list) / max(1, len(faithfulness_list)),
                    "faithfulness_list": faithfulness_list,
                    "answer_relevancy_avg": sum(relevancy_list) / max(1, len(relevancy_list)),
                    "answer_relevancy_list": relevancy_list,
                    "answer_correctness_avg": sum(correctness_list) / max(1, len(correctness_list)),
                    "answer_correctness_list": correctness_list,
                }
                logger.info("RAGAS 评分完成: Faithfulness=%.3f, Relevancy=%.3f, Correctness=%.3f",
                             ragas_scores["faithfulness_avg"],
                             ragas_scores["answer_relevancy_avg"],
                             ragas_scores["answer_correctness_avg"])

            except Exception as e:
                logger.error("RAGAS 评分失败: %s", e)
                ragas_scores = {"error": str(e)}

        # 构建输出
        baseline = {
            "dataset": "golden_qa",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "mode": mode,
            "skip_llm": args.skip_llm,
            "sample": args.sample,
            "total_questions": n,
            "elapsed_seconds": round(elapsed, 1),
            "summary": {},
            "questions": [],
        }

        for i in range(n):
            q_entry = {
                "question": dataset["question"][i],
                "ground_truth": dataset["ground_truth"][i],
            }
            if not args.skip_llm:
                if not args.retrieval_only:
                    q_entry["answer"] = dataset["answer"][i]
                    q_entry["context_count"] = len(dataset["contexts"][i])
                if ragas_scores and "faithfulness_list" in ragas_scores:
                    q_entry["faithfulness"] = _safe_float(ragas_scores["faithfulness_list"][i])
                    q_entry["answer_relevancy"] = _safe_float(ragas_scores["answer_relevancy_list"][i])
                    if "answer_correctness_list" in ragas_scores:
                        q_entry["answer_correctness"] = _safe_float(ragas_scores["answer_correctness_list"][i])
            baseline["questions"].append(q_entry)

        # 汇总统计
        baseline["summary"] = {
            "total": n,
            "mode": mode,
            "skip_llm": args.skip_llm,
        }
        if ragas_scores and "faithfulness_avg" in ragas_scores:
            baseline["summary"]["faithfulness_avg"] = _safe_float(ragas_scores["faithfulness_avg"])
            baseline["summary"]["answer_relevancy_avg"] = _safe_float(ragas_scores["answer_relevancy_avg"])
            baseline["summary"]["answer_correctness_avg"] = _safe_float(ragas_scores["answer_correctness_avg"])
        if "error" in ragas_scores:
            baseline["summary"]["error"] = ragas_scores["error"]

        # 写入备注
        baseline["notes"] = (
            "ground_truth 取自 expect.content_contains（弱真值，片段而非完整答案）。"
            "Faithfulness 不需要 ground_truth；Answer Correctness 需要 ground_truth，"
            "由于 content_contains 是片段而非完整答案，correctness 分数为弱基线。"
        )

        # 保存
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(baseline, f, ensure_ascii=False, indent=2)
        logger.info("基线结果已保存: %s", output_path)
        print(json.dumps(baseline, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
