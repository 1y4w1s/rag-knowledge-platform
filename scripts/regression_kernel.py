"""回归检测内核（在 Docker 内执行）"""
import asyncio
import json
import logging
import os
import random
import sys
import uuid

os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"
logging.basicConfig(level=logging.WARNING)

BASELINE_JSON = os.environ.get("BASELINE_JSON", "{}")
QUICK_SAMPLE = int(os.environ.get("QUICK_SAMPLE", "50"))
FULL = os.environ.get("FULL", "false") == "true"

BASELINE = json.loads(BASELINE_JSON)
QA_PATH = "/app/tests/fixtures/golden_qa.json"
hit_k = 3


async def run():
    from pathlib import Path
    data = json.loads(Path(QA_PATH).read_text(encoding="utf-8"))
    cases = data["cases"]

    if FULL:
        sample = cases
    else:
        random.seed(42)
        by_tag = {}
        for c in cases:
            for t in c.get("tags", []):
                by_tag.setdefault(t, []).append(c)
        pool = []
        seen = set()
        for tag, tagged in sorted(by_tag.items()):
            for c in tagged:
                if c["case_id"] not in seen:
                    seen.add(c["case_id"])
                    pool.append(c)
        while len(pool) < QUICK_SAMPLE and len(pool) < len(cases):
            c = random.choice(cases)
            if c["case_id"] not in seen:
                seen.add(c["case_id"])
                pool.append(c)
        sample = pool[:QUICK_SAMPLE]

    print(f"Regression: {len(sample)} cases")

    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.core.database import SessionLocal
    from app.services.rag.retrieval import retrieve_chunks

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"reg-{uuid.uuid4().hex[:8]}@example.com"
        await client.post("/api/v1/auth/register", json={
            "email": email, "username": f"reg{uuid.uuid4().hex[:8]}",
            "password": "Test123!@", "account_type": "personal",
        })
        r = await client.post("/api/v1/auth/login", json={"identifier": email, "password": "Test123!@"})
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

        r = await client.post("/api/v1/knowledge-bases?workspace=personal", headers=headers, json={"name": "Reg-KB"})
        kb_id_str = r.json()["id"]

        with open("/app/tests/fixtures/golden_handbook.md", "rb") as f:
            await client.post(
                f"/api/v1/knowledge-bases/{kb_id_str}/documents?workspace=personal",
                headers=headers, files={"files": ("hb.md", f, "text/markdown")},
            )
        for _ in range(30):
            r = await client.get(
                f"/api/v1/knowledge-bases/{kb_id_str}/documents?workspace=personal&per_page=1",
                headers=headers,
            )
            if r.json().get("items", []) and r.json()["items"][0].get("status") == "completed":
                break
            await asyncio.sleep(2)

        kb_id = uuid.UUID(kb_id_str)
        async with SessionLocal() as db:
            results = []
            for i, case in enumerate(sample):
                expect = case.get("expect", {})
                is_rej = case.get("expect_rejection", False)
                chunks = await retrieve_chunks(db, kb_id=kb_id, query=case["query"], top_k=hit_k)

                match_pos = []
                for pos, chunk in enumerate(chunks[:hit_k]):
                    content = (chunk.content or "").lower()
                    st = (chunk.heading_path or chunk.section_title or "").lower()
                    cc = expect.get("content_contains", "").lower()
                    sp = expect.get("section_title", "").lower()
                    hp = expect.get("heading_path_contains", "").lower()
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

                hit = len(match_pos) > 0 and not is_rej
                mrr = 1.0 / (match_pos[0] + 1) if match_pos else 0.0
                results.append({"hit": hit, "mrr": mrr, "is_rej": is_rej})

    n = len(results)
    total_hits = sum(1 for r2 in results if r2["hit"])
    avg_mrr = sum(r2["mrr"] for r2 in results) / n
    rej_ok = sum(1 for r2 in results if r2["is_rej"] and not r2["hit"])
    rej_n = sum(1 for r2 in results if r2["is_rej"])
    rej_acc = rej_ok / max(1, rej_n)

    bl = BASELINE["golden_qa"]
    th = BASELINE["thresholds"]
    hit_diff = total_hits / n - bl["hit_at_k"]
    mrr_diff = avg_mrr - bl["mrr"]

    status = "PASS"
    exit_code = 0
    failures = []
    if total_hits / n < th["hit_at_k_min"]:
        status = "FAIL"
        exit_code = 2
        failures.append(f"Hit@3 {total_hits/n*100:.1f}% < {th['hit_at_k_min']*100:.0f}%")
    if avg_mrr < th["mrr_min"]:
        status = "FAIL"
        exit_code = 2
        failures.append(f"MRR {avg_mrr:.4f} < {th['mrr_min']}")
    if hit_diff < -0.02 and status == "PASS":
        status = "WARN"
        exit_code = 1

    print(f"Hit@3: {total_hits}/{n} = {total_hits/n*100:.1f}%")
    print(f"MRR:   {avg_mrr:.4f}")
    print(f"Rej:   {rej_ok}/{rej_n} ({rej_acc:.0%})")
    print(f"Diff:  Hit@3={hit_diff*100:+.1f}% MRR={mrr_diff:+.4f}")
    print(f"Status: {status}")
    for f in failures:
        print(f"  FAIL: {f}")

    output = {
        "status": status, "exit_code": exit_code,
        "current": {"hit_at_k": total_hits / n, "mrr": avg_mrr},
        "baseline": {"hit_at_k": bl["hit_at_k"], "mrr": bl["mrr"]},
        "diff": {"hit_at_k": round(hit_diff, 4), "mrr": round(mrr_diff, 4)},
        "failures": failures,
    }
    print(f"\nJSON_START\n{json.dumps(output, indent=2)}\nJSON_END")
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(run())
