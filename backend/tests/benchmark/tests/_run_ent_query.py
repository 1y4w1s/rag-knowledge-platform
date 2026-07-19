import asyncio, json
from pathlib import Path

FIXTURES = Path("/app/tests/fixtures")
HIT_K = 3
THRESHOLDS = {"L1": 0.90, "L2": 0.80, "L3": 0.65, "L4": 0.50}
KB_ID = "f8ec1242-e422-4190-a1f9-f95769d69014"

async def main():
    import uuid, os
    os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"
    from app.core.database import SessionLocal
    from app.services.rag.retrieval import retrieve_chunks

    kb_id = uuid.UUID(KB_ID)
    data = json.loads((FIXTURES / "enterprise_qa.json").read_text(encoding="utf-8"))
    cases = data["cases"]
    print(f"加载 {len(cases)} 题，KB_ID={KB_ID}\n")

    by_level = {}
    results = []
    async with SessionLocal() as db:
        for i, case in enumerate(cases):
            level = case.get("difficulty", "L1")
            by_level.setdefault(level, {"total": 0, "hit": 0})
            by_level[level]["total"] += 1

            expect = case.get("expect", {})
            cc = expect.get("content_contains", "").lower()
            sp = expect.get("section_title", "").lower()
            hp = expect.get("heading_path_contains", "").lower()

            chunks = await retrieve_chunks(db, kb_id=kb_id, query=case["query"], top_k=HIT_K)
            hit = False
            if chunks:
                for ck in chunks[:HIT_K]:
                    content = (ck.content or "").lower()
                    st = (ck.heading_path or ck.section_title or "").lower()
                    ok = True
                    if cc and cc not in content: ok = False
                    if sp and sp not in st: ok = False
                    if hp and hp not in st: ok = False
                    if ok: hit = True; break

            if hit: by_level[level]["hit"] += 1
            results.append({"case_id": case["case_id"], "level": level, "query": case["query"][:40], "hit": hit})
            if (i+1) % 25 == 0: print(f"  [{i+1}/{len(cases)}]")

    print(f"\n{'='*60}")
    print(f"Enterprise QA 检索评测 ({len(cases)} 题, Hit@{HIT_K})")
    print(f"{'='*60}")
    all_pass = True
    for level in ["L1", "L2", "L3", "L4"]:
        s = by_level.get(level, {"total": 0, "hit": 0})
        rate = s["hit"] / max(1, s["total"])
        th = THRESHOLDS[level]
        ok = rate >= th
        tag = "PASS" if ok else "FAIL"
        print(f"  {level}: {s['hit']}/{s['total']} = {rate:.0%}  (门禁 >= {th:.0%})  {tag}")
        if not ok: all_pass = False

    total_hits = sum(1 for r in results if r["hit"])
    print(f"  总体: {total_hits}/{len(results)} = {total_hits/max(1,len(results)):.0%}")

    fails = [r for r in results if not r["hit"]]
    if fails:
        print(f"\n  失败 ({len(fails)}):")
        for r in fails: print(f"    [{r['level']}] {r['case_id']}: {r['query']}")
    print(f"\n{'='*60}\nALL {'PASS' if all_pass else 'FAIL'} {'✅' if all_pass else '❌'}")

    summary = {"dataset": "enterprise_qa", "total": len(results), "hit_k": HIT_K,
        "by_level": {l: {"total": s["total"], "hit": s["hit"],
            "rate": round(s["hit"]/max(1,s["total"]),4)} for l,s in sorted(by_level.items())},
        "overall_hit_rate": round(total_hits/max(1,len(results)),4)}
    Path("/app/benchmark_results/enterprise_qa.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"结果: /app/benchmark_results/enterprise_qa.json")

asyncio.run(main())
