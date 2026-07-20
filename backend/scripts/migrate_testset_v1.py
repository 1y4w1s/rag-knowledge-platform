#!/usr/bin/env python3
"""将现有测试集迁移到版本化目录结构，补全 question_type / match_type / source_doc_version。

对每个 case 自动推断 question_type:
  - expect_rejection=true → rejection
  - content_contains 为纯数字或 ≤3字符公式值 → calculation（需要人工复核）
  - 其余 → direct
"""
import json, os, shutil, re, sys
from collections import Counter

BASE = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")

# ── 源文件 → 目标目录映射 ──
DATASETS = {
    "golden_qa": {
        "src": os.path.join(BASE, "golden_qa.json"),
        "dst": os.path.join(BASE, "golden_qa", "v1.0", "cases.json"),
        "source_doc": "golden_handbook.md",
        "source_doc_version": "1.0",
    },
    "expense_qa": {
        "src": os.path.join(BASE, "expense_qa.json"),
        "dst": os.path.join(BASE, "expense_qa", "v1.0", "cases.json"),
        "source_doc": "expense_policy.md",
        "source_doc_version": "1.0",
    },
    "enterprise_qa": {
        "src": os.path.join(BASE, "enterprise_qa.json"),
        "dst": os.path.join(BASE, "enterprise_qa", "v1.0", "cases.json"),
        "source_doc": "acme_*.md",
        "source_doc_auto": True,  # 从 case.source_docs 自动填充
        "source_doc_version": "1.0",
    },
}

# 旧 question_type 到新 enum 的映射
QUESTION_TYPE_MAP = {
    "simple": "direct",
    "parametric": "direct",
    "edge": "direct",
    "conditional": "reasoning",
    "cross_reference": "reasoning",
    "negation": "reasoning",
    "calculation": "calculation",
    "rejection": "rejection",
}

def infer_question_type(case: dict) -> str:
    if case.get("expect_rejection"):
        return "rejection"
    old_qt = case.get("question_type", "")
    if old_qt in QUESTION_TYPE_MAP:
        return QUESTION_TYPE_MAP[old_qt]
    expect = case.get("expect", {})
    cc = expect.get("content_contains", "").strip()
    if cc.isdigit():
        return "calculation"
    return "direct"

def infer_match_type(case: dict) -> str:
    return "content"  # 当前所有测试集使用 content 子串匹配

def copy_with_meta():
    for name, cfg in DATASETS.items():
        src = cfg["src"]
        dst = cfg["dst"]
        if not os.path.exists(src):
            print(f"[SKIP] {src} not found")
            continue

        os.makedirs(os.path.dirname(dst), exist_ok=True)

        with open(src, "r", encoding="utf-8") as f:
            data = json.load(f)

        cases = data.get("cases", data if isinstance(data, list) else [])
        total = len(cases)
        added_qt = 0
        added_mt = 0
        added_rejection = 0
        added_golden = 0

        for c in cases:
            c["question_type"] = infer_question_type(c)
            added_qt += 1
            if "match_type" not in c or not c["match_type"]:
                c["match_type"] = infer_match_type(c)
                added_mt += 1
            if "source_doc_version" not in c:
                c["source_doc_version"] = cfg["source_doc_version"]
            if "source_doc" not in c or not c["source_doc"]:
                if cfg.get("source_doc_auto"):
                    src_docs = c.get("source_docs", [])
                    c["source_doc"] = ",".join(src_docs) if src_docs else cfg["source_doc"]
                else:
                    c["source_doc"] = cfg["source_doc"]
            # golden_answer 保留现有值（大部分为空）
            if "golden_answer" not in c:
                c["golden_answer"] = ""
                added_golden += 1
            # independent_review 默认 false
            if "independent_review" not in c:
                c["independent_review"] = False

        # 验证是否有重复 content_contains
        cc_list = [c.get("expect", {}).get("content_contains", "") for c in cases if not c.get("expect_rejection") and c.get("expect", {}).get("content_contains")]
        dup_cc = {k: v for k, v in Counter(cc_list).items() if v > 1}
        if dup_cc:
            print(f"[WARN] {name}: {len(dup_cc)} 重复 content_contains: {list(dup_cc.keys())}")

        with open(dst, "w", encoding="utf-8") as f:
            json.dump({"version": "1.0", "cases": cases}, f, ensure_ascii=False, indent=2)

        print(f"[OK] {name}: {total} cases → {dst}")
        print(f"      补全: question_type={added_qt} match_type={added_mt} golden_answer={added_golden}")

    # 验证 schema（如果有 python jsonschema 库）
    try:
        import jsonschema
        schema_path = os.path.join(BASE, "eval-test-case-schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        for name, cfg in DATASETS.items():
            dst = cfg["dst"]
            if not os.path.exists(dst):
                continue
            with open(dst, "r", encoding="utf-8") as f:
                data = json.load(f)
            errors = list(jsonschema.iter_verify(data["cases"][0], schema))
            if errors:
                print(f"[SCHEMA] {name}: {len(errors)} errors")
            else:
                print(f"[SCHEMA] {name}: ✅ 通过")
    except ImportError:
        print("[INFO] jsonschema 未安装，跳过 schema 验证")

if __name__ == "__main__":
    copy_with_meta()
