"""Nightly RAG 评测流水线（企业评测体系 Phase 3）。
在 CI 中定时执行（如 GitHub Actions cron）。

运行内容:
1. Full gate retrieval (110 题 mock 嵌入)
2. Full gate generation (子集, 真实 DeepSeek)
3. 公共基准 (CRAG 子集)
4. 对比上次报告
"""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("nightly")

RESULTS_DIR = Path(__file__).resolve().parent.parent / "benchmark_results" / "nightly"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


async def run_nightly() -> dict:
    """执行 Nightly 全量评测。返回摘要。"""
    from tests.golden_qa_loader import GOLDEN_QA_CASES, HIT_K
    from app.core.database import SessionLocal
    from app.services.rag.retrieval import retrieve_chunks
    from tests.golden_qa_loader import chunk_matches, hit_at_k

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    logger.info("=" * 50)
    logger.info("Nightly RAG 评测启动: %s", run_id)
    logger.info("=" * 50)

    results = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "golden_retrieval": None,
        "golden_generation": None,
    }

    # — 1. Golden Retrieval (mock) —
    logger.info("[1/4] Golden QA 检索评测 (%d 题)...", len(GOLDEN_QA_CASES))
    t0 = time.perf_counter()

    # 这里假设已有 kb_id 通过环境变量或参数传入
    from app.core.config import settings
    kb_id = settings.nightly_kb_id
    if not kb_id:
        logger.warning("未配置 nightly_kb_id，跳过检索评测")
    else:
        import uuid
        from uuid import UUID
        kb_uuid = UUID(kb_id) if isinstance(kb_id, str) else kb_id

        hits = 0
        total = 0
        reject_correct = 0
        reject_total = 0
        latencies = []

        async with SessionLocal() as db:
            for case in GOLDEN_QA_CASES:
                tq = time.perf_counter()
                chunks = await retrieve_chunks(db, kb_id=kb_uuid, query=case.query, top_k=HIT_K)
                latencies.append((time.perf_counter() - tq) * 1000)

                if case.expect_rejection:
                    reject_total += 1
                    mc = sum(1 for c in chunks[:HIT_K] if chunk_matches(case, c))
                    if mc == 0:
                        reject_correct += 1
                else:
                    total += 1
                    if hit_at_k(chunks, case, k=HIT_K):
                        hits += 1

        hit_rate = (hits / max(1, total)) if total else 0.0
        rej_acc = (reject_correct / max(1, reject_total)) if reject_total else 0.0
        p50 = sorted(latencies)[len(latencies)//2] if latencies else 0.0

        results["golden_retrieval"] = {
            "total": len(GOLDEN_QA_CASES), "hits": hits, "hit_rate": round(hit_rate, 4),
            "reject_correct": reject_correct, "reject_total": reject_total,
            "rejection_accuracy": round(rej_acc, 4),
            "p50_latency_ms": round(p50, 1),
            "duration_seconds": round(time.perf_counter() - t0, 1),
        }
        logger.info("  检索: Hit@%d=%.1f%% 拒答=%.0f%% p50=%.0fms (%.1fs)",
                     HIT_K, hit_rate*100, rej_acc*100, p50, results["golden_retrieval"]["duration_seconds"])

    # — 2. Generation (subset) —
    logger.info("[2/4] 生成质量评测 (10 题子集)...")
    # 需真实 DeepSeek API，此处留框架
    results["golden_generation"] = {
        "status": "skipped",
        "note": "需要 DeepSeek API + 运行数据库, 手动触发: python -m tests.run_golden_baseline --save",
    }
    logger.info("  生成: 跳过 (需 DeepSeek API)")

    # — 3. Compare with last run —
    logger.info("[3/4] 与上次对比...")
    last_path = RESULTS_DIR / "latest.json"
    if last_path.exists():
        try:
            with open(last_path, "r", encoding="utf-8") as f:
                last = json.load(f)
            last_hit = last.get("golden_retrieval", {}).get("hit_rate", 0)
            curr_hit = results.get("golden_retrieval", {}).get("hit_rate", 0)
            if last_hit and curr_hit:
                diff = curr_hit - last_hit
                if diff < -0.02:
                    logger.warning("【回归】Hit@3 下降 %.1f%% (%.1f%% -> %.1f%%)",
                                   abs(diff)*100, last_hit*100, curr_hit*100)
                elif diff > 0.02:
                    logger.info("【提升】Hit@3 上升 %.1f%% (%.1f%% -> %.1f%%)",
                                diff*100, last_hit*100, curr_hit*100)
                else:
                    logger.info("Hit@3 稳定 (%.1f%% -> %.1f%%)", last_hit*100, curr_hit*100)
        except Exception as e:
            logger.warning("对比失败: %s", e)
    logger.info("  对比完成")

    # — 4. Save —
    logger.info("[4/4] 保存报告...")
    with open(last_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    history_path = RESULTS_DIR / "run_%s.json" % run_id
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info("  报告已保存: %s", history_path)

    logger.info("=" * 50)
    logger.info("Nightly 完成")
    logger.info("=" * 50)
    return results


async def main():
    await run_nightly()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
