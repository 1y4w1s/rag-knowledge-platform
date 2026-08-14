#!/usr/bin/env python3
"""索隐消融实验运行器。

按设计文档 docs/design/rag-optimization-evolution-design.md §2.4 / §5.5，
通过环境变量控制每轮实验的检索融合模式、Rerank 策略、Query Rewrite 策略，
用独立子进程隔离各轮配置。

用法:
    python scripts/comparison/ablation_runner.py --dataset golden_qa
    python scripts/comparison/ablation_runner.py --dataset golden_qa --output report.md
    python scripts/comparison/ablation_runner.py --dataset all
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Optional

_SCRIPTS_DIR = Path(__file__).parent.parent
_BENCHMARK = str(_SCRIPTS_DIR / "run_benchmark.py")


# ──────────────────────────────────────────────
# §2.4 消融配置映射
# ──────────────────────────────────────────────

def _fusion_mode(cfg: dict) -> str:
    """根据配置条目计算 RETRIEVAL_FUSION_MODE。"""
    if not cfg.get("use_hybrid", True):
        return "vector_only"
    if not cfg.get("rrf_enabled", True):
        return "concat"
    return "rrf"


ABLATION_CONFIGS = OrderedDict({
    "baseline": {
        "label": "① Baseline（纯向量）",
        "use_hybrid": False,
        "rrf_enabled": False,
        "use_rerank": False,
        "rerank_policy": "off",
        "query_rewrite_policy": "off",
        "note": "纯向量检索 BGE 512 维，最低可行配置",
    },
    "plus_fts": {
        "label": "② +FTS（纯向量+FTS）",
        "use_hybrid": True,
        "rrf_enabled": False,
        "use_rerank": False,
        "rerank_policy": "off",
        "query_rewrite_policy": "off",
        "note": "纯向量 + FTS，简单拼接去重，不开 RRF",
    },
    "plus_rrf": {
        "label": "③ +RRF（RRF 融合）",
        "use_hybrid": True,
        "rrf_enabled": True,
        "use_rerank": False,
        "rerank_policy": "off",
        "query_rewrite_policy": "off",
        "note": "向量 + FTS + Reciprocal Rank Fusion",
    },
    "plus_rerank": {
        "label": "④ +Rerank",
        "use_hybrid": True,
        "rrf_enabled": True,
        "use_rerank": True,
        "rerank_policy": "always",
        "query_rewrite_policy": "off",
        "note": "③ + BGE Rerank 精排（always）",
    },
    "plus_multi_turn": {
        "label": "⑤ +Multi-turn",
        "use_hybrid": True,
        "rrf_enabled": True,
        "use_rerank": True,
        "rerank_policy": "always",
        "query_rewrite_policy": "always",
        "note": "④ + 多轮对话改写（仅 multi_turn 数据有效）",
    },
    "full": {
        "label": "⑥ Full（生产）",
        "use_hybrid": True,
        "rrf_enabled": True,
        "use_rerank": True,
        "rerank_policy": "conditional",
        "query_rewrite_policy": "conditional",
        "note": "生产配置：条件 Rerank + 条件改写",
    },
})

MULTI_TURN_NOTE = (
    "多轮改写需要多轮对话数据验证。\n"
    "本轮消融聚焦单轮检索，暂不纳入，见独立 multi_turn 测试。"
)


# ──────────────────────────────────────────────
# 子进程运行与结果解析
# ──────────────────────────────────────────────

def _build_env(cfg: dict) -> dict:
    """为给定配置构建子进程环境变量。"""
    env = os.environ.copy()
    env["RETRIEVAL_FUSION_MODE"] = _fusion_mode(cfg)
    env["RERANK_POLICY"] = cfg.get("rerank_policy", "off")
    env["QUERY_REWRITE_POLICY"] = cfg.get("query_rewrite_policy", "off")
    return env


_BENCHMARK_SUMMARY_RE = re.compile(
    r"BENCHMARK_SUMMARY\s+dataset=(?P<dataset>\S+)\s+"
    r"hit_at_k=(?P<hit_at_k>[0-9.]+)\s+"
    r"hit_at_1=(?P<hit_at_1>[0-9.]+)\s+"
    r"hit_at_3=(?P<hit_at_3>[0-9.]+)\s+"
    r"hit_at_5=(?P<hit_at_5>[0-9.]+)\s+"
    r"mrr=(?P<mrr>[0-9.]+)\s+"
    r"total=(?P<total>\d+)"
)


def _parse_benchmark_output(stdout: str, stderr: str) -> Optional[dict]:
    """从 run_benchmark.py 的子进程输出中解析 Benchmark 摘要。

    返回 {dataset, hit_at_1, hit_at_3, hit_at_5, mrr, total} 或 None。
    """
    for line in stdout.splitlines():
        m = _BENCHMARK_SUMMARY_RE.search(line)
        if m:
            return {
                "dataset": m.group("dataset"),
                "hit_at_1": float(m.group("hit_at_1")),
                "hit_at_3": float(m.group("hit_at_3")),
                "hit_at_5": float(m.group("hit_at_5")),
                "mrr": float(m.group("mrr")),
                "total": int(m.group("total")),
            }
    if stderr:
        print(f"  [stderr]: {stderr.strip()[:200]}", file=sys.stderr)
    return None


def _run_single_config(
    name: str,
    cfg: dict,
    dataset: str,
    verbose: bool = False,
    timeout: int = 600,
) -> dict:
    """运行一轮消融实验，返回结果摘要。

    返回结构：
        {name, label, hit_at_k, total,
         elapsed_seconds, run_id, dataset, note, skipped}
    """
    if dataset == "multi_turn_qa" and name == "plus_multi_turn":
        # multi_turn_qa 数据集只有 plus_multi_turn 配置有意义
        pass  # 正常跑
    elif name == "plus_multi_turn" and dataset in ("golden_qa", "expense_qa", "advanced_qa"):
        print(f"  \u26a0  \u2464 +Multi-turn \u5728\u5355\u8f6e\u6570\u636e\u96c6 '{dataset}' \u4e0a\u65e0\u6548\uff0c\u8df3\u8fc7\uff08\u6807\u6ce8 N/A\uff09")
        return {
            "name": name,
            "label": cfg["label"],
            "dataset": dataset,
            "hit_at_1": None, "hit_at_3": None, "hit_at_5": None, "mrr": None,
            "total": 0,
            "elapsed_seconds": 0,
            "skipped": True,
            "note": MULTI_TURN_NOTE,
        }

    env = _build_env(cfg)
    cmd = [
        sys.executable, _BENCHMARK,
        "--dataset", dataset,
        "--mode", "retrieval",
        "--output", "text",
    ]
    if verbose:
        print(f"  Running: {' '.join(cmd)}")

    t0 = time.perf_counter()
    proc = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    elapsed = time.perf_counter() - t0

    if proc.returncode != 0:
        print(f"  ❌ 子进程退出码 {proc.returncode}, stderr={proc.stderr[:200]}", file=sys.stderr)
        return {
            "name": name,
            "label": cfg["label"],
            "dataset": dataset,
            "hit_at_1": None, "hit_at_3": None, "hit_at_5": None, "mrr": None,
            "total": 0,
            "elapsed_seconds": elapsed,
            "skipped": True,
            "note": f"运行失败 (exit={proc.returncode})",
        }

    parsed = _parse_benchmark_output(proc.stdout, proc.stderr)
    if parsed is None:
        print(f"  ⚠  未能从 benchmark 输出解析 BENCHMARK_SUMMARY 行", file=sys.stderr)
        if verbose:
            print(f"  --- stdout (last 20 lines) ---\n" + "\n".join(proc.stdout.splitlines()[-20:]))
        return {
            "name": name,
            "label": cfg["label"],
            "dataset": dataset,
            "hit_at_1": None, "hit_at_3": None, "hit_at_5": None, "mrr": None,
            "total": 0,
            "elapsed_seconds": elapsed,
            "skipped": True,
            "note": "解析 BENCHMARK_SUMMARY 失败",
        }

    return {
        "name": name,
        "label": cfg["label"],
        "dataset": dataset,
        "hit_at_1": parsed["hit_at_1"],
        "hit_at_3": parsed["hit_at_3"],
        "hit_at_5": parsed["hit_at_5"],
        "mrr": parsed["mrr"],
        "total": parsed["total"],
        "elapsed_seconds": round(elapsed, 1),
        "skipped": False,
        "note": cfg["note"],
    }


# ──────────────────────────────────────────────
# 控制台输出
# ──────────────────────────────────────────────

def _print_console(results: list[dict]):
    """打印消融矩阵 + 边际提升表到控制台（含 Hit@1/3/5 + MRR）。"""
    baseline_h3 = None
    for r in results:
        if r["name"] == "baseline":
            baseline_h3 = r["hit_at_3"]
            break

    print(f"\n{'=' * 80}")
    print(f"  检索质量消融矩阵")
    print(f"  数据集: {results[0]['dataset']}")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 80}")

    # --- 消融矩阵 ---
    print(f"\n{'配置':<26} {'Hit@1':>7} {'Hit@3':>7} {'Hit@5':>7} {'MRR':>7} {'题数':>5} {'耗时(s)':>7}  {'说明'}")
    print("-" * 90)
    for r in results:
        h3 = r.get("hit_at_3")
        if h3 is not None:
            if baseline_h3 and baseline_h3 > 0:
                delta = (h3 - baseline_h3) / baseline_h3 * 100
                delta_str = f"  (+{delta:.1f}%)"
            else:
                delta_str = "  (基线)"
            h1_s = f"{r.get('hit_at_1',0):.3f}"
            h3_s = f"{h3:.3f}"
            h5_s = f"{r.get('hit_at_5',0):.3f}"
            mrr_s = f"{r.get('mrr',0):.3f}"
        else:
            h1_s = h3_s = h5_s = mrr_s = "  N/A"
            delta_str = ""
        label = r["label"]
        total_str = str(r["total"]) if r["total"] > 0 else "--"
        elapsed_str = f"{r['elapsed_seconds']:>5.1f}" if r["elapsed_seconds"] > 0 else "   --"
        print(f"  {label:<24} {h1_s:>7} {h3_s:>7} {h5_s:>7} {mrr_s:>7} {total_str:>5} {elapsed_str:>7} {delta_str}")

    # --- 边际提升分析（基于 Hit@3） ---
    print(f"\n{'─' * 70}")
    print(f"  边际提升分析（独立归因, 基于 Hit@3）")
    print(f"{'─' * 70}")
    print(f"\n{'优化步骤':<40} {'边际 Hit@3':>14} {'累计':>10}")
    print("-" * 70)

    prev = None
    for r in results:
        if r["name"] == "plus_multi_turn" and r.get("hit_at_3") is None:
            print(f"  {r['label']:<38} {'N/A':>14} {'N/A':>10}  -- 单轮数据集不适用")
            continue
        if r.get("hit_at_3") is None:
            continue

        if prev is not None and prev.get("hit_at_3") is not None:
            marginal = (r["hit_at_3"] - prev["hit_at_3"]) / prev["hit_at_3"] * 100 if prev["hit_at_3"] > 0 else 0
            marginal_pp = r["hit_at_3"] - prev["hit_at_3"]
            cumulative = (r["hit_at_3"] - baseline_h3) / baseline_h3 * 100 if baseline_h3 and baseline_h3 > 0 else 0
            marginal_str = f"+{marginal:.1f}%  ({marginal_pp:+.4f})"
            cum_str = f"+{cumulative:.1f}%"
        else:
            marginal_str = "--"
            cum_str = "--"
        print(f"  {r['label']:<38} {marginal_str:>14} {cum_str:>10}")
        prev = r

    print(f"\n{'─' * 70}")
    has_multi_turn_skip = any(r.get("skipped") and r["name"] == "plus_multi_turn" for r in results)
    if has_multi_turn_skip:
        print(f"\n  ⚠ Multi-turn 在此数据集上跳过，原因是：")
        print(f"     {MULTI_TURN_NOTE}")
    print()


# ──────────────────────────────────────────────
# Markdown 报告
# ──────────────────────────────────────────────

def _generate_markdown_report(results: list[dict], dataset: str) -> str:
    """生成可渲染的 Markdown 报告（含 Hit@1/3/5 + MRR）。"""
    baseline_h3 = None
    for r in results:
        if r["name"] == "baseline":
            baseline_h3 = r["hit_at_3"]
            break

    lines = []
    lines.append(f"# 索隐消融实验报告")
    lines.append(f"")
    lines.append(f"- **数据集**: {dataset}")
    lines.append(f"- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- **评测模式**: retrieval（仅检索，不调用 LLM）")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    # --- 消融矩阵 ---
    lines.append(f"## 检索质量消融矩阵")
    lines.append(f"")
    lines.append(f"| 配置 | Hit@1 | Hit@3 | Hit@5 | MRR | 题数 | 耗时(s) | 比 Baseline ↑ | 说明 |")
    lines.append(f"|------|-------|-------|-------|-----|------|---------|--------------|------|")

    for r in results:
        h3 = r.get("hit_at_3")
        if h3 is not None:
            if baseline_h3 and baseline_h3 > 0:
                delta_pct = (h3 - baseline_h3) / baseline_h3 * 100
                delta_str = f"+{delta_pct:.1f}%"
            else:
                delta_str = "--"
            h1_s = f"{r.get('hit_at_1',0):.3f}"
            h3_s = f"{h3:.3f}"
            h5_s = f"{r.get('hit_at_5',0):.3f}"
            mrr_s = f"{r.get('mrr',0):.3f}"
        else:
            h1_s = h3_s = h5_s = mrr_s = "N/A"
            delta_str = "N/A"
        label_clean = r["label"]
        total_str = str(r["total"]) if r["total"] > 0 else "--"
        elapsed_str = f"{r['elapsed_seconds']:.1f}" if r["elapsed_seconds"] > 0 else "--"
        note_str = r.get("note", "")
        lines.append(f"| {label_clean} | {h1_s} | {h3_s} | {h5_s} | {mrr_s} | {total_str} | {elapsed_str} | {delta_str} | {note_str} |")

    # --- 边际提升表 ---
    lines.append(f"")
    lines.append(f"### 边际提升分析（独立归因, 基于 Hit@3）")
    lines.append(f"")
    lines.append(f"| 优化步骤 | 边际 Hit@3 | 累计 | 归因结论 |")
    lines.append(f"|---------|-----------|------|---------|")

    prev = None
    for r in results:
        if r["name"] == "plus_multi_turn" and r.get("hit_at_3") is None:
            if dataset not in ("multi_turn_qa",):
                lines.append(f"| {r['label']} | N/A | N/A | 多轮改写需要多轮对话数据验证 |")
            continue
        if r.get("hit_at_3") is None:
            continue
        if prev is not None and prev.get("hit_at_3") is not None:
            marginal_pp = r["hit_at_3"] - prev["hit_at_3"]
            marginal_pct = (marginal_pp / prev["hit_at_3"] * 100) if prev["hit_at_3"] > 0 else 0
            cumulative = (r["hit_at_3"] - baseline_h3) / baseline_h3 * 100 if baseline_h3 and baseline_h3 > 0 else 0
            marginal_str = f"+{marginal_pct:.1f}% ({marginal_pp:+.4f})"
            cum_str = f"+{cumulative:.1f}%"
        else:
            marginal_str = "--"
            cum_str = "--"
        lines.append(f"| {r['label']} | {marginal_str} | {cum_str} | -- |")
        prev = r

    lines.append(f"")
    lines.append(f"> ⚠ Multi-turn 在单轮数据集上标注 N/A。多轮改写需要多轮对话数据验证。")
    lines.append(f"")

    # --- 延迟-质量对照 ---
    lines.append(f"---")
    lines.append(f"## 延迟-质量 Trade-off 分析")
    lines.append(f"")
    lines.append(f"| 配置 | 耗时(s) | Hit@1 | Hit@3 | Hit@5 | MRR | 性价比 |")
    lines.append(f"|------|---------|-------|-------|-------|-----|--------|")
    for r in results:
        if r.get("hit_at_3") is not None:
            elapsed_str = f"{r['elapsed_seconds']:.1f}" if r["elapsed_seconds"] > 0 else "--"
            h1_s = f"{r.get('hit_at_1',0):.3f}"
            h3_s = f"{r['hit_at_3']:.3f}"
            h5_s = f"{r.get('hit_at_5',0):.3f}"
            mrr_s = f"{r.get('mrr',0):.3f}"
            cost_map = {"baseline": "--", "plus_fts": "几乎免费", "plus_rrf": "少量计算增量",
                         "plus_rerank": "代价较高", "full": "条件触发均值可控"}
            cost_str = cost_map.get(r["name"], "--")
            lines.append(f"| {r['label']} | {elapsed_str} | {h1_s} | {h3_s} | {h5_s} | {mrr_s} | {cost_str} |")
        else:
            continue

    lines.append(f"")
    lines.append(f"> ⚠ 延迟数据为此轮实验的 wall-clock 总耗时，非单次检索 P50/P99 延迟。")
    lines.append(f"> 精确的 P50/P99 延迟需在 production 环境下使用 LatencyTracker 采集。")
    lines.append(f"")

    # --- 附录 ---
    lines.append(f"---")
    lines.append(f"## 附录：配置说明")
    lines.append(f"")
    lines.append(f"| # | 配置 | `RETRIEVAL_FUSION_MODE` | `RERANK_POLICY` | `QUERY_REWRITE_POLICY` |")
    lines.append(f"|---|------|--------------------------|----------------|------------------------|")
    for name, cfg in ABLATION_CONFIGS.items():
        label_clean = cfg["label"]
        fm = _fusion_mode(cfg)
        rp = cfg.get("rerank_policy", "off")
        qr = cfg.get("query_rewrite_policy", "off")
        lines.append(f"| {name} | {label_clean} | `{fm}` | `{rp}` | `{qr}` |")

    lines.append(f"")
    return "\n".join(lines)


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="索隐消融实验运行器 — 6 种配置独立跑分 + 消融矩阵输出",
    )
    p.add_argument(
        "--dataset", default="golden_qa",
        choices=["golden_qa", "expense_qa", "enterprise_qa", "advanced_qa", "multi_turn_qa", "all"],
        help="要运行的数据集（默认 golden_qa）",
    )
    p.add_argument(
        "--output", default=None,
        help="输出 Markdown 报告到指定文件路径（如 report.md），不传则仅打印控制台",
    )
    p.add_argument(
        "--verbose", "-v", action="store_true",
        help="显示子进程命令和详细输出",
    )
    p.add_argument(
        "--timeout", type=int, default=600,
        help="每轮子进程超时秒数（默认 600）",
    )
    return p.parse_args()


def main():
    args = parse_args()

    # 解析数据集列表
    if args.dataset == "all":
        datasets = ["golden_qa", "expense_qa", "enterprise_qa", "advanced_qa"]
    else:
        datasets = [args.dataset]

    # 如果用户指定了 multi_turn_qa，也允许（但不作为 all 的默认选项）
    if args.dataset == "multi_turn_qa":
        datasets = ["multi_turn_qa"]

    all_results = []

    for ds in datasets:
        print(f"{'=' * 70}")
        print(f"  数据集: {ds}")
        print(f"  共 {len(ABLATION_CONFIGS)} 种配置")
        print(f"{'=' * 70}")

        results = []
        for name, cfg in ABLATION_CONFIGS.items():
            print(f"\n{'─' * 50}")
            print(f"  [{name}] {cfg['label']}")
            print(f"  {cfg['note']}")

            result = _run_single_config(
                name=name,
                cfg=cfg,
                dataset=ds,
                verbose=args.verbose,
                timeout=args.timeout,
            )
            results.append(result)

            if result.get("skipped"):
                print(f"  → 跳过")
            elif result.get("hit_at_3") is not None:
                h1 = result.get("hit_at_1", 0)
                h3 = result["hit_at_3"]
                h5 = result.get("hit_at_5", 0)
                mr = result.get("mrr", 0)
                print(f"  → Hit@1={h1:.3f} Hit@3={h3:.3f} Hit@5={h5:.3f} MRR={mr:.3f}  ({result['total']} 题, {result['elapsed_seconds']:.1f}s)")
            else:
                print(f"  → 失败/无数据")

        all_results.append((ds, results))

        # 打印控制台矩阵
        _print_console(results)

    # Markdown 报告输出（仅单数据集时自动生成）
    if args.output and len(all_results) == 1:
        ds, results = all_results[0]
        md = _generate_markdown_report(results, ds)
        out_path = Path(args.output)
        out_path.write_text(md, encoding="utf-8")
        print(f"📄 Markdown 报告已写入: {out_path.resolve()}")
    elif args.output and len(all_results) > 1:
        # 多数据集时在每个报告文件名后加数据集名
        base = Path(args.output)
        if base.suffix:
            stem = base.stem
            suffix = base.suffix
        else:
            stem = base.name
            suffix = ".md"
        for ds, results in all_results:
            md = _generate_markdown_report(results, ds)
            path = base.parent / f"{stem}_{ds}{suffix}"
            path.write_text(md, encoding="utf-8")
            print(f"📄 Markdown 报告已写入: {path.resolve()}")


if __name__ == "__main__":
    main()
