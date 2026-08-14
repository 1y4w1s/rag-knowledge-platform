#!/usr/bin/env python3
"""索隐消融实验典型案例分析脚本。

在容器内运行，对比 Baseline (vector_only) 和 Full (rrf+conditional rerank)
在每个 query 上的 Top-1 检索结果差异，输出典型案例候选。
"""
import asyncio, json, os, sys, uuid, time
from pathlib import Path

os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

_FIXTURES_CANDIDATES = [
    Path("/app/tests/fixtures"),
    Path(__file__).parent.parent.parent / "tests/fixtures",
    Path(__file__).parent.parent.parent / "backend/tests/fixtures",
]
FIXTURES = next((p for p in _FIXTURES_CANDIDATES if p.exists()), _FIXTURES_CANDIDATES[0])

CONFIGS = {
    "baseline": {"RETRIEVAL_FUSION_MODE": "vector_only", "RERANK_POLICY": "off", "QUERY_REWRITE_POLICY": "off"},
    "full": {"RETRIEVAL_FUSION_MODE": "rrf", "RERANK_POLICY": "conditional", "QUERY_REWRITE_POLICY": "conditional"},
}


async def run_one_config(dataset_cfg: dict, config_name: str, config_env: dict) -> list[dict]:
    """在单一配置下检索所有 query，返回每个 query 的 Top-1 详情。"""
    # 设置环境变量后再导入 app
    for k, v in config_env.items():
        os.environ[k] = v

    from httpx import ASGITransport, AsyncClient
    from app.main import app as fastapi_app
    from app.core.database import SessionLocal
    from app.core.config import settings
    from app.models.document import Document as Doc
    from app.models.enums import DocumentStatus
    from app.services.ingestion.pipeline import process_document_ingestion
    from app.services.rag.retrieval import retrieve_chunks

    qa_path = FIXTURES / dataset_cfg["qa_file"]
    data = json.loads(qa_path.read_text(encoding="utf-8"))
    cases = [c for c in data["cases"] if not c.get("expect_rejection")]

    # 建 KB + 入库
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"ca-{uuid.uuid4().hex[:8]}@e.com"
        await client.post("/api/v1/auth/register", json={
            "email": email, "username": f"ca{uuid.uuid4().hex[:8]}",
            "password": "JudgePass123!", "account_type": "personal",
        })
        resp = await client.post("/api/v1/auth/login", json={"identifier": email, "password": "JudgePass123!"})
        j = resp.json()
        uid = uuid.UUID(j["user"]["id"])
        headers = {"Authorization": f"Bearer {j['access_token']}"}
        r = await client.post("/api/v1/knowledge-bases?workspace=personal", headers=headers,
                              json={"name": f"CA-{config_name}-{dataset_cfg['name']}"})
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

    # 检索所有 query
    results = []
    async with SessionLocal() as db:
        for i, case in enumerate(cases):
            t0 = time.perf_counter()
            chunks = await retrieve_chunks(db, kb_id=kb_id, query=case["query"], top_k=3)
            lat = (time.perf_counter() - t0) * 1000

            expect = case.get("expect", {})
            cc = expect.get("content_contains", "").lower()
            sp = expect.get("section_title", "").lower()
            hp = expect.get("heading_path_contains", "").lower()

            # 判断 Top-1/3 是否命中
            top1_ok = False
            top3_ok = False
            best_rank = None
            if chunks:
                for rank, ck in enumerate(chunks[:3]):
                    content = (ck.content or "").lower()
                    st = (ck.heading_path or ck.section_title or "").lower()
                    ok = True
                    if cc and cc not in content: ok = False
                    if sp and sp not in st: ok = False
                    if hp and hp not in st: ok = False
                    if ok:
                        best_rank = rank
                        if rank == 0: top1_ok = True
                        if rank < 3: top3_ok = True
                        break

            results.append({
                "case_id": case.get("case_id", f"Q{i}"),
                "query": case["query"],
                "domain": case.get("domain", ""),
                "top1_content": chunks[0].content[:200] if chunks and chunks[0].content else "",
                "top1_section": chunks[0].heading_path or chunks[0].section_title or "" if chunks else "",
                "top1_ok": top1_ok,
                "top3_ok": top3_ok,
                "latency_ms": round(lat, 1),
                "n_chunks": len(chunks) if chunks else 0,
                "expect": expect,
            })
    return results


def print_diff(baseline: list[dict], full: list[dict]):
    """打印 baseline 和 full 的差异。"""
    diff_cases = []
    for b, f in zip(baseline, full):
        if b["top1_ok"] != f["top1_ok"]:
            diff_cases.append({
                "case_id": b["case_id"],
                "query": b["query"],
                "domain": b["domain"],
                "baseline_top1_ok": b["top1_ok"],
                "full_top1_ok": f["top1_ok"],
                "baseline_top1_section": b["top1_section"],
                "full_top1_section": f["top1_section"],
                "baseline_top1_preview": b["top1_content"][:120],
                "full_top1_preview": f["top1_content"][:120],
                "expect": b["expect"],
            })

    # 统计
    total = len(baseline)
    b_h1 = sum(1 for r in baseline if r["top1_ok"])
    f_h1 = sum(1 for r in full if r["top1_ok"])
    print(f"\n{'='*70}")
    print(f"  配置对比：Baseline vs Full")
    print(f"  总题数: {total}")
    print(f"  Baseline Hit@1: {b_h1}/{total} = {b_h1/total:.1%}")
    print(f"  Full     Hit@1: {f_h1}/{total} = {f_h1/total:.1%}")
    print(f"  Top-1 差异题数: {len(diff_cases)}")
    print(f"{'='*70}")

    if not diff_cases:
        print("\n  无差异案例。")
        return

    # 分类：baseline 错 + full 对 vs 其他
    fixed = [c for c in diff_cases if not c["baseline_top1_ok"] and c["full_top1_ok"]]
    regressed = [c for c in diff_cases if c["baseline_top1_ok"] and not c["full_top1_ok"]]
    print(f"\n  Baseline错+Full对（改善）: {len(fixed)}")
    print(f"  Baseline对+Full错（退化）: {len(regressed)}")

    print(f"\n{'─'*70}")
    print(f"  典型案例候选（改善）")
    print(f"{'─'*70}")
    for c in fixed[:5]:
        print(f"\n  [{c['case_id']}] {c['query']}  (domain={c['domain']})")
        print(f"    Expect: section='{c['expect'].get('section_title','')}' content='{c['expect'].get('content_contains','')}'")
        print(f"    Baseline Top-1: '{c['baseline_top1_section'][:80]}'  (MISS)")
        print(f"    Full     Top-1: '{c['full_top1_section'][:80]}'  (HIT)")

    if regressed:
        print(f"\n{'─'*70}")
        print(f"  退化案例")
        print(f"{'─'*70}")
        for c in regressed[:3]:
            print(f"\n  [{c['case_id']}] {c['query']}  (domain={c['domain']})")
            print(f"    Baseline Top-1: '{c['baseline_top1_section'][:80]}'  (HIT)")
            print(f"    Full     Top-1: '{c['full_top1_section'][:80]}'  (MISS)")

    # 输出 JSON 供后续分析
    out_path = Path(f"/app/scripts/comparison/case_diff_{len(diff_cases)}.json")
    out_path.write_text(json.dumps({"fixed": fixed, "regressed": regressed, "total": total,
                                     "baseline_h1": b_h1, "full_h1": f_h1}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  JSON 差异详情已写入: {out_path}")


async def main():
    dataset_name = sys.argv[1] if len(sys.argv) > 1 else "golden_qa"
    from scripts.run_benchmark import DATASETS
    dataset_cfg = DATASETS.get(dataset_name)
    if not dataset_cfg:
        print(f"Unknown dataset: {dataset_name}")
        sys.exit(1)

    print(f"Running case analysis for dataset={dataset_name}")

    print(f"\n{'='*60}")
    print(f"  Config: Baseline (vector_only)")
    print(f"{'='*60}")
    base_results = await run_one_config(dataset_cfg, "baseline", CONFIGS["baseline"])

    print(f"\n{'='*60}")
    print(f"  Config: Full (rrf+conditional rerank)")
    print(f"{'='*60}")
    full_results = await run_one_config(dataset_cfg, "full", CONFIGS["full"])

    print_diff(base_results, full_results)


if __name__ == "__main__":
    asyncio.run(main())
