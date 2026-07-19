"""Enterprise QA query phase. KB_ID=bad0799a-c840-4563-89ac-5a00aa0b72a7"""
import asyncio, json, os, uuid
from pathlib import Path
os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"
KB_ID = "bad0799a-c840-4563-89ac-5a00aa0b72a7"
HIT_K = 3
THRESHOLDS = {"L1": 0.90, "L2": 0.80, "L3": 0.65, "L4": 0.50}
SEP = "=" * 60

async def main():
    from app.core.database import SessionLocal
    from app.services.rag.retrieval import retrieve_chunks

    data = json.loads((Path("/app/tests/fixtures") / "enterprise_qa.json").read_text(encoding="utf-8"))
    cases = data["cases"]
    print(f"Loaded {len(cases)} cases")

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
            chunks = await retrieve_chunks(db, kb_id=uuid.UUID(KB_ID), query=case["query"], top_k=HIT_K)
            hit = False
            if chunks:
                for ck in chunks[:HIT_K]:
                    content = (ck.content or "").lower()
                    st = (ck.heading_path or ck.section_title or "").lower()
                    ok = True
                    if cc and cc not in content:
                        ok = False
                    if sp and sp not in st:
                        ok = False
                    if hp and hp not in st:
                        ok = False
                    if ok:
                        hit = True
                        break
            if hit:
                by_level[level]["hit"] += 1
            results.append(hit)
            if (i + 1) % 25 == 0:
                print(f"  [{i+1}/{len(cases)}]")

    n = len(results)
    hits = sum(results)
    hit3 = hits / max(1, n)
    print(f"\n{SEP}")
    print(f"Enterprise QA 检索评测 ({n} 题, Hit@{HIT_K})")
    print(SEP)
    all_pass = True
    for level in ["L1", "L2", "L3", "L4"]:
        s = by_level.get(level, {"total": 0, "hit": 0})
        rate = s["hit"] / max(1, s["total"])
        th = THRESHOLDS[level]
        ok = rate >= th
        tag = "PASS" if ok else "FAIL"
        print(f"  {level}: {s['hit']}/{s['total']} = {rate:.0%}  (门禁 >= {th:.0%})  {tag}")
        if not ok:
            all_pass = False
    print(f"  总体: {hits}/{n} = {hit3:.0%}")

    fails = [
        {"case_id": case["case_id"], "level": case.get("difficulty", "L1"), "query": case["query"][:40]}
        for case, h in zip(cases, results) if not h
    ]
    if fails:
        print(f"\n  失败 ({len(fails)}):")
        for r in fails[:10]:
            print(f"    [{r['level']}] {r['case_id']}: {r['query']}")
        if len(fails) > 10:
            print(f"    ... + {len(fails)-10} more")
    print(f"\n{SEP}")
    print(f"ALL {'PASS' if all_pass else 'FAIL'}")

asyncio.run(main())
