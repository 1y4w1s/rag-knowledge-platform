"""新旧评分引擎对比脚本。
对 Golden QA v1.0 分别用旧引擎和 ContentMatchScorer 评分，输出差异。
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tests"))

from benchmark.scorers.content_match import ContentMatchScorer
from benchmark.scorers.base import Expect, RetrievedChunk

CASES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "tests", "fixtures",
    "golden_qa", "v1.0", "cases.json"
)

def load_cases():
    with open(CASES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [c for c in data["cases"] if not c.get("expect_rejection")]

def old_scorer(case: dict, chunks: list[dict]) -> bool:
    """旧评分逻辑（run_benchmark.py 的匹配方式）。"""
    expect = case.get("expect", {})
    cc = expect.get("content_contains", "").lower()
    sp = expect.get("section_title", "").lower()
    hp = expect.get("heading_path_contains", "").lower()

    for ck in chunks[:3]:
        content = (ck.get("content") or "").lower()
        st = (ck.get("heading_path") or ck.get("section_title") or "").lower()
        ok = True
        if cc and cc not in content:
            ok = False
        if sp and sp not in st:
            ok = False
        if hp and hp not in st:
            ok = False
        if ok:
            return True
    return False

def main():
    cases = load_cases()
    print(f"Cases: {len(cases)}")

    scorer = ContentMatchScorer()
    diffs = []
    old_hits = 0
    new_hits = 0

    # 模拟 chunks（用 expect.content_contains 构建一个包含它的 chunk）
    for i, case in enumerate(cases):
        expect = case.get("expect", {})
        cc = expect.get("content_contains", "")
        valid = True
        # 验证 content_contains 能在模拟 chunk 中匹配
        fake_chunks = [{"content": f"相关文本内容包含{cc}在内的完整段落", "section_title": expect.get("section_title", ""), "heading_path": ""}]
        
        old_result = old_scorer(case, fake_chunks)
        new_result = scorer.score_retrieval(
            case["query"],
            [RetrievedChunk.from_raw(c) for c in fake_chunks],
            Expect.from_case(case),
        )
        
        old_hit = old_result
        new_hit = new_result.hit_at_3

        if old_hit:
            old_hits += 1
        if new_hit:
            new_hits += 1

        if old_hit != new_hit:
            diffs.append((case["case_id"], old_hit, new_hit, cc[:40]))

    print(f"\nOld engine: {old_hits}/{len(cases)} = {old_hits/len(cases)*100:.1f}%")
    print(f"New engine: {new_hits}/{len(cases)} = {new_hits/len(cases)*100:.1f}%")

    if diffs:
        print(f"\nDiffs: {len(diffs)}")
        for cid, old, new, cc in diffs[:10]:
            print(f"  {cid}: old={'✅' if old else '❌'} new={'✅' if new else '❌'} cc={cc}")
    else:
        print("\n✅ No differences - engines match")

if __name__ == "__main__":
    main()
