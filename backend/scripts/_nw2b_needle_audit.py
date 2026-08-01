"""NW-2b one-shot needle audit (no retrieval). Delete after attribution doc."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s.lower()).replace("**", "")


def main() -> None:
    qa = json.loads((FIX / "enterprise_qa.json").read_text(encoding="utf-8"))
    non = [c for c in qa["cases"] if not c.get("expect_rejection")]
    docs = {p.name: p.read_text(encoding="utf-8") for p in FIX.glob("acme_*.md")}
    raw = "\n".join(docs.values()).lower()
    blob = norm("\n".join(docs.values()))

    exact, ws, miss = [], [], []
    len200 = 0
    for c in non:
        cid = c["case_id"]
        cc = (c.get("expect") or {}).get("content_contains") or ""
        if len(cc) == 200:
            len200 += 1
        if cc.lower() in raw:
            exact.append(cid)
        elif norm(cc) in blob:
            ws.append(cid)
        else:
            miss.append(cid)

    n = len(non)
    print(f"non_rejection={n}")
    print(f"len_eq_200={len200} ({len200/n:.1%})")
    print(f"exact_in_source={len(exact)} ({len(exact)/n:.1%})")
    print(f"ws_norm_only={len(ws)} ({len(ws)/n:.1%})")
    print(f"absent_even_ws={len(miss)} ({len(miss)/n:.1%})")
    print(f"upper_bound_if_exact_only={len(exact)/n:.3f}")
    print(f"MISS={','.join(miss)}")
    print(f"WS={','.join(ws)}")

    # CRAG answer-in-doc upper bound on first 100 (cheap; full optional)
    crag = ROOT / "data" / "benchmark" / "crag" / "crag_task_1_and_2_dev_v4.jsonl.bz2"
    if crag.exists():
        import bz2

        in_doc = 0
        total = 0
        with bz2.open(crag, "rt", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= 100:
                    break
                raw_j = json.loads(line)
                snippets = []
                for sr in raw_j.get("search_results", [])[:3]:
                    snip = sr.get("page_snippet", "")[:600]
                    if snip:
                        snippets.append(snip)
                doc = "\n".join(snippets).lower()
                ans = (raw_j.get("answer") or "").lower().strip()[:40]
                total += 1
                if ans and ans in doc:
                    in_doc += 1
        print(f"crag_sample100_answer_in_3snip={in_doc}/{total}={in_doc/max(1,total):.1%}")


if __name__ == "__main__":
    main()
