"""A Phase 1 Nightly CI — BEIR × RAGAS 定期评测 + 基线漂移检测。

Usage:
    python -m tests.benchmark.run_nightly                  # 全量
    python -m tests.benchmark.run_nightly --quick          # 快速（sample=10）
    python -m tests.benchmark.run_nightly --reset-baseline # 重置基线
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path


def _load_dotenv():
    """从项目 .env 加载缺失的环境变量（独立脚本不自动读 .env）。"""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip("\"'")
            if key and not os.environ.get(key):
                os.environ[key] = val


_load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("run_nightly")

# ── 配置 ──
NIGHTLY_DATASETS = ["beir/nfcorpus", "beir/fiqa"]
RESULTS_DIR = Path("benchmark_results")
BASELINE_FILE = RESULTS_DIR / "nightly_baseline.json"
DRIFT_THRESHOLD = 0.05  # 5%


def _resolve_results_dir() -> Path:
    cwd = Path.cwd() / "benchmark_results"
    if cwd.is_dir():
        return cwd
    root = Path(__file__).resolve().parents[2] / "benchmark_results"
    if root.is_dir():
        return root
    cwd.mkdir(parents=True, exist_ok=True)
    return cwd


def run_one(dataset: str, quick: bool) -> Path | None:
    """跑一个 BEIR 数据集 RAGAS 评测，返回结果文件路径。"""
    ts = time.strftime("%Y%m%d_%H%M%S")
    sample_args = ["--sample", "10"] if quick else ["--sample", "30"]
    cmd = [
        "python", "-m", "tests.benchmark.run_benchmark",
        "--datasets", dataset,
        "--scorer", "ragas",
        "--top-k", "3",
    ] + sample_args
    logger.info("运行: %s", " ".join(cmd))
    env = os.environ.copy()
    if "HF_ENDPOINT" not in env:
        env["HF_ENDPOINT"] = "https://hf-mirror.com"
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("%s 失败: %s", dataset, result.stderr[:300])
        return None

    src = Path("benchmark_results/benchmark_retrieval_ragas.json")
    if not src.exists():
        logger.warning("%s 结果文件未找到: %s", dataset, src)
        return None

    safe_ds = dataset.replace("/", "_")
    dst = RESULTS_DIR / f"benchmark_retrieval_ragas_{safe_ds}_{ts}.json"
    import shutil
    shutil.copy2(src, dst)
    logger.info("结果已保存: %s", dst)
    return dst


def _extract_metrics(path: Path) -> dict[str, float]:
    """从结果 JSON 提取 CP/CR。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    metrics = {}
    for ds_entry in data.get("datasets", []):
        ret = ds_entry.get("retrieval", {})
        ds_name = ds_entry.get("dataset_name", "unknown")
        cp = ret.get("context_precision_avg")
        cr = ret.get("context_recall_avg")
        if cp is not None:
            metrics[f"{ds_name}_cp"] = cp
        if cr is not None:
            metrics[f"{ds_name}_cr"] = cr
    return metrics


def _load_baseline() -> dict:
    if BASELINE_FILE.exists():
        return json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    return {}


def _save_baseline(metrics: dict, run_id: str):
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_FILE.write_text(json.dumps({
        "run_id": run_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "metrics": metrics,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("基线已更新: %s", BASELINE_FILE)


def _check_drift(current: dict, baseline: dict) -> list[str]:
    """对比当前与基线，返回告警列表。"""
    alarms = []
    base_metrics = baseline.get("metrics", {})
    for key, cur_val in current.items():
        base_val = base_metrics.get(key)
        if base_val is None or base_val == 0 or base_val != base_val:  # nan 守卫
            continue
        if cur_val - base_val < -DRIFT_THRESHOLD:  # 仅下降告警
            pct = (base_val - cur_val) / base_val * 100
            alarms.append(
                f"⚠️ {key}: {base_val:.4f} → {cur_val:.4f} (↓{pct:.1f}%)"
            )
    return alarms


def generate_report(
    results: dict[str, Path | None],
    alarms: list[str],
    elapsed: float,
    run_id: str,
) -> str:
    """生成 Nightly MD 报告。"""
    lines = [
        f"# Nightly 报告 — {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Run ID**: {run_id}",
        f"**耗时**: {elapsed:.0f}s",
        "",
    ]
    if alarms:
        lines.append("## ⚠️ 基线漂移告警")
        lines.extend(alarms)
        lines.append("")
    else:
        lines.append("## ✅ 无显著漂移")
        lines.append("")

    lines.append("## 各数据集指标")
    lines.append("")
    lines.append("| 数据集 | Context Precision | Context Recall |")
    lines.append("|--------|-------------------|----------------|")
    for ds in NIGHTLY_DATASETS:
        path = results.get(ds)
        cp = cr = "—"
        if path and path.exists():
            m = _extract_metrics(path)
            cp = f"{m.get(f'{ds}_cp', 0)*100:.1f}%" if f"{ds}_cp" in m else "—"
            cr = f"{m.get(f'{ds}_cr', 0)*100:.1f}%" if f"{ds}_cr" in m else "—"
        lines.append(f"| {ds} | {cp} | {cr} |")

    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="A Phase 1 Nightly CI")
    parser.add_argument("--quick", action="store_true", help="快速模式（sample=10）")
    parser.add_argument("--reset-baseline", action="store_true", help="重置基线")
    args = parser.parse_args()

    global RESULTS_DIR
    RESULTS_DIR = _resolve_results_dir()
    run_id = time.strftime("nightly_%Y%m%d_%H%M%S")
    t0 = time.perf_counter()

    # 收集所有结果
    nightly_results: dict[str, Path | None] = {}
    for ds in NIGHTLY_DATASETS:
        logger.info("===== %s =====", ds)
        path = run_one(ds, quick=args.quick)
        nightly_results[ds] = path

    elapsed = time.perf_counter() - t0

    # 提取指标
    current_metrics = {}
    for ds, path in nightly_results.items():
        if path and path.exists():
            current_metrics.update(_extract_metrics(path))

    # 基线漂移检测
    baseline = {} if args.reset_baseline else _load_baseline()
    alarms = _check_drift(current_metrics, baseline) if baseline else []
    if not baseline or args.reset_baseline:
        _save_baseline(current_metrics, run_id)
        logger.info("基线已初始化（首次运行或重置）")

    # 报告
    report = generate_report(nightly_results, alarms, elapsed, run_id)
    report_path = RESULTS_DIR / f"nightly_{run_id}.md"
    report_path.write_text(report, encoding="utf-8")
    logger.info("报告已保存: %s", report_path)
    import sys
    report_text = "\n" + report + "\n"
    try:
        print(report_text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(report_text.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")

    if alarms:
        logger.warning("基线漂移告警:\n%s", "\n".join(alarms))
        sys.exit(1)


if __name__ == "__main__":
    main()
