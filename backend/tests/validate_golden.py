"""
golden_qa 数据集校验脚本（企业评测体系 Phase 1-4）。
验证每个 case 的完整性、一致性、数据结构正确性。

用法:
    python -m tests.validate_golden                     # 默认校验 golden_qa.json
    python -m tests.validate_golden --strict             # 严格模式（含 expect 内容合理性检查）
    python -m tests.validate_golden --path <path>        # 指定 JSON 路径
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
DEFAULT_JSON = FIXTURES / "golden_qa.json"

VALID_SOURCES = {"md", "pdf", "docx"}
VALID_DOMAINS = {"attendance", "benefits", "career", "compensation", "cross", "finance", "performance", "security", "separation"}
VALID_TYPES = {"simple", "parametric", "conditional", "cross_reference", "edge", "rejection", "calculation", "negation"}
VALID_TAGS = {"md", "pdf", "docx", "section", "number", "date", "negation", "edge", "complex",
              "parametric", "condition", "cross_section", "table", "english", "cross_page",
              "negative", "clause_number", "paraphrase", "term", "r2-2", "calculation", "conditional"}


def validate(path: Path, strict: bool = False) -> int:
    """校验 golden_qa.json。返回 issue 数。"""
    if not path.exists():
        print("[FATAL] 文件不存在: %s" % path)
        return 1

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cases = data.get("cases", [])
    issues: list[str] = []

    for idx, c in enumerate(cases):
        cid = c.get("case_id", "case[%d]" % idx)

        # case_id 格式
        if not isinstance(cid, str) or not cid.startswith("GQ-"):
            issues.append("[%s] invalid case_id format" % cid)

        # source
        src = c.get("source")
        if src not in VALID_SOURCES:
            issues.append("[%s] invalid source: %s" % (cid, src))

        # domain
        dom = c.get("domain", "")
        if not dom:
            issues.append("[%s] missing domain" % cid)
        elif strict and dom not in VALID_DOMAINS:
            issues.append("[%s] unrecognized domain: %s" % (cid, dom))

        # question_type
        qt = c.get("question_type", "")
        if not qt:
            issues.append("[%s] missing question_type" % cid)
        elif strict and qt not in VALID_TYPES:
            issues.append("[%s] unrecognized question_type: %s" % (cid, qt))

        # difficulty
        diff = c.get("difficulty")
        if diff is None:
            issues.append("[%s] missing difficulty" % cid)
        elif not isinstance(diff, (int, float)) or diff < 0 or diff > 1:
            issues.append("[%s] invalid difficulty: %s" % (cid, diff))

        # rejection vs expect 一致性
        is_rej = c.get("expect_rejection", False)
        has_expect = "expect" in c and c["expect"] and any(v for v in c["expect"].values() if v is not None)
        has_expects = "expects" in c and c["expects"]

        if is_rej:
            if has_expect:
                issues.append("[%s] rejection case should not have expect" % cid)
            if has_expects:
                issues.append("[%s] rejection case should not have expects" % cid)
        else:
            if not has_expect and not has_expects:
                issues.append("[%s] non-rejection case missing both expect and expects" % cid)

        # min_match vs expects
        if has_expects:
            mm = c.get("min_match", 1)
            if not isinstance(mm, int) or mm < 1:
                issues.append("[%s] invalid min_match: %s" % (cid, mm))
            elif mm > len(c["expects"]):
                issues.append("[%s] min_match=%d > expects count=%d" % (cid, mm, len(c["expects"])))

        # tags 合理性
        tags = c.get("tags", [])
        if not isinstance(tags, list) or not tags:
            issues.append("[%s] missing or empty tags" % cid)

        # 严格模式：expect content_contains 的合理性
        if strict and has_expect:
            cc = c["expect"].get("content_contains")
            if cc and len(cc) < 2:
                issues.append("[%s] content_contains too short: %s" % (cid, repr(cc)))

    # 检查 case_id 连续
    ids = []
    for c in cases:
        cid = c.get("case_id", "")
        if cid.startswith("GQ-"):
            try:
                ids.append(int(cid.split("-")[1]))
            except ValueError:
                pass
    if ids:
        expected = list(range(1, max(ids) + 1))
        missing = [i for i in expected if i not in ids]
        if missing:
            issues.append("[META] missing case_ids: %s" % missing)

    # 报告
    print("=" * 50)
    print("  golden_qa 校验报告")
    print("=" * 50)
    print("  文件:    %s" % path)
    print("  版本:    %s" % data.get("version", "?"))
    print("  总题数:  %d" % len(cases))
    print("  严格:    %s" % ("是" if strict else "否"))
    print("  ---")
    if issues:
        print("  问题:    %d 个" % len(issues))
        for i in issues:
            print("    %s" % i)
    else:
        print("  [PASS] 全部通过验证")
    print("=" * 50)
    return len(issues)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="golden_qa 数据集校验")
    parser.add_argument("--strict", action="store_true", help="严格模式")
    parser.add_argument("--path", type=str, default=None, help="JSON 文件路径")
    args = parser.parse_args()

    path = Path(args.path) if args.path else DEFAULT_JSON
    return validate(path, strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
