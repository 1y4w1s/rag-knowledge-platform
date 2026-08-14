"""B1 HyDE 正式消融 runner（Golden QA · on/off 各 3 轮，中位数口径）。

用法（backend 目录 + .venv）：
    python -m tests.benchmark.tests.run_hyde_ablation --variant off --rounds 3
    python -m tests.benchmark.tests.run_hyde_ablation --variant hyde --rounds 3

由 tests/benchmark/run_ablation.py 驱动时环境变量由父进程注入；
直接运行会从 backend/.env 读取 DEEPSEEK_API_KEY / DATABASE_URL。

输出：
    backend/tests/benchmark_results/hyde_ablation_{variant}.json
    （每题含 answer、citations、3 轮 Faithfulness 与中位数、Hit@3/MRR、低分判据）
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import statistics
import sys
import time
import uuid
from pathlib import Path

os.environ.setdefault("RAG_RATE_LIMIT_MODE", "bypass")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("run_hyde_ablation")

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures"
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "benchmark_results"
QA_PATH = FIXTURE_DIR / "golden_qa.json"
HANDBOOK_PATH = FIXTURE_DIR / "golden_handbook.md"

# 实验 K 低分定性回溯（docs/tasks/rag-evolution/chunk-quality-optimization-plan.md §九）
K25_IDS = [
    "GQ-104", "GQ-108", "GQ-26", "GQ-41", "GQ-11",
    "GQ-101", "GQ-105", "GQ-109", "GQ-14", "GQ-31",
    "GQ-32", "GQ-34", "GQ-45", "GQ-49", "GQ-55",
    "GQ-56", "GQ-58", "GQ-62", "GQ-66", "GQ-69",
    "GQ-72", "GQ-73", "GQ-76", "GQ-79", "GQ-80",
]

LOW_SCORE_CRITERIA = {
    "GQ-104": {"root_cause": "其他：开放语义题", "key_evidence": "“没满一年”需由 1.1 年假规则推导"},
    "GQ-108": {"root_cause": "评分噪声：表格", "key_evidence": "附录 B 单 chunk 同时含 200 元与 500 元"},
    "GQ-26": {"root_cause": "其他：生成侧拒答/跨章节组合失败", "key_evidence": "需 1.1 年假 + 3.1 加班"},
    "GQ-41": {"root_cause": "其他：生成侧附加未支撑句", "key_evidence": "1.1 规则可推导“不能申请”"},
    "GQ-11": {"root_cause": "评分噪声：正文+表格双 chunk", "key_evidence": "2.2 正文与表格均含 300 元/月"},
    "GQ-101": {"root_cause": "评分噪声", "key_evidence": "1.2 chunk 逐字支撑“超过 30 分钟按旷工半天处理”"},
    "GQ-105": {"root_cause": "评分噪声：表格", "key_evidence": "附录 B chunk 含“500 元/晚”"},
    "GQ-109": {"root_cause": "其他：复合题+未明示项", "key_evidence": "5.2 竞业有依据；未休年假无明示"},
    "GQ-14": {"root_cause": "评分噪声", "key_evidence": "3.2 chunk 逐字含“一线城市 200 元”"},
    "GQ-31": {"root_cause": "评分噪声", "key_evidence": "3.2 chunk 逐字含“二线城市 150 元”"},
    "GQ-32": {"root_cause": "其他：生成侧附加否定句", "key_evidence": "历史答案正确但附加“未明确周六日”"},
    "GQ-34": {"root_cause": "评分噪声", "key_evidence": "5.1 chunk 逐字含“试用期员工提前 3 天通知”"},
    "GQ-45": {"root_cause": "其他：生成侧附加否定句", "key_evidence": "历史答案正确但附加“未找到事后补填流程”"},
    "GQ-49": {"root_cause": "评分噪声", "key_evidence": "1.2 chunk 逐字含“超过 30 分钟按旷工半天处理”"},
    "GQ-55": {"root_cause": "评分噪声", "key_evidence": "6.3 chunk 逐字含“每人 50 元”"},
    "GQ-56": {"root_cause": "评分噪声", "key_evidence": "6.3 chunk 逐字含“超过 500 元须部门总监审批”"},
    "GQ-58": {"root_cause": "评分噪声", "key_evidence": "6.4 chunk 逐字含“超过 5000 元须财务总监加签”"},
    "GQ-62": {"root_cause": "评分噪声", "key_evidence": "7.1 chunk 逐字含“每 90 天更换一次”"},
    "GQ-66": {"root_cause": "评分噪声", "key_evidence": "8.1 chunk 逐字含“每人 800 元”"},
    "GQ-69": {"root_cause": "评分噪声", "key_evidence": "8.4 chunk 逐字含“人均预算 300 元”"},
    "GQ-72": {"root_cause": "评分噪声", "key_evidence": "9.2 chunk 逐字含“S 级评分 ≥ 95 分”"},
    "GQ-73": {"root_cause": "评分噪声", "key_evidence": "9.3 chunk 逐字含“S 级年终奖系数 1.5”"},
    "GQ-76": {"root_cause": "评分噪声", "key_evidence": "9.3 chunk 逐字含“A 级上浮 10%”"},
    "GQ-79": {"root_cause": "评分噪声：流程图", "key_evidence": "附录 A mermaid chunk 含 3 天/7 天审批路径"},
    "GQ-80": {"root_cause": "评分噪声：表格/附录", "key_evidence": "附录 C chunk 同时含 S 级与 D 级 10%"},
}


def _load_dotenv():
    """从 backend/.env 加载缺失的环境变量（独立脚本不自动读 .env）。"""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip("\"'")
            if key and not os.environ.get(key):
                os.environ[key] = val


def _ensure_fastembed_cache():
    """本地 Windows 评测常用 C:\\tmp\\fastembed_cache，未显式配置时自动兜底。"""
    if os.environ.get("FASTEMBED_CACHE_PATH"):
        return
    if os.name != "nt":
        return
    candidate = Path("C:/tmp/fastembed_cache")
    if candidate.is_dir():
        os.environ["FASTEMBED_CACHE_PATH"] = str(candidate)


def _safe_score(value, error: str | None):
    if error or value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return round(float(value), 4)


def _median(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return round(statistics.median(clean), 4)


def _load_checkpoint(path: Path, variant: str, rounds: int, sample: str) -> dict | None:
    """读取同参数的历史结果，用于断点续跑。"""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if (
        data.get("variant") != variant
        or data.get("rounds") != rounds
        or data.get("sample") != sample
    ):
        return None
    return data


def _build_payload(
    variant: str,
    rounds: int,
    sample: str,
    question_records: list[dict],
) -> dict:
    hits = [q["retrieval"]["hit_at_3"] for q in question_records]
    mrrs = [q["retrieval"]["mrr"] for q in question_records]
    medians = [q["faithfulness_median"] for q in question_records if q["faithfulness_median"] is not None]
    summary = {
        "questions": len(question_records),
        "hit_at_3": round(sum(hits) / max(1, len(hits)), 4),
        "mrr": round(sum(mrrs) / max(1, len(mrrs)), 4),
        "faithfulness_median": _median(medians),
        "faithfulness_mean": round(sum(medians) / max(1, len(medians)), 4) if medians else None,
        "low_score_median_count": sum(1 for m in medians if m is not None and m <= 0.5),
    }
    return {
        "dataset": "golden_qa",
        "variant": variant,
        "rounds": rounds,
        "sample": sample,
        "hit_k": 3,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "low_score_ids": K25_IDS,
        "summary": summary,
        "questions": question_records,
    }


def _expect_obj(case: dict):
    from tests.benchmark.scorers.base import Expect

    expect = case.get("expect") or {}
    return Expect(
        content_contains=expect.get("content_contains", ""),
        section_title=expect.get("section_title", ""),
        heading_path_contains=expect.get("heading_path_contains", ""),
        answer=case.get("answer", "") or "",
    )


def _faithfulness_only_expect():
    """空真值 Expect：让 RagasGenerationScorer 只跑 Faithfulness（无需 embedding）。"""
    from tests.benchmark.scorers.base import Expect

    return Expect(content_contains="", answer="")


def _eval_retrieval(raw_chunks, case: dict) -> tuple[bool, float]:
    """与 run_golden_full 一致的 Hit@3/MRR 口径。"""
    expect = case.get("expect") or {}
    is_rej = bool(case.get("expect_rejection", False))
    match_pos = []
    for pos, chunk in enumerate(raw_chunks[:3]):
        content = (chunk.content or "").lower()
        st = (chunk.heading_path or chunk.section_title or "").lower()
        cc = (expect.get("content_contains") or "").lower()
        sp = (expect.get("section_title") or "").lower()
        hp = (expect.get("heading_path_contains") or "").lower()
        ok = True
        if cc and cc not in content:
            ok = False
        if sp and sp not in st:
            ok = False
        if hp and hp not in st:
            ok = False
        if ok:
            match_pos.append(pos)
            break
    hit = bool(match_pos) and not is_rej
    mrr = 1.0 / (match_pos[0] + 1) if match_pos else 0.0
    return hit, mrr


def _citation_to_chunk(citation: dict):
    from tests.benchmark.scorers.base import RetrievedChunk

    return RetrievedChunk(
        chunk_id=citation.get("chunk_id", str(id(citation))),
        content=citation.get("excerpt") or citation.get("content") or "",
        section_title=citation.get("section_title", ""),
        heading_path=citation.get("heading_path", ""),
        page_number=citation.get("page"),
    )


async def _create_kb() -> uuid.UUID:
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"hyde-{uuid.uuid4().hex[:8]}@example.com"
        await client.post("/api/v1/auth/register", json={
            "email": email,
            "username": f"hyde{uuid.uuid4().hex[:8]}",
            "password": "Test123!@",
            "account_type": "personal",
        })
        r = await client.post("/api/v1/auth/login", json={
            "identifier": email, "password": "Test123!@",
        })
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = await client.post(
            "/api/v1/knowledge-bases?workspace=personal", headers=headers,
            json={"name": "GoldenQA-HyDE-Ablation"},
        )
        kb_id = uuid.UUID(r.json()["id"])
        with open(HANDBOOK_PATH, "rb") as f:
            await client.post(
                f"/api/v1/knowledge-bases/{kb_id}/documents?workspace=personal",
                headers=headers,
                files={"files": ("hb.md", f, "text/markdown")},
            )
        for _ in range(30):
            r = await client.get(
                f"/api/v1/knowledge-bases/{kb_id}/documents?workspace=personal&per_page=1",
                headers=headers,
            )
            items = r.json().get("items", [])
            if items and items[0].get("status") == "completed":
                logger.info("Ingestion completed kb_id=%s", kb_id)
                return kb_id
            await asyncio.sleep(2)
    raise RuntimeError("ingestion timeout")


async def _run_variant(variant: str, rounds: int, sample: str, limit: int | None) -> Path:
    from app.core.database import SessionLocal
    from app.services.rag.retrieval import retrieve_chunks
    from tests.benchmark.adapters.generation import GenerationAdapter
    from tests.benchmark.rate_limit import RateLimitWrapper
    from tests.benchmark.scorers.ragas_scorer import RagasGenerationScorer

    data = json.loads(QA_PATH.read_text(encoding="utf-8"))
    cases = data["cases"]

    if sample == "low-score":
        cases = [c for c in cases if not c.get("expect_rejection") and c["case_id"] in K25_IDS]
    elif sample == "all":
        cases = [c for c in cases if not c.get("expect_rejection")]
    else:
        cases = [c for c in cases if not c.get("expect_rejection")][: int(sample)]
    if limit:
        cases = cases[:limit]

    logger.info(
        "variant=%s sample=%s questions=%d rounds=%d", variant, sample, len(cases), rounds,
    )
    if not cases:
        raise RuntimeError("empty sample")

    kb_id = await _create_kb()
    user_id = uuid.uuid4()
    rate_limit = RateLimitWrapper(mode="bypass")
    ragas_scorer = RagasGenerationScorer()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / f"hyde_ablation_{variant}.json"
    checkpoint = _load_checkpoint(out, variant, rounds, sample)
    question_records: list[dict] = list(checkpoint.get("questions", [])) if checkpoint else []
    done_ids = {
        q["case_id"] for q in question_records
        if len(q.get("rounds", [])) >= rounds
        and any(r.get("faithfulness") is not None for r in q.get("rounds", []))
    }
    if question_records:
        logger.info(
            "断点续跑：已有 %d 题完成，继续 %d 题",
            len(done_ids), len(cases) - len(done_ids),
        )

    async with SessionLocal() as db:
        adapter = GenerationAdapter(db, kb_id)
        for idx, case in enumerate(cases):
            case_id = case["case_id"]
            query = case["query"]
            if case_id in done_ids:
                continue

            try:
                raw_chunks = await retrieve_chunks(db, kb_id=kb_id, query=query, top_k=3)
                hit, mrr = _eval_retrieval(raw_chunks, case)
            except Exception as e:
                logger.warning("retrieval 失败 case=%s err=%s", case_id, e)
                hit, mrr = False, 0.0

            expect_obj = _expect_obj(case)
            round_records: list[dict] = []
            for rnd in range(1, rounds + 1):
                answer: str | None = None
                citations: list[dict] = []
                generate_error = ""
                for attempt in range(2):
                    try:
                        await rate_limit.wait_for_chat(user_id)
                        answer, citations = await adapter.generate(query)
                        break
                    except Exception as e:
                        generate_error = f"{type(e).__name__}: {e}"
                        logger.warning(
                            "生成失败将重试 case=%s rnd=%d attempt=%d err=%s",
                            case_id, rnd, attempt + 1, generate_error,
                        )
                        if attempt == 0:
                            await asyncio.sleep(3)

                if answer is None:
                    round_records.append({
                        "round": rnd,
                        "faithfulness": None,
                        "error": generate_error or "generation failed",
                        "answer": "",
                        "citations": [],
                    })
                    continue

                scorer_chunks = [_citation_to_chunk(c) for c in citations]
                try:
                    # 空真值入参：消融只取 Faithfulness，避免 answer_relevancy 依赖 OpenAI embeddings
                    gscore = ragas_scorer.score_generation(
                        query, answer, _faithfulness_only_expect(), scorer_chunks,
                    )
                    score = _safe_score(gscore.faithfulness, gscore.error)
                    score_error = gscore.error or ""
                except Exception as e:
                    score = None
                    score_error = f"{type(e).__name__}: {e}"
                round_records.append({
                    "round": rnd,
                    "faithfulness": score,
                    "error": score_error,
                    "answer": answer,
                    "citations": citations,
                })

            med = _median([r["faithfulness"] for r in round_records])
            question_records = [q for q in question_records if q["case_id"] != case_id]
            question_records.append({
                "case_id": case_id,
                "query": query,
                "domain": case.get("domain", ""),
                "expect_content": expect_obj.content_contains,
                "low_score_criterion": LOW_SCORE_CRITERIA.get(
                    case_id, {"root_cause": "非 K25 低分题", "key_evidence": ""},
                ),
                "retrieval": {"hit_at_3": hit, "mrr": round(mrr, 4)},
                "faithfulness_scores": [r["faithfulness"] for r in round_records],
                "faithfulness_median": med,
                "rounds": round_records,
            })
            payload = _build_payload(variant, rounds, sample, question_records)
            out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info(
                "[%d/%d] %s off_hit=%s mrr=%.3f median=%.3f",
                idx + 1, len(cases), case_id, hit, mrr, med or 0.0,
            )

    payload = _build_payload(variant, rounds, sample, question_records)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = payload["summary"]

    print(f"\n{'='*64}")
    print(f"variant={variant} 完成: {summary['questions']} 题 x {rounds} 轮")
    print(f"  Hit@3={summary['hit_at_3']:.1%}  MRR={summary['mrr']:.4f}")
    print(f"  Faithfulness 中位数={summary['faithfulness_median']}  均值={summary['faithfulness_mean']}")
    print(f"  中位数<=0.5 低分题={summary['low_score_median_count']}")
    print(f"  结果: {out}")
    print(f"{'='*64}")
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="B1 HyDE 正式消融（单变体）")
    p.add_argument("--variant", choices=["off", "hyde"], default="off")
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--sample", default="low-score", help="low-score | all | N")
    p.add_argument("--limit", type=int, default=None, help="调试用：只跑前 N 题")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    _load_dotenv()
    _ensure_fastembed_cache()
    if "DEEPSEEK_API_KEY" in os.environ and "OPENAI_API_KEY" not in os.environ:
        os.environ["OPENAI_API_KEY"] = os.environ["DEEPSEEK_API_KEY"]
    # ragas 0.3.9 内部 factory 读 OPENAI_API_BASE，缺省会尝试 OpenAI 默认端点并报缺 key
    os.environ.setdefault("OPENAI_API_BASE", "https://api.deepseek.com")
    asyncio.run(_run_variant(args.variant, args.rounds, args.sample, args.limit))


if __name__ == "__main__":
    main()
