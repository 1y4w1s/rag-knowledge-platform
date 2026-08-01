"""一次性脚本（G3）：Enterprise QA 108 题 RAGAS 双轨（faithfulness + answer_correctness）。

复用 RagasAdapter + RagasGenerationScorer（与 run_golden_qa_baseline.py 同评分链路），
参数化 dataset_name=enterprise_qa。输出 benchmark_results JSON + 汇总打印。

运行：cd backend && python tests/benchmark/tests/_run_ragas_enterprise.py
前提：真实嵌入（fastembed）、DEEPSEEK_API_KEY（.env）、acme_* 文档已入库的 KB。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import sys
import time
import uuid
from pathlib import Path
from uuid import UUID

os.environ.setdefault("RAG_RATE_LIMIT_MODE", "bypass")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_ragas_enterprise")

OUT_DIR = Path(__file__).resolve().parents[2] / "benchmark_results"


def _safe_float(val: float) -> float | None:
    if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
        return None
    return round(val, 4)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Enterprise QA RAGAS 双轨基线（一次性，G3）")
    p.add_argument("--sample", type=int, default=None, help="抽样题数（默认全量 108）")
    p.add_argument("--kb-id", type=str, default=None, help="KB ID（默认自动创建+入库）")
    p.add_argument("--skip-llm", action="store_true", help="跳过 LLM（仅结构验证）")
    return p.parse_args()


async def main() -> None:
    args = parse_args()

    if "DEEPSEEK_API_KEY" in os.environ and "OPENAI_API_KEY" not in os.environ:
        os.environ["OPENAI_API_KEY"] = os.environ["DEEPSEEK_API_KEY"]

    from app.core.database import SessionLocal
    from tests.benchmark.loaders.ragas_adapter import RagasAdapter
    from tests.benchmark.scorers.ragas_scorer import RagasGenerationScorer, _get_llm

    # ── KB：自动创建 + 入库 acme_* 文档 ──
    kb_id: UUID | None = None
    if args.kb_id:
        kb_id = UUID(args.kb_id)
    elif not args.skip_llm:
        logger.info("自动创建 KB + 入库 acme_* 文档...")
        from httpx import ASGITransport, AsyncClient
        from app.main import app

        fixture_dir = Path(__file__).resolve().parents[2] / "fixtures"
        doc_files = sorted(fixture_dir.glob("acme_*.md"))

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            email = f"ent-ragas-{uuid.uuid4().hex[:8]}@example.com"
            await client.post("/api/v1/auth/register", json={
                "email": email, "username": f"entragas{uuid.uuid4().hex[:8]}",
                "password": "Test123!@", "account_type": "personal",
            })
            r = await client.post("/api/v1/auth/login", json={
                "identifier": email, "password": "Test123!@",
            })
            headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
            r = await client.post(
                "/api/v1/knowledge-bases?workspace=personal",
                headers=headers, json={"name": "EntQA-RAGAS-Baseline"},
            )
            kb_id = UUID(r.json()["id"])
            logger.info("KB created: %s", kb_id)

            for f in doc_files:
                with open(f, "rb") as fh:
                    resp = await client.post(
                        f"/api/v1/knowledge-bases/{kb_id}/documents?workspace=personal",
                        headers=headers,
                        files={"files": (f.name, fh, "text/markdown")},
                    )
                    logger.info("  upload %s → %s", f.name, resp.status_code)

            for _ in range(60):
                r = await client.get(
                    f"/api/v1/knowledge-bases/{kb_id}/documents?workspace=personal&per_page=20",
                    headers=headers,
                )
                items = r.json().get("items", [])
                statuses = {it.get("status") for it in items}
                if items and statuses == {"completed"}:
                    logger.info("Ingestion completed (%d docs)", len(items))
                    break
                await asyncio.sleep(3)

    async with SessionLocal() as db:
        adapter = RagasAdapter(db, kb_id, skip_llm=args.skip_llm)
        dataset = await adapter.to_ragas_dataset(
            "enterprise_qa", top_k=3, sample=args.sample,
        )
        n = len(dataset["question"])
        logger.info("Adapter 完成: %d 题", n)

        scores = {}
        if not args.skip_llm:
            llm = _get_llm()
            scorer = RagasGenerationScorer()
            faith_list, rel_list, corr_list = [], [], []
            for i in range(n):
                try:
                    s = scorer._single_evaluate(
                        query=dataset["question"][i],
                        answer=dataset["answer"][i],
                        chunks_text=dataset["contexts"][i],
                        llm=llm,
                        ground_truth=dataset["ground_truth"][i] or None,
                        faithfulness_only=not (dataset["ground_truth"][i] or None),
                    )
                    faith_list.append(s.get("faithfulness", 0.0))
                    rel_list.append(s.get("answer_relevancy", 0.0))
                    corr_list.append(s.get("answer_correctness", 0.0))
                except Exception as e:
                    logger.warning("RAGAS eval 失败 idx=%d: %s", i, e)
                    faith_list.append(0.0)
                    rel_list.append(0.0)
                    corr_list.append(0.0)
                if (i + 1) % 10 == 0:
                    logger.info("  RAGAS: %d/%d", i + 1, n)
            scores = {
                "faithfulness_avg": sum(faith_list) / max(1, len(faith_list)),
                "answer_relevancy_avg": sum(rel_list) / max(1, len(rel_list)),
                "answer_correctness_avg": sum(corr_list) / max(1, len(corr_list)),
                "faithfulness_list": faith_list,
                "answer_relevancy_list": rel_list,
                "answer_correctness_list": corr_list,
            }
            logger.info(
                "RAGAS 完成: Faithfulness=%.3f Relevancy=%.3f Correctness=%.3f",
                scores["faithfulness_avg"], scores["answer_relevancy_avg"],
                scores["answer_correctness_avg"],
            )

        baseline = {
            "dataset": "enterprise_qa",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "mode": "generation",
            "skip_llm": args.skip_llm,
            "sample": args.sample,
            "total_questions": n,
            "summary": {"total": n, "mode": "generation", "skip_llm": args.skip_llm},
            "questions": [],
        }
        if scores:
            baseline["summary"]["faithfulness_avg"] = _safe_float(scores["faithfulness_avg"])
            baseline["summary"]["answer_relevancy_avg"] = _safe_float(scores["answer_relevancy_avg"])
            baseline["summary"]["answer_correctness_avg"] = _safe_float(scores["answer_correctness_avg"])
            for i in range(n):
                baseline["questions"].append({
                    "question": dataset["question"][i],
                    "ground_truth": dataset["ground_truth"][i],
                    "answer": dataset["answer"][i],
                    "context_count": len(dataset["contexts"][i]),
                    "faithfulness": _safe_float(scores["faithfulness_list"][i]),
                    "answer_relevancy": _safe_float(scores["answer_relevancy_list"][i]),
                    "answer_correctness": _safe_float(scores["answer_correctness_list"][i]),
                })
        baseline["notes"] = (
            "G3 一次性脚本：Enterprise QA 108 题 RAGAS 双轨（faithfulness + answer_correctness）。"
            "ground_truth 取自 expect.content_contains（弱真值）。"
        )

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUT_DIR / f"generation_ragas_enterprise_qa_{time.strftime('%Y%m%d_%H%M%S')}.json"
        out.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("已保存: %s", out)

        print(json.dumps(baseline["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
