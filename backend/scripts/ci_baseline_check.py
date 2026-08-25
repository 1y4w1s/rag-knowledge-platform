#!/usr/bin/env python3
"""CI 基线对比：解析 BENCHMARK_SUMMARY 行，对比 baseline.json。

compare_mode:
  - gate: 掉分超过 drop_fail_pp → exit 1（golden / enterprise / advanced · C3）
  - informational: 掉分超过 drop_warn_pp → WARN，仍 exit 0（CRAG sample / crag_full · C4）

Failure semantics (V1.0-C5):
  - Missing baseline file → exit 1 (not soft skip)
  - Empty / unparseable output when gate datasets are expected → exit 1
  - Gate-mode dataset present in baseline but missing from run → exit 1
  - Informational datasets may still SKIP when absent
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

BASELINE_PATH = os.environ.get(
    "BASELINE_PATH", "backend/tests/benchmark/baseline.json"
)
# 逗号分隔的评测输出文件（tee 产物）
OUTPUT_GLOBS = os.environ.get(
    "BENCHMARK_OUT_FILES",
    "backend/benchmark_output.txt,backend/benchmark_enterprise.txt,"
    "backend/benchmark_advanced.txt,backend/benchmark_crag.txt,"
    "backend/benchmark_crag_full.txt",
)

SUMMARY_RE = re.compile(
    r"BENCHMARK_SUMMARY\s+dataset=(?P<dataset>\S+)\s+hit_at_k=(?P<hit>[\d.]+).*?\s+total=(?P<total>\d+)",
)
# 兼容旧 golden 纯文本：Hit@3: 95.5%
LEGACY_HIT_RE = re.compile(r"Hit@3:\s*([\d.]+)%")


def _load_baseline(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"FAIL: Baseline not found at {path}")
        sys.exit(1)


def _collect_text(files_csv: str) -> tuple[str, list[str]]:
    chunks: list[str] = []
    found_files: list[str] = []
    for part in files_csv.split(","):
        p = Path(part.strip())
        if p.is_file():
            found_files.append(str(p))
            chunks.append(p.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks), found_files


def _parse_summaries(text: str) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for m in SUMMARY_RE.finditer(text):
        found[m.group("dataset")] = {
            "hit_at_k": float(m.group("hit")),
            "total": int(m.group("total")),
        }
    # 仅有旧格式且尚无 golden_qa 时兜底
    if "golden_qa" not in found:
        m = LEGACY_HIT_RE.search(text)
        if m:
            found["golden_qa"] = {"hit_at_k": float(m.group(1)) / 100.0, "total": -1}
    return found


def _gate_dataset_names(baseline: dict) -> list[str]:
    names: list[str] = []
    for name, spec in baseline.items():
        if isinstance(spec, dict) and spec.get("compare_mode") == "gate":
            names.append(name)
    return names


def _compare_one(name: str, current: dict, spec: dict) -> int:
    """返回 1 表示应硬失败，0 表示通过/仅告警。"""
    baseline_score = float(spec.get("hit_at_k", 0))
    cur = float(current["hit_at_k"])
    diff = cur - baseline_score
    mode = spec.get("compare_mode", "informational")
    print(
        f"[{name}] Hit@3: current={cur * 100:.1f}%, "
        f"baseline={baseline_score * 100:.1f}%, diff={diff * 100:+.1f}pp "
        f"(mode={mode}, n={current.get('total')})"
    )

    # G3: golden 绝对阈值（评测可信化门禁）——低于 absolute_min 直接硬红，
    # 防止 baseline 被连带下修后对比 gate 失去兜底。
    abs_min = spec.get("absolute_min")
    if abs_min is not None and cur < float(abs_min):
        print(
            f"FAIL: {name} Hit@3={cur * 100:.1f}% below absolute_min={float(abs_min) * 100:.1f}%"
        )
        return 1

    if mode == "gate":
        threshold = float(spec.get("drop_fail_pp", 0.02))
        if diff < -threshold:
            print(
                f"FAIL: {name} Hit@3 dropped {abs(diff) * 100:.1f}pp "
                f"(threshold: {threshold * 100:.0f}%)"
            )
            return 1
        print(f"PASS {name} (gate threshold: {threshold * 100:.0f}%)")
        return 0

    warn_pp = float(spec.get("drop_warn_pp", 0.05))
    if diff < -warn_pp:
        print(
            f"WARN: {name} Hit@3 dropped {abs(diff) * 100:.1f}pp "
            f"(informational threshold: {warn_pp * 100:.0f}%) — 不挡合并"
        )
    else:
        print(f"OK {name} (informational)")
    return 0


def main() -> None:
    baseline = _load_baseline(BASELINE_PATH)
    text, found_files = _collect_text(OUTPUT_GLOBS)
    gate_names = _gate_dataset_names(baseline)

    if not found_files:
        print(f"FAIL: No benchmark output files found in {OUTPUT_GLOBS}")
        sys.exit(1)

    if not text.strip():
        print(f"FAIL: Benchmark output files are empty: {found_files}")
        sys.exit(1)

    current = _parse_summaries(text)
    if not current:
        print("FAIL: Could not parse BENCHMARK_SUMMARY / Hit@3 from outputs")
        sys.exit(1)

    hard_fail = 0
    checked = 0
    for name, spec in baseline.items():
        if not isinstance(spec, dict) or "hit_at_k" not in spec:
            continue
        mode = spec.get("compare_mode", "informational")
        if name not in current:
            if mode == "gate":
                print(f"FAIL: {name}: gate dataset missing from this run")
                hard_fail = 1
            else:
                print(f"SKIP {name}: no current summary in this run (informational)")
            continue
        checked += 1
        hard_fail |= _compare_one(name, current[name], spec)

    if gate_names and checked == 0:
        print("FAIL: No gate datasets compared")
        sys.exit(1)

    if checked == 0:
        print("No overlapping datasets between baseline and run; skip")
        sys.exit(0)
    sys.exit(hard_fail)


if __name__ == "__main__":
    main()
