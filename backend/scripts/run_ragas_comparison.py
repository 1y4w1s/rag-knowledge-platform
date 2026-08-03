"""Enterprise QA Faithfulness 基线评测（修复版：走 HTTP API）。

流程：
1. 注册临时用户 → 登录获取 token
2. 创建临时知识库 → 上传 acme_*.md 源文档 → 等待入库完成
3. 加载 enterprise_qa.json
4. 对每个问题：调用 POST chat SSE → 解析 answer + citations → FaithfulnessJudge
5. 打印 + 保存结果

用法（容器内）：
    export PYTHONPATH=/app
    python scripts/run_ragas_comparison.py                  # 全量 108 题
    python scripts/run_ragas_comparison.py --sample 5       # 先试 5 题
    python scripts/run_ragas_comparison.py --skip-upload    # 复用已有 KB + 文档
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

API_BASE = "http://localhost:8000/api/v1"
RESULTS_DIR = Path("/app/benchmark_results")
FIXTURES_DIR = Path("/app/tests/fixtures")

# 数据集配置
DATASETS = {
    "enterprise": {
        "qa_file": "enterprise_qa.json",
        "source_docs": [
            "acme_产品规格书.md", "acme_FAQ合集.md", "acme_员工手册_英文.md",
            "acme_季度报告.md", "acme_操作手册.md", "acme_框架合同.md",
        ],
        "kb_name": "enterprise-qa-bench-temp",
        "description": "Enterprise QA Faithfulness 临时评测库",
    },
    "golden": {
        "qa_file": "golden_qa.json",
        "source_docs": ["golden_handbook.md"],
        "kb_name": "golden-qa-bench-temp",
        "description": "Golden QA Faithfulness 临时评测库",
    },
}

# 测试账号
TEST_EMAIL = "faithfulness-bench@example.com"
TEST_USERNAME = "faithbench"
TEST_PASSWORD = "Test123!@"


# ═══════════════════════════════════════════════════════════════════
# 1. Auth
# ═══════════════════════════════════════════════════════════════════

async def register_and_login(client: httpx.AsyncClient) -> tuple[str, dict]:
    """注册临时用户并登录，返回 (access_token, user)。"""
    # 先尝试登录（如果用户已存在）
    login_resp = await client.post(
        f"{API_BASE}/auth/login",
        json={"identifier": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    if login_resp.status_code == 200:
        data = login_resp.json()
        logger.info("已存在用户，直接登录: %s", TEST_EMAIL)
        return data["access_token"], data["user"]

    # 注册
    reg_resp = await client.post(
        f"{API_BASE}/auth/register",
        json={
            "email": TEST_EMAIL,
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
            "account_type": "personal",
        },
    )
    if reg_resp.status_code == 201:
        logger.info("注册新用户: %s", TEST_EMAIL)
    else:
        logger.warning("注册响应: %s %s", reg_resp.status_code, reg_resp.text)

    # 登录获取 token
    login_resp = await client.post(
        f"{API_BASE}/auth/login",
        json={"identifier": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    login_resp.raise_for_status()
    data = login_resp.json()
    return data["access_token"], data["user"]


# ═══════════════════════════════════════════════════════════════════
# 2. 知识库管理
# ═══════════════════════════════════════════════════════════════════

async def find_or_create_kb(client: httpx.AsyncClient, headers: dict, dataset: str) -> str:
    """查找已有 KB 或创建新 KB，返回 kb_id。"""
    cfg = DATASETS[dataset]
    kb_name = cfg["kb_name"]
    # 先列出已有 KB
    resp = await client.get(
        f"{API_BASE}/knowledge-bases",
        params={"workspace": "personal", "limit": 50},
        headers=headers,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    for kb in items:
        if kb["name"] == kb_name:
            logger.info("复用已有 KB: %s (%s)", kb["name"], kb["id"])
            return kb["id"]

    # 创建新 KB
    resp = await client.post(
        f"{API_BASE}/knowledge-bases",
        params={"workspace": "personal"},
        json={"name": kb_name, "description": cfg["description"]},
        headers=headers,
    )
    resp.raise_for_status()
    kb_id = resp.json()["id"]
    logger.info("创建 KB: %s", kb_id)
    return kb_id


async def upload_source_docs(
    client: httpx.AsyncClient, headers: dict, kb_id: str, dataset: str,
) -> None:
    """上传数据集源文档到知识库。"""
    cfg = DATASETS[dataset]
    files_uploaded = 0
    for doc_name in cfg["source_docs"]:
        doc_path = FIXTURES_DIR / doc_name
        if not doc_path.exists():
            logger.warning("源文档不存在，跳过: %s", doc_path)
            continue

        files = {"files": (doc_name, doc_path.read_bytes(), "text/markdown")}
        resp = await client.post(
            f"{API_BASE}/knowledge-bases/{kb_id}/documents",
            files=files,
            headers=headers,
        )
        if resp.status_code == 201:
            files_uploaded += 1
            doc_id = resp.json()["documents"][0]["id"]
            logger.info("上传: %s → %s", doc_name, doc_id)
        else:
            logger.warning("上传失败 %s: %s %s", doc_name, resp.status_code, resp.text)
    logger.info("上传完成: %d/%d 文件", files_uploaded, len(cfg["source_docs"]))


async def wait_for_ingestion(
    client: httpx.AsyncClient, headers: dict, kb_id: str,
    timeout: int = 60, poll_interval: int = 5,
) -> None:
    """轮询等待所有文档完成入库。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        resp = await client.get(
            f"{API_BASE}/knowledge-bases/{kb_id}/documents",
            params={"limit": 50},
            headers=headers,
        )
        resp.raise_for_status()
        docs = resp.json().get("items", [])
        total = len(docs)
        completed = sum(1 for d in docs if d["status"] == "completed")
        failed = sum(1 for d in docs if d["status"] == "failed")
        processing = sum(1 for d in docs if d["status"] in ("queued", "processing"))

        elapsed = time.time() - t0
        logger.info(
            "入库进度: %d/%d completed, %d failed, %d processing (%.0fs)",
            completed, total, failed, processing, elapsed,
        )

        if total > 0 and completed + failed == total:
            if failed > 0:
                logger.warning("%d 个文档入库失败", failed)
            return

        # 超时后也继续（使用已完成文档）
        if elapsed > timeout:
            logger.warning("入库超时 (%ds)，使用已完成文档继续 (%d/%d)", timeout, completed, total)
            return

        await asyncio.sleep(poll_interval)


# ═══════════════════════════════════════════════════════════════════
# 3. QA 评测
# ═══════════════════════════════════════════════════════════════════

def load_qa(sample: int | None = None, dataset: str = "enterprise") -> list[dict]:
    """加载 QA JSON，返回统一格式的 QA 列表。"""
    cfg = DATASETS[dataset]
    path = FIXTURES_DIR / cfg["qa_file"]
    if not path.exists():
        raise FileNotFoundError(f"{cfg['qa_file']} not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    cases = raw.get("cases", raw) if isinstance(raw, dict) else raw

    result = []
    for c in cases:
        result.append({
            "case_id": c.get("case_id", ""),
            "query": c.get("query", ""),
            "expect_rejection": c.get("expect_rejection", False),
        })

    if sample and sample < len(result):
        result = result[:sample]
        logger.info("抽样: %d 条（前 %d 条）", len(result), sample)
    else:
        logger.info("加载: %d 条", len(result))
    return result


async def parse_sse_chat(
    client: httpx.AsyncClient, headers: dict, kb_id: str, query: str,
) -> tuple[str, list[dict]]:
    """调用 POST chat SSE，返回 (answer_text, citations_list)。"""
    resp = await client.post(
        f"{API_BASE}/knowledge-bases/{kb_id}/chat",
        json={"message": query, "mode": "fast"},
        headers=headers,
    )
    resp.raise_for_status()

    answer_parts: list[str] = []
    citations: list[dict] = []

    # 解析 SSE 流
    # SSE 格式: event: xxx\ndata: {...}\n\n
    current_event = ""
    current_data = ""
    for line_bytes in resp.iter_lines():
        line = line_bytes.decode("utf-8") if isinstance(line_bytes, bytes) else line_bytes
        line = line.strip()
        if line.startswith("event:"):
            current_event = line[6:].strip()
            current_data = ""
        elif line.startswith("data:"):
            current_data = line[5:].strip()
        elif line == "":
            # 空行 = SSE 事件结束
            if current_event == "token" and current_data:
                try:
                    payload = json.loads(current_data)
                    answer_parts.append(payload.get("text", ""))
                except json.JSONDecodeError:
                    pass
            elif current_event == "citation" and current_data:
                try:
                    payload = json.loads(current_data)
                    citations.append(payload)
                except json.JSONDecodeError:
                    pass
            elif current_event == "done" and current_data:
                try:
                    payload = json.loads(current_data)
                    # done 事件也可能携带 citations
                    done_citations = payload.get("citations", [])
                    if done_citations and not citations:
                        citations = done_citations
                except json.JSONDecodeError:
                    pass
            current_event = ""
            current_data = ""

    answer = "".join(answer_parts)
    return answer, citations


async def evaluate_single(
    client: httpx.AsyncClient,
    headers: dict,
    kb_id: str,
    qa: dict,
    faith_judge,
) -> dict | None:
    """评估单个 QA 对：调用 chat → FaithfulnessJudge。"""
    if qa.get("expect_rejection"):
        logger.info("  [跳过] %s: expect_rejection=True", qa["case_id"])
        return {
            "case_id": qa["case_id"],
            "skipped": True,
            "reason": "expect_rejection",
            "answer": "",
            "answer_preview": "",
            "contexts": [],
        }

    logger.info("  [问答] %s: %s", qa["case_id"], qa["query"][:80])
    try:
        answer, citations = await parse_sse_chat(client, headers, kb_id, qa["query"])
    except Exception as e:
        logger.warning("  [失败] %s: %s", qa["case_id"], e)
        return {
            "case_id": qa["case_id"],
            "skipped": True,
            "reason": str(e),
            "answer": "",
            "answer_preview": "",
            "contexts": [],
        }

    if not answer.strip():
        logger.info("  [空回答] %s", qa["case_id"])
        return {
            "case_id": qa["case_id"],
            "faithfulness": 1.0,
            "hallucination_rate": 0.0,
            "answer": "",
            "answer_preview": "",
            "citations_count": len(citations),
            "contexts": [],
        }

    # FaithfulnessJudge 评估
    try:
        faith_score, hallu_rate = await faith_judge.evaluate(answer, citations)
    except Exception as e:
        logger.warning("  [Judge 失败] %s: %s", qa["case_id"], e)
        return {
            "case_id": qa["case_id"],
            "faithfulness": None,
            "hallucination_rate": None,
            "answer": answer,
            "answer_preview": answer[:200],
            "citations_count": len(citations),
            "contexts": [c.get("excerpt", c.get("content", "")) for c in citations],
            "error": str(e),
        }

    logger.info(
        "  [结果] %s: faith=%.2f%% hallu=%.2f%% (answer=%dch, cites=%d)",
        qa["case_id"], faith_score * 100, hallu_rate * 100,
        len(answer), len(citations),
    )
    return {
        "case_id": qa["case_id"],
        "faithfulness": round(faith_score, 4),
        "hallucination_rate": round(hallu_rate, 4),
        "answer": answer,
        "answer_preview": answer[:200],
        "citations_count": len(citations),
        "contexts": [c.get("excerpt", c.get("content", "")) for c in citations],
    }


# ═══════════════════════════════════════════════════════════════════
# RAGAS 对比评估
# ═══════════════════════════════════════════════════════════════════

async def run_ragas_evaluation(questions: list[str], answers: list[str], contexts_list: list[list[str]], qa_ids: list[str]) -> list[dict]:
    """用 RAGAS + DeepSeek judge 评估 faithfulness + answer_relevancy。"""
    try:
        from datasets import Dataset as HFDataset
        from langchain_openai import ChatOpenAI
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy
    except ImportError as e:
        logger.warning("RAGAS 依赖未安装: %s", e)
        logger.warning("请运行: pip install ragas datasets langchain-openai")
        return []

    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    deepseek_base = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    if not deepseek_key:
        logger.warning("DEEPSEEK_API_KEY 未设置，跳过 RAGAS")
        return []

    # 配置 DeepSeek 为 RAGAS 的 judge LLM
    deepseek_llm = ChatOpenAI(
        model="deepseek-chat",
        openai_api_key=deepseek_key,
        openai_api_base=deepseek_base,
    )

    # 创建 dataset
    data = HFDataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts_list,
    })

    logger.info("RAGAS evaluate 开始（%d 题, judge=deepseek-chat）...", len(questions))
    t0 = time.time()
    try:
        result = evaluate(data, metrics=[faithfulness, answer_relevancy], llm=deepseek_llm)
    except Exception as e:
        logger.warning("RAGAS evaluate 失败: %s", e)
        return []
    elapsed = time.time() - t0
    logger.info("RAGAS 完成 (%.1fs)", elapsed)

    scores = []
    for i, cid in enumerate(qa_ids):
        scores.append({
            "case_id": cid,
            "ragas_faithfulness": round(float(result["faithfulness"][i]), 4),
            "ragas_relevancy": round(float(result["answer_relevancy"][i]), 4),
        })
    return scores


def print_ragas_comparison(own_scores: list[dict], ragas_scores: list[dict]) -> dict:
    """对比 FaithfulnessJudge vs RAGAS 分数。"""
    own_map = {s["case_id"]: s for s in own_scores if s.get("faithfulness") is not None}
    rag_map = {s["case_id"]: s for s in ragas_scores}

    total, f_own_total, f_rag_total, r_rag_total = 0, 0.0, 0.0, 0.0
    detailed = []
    for cid in sorted(set(own_map.keys()) & set(rag_map.keys())):
        fo = own_map[cid]["faithfulness"]
        fr = rag_map[cid]["ragas_faithfulness"]
        rr = rag_map[cid].get("ragas_relevancy")
        if fo is not None and fr is not None:
            total += 1
            f_own_total += fo
            f_rag_total += fr
            if rr is not None:
                r_rag_total += rr
            detailed.append({
                "case_id": cid,
                "faithfulness_own": fo,
                "faithfulness_ragas": fr,
                "relevancy_ragas": rr,
            })

    if total == 0:
        return {"total": 0}

    avg_f_own = round(f_own_total / total, 4)
    avg_f_rag = round(f_rag_total / total, 4)
    avg_r_rag = round(r_rag_total / total, 4) if r_rag_total > 0 else None

    logger.info("")
    logger.info("=" * 50)
    logger.info("RAGAS 对比结果（%d 题）", total)
    logger.info("=" * 50)
    logger.info("  FaithfulnessJudge (DeepSeek): %.2f%%", avg_f_own * 100)
    logger.info("  RAGAS faithfulness (DeepSeek): %.2f%%", avg_f_rag * 100)
    logger.info("  差值:                         %+.2f%%", (avg_f_own - avg_f_rag) * 100)
    if avg_r_rag is not None:
        logger.info("  RAGAS answer_relevancy:       %.2f%%", avg_r_rag * 100)

    return {
        "total": total,
        "faithfulness_own_avg": avg_f_own,
        "faithfulness_ragas_avg": avg_f_rag,
        "relevancy_ragas_avg": avg_r_rag,
        "faithfulness_delta": round(avg_f_own - avg_f_rag, 4),
        "detailed": detailed,
    }


# ═══════════════════════════════════════════════════════════════════
# 4. 主流程
# ═══════════════════════════════════════════════════════════════════

async def main_async(args: argparse.Namespace) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 50)
    logger.info("Enterprise QA Faithfulness 基线评测")
    logger.info("=" * 50)

    # ── Step 1: 认证 ──
    logger.info("[1/5] 认证...")
    async with httpx.AsyncClient(timeout=120.0) as client:
        token, user = await register_and_login(client)
        headers = {"Authorization": f"Bearer {token}"}
        logger.info("用户: %s (%s)", user.get("email"), user.get("id"))

        # ── Step 2: 知识库 ──
        logger.info("[2/5] 知识库...")
        if args.kb_id:
            kb_id = args.kb_id
            logger.info("使用指定 KB: %s", kb_id)
        else:
            kb_id = await find_or_create_kb(client, headers, args.dataset)
            # 检查 KB 中是否有文档
            resp = await client.get(
                f"{API_BASE}/knowledge-bases/{kb_id}/documents",
                params={"limit": 5},
                headers=headers,
            )
            existing_docs = resp.json().get("items", [])

            if not existing_docs or args.force_upload:
                logger.info("[3/5] 上传源文档...")
                await upload_source_docs(client, headers, kb_id, args.dataset)
                logger.info("[4/5] 等待入库...")
                await wait_for_ingestion(client, headers, kb_id)
            else:
                logger.info(
                    "[3-4/5] 跳过上传/等待: KB 已有 %d 个文档",
                    len(existing_docs),
                )

        # ── Step 5: QA 评测 ──
        logger.info("[5/5] QA Faithfulness 评测...")
        qa_list = load_qa(sample=args.sample, dataset=args.dataset)

        # 初始化 FaithfulnessJudge
        from tests.benchmark.faithfulness import FaithfulnessJudge
        faith_judge = FaithfulnessJudge()

        results = []
        t_start = time.time()
        for i, qa in enumerate(qa_list):
            logger.info("[%d/%d]", i + 1, len(qa_list))
            result = await evaluate_single(client, headers, kb_id, qa, faith_judge)
            results.append(result)
            # 每 5 题存一次中间结果
            if (i + 1) % 5 == 0:
                _save_interim(results, args)

        elapsed = time.time() - t_start

        # ── 汇总 ──
        valid = [r for r in results if r.get("faithfulness") is not None and not r.get("skipped")]
        skipped = [r for r in results if r.get("skipped")]
        errors = [r for r in results if r.get("error")]

        if valid:
            avg_faith = sum(r["faithfulness"] for r in valid) / len(valid)
            avg_hallu = sum(r["hallucination_rate"] for r in valid) / len(valid)
        else:
            avg_faith = 0.0
            avg_hallu = 0.0

        logger.info("")
        logger.info("=" * 50)
        logger.info("评测完成")
        logger.info("=" * 50)
        logger.info("  总题数:        %d", len(qa_list))
        logger.info("  有效评估:      %d", len(valid))
        logger.info("  跳过(拒答等):  %d", len(skipped))
        logger.info("  评估失败:      %d", len(errors))
        logger.info("  Faithfulness:  %.2f%%", avg_faith * 100)
        logger.info("  Hallucination: %.2f%%", avg_hallu * 100)
        logger.info("  总耗时:        %.1fs", elapsed)
        if len(valid) > 0:
            logger.info("  每题平均:      %.1fs", elapsed / len(valid))

        # ── RAGAS 对比 ──
        ragas_summary = None
        if args.ragas:
            logger.info("")
            logger.info("=" * 50)
            logger.info("RAGAS 对比评测")
            logger.info("=" * 50)
            # 收集有效 QA 的 RAGAS 数据
            rag_questions = []
            rag_answers = []
            rag_contexts = []
            rag_ids = []
            for r in results:
                if r.get("faithfulness") is not None and not r.get("skipped") and r.get("answer"):
                    # 找对应的 qa 条目来获取完整 query
                    match = next((q for q in qa_list if q["case_id"] == r["case_id"]), None)
                    if match:
                        rag_questions.append(match["query"])
                        rag_answers.append(r["answer"])
                        rag_contexts.append(r.get("contexts", []))
                        rag_ids.append(r["case_id"])

            ragas_scores = await run_ragas_evaluation(rag_questions, rag_answers, rag_contexts, rag_ids)
            if ragas_scores:
                ragas_summary = print_ragas_comparison(results, ragas_scores)

        # ── 保存 ──
        output = {
            "dataset": args.dataset,
            "ts": time.time(),
            "config": {
                "judge": "FaithfulnessJudge (DeepSeek)",
                "ragas": args.ragas,
                "sample": args.sample,
                "kb_id": kb_id,
            },
            "total": len(qa_list),
            "valid": len(valid),
            "skipped": len(skipped),
            "errors": len(errors),
            "avg_faithfulness": round(avg_faith, 4),
            "avg_hallucination_rate": round(avg_hallu, 4),
            "elapsed_seconds": round(elapsed, 1),
            "results": results,
            "ragas": ragas_summary,
        }

        # ── 版本化保存（faithfulness/{dataset}/{date}.json）──
        date_str = datetime.now().strftime("%Y-%m-%d")
        version_dir = RESULTS_DIR / "faithfulness" / args.dataset
        version_dir.mkdir(parents=True, exist_ok=True)
        out_path = version_dir / f"{date_str}.json"

        # 读取上次结果做趋势对比
        prev_faith = None
        for f in sorted(version_dir.glob("*.json")):
            if f.name != f"{date_str}.json":
                try:
                    prev = json.loads(f.read_text(encoding="utf-8"))
                    if prev.get("avg_faithfulness") is not None:
                        prev_faith = prev["avg_faithfulness"]
                except (json.JSONDecodeError, KeyError, OSError):
                    pass

        if prev_faith is not None:
            delta = avg_faith - prev_faith
            logger.info("=" * 40)
            logger.info("趋势: %s Faithfulness: %.2f%% → %.2f%% (%+.2fpp)",
                        args.dataset, prev_faith * 100, avg_faith * 100, delta * 100)
            logger.info("=" * 40)

        out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
        logger.info("结果已保存: %s", out_path)


def _save_interim(results: list, args: argparse.Namespace) -> None:
    """保存中间结果。"""
    out_path = RESULTS_DIR / f"faithfulness_{args.dataset}_interim.json"
    out_path.write_text(
        json.dumps({"results": results}, ensure_ascii=False, indent=2),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Enterprise QA Faithfulness 基线评测")
    parser.add_argument(
        "--dataset", type=str, default="enterprise", choices=["enterprise", "golden"],
        help="数据集 (默认 enterprise)",
    )
    parser.add_argument(
        "--sample", type=int, default=None,
        help="抽样数量（先验流程，默认全量）",
    )
    parser.add_argument(
        "--kb-id", type=str, default=None,
        help="指定已有 KB ID（跳过创建/上传）",
    )
    parser.add_argument(
        "--force-upload", action="store_true",
        help="强制重新上传源文档（即使 KB 已有文档）",
    )
    parser.add_argument(
        "--ragas", action="store_true",
        help="同时运行 RAGAS（需 pip install ragas datasets langchain-openai）",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
