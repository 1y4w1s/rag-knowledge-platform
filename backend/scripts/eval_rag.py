#!/usr/bin/env python3
"""RAG 质量评测脚本：跑 golden 测试集，输出 Markdown 报告。

用法:
    python backend/scripts/eval_rag.py --mode mock        # mock 嵌入（无需 API Key）
    python backend/scripts/eval_rag.py --mode production  # 通义嵌入（需 TONGYI_API_KEY）
    python backend/scripts/eval_rag.py --mode all         # 两种都跑 + 对比
    python backend/scripts/eval_rag.py --mode mock --save  # 跑完后保存报告到 eval-reports/

依赖: pytest, pytest-asyncio, httpx (通常已安装)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_REPORTS_DIR = REPO_ROOT / "eval-reports"

# golden 测试文件路径
GOLDEN_TEST = "tests/test_retrieval_golden.py"
AGENT_GOLDEN_TEST = "tests/test_agent_golden.py"


def _run_pytest(test_path: str, *extra_args: str) -> subprocess.CompletedProcess:
    """运行 pytest 并捕获输出。"""
    cmd = [
        sys.executable, "-m", "pytest",
        test_path,
        "-v",
        "--tb=short",
        "--no-header",
        *extra_args,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)


def parse_results(stdout: str, stderr: str) -> dict[str, Any]:
    """从 pytest 输出中解析测试结果。"""
    lines = stdout.splitlines()
    passed = 0
    failed = 0
    total = 0
    results: list[dict[str, Any]] = []

    for line in lines:
        if line.startswith("tests/"):
            total += 1
            if "PASSED" in line:
                passed += 1
                results.append({"status": "PASSED", "test": line})
            elif "FAILED" in line:
                failed += 1
                results.append({"status": "FAILED", "test": line})

    # 提取 RR 行（来自 print 输出）
    rr_lines = [l for l in lines if "RR=" in l]

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "hit_rate": round(passed / total * 100, 1) if total > 0 else 0.0,
        "rr_lines": rr_lines,
        "details": results,
        "raw_stdout": stdout,
        "raw_stderr": stderr,
    }


def _compute_mrr(rr_lines: list[str]) -> float:
    """从 RR 行计算 Mean Reciprocal Rank。"""
    rrs: list[float] = []
    for line in rr_lines:
        # 格式: "  GQ-1: RR=0.500"
        try:
            val = float(line.split("RR=")[1])
            rrs.append(val)
        except (IndexError, ValueError):
            continue
    if not rrs:
        return 1.0  # 所有都是 top-1 → MRR=1.0
    return round(sum(rrs) / len(rrs), 4)


def _make_report(
    mock_result: dict[str, Any] | None,
    prod_result: dict[str, Any] | None,
    mode: str,
) -> str:
    """生成 Markdown 报告。"""
    lines: list[str] = []
    lines.append("# RAG 质量评测报告")
    lines.append(f"\n**时间**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"\n**模式**: {mode}")
    lines.append("")

    for label, result in [("Mock 嵌入", mock_result), ("生产嵌入", prod_result)]:
        if result is None:
            continue
        mrr = _compute_mrr(result.get("rr_lines", []))
        lines.append(f"## {label}")
        lines.append("")
        lines.append(f"| 指标 | 值 |")
        lines.append(f"|------|-----|")
        lines.append(f"| 通过/总数 | {result['passed']}/{result['total']} |")
        lines.append(f"| Hit@3 命中率 | {result['hit_rate']}% |")
        lines.append(f"| MRR | {mrr} |")
        lines.append("")
        if result["rr_lines"]:
            lines.append("### 各题 Reciprocal Rank")
            lines.append("")
            lines.append("| 题号 | RR |")
            lines.append("|------|----|")
            for rr_line in result["rr_lines"]:
                parts = rr_line.strip().split(":")
                case_id = parts[0].strip() if len(parts) > 0 else ""
                rr_val = parts[1].strip().replace("RR=", "") if len(parts) > 1 else ""
                lines.append(f"| {case_id} | {rr_val} |")
            lines.append("")

    if mock_result and prod_result:
        mock_mrr = _compute_mrr(mock_result.get("rr_lines", []))
        prod_mrr = _compute_mrr(prod_result.get("rr_lines", []))
        lines.append("## 对比")
        lines.append("")
        lines.append(f"| 指标 | Mock | 生产 | 差异 |")
        lines.append(f"|------|------|------|------|")
        lines.append(f"| Hit@3 | {mock_result['hit_rate']}% | {prod_result['hit_rate']}% | "
                      f"{prod_result['hit_rate'] - mock_result['hit_rate']:+.1f}% |")
        lines.append(f"| MRR | {mock_mrr} | {prod_mrr} | "
                      f"{prod_mrr - mock_mrr:+.4f} |")
        lines.append("")

    if mock_result and mock_result["failed"] > 0:
        lines.append("### 失败详情")
        lines.append("")
        lines.append("```")
        for d in mock_result["details"]:
            if d["status"] == "FAILED":
                lines.append(d["test"])
        lines.append("```")
        lines.append("")

    lines.append("---")
    lines.append("*由 `scripts/eval_rag.py` 自动生成*")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG 质量评测")
    parser.add_argument(
        "--mode", choices=["mock", "production", "all"], default="mock",
        help="评测模式: mock=Mock 嵌入, production=通义嵌入, all=两者",
    )
    parser.add_argument(
        "--save", action="store_true",
        help="保存报告到 eval-reports/ 目录",
    )
    args = parser.parse_args()

    EVAL_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    mock_result = None
    prod_result = None

    if args.mode in ("mock", "all"):
        print("=== Mock 嵌入评测 ===")
        env = {"EMBEDDING_PROVIDER": "mock"}
        result = _run_pytest(GOLDEN_TEST)
        mock_result = parse_results(result.stdout, result.stderr)
        print(f"通过: {mock_result['passed']}/{mock_result['total']}  "
              f"命中率: {mock_result['hit_rate']}%")
        if result.returncode != 0:
            print("失败详情:")
            print(result.stdout)

    if args.mode in ("production", "all"):
        print("\n=== 生产嵌入评测 ===")
        env = {"EMBEDDING_PROVIDER": "tongyi"}
        result = _run_pytest(GOLDEN_TEST)
        prod_result = parse_results(result.stdout, result.stderr)
        print(f"通过: {prod_result['passed']}/{prod_result['total']}  "
              f"命中率: {prod_result['hit_rate']}%")
        if result.returncode != 0:
            print("失败详情:")
            print(result.stdout)

    report = _make_report(mock_result, prod_result, args.mode)
    print("\n" + report)

    if args.save:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        report_path = EVAL_REPORTS_DIR / f"eval-{timestamp}.md"
        report_path.write_text(report, encoding="utf-8")
        print(f"\n报告已保存: {report_path}")

    # 失败时返回非零退出码
    all_results = [r for r in (mock_result, prod_result) if r is not None]
    if any(r["failed"] > 0 for r in all_results):
        sys.exit(1)


if __name__ == "__main__":
    main()
