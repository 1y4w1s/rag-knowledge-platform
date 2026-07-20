#!/usr/bin/env python3
"""CI 基线对比脚本。解析 benchmark 输出，对比 docs/baseline.json。"""
import json, os, re, sys

BASELINE_PATH = os.environ.get("BASELINE_PATH", "docs/baseline.json")
BENCHMARK_OUT = "backend/benchmark_output.txt"

try:
    with open(BASELINE_PATH, encoding="utf-8") as f:
        baseline = json.load(f)
except FileNotFoundError:
    print(f"Baseline not found at {BASELINE_PATH}, skipping comparison")
    sys.exit(0)

try:
    with open(BENCHMARK_OUT, encoding="utf-8") as f:
        output = f.read()
except FileNotFoundError:
    print(f"Benchmark output not found at {BENCHMARK_OUT}, skipping comparison")
    sys.exit(0)

m = re.search(r'Hit@3:\s*([\d.]+)%', output)
if not m:
    print("Could not parse Hit@3 from benchmark output")
    sys.exit(0)

current = float(m.group(1)) / 100
baseline_score = baseline.get("golden_qa", {}).get("hit_at_k", 0)
diff = current - baseline_score
threshold = 0.02

print(f"Hit@3: current={current*100:.1f}%, baseline={baseline_score*100:.1f}%, diff={diff*100:+.1f}pp")

if diff < -threshold:
    print(f"FAIL: Hit@3 dropped {abs(diff)*100:.1f}pp (threshold: {threshold*100:.0f}%)")
    sys.exit(1)
else:
    print(f"PASS (threshold: {threshold*100:.0f}%)")
