"""基线模拟评测：is_composite_query 恒 False（composite 永不触发）+ 归一化判定。"""
import asyncio, json, os, re, uuid
from pathlib import Path

os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"
FIXTURES = Path("/app/tests/fixtures")


def _norm(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"[\s，。、；：？！—\-–—()（）【】\[\]\"\'“”‘’·|]+", "", s or "").lower()


async def run_queries():
    import app.services.rag.retrieval as retrieval_mod

    # 基线模拟：复合题判定永不触发（retrieval 模块直接导入，patch 该模块绑定）
    retrieval_mod.is_composite_query = lambda query: False

    from app.core.database import SessionLocal
    from app.services.rag.retrieval import retrieve_chunks

    kb_id = uuid.UUID(Path("/tmp/ent_kb_id.txt").read_text().strip())
    HIT_K = 3
    THRESHOLDS = {"L1": 0.90, "L2": 0.80, "L3": 0.65, "L4": 0.50}

    data = json.loads((FIXTURES / "enterprise_qa.json").read_text(encoding="utf-8"))
    cases = data["cases"]
    by_level = {}
    results = []
    async with SessionLocal() as db:
        for i, case in enumerate(cases):
            level = case.get("difficulty", "L1")
            by_level.setdefault(level, {"total": 0, "hit": 0})
            by_level[level]["total"] += 1

            expect = case.get("expect", {})
            cc = _norm(expect.get("content_contains"))
            sp = _norm(expect.get("section_title"))
            hp = _norm(expect.get("heading_path_contains"))

            chunks = await retrieve_chunks(db, kb_id=kb_id, query=case["query"], top_k=HIT_K)
            hit = False
            if chunks:
                for ck in chunks[:HIT_K]:
                    content = _norm(ck.content or "")
                    st = _norm(ck.heading_path or ck.section_title or "")
                    ok = True
                    if cc and cc not in content: ok = False
                    if sp and sp not in st: ok = False
                    if hp and hp not in st: ok = False
                    if ok: hit = True; break
            if hit:
                by_level[level]["hit"] += 1
            results.append({"case_id": case["case_id"], "level": level, "query": case["query"], "hit": hit})
            if (i + 1) % 25 == 0:
                print(f"  [{i+1}/{len(cases)}]")

    print(f"\n{'='*60}")
    print(f"Enterprise QA 基线模拟 (composite off + 归一化) ({len(cases)} 题, Hit@{HIT_K})")
    for level in ["L1", "L2", "L3", "L4"]:
        s = by_level.get(level, {"total": 0, "hit": 0})
        rate = s["hit"] / max(1, s["total"])
        th = THRESHOLDS[level]
        print(f"  {level}: {s['hit']}/{s['total']} = {rate:.0%}  (门禁 >= {th:.0%})  {'PASS' if rate>=th else 'FAIL'}")
    total_hits = sum(1 for r in results if r["hit"])
    print(f"  总体: {total_hits}/{len(results)} = {total_hits/max(1,len(results)):.0%}")
    fails = [r for r in results if not r["hit"]]
    if fails:
        print(f"\n  失败 ({len(fails)}):")
        for r in fails:
            print(f"    [{r['level']}] {r['case_id']}: {r['query'][:44]}")

    summary = {"dataset": "enterprise_qa_base_sim", "total": len(results), "hit_k": HIT_K,
        "by_level": {l: {"total": s["total"], "hit": s["hit"],
            "rate": round(s["hit"]/max(1,s["total"]),4)} for l, s in sorted(by_level.items())},
        "overall_hit_rate": round(total_hits/max(1,len(results)),4)}
    Path("/app/benchmark_results/enterprise_qa_base_sim.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(run_queries())
