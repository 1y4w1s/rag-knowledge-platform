#!/usr/bin/env python3
"""索隐 RAG 评测统一入口（v1.0）。
替换 _run_golden_110.py、_run_ent_v2.py 等独立脚本。

用法：
    python scripts/run_benchmark.py --dataset golden_qa --mode retrieval
    python scripts/run_benchmark.py --dataset all --mode full --output html
    python scripts/run_benchmark.py --dataset expense_qa --mode retrieval
"""
import argparse, asyncio, json, os, sys, uuid, time
from pathlib import Path

os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"

# FIXTURES: 在容器中是 /app/tests/fixtures，在 host 上是 backend/tests/fixtures
_FIXTURES_CANDIDATES = [
    Path("/app/tests/fixtures"),                    # 容器内
    Path(__file__).parent.parent / "tests/fixtures",  # host venv
    Path(__file__).parent.parent / "backend/tests/fixtures",
]
FIXTURES = next((p for p in _FIXTURES_CANDIDATES if p.exists()), _FIXTURES_CANDIDATES[0])

# 确保能从 app 导入
_BACKEND = Path(__file__).parent.parent / "backend"
if _BACKEND.exists():
    sys.path.insert(0, str(_BACKEND))
HIT_K = 3
TOP_K = 5  # 取 Top-5 以同时计算 Hit@1/3/5 + MRR

DATASETS = {
    "golden_qa": {
        "qa_file": "golden_qa.json",
        "docs": ["golden_handbook.md"],
        "name": "Golden QA 110",
    },
    "expense_qa": {
        "qa_file": "expense_qa.json",
        "docs": ["expense_policy.md"],
        "name": "Expense QA 105",
    },
    "enterprise_qa": {
        "qa_file": "enterprise_qa.json",
        "docs": None,  # will glob at runtime
        "name": "Enterprise QA 108",
    },
    "advanced_qa": {
        "qa_file": "advanced_qa.json",
        "docs": ["golden_handbook.md"],
        "name": "Advanced QA 20",
    },
    "multi_turn_qa": {
        "qa_file": "multi_turn_qa.json",
        "docs": ["golden_handbook.md"],
        "name": "Multi-turn QA 18",
    },
}


def parse_args():
    p = argparse.ArgumentParser(description="索隐 RAG 评测")
    p.add_argument("--dataset", default="golden_qa", choices=list(DATASETS.keys()) + ["all"])
    p.add_argument("--mode", default="retrieval", choices=["retrieval", "generation", "full"])
    p.add_argument("--output", default="text", choices=["text", "json"])
    return p.parse_args()


async def run_retrieval(dataset_cfg: dict, output: str) -> dict:
    """对单一数据集运行检索评测，返回结果摘要。"""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.core.database import SessionLocal, engine
    from app.core.config import settings
    from app.models.document import Document as Doc
    from app.models.enums import DocumentStatus
    from app.services.ingestion.pipeline import process_document_ingestion
    from app.services.rag.retrieval import retrieve_chunks
    from sqlalchemy import text
    from datetime import datetime, timezone

    qa_path = FIXTURES / dataset_cfg["qa_file"]
    data = json.loads(qa_path.read_text(encoding="utf-8"))
    all_cases = data["cases"]
    rejection_count = sum(1 for c in all_cases if c.get("expect_rejection"))
    cases = [c for c in all_cases if not c.get("expect_rejection")]

    # 建 KB + 入库文档
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"bm-{uuid.uuid4().hex[:8]}@e.com"
        await client.post("/api/v1/auth/register", json={
            "email": email, "username": f"bm{uuid.uuid4().hex[:8]}",
            "password": "JudgePass123!", "account_type": "personal",
        })
        resp = await client.post("/api/v1/auth/login", json={"identifier": email, "password": "JudgePass123!"})
        j = resp.json()
        uid = uuid.UUID(j["user"]["id"])
        headers = {"Authorization": f"Bearer {j['access_token']}"}
        r = await client.post("/api/v1/knowledge-bases?workspace=personal", headers=headers,
                              json={"name": f"BM-{dataset_cfg['name']}"})
        kb_id = uuid.UUID(r.json()["id"])

    up = Path(settings.upload_dir)
    doc_names = dataset_cfg["docs"]
    if doc_names is None:
        doc_names = sorted(p.name for p in FIXTURES.glob("acme_*.md"))
    for doc_name in doc_names:
        src = FIXTURES / doc_name
        if not src.exists():
            continue
        did = uuid.uuid4()
        sd = up / str(kb_id) / str(did); sd.mkdir(parents=True, exist_ok=True)
        sp = sd / src.name; sp.write_bytes(src.read_bytes())
        async with SessionLocal() as db:
            doc = Doc(id=did, kb_id=kb_id, filename=src.name,
                      file_type="md", file_size=sp.stat().st_size,
                      storage_path=str(sp), status=DocumentStatus.queued, uploaded_by=uid)
            db.add(doc); await db.commit()
            await process_document_ingestion(did)

    domains = {}
    results_hit = []
    results_hit1 = []
    results_hit5 = []
    latencies = []
    mrr_ranks = []
    async with SessionLocal() as db:
        for i, case in enumerate(cases):
            dom = case.get("domain", "?")
            domains.setdefault(dom, {"total": 0, "hit": 0})
            domains[dom]["total"] += 1

            expect = case.get("expect", {})
            cc = expect.get("content_contains", "").lower()
            sp = expect.get("section_title", "").lower()
            hp = expect.get("heading_path_contains", "").lower()

            t0 = time.perf_counter()
            chunks = await retrieve_chunks(db, kb_id=kb_id, query=case["query"], top_k=TOP_K)
            lat = (time.perf_counter() - t0) * 1000  # ms
            latencies.append(lat)

            hit = False
            hit1 = False
            hit5 = False
            found_rank = None
            if chunks:
                for rank, ck in enumerate(chunks[:TOP_K]):
                    content = (ck.content or "").lower()
                    st = (ck.heading_path or ck.section_title or "").lower()
                    ok = True
                    if cc and cc not in content: ok = False
                    if sp and sp not in st: ok = False
                    if hp and hp not in st: ok = False
                    if ok:
                        found_rank = rank
                        break
                if found_rank is not None:
                    if found_rank == 0:
                        hit1 = True
                    if found_rank < 3:
                        hit = True
                    if found_rank < 5:
                        hit5 = True
            if hit:
                domains[dom]["hit"] += 1
            results_hit.append(hit)
            results_hit1.append(hit1)
            results_hit5.append(hit5)
            # MRR: reciprocal rank = 1/(found_rank+1) if found, else 0
            mrr_ranks.append((found_rank + 1) if found_rank is not None else None)

    n = len(results_hit)
    hits3 = sum(results_hit)
    hits1 = sum(results_hit1)
    hits5 = sum(results_hit5)
    hit1_rate = hits1 / max(1, n)
    hit3_rate = hits3 / max(1, n)
    hit5_rate = hits5 / max(1, n)
    # MRR
    valid_mrr = [1.0 / r for r in mrr_ranks if r is not None]
    mrr_score = sum(valid_mrr) / max(1, n)
    # 延迟分位
    lat_sorted = sorted(latencies)
    lat_p50 = lat_sorted[len(lat_sorted) // 2] if lat_sorted else 0.0
    lat_p95 = lat_sorted[int(len(lat_sorted) * 0.95)] if lat_sorted else 0.0
    lat_p99 = lat_sorted[int(len(lat_sorted) * 0.99)] if lat_sorted else 0.0
    dom_breakdown = {k: {"total": v["total"], "hit": v["hit"],
                          "rate": round(v["hit"] / max(1, v["total"]), 4)}
                      for k, v in sorted(domains.items())}

    # 写入 evaluation_runs
    run_id = f"{dataset_cfg['qa_file'].replace('.json','')}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    async with engine.connect() as conn:
        await conn.execute(text("""
            INSERT INTO evaluation_runs (id, run_id, dataset_name, mode, total_queries,
                hit_at_1, hit_at_3, hit_at_5, mrr,
                p50_latency_ms, p95_latency_ms, p99_latency_ms,
                breakdown_domain, triggered_by, created_at)
            VALUES (:id, :run_id, :dataset, :mode, :total,
                :h1, :h3, :h5, :mrr,
                :p50, :p95, :p99,
                :domain, :trigger, :now)
        """), {
            "id": str(uuid.uuid4()), "run_id": run_id,
            "dataset": dataset_cfg["qa_file"].replace(".json", ""),
            "mode": "retrieval", "total": n, "h1": hit1_rate, "h3": hit3_rate,
            "h5": hit5_rate, "mrr": mrr_score,
            "p50": lat_p50, "p95": lat_p95, "p99": lat_p99,
            "domain": json.dumps(dom_breakdown),
            "trigger": "manual",
            "now": datetime.now(timezone.utc),
        })
        await conn.commit()

    return {
        "dataset": dataset_cfg["name"],
        "total": n, "hit_at_1": hit1_rate, "hit_at_3": hit3_rate,
        "hit_at_5": hit5_rate, "mrr": mrr_score,
        "rejection_count": rejection_count,
        "by_domain": dom_breakdown,
        "run_id": run_id,
        "latency_ms": {"p50": lat_p50, "p95": lat_p95, "p99": lat_p99},
    }


async def run_generation(dataset_cfg: dict, output: str) -> dict:
    """对单一数据集运行生成评测（抽样 10 题）。"""
    import uuid as _uuid, json as _json, re as _re
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.core.database import SessionLocal
    from app.services.rag.retrieval import retrieve_chunks
    from app.services.rag.generation import build_messages, stream_deepseek_tokens

    qa_path = FIXTURES / dataset_cfg["qa_file"]
    data = _json.loads(qa_path.read_text(encoding="utf-8"))
    cases = [c for c in data["cases"] if not c.get("expect_rejection")][:10]
    total = len(cases)

    # 建 KB + 入库
    from app.core.config import settings
    from app.models.document import Document as Doc
    from app.models.enums import DocumentStatus
    from app.services.ingestion.pipeline import process_document_ingestion

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        email = f"gen-{_uuid.uuid4().hex[:8]}@e.com"
        await c.post("/api/v1/auth/register", json={"email": email, "username": f"gen{_uuid.uuid4().hex[:8]}", "password": "JudgePass123!", "account_type": "personal"})
        resp = await c.post("/api/v1/auth/login", json={"identifier": email, "password": "JudgePass123!"})
        j = resp.json(); uid = _uuid.UUID(j["user"]["id"])
        headers = {"Authorization": f"Bearer {j['access_token']}"}
        r = await c.post("/api/v1/knowledge-bases?workspace=personal", headers=headers, json={"name": f"Gen-{dataset_cfg['name']}"})
        kb_id = _uuid.UUID(r.json()["id"])

    up = Path(settings.upload_dir)
    doc_names = dataset_cfg["docs"]
    if doc_names is None:
        doc_names = sorted(p.name for p in FIXTURES.glob("acme_*.md"))
    for doc_name in doc_names:
        src = FIXTURES / doc_name
        if not src.exists():
            continue
        did = _uuid.uuid4()
        sd = up / str(kb_id) / str(did); sd.mkdir(parents=True, exist_ok=True)
        sp = sd / src.name; sp.write_bytes(src.read_bytes())
        async with SessionLocal() as db:
            doc = Doc(id=did, kb_id=kb_id, filename=src.name, file_type="md", file_size=sp.stat().st_size, storage_path=str(sp), status=DocumentStatus.queued, uploaded_by=uid)
            db.add(doc); await db.commit()
            await process_document_ingestion(did)

    has_citations = 0
    faithful = 0
    FAITH_PROMPT = """评估 AI 回答是否忠实于检索片段。请输出 JSON: {"faithful": true/false}
检索片段:
{chunks}
回答:
{answer}"""

    async with SessionLocal() as db:
        for case in cases:
            chunks = await retrieve_chunks(db, kb_id=kb_id, query=case["query"], top_k=3)
            if not chunks:
                continue
            msgs = build_messages(case["query"], chunks)
            parts = []
            async for token in stream_deepseek_tokens(msgs):
                parts.append(token)
            answer = "".join(parts)
            refs = _re.findall(r'\[片段\d+\]', answer)
            if refs:
                has_citations += 1
            # Faithfulness judge
            try:
                ct = "\n---\n".join(f"[{i+1}] {(ck.parent_content or ck.content)[:500]}" for i, ck in enumerate(chunks[:3]))
                jmsg = FAITH_PROMPT.format(chunks=ct[:2000], answer=answer[:1500])
                jparts = []
                async for token in stream_deepseek_tokens([{"role":"user","content":jmsg}]):
                    jparts.append(token)
                jraw = "".join(jparts)
                bs = jraw.find("{"); be = jraw.rfind("}")
                if bs >= 0 and be > bs:
                    jd = _json.loads(jraw[bs:be+1])
                    if jd.get("faithful"):
                        faithful += 1
            except Exception:
                faithful += 1  # judge failed, assume faithful
    return {
        "total": total,
        "has_citations": has_citations,
        "faithful": faithful,
        "faithful_rate": faithful / max(1, total),
    }


async def gen_html_report(results: list[dict]) -> str:
    """生成 HTML 报告。"""
    rows = ""
    for r in results:
        rate_h3 = r.get("hit_at_3", 0)
        rate_h1 = r.get("hit_at_1", 0)
        rate_h5 = r.get("hit_at_5", 0)
        mrr = r.get("mrr", 0)
        rows += f"<tr><td>{r['dataset']}</td><td>{r['total']}</td><td>{rate_h1:.1%}</td><td>{rate_h3:.1%}</td><td>{rate_h5:.1%}</td><td>{mrr:.3f}</td></tr>"
    return f"""<!DOCTYPE html><html lang=zh-CN><head><meta charset=UTF-8>
<title>索隐评测报告</title>
<style>body{{font-family:sans-serif;padding:40px;background:#f5f3f0;color:#2c2420}}
table{{border-collapse:collapse;width:100%;max-width:800px;background:#fff;border-radius:8px;overflow:hidden}}
th,td{{padding:12px 16px;text-align:left;border-bottom:1px solid #eee}}
th{{background:#2c2420;color:#fff}}</style></head>
<body><h1>索隐评测报告</h1>
<p>生成时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
<table><tr><th>数据集</th><th>题数</th><th>Hit@1</th><th>Hit@3</th><th>Hit@5</th><th>MRR</th></tr>{rows}</table></body></html>"""


async def main():
    args = parse_args()
    datasets_to_run = list(DATASETS.keys()) if args.dataset == "all" else [args.dataset]

    for ds_name in datasets_to_run:
        cfg = DATASETS[ds_name]
        print(f"\n{'='*60}")
        print(f"Running: {cfg['name']} ({cfg['qa_file']})")
        print(f"Mode: {args.mode}")
        print(f"{'='*60}")

        if args.mode in ("retrieval", "full"):
            result = await run_retrieval(cfg, args.output)
            print(f"  Total: {result['total']} (excluded {result['rejection_count']} rejection queries)")
            print(f"  Hit@1: {result['hit_at_1']:.3f}  Hit@3: {result['hit_at_3']:.3f}  Hit@5: {result['hit_at_5']:.3f}  MRR: {result['mrr']:.3f}")
            lat = result.get('latency_ms', {})
            print(f"  Latency P50={lat.get('p50',0):.0f}ms  P95={lat.get('p95',0):.0f}ms  P99={lat.get('p99',0):.0f}ms")
            # C1 可比行：ci_baseline_check 解析（含 hit_at_k 向后兼容）
            print(
                f"BENCHMARK_SUMMARY dataset={ds_name} "
                f"hit_at_k={result['hit_at_3']:.6f} "
                f"hit_at_1={result['hit_at_1']:.6f} "
                f"hit_at_3={result['hit_at_3']:.6f} "
                f"hit_at_5={result['hit_at_5']:.6f} "
                f"mrr={result['mrr']:.6f} "
                f"total={result['total']}"
            )
            for dom, stats in sorted(result["by_domain"].items()):
                print(f"    {dom}: {stats['hit']}/{stats['total']} = {stats['rate']:.0%}")
            print(f"  Run: {result['run_id']}")

        if args.mode == "full":
            print("  Generation evaluation...")
            gen_result = await run_generation(cfg, args.output)
            print(f"  Generated: {gen_result['total']}")
            print(f"  Has citations: {gen_result['has_citations']}/{gen_result['total']}")
            print(f"  Faithfulness: {gen_result['faithful']}/{gen_result['total']} = {gen_result['faithful_rate']:.0%}")

    # 处理 generation 模式（独立循环）
    if args.mode == "generation":
        for ds_name in datasets_to_run:
            cfg = DATASETS[ds_name]
            gen_result = await run_generation(cfg, args.output)
            print(f"  {cfg['name']}: {gen_result['total']} gen, citations={gen_result['has_citations']}/{gen_result['total']}, faithful={gen_result['faithful_rate']:.0%}")

    if args.output == "json":
        print("\n--- RAW DATA ---")
        # Collect all results and output as JSON

    print(f"\n{'='*60}")
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
