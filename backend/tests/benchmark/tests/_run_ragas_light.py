"""G3 一次性脚本：轻量双轨 judge（faithfulness + correctness，均直接调 DeepSeek，不经 ragas evaluate）。

背景：ragas 0.3.9 的 answer_relevancy/answer_correctness 在本环境（无 OpenAI embeddings）挂起；
faithfulness 经 ragas evaluate 每题 ~84s 过慢。本脚本：
  - faithfulness: 基于检索 chunks 的声明核对（LLM judge）
  - correctness: 基于 ground_truth 的语义一致性（LLM judge）
用于 G3 双轨基线刷新（docs/baseline-ragas.json），评分方式在基线文件中注明。

用法：cd backend && python -m tests.benchmark.tests._run_ragas_light --dataset golden_qa --sample 5
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
import uuid
from pathlib import Path
from uuid import UUID

os.environ.setdefault("RAG_RATE_LIMIT_MODE", "bypass")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("run_ragas_light")

OUT_DIR = Path(__file__).resolve().parents[2] / "benchmark_results"

FAITH_PROMPT = """判断 AI 回答是否忠实于检索片段（不得编造片段外信息）。只输出 JSON：{{"faithful": 0.0 或 1.0}}
检索片段：
{chunks}
回答：
{answer}"""

CORRECT_PROMPT = """判断模型回答与标准答案是否语义一致（意思一致即 1.0）。只输出 JSON：{{"correct": 0.0 或 1.0}}
标准答案：
{gt}
模型回答：
{answer}"""


def _parse_json_score(text: str) -> float | None:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
        for k in ("faithful", "correct"):
            if k in d:
                v = float(d[k])
                return 1.0 if v >= 0.5 else 0.0
    except Exception:
        pass
    return None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="G3 轻量双轨 judge")
    p.add_argument("--dataset", default="golden_qa", choices=["golden_qa", "enterprise_qa"])
    p.add_argument("--sample", type=int, default=None)
    p.add_argument("--kb-id", type=str, default=None)
    p.add_argument("--skip-llm", action="store_true")
    return p.parse_args()


async def main() -> None:
    args = parse_args()

    from app.core.config import settings
    os.environ.setdefault("OPENAI_API_KEY", settings.deepseek_api_key)
    from langchain_openai import ChatOpenAI

    from app.core.database import SessionLocal
    from tests.benchmark.loaders.ragas_adapter import RagasAdapter

    llm = ChatOpenAI(
        model="deepseek-chat",
        openai_api_key=os.environ["OPENAI_API_KEY"],
        openai_api_base=settings.deepseek_base_url,
        temperature=0.0,
    )

    # ── KB 准备（golden: golden_handbook.md；enterprise: acme_*）──
    kb_id: UUID | None = None
    if args.kb_id:
        kb_id = UUID(args.kb_id)
    elif not args.skip_llm:
        from httpx import ASGITransport, AsyncClient
        from app.main import app

        fixture_dir = Path(__file__).resolve().parents[2] / "fixtures"
        if args.dataset == "golden_qa":
            doc_files = [fixture_dir / "golden_handbook.md"]
        else:
            doc_files = sorted(fixture_dir.glob("acme_*.md"))

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            email = f"rg-{uuid.uuid4().hex[:8]}@example.com"
            await client.post("/api/v1/auth/register", json={
                "email": email, "username": f"rg{uuid.uuid4().hex[:8]}",
                "password": "Test123!@", "account_type": "personal",
            })
            r = await client.post("/api/v1/auth/login", json={
                "identifier": email, "password": "Test123!@",
            })
            headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
            r = await client.post(
                "/api/v1/knowledge-bases?workspace=personal",
                headers=headers, json={"name": f"RG-{args.dataset}"},
            )
            kb_id = UUID(r.json()["id"])
            logger.info("KB created: %s", kb_id)
            for f in doc_files:
                with open(f, "rb") as fh:
                    await client.post(
                        f"/api/v1/knowledge-bases/{kb_id}/documents?workspace=personal",
                        headers=headers,
                        files={"files": (f.name, fh, "text/markdown")},
                    )
            for _ in range(60):
                r = await client.get(
                    f"/api/v1/knowledge-bases/{kb_id}/documents?workspace=personal&per_page=20",
                    headers=headers,
                )
                items = r.json().get("items", [])
                statuses = {it.get("status") for it in items}
                if items and statuses == {"completed"}:
                    break
                await asyncio.sleep(3)

    async with SessionLocal() as db:
        adapter = RagasAdapter(db, kb_id, skip_llm=args.skip_llm)
        dataset = await adapter.to_ragas_dataset(args.dataset, top_k=3, sample=args.sample)
        n = len(dataset["question"])
        logger.info("Dataset ready: %s (%d 题)", args.dataset, n)

        faith_list: list[float] = []
        corr_list: list[float] = []
        lat_list: list[float] = []
        skip_gt = 0

        for i in range(n):
            _q, ans, ctxs, gt = (
                dataset["question"][i], dataset["answer"][i],
                dataset["contexts"][i], dataset["ground_truth"][i],
            )
            t0 = time.time()
            f, c = 0.0, 0.0
            if ans.strip() and ctxs:
                f = _parse_json_score(
                    llm.invoke(FAITH_PROMPT.format(
                        chunks="\n".join(ctxs)[:2000], answer=ans[:1500],
                    )).content
                ) or 0.0
                if gt.strip():
                    c = _parse_json_score(
                        llm.invoke(CORRECT_PROMPT.format(gt=gt[:1000], answer=ans[:1500])).content
                    ) or 0.0
                else:
                    skip_gt += 1
            faith_list.append(f)
            corr_list.append(c)
            lat_list.append(time.time() - t0)
            if (i + 1) % 5 == 0:
                logger.info("  %d/%d (faith=%.2f corr=%.2f)", i + 1, n,
                            sum(faith_list) / len(faith_list), sum(corr_list) / len(corr_list))

        summary = {
            "dataset": args.dataset,
            "mode": "generation_light",
            "total": n,
            "faithfulness_avg": round(sum(faith_list) / max(1, len(faith_list)), 4),
            "correctness_avg": round(sum(corr_list) / max(1, len(corr_list)), 4),
            "correctness_gt_skipped": skip_gt,
            "avg_judge_seconds": round(sum(lat_list) / max(1, len(lat_list)), 2),
            "judge": "DeepSeek direct prompt（faithfulness: 片段忠实性；correctness: 语义一致性）",
            "notes": "G3 一次性脚本：ragas 0.3.9 的 relevancy/correctness 需 OpenAI embeddings（本环境不可用）",
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUT_DIR / f"generation_light_{args.dataset}_{time.strftime('%Y%m%d_%H%M%S')}.json"
        out.write_text(json.dumps({
            "summary": summary,
            "per_question": [
                {"question": dataset["question"][i], "answer": dataset["answer"][i][:200],
                 "faithfulness": faith_list[i], "correctness": corr_list[i]}
                for i in range(n)
            ],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("saved: %s", out)


if __name__ == "__main__":
    asyncio.run(main())
