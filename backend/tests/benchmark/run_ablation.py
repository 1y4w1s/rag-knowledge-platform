"""A Phase 1 消融 runner — 一键遍历配置组合，产出对比报告。

Usage:
    python -m tests.benchmark.run_ablation --datasets golden_qa --variants off,hyde,b2
    python -m tests.benchmark.run_ablation --datasets beir/nfcorpus --variants off,hyde,b2 --quick
"""

from __future__ import annotations

import json
import logging
import os
import shutil
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
logger = logging.getLogger("run_ablation")

# ── 变体环境变量映射 ──

VARIANTS_ENV: dict[str, dict[str, str]] = {
    "off":  {"HYDE_ENABLED": "false", "QUERY_REWRITE_POLICY": "off"},
    "hyde": {"HYDE_ENABLED": "true",  "QUERY_REWRITE_POLICY": "off"},
    "b2":   {"HYDE_ENABLED": "false", "QUERY_REWRITE_POLICY": "conditional"},
    # b3（自适应策略）无独立 env 开关，当前通过 planner.select_strategy 默认启用
    # 隔离方式：b2 (conditional) vs off (off) 测 B2
}

# ── 默认输出目录 ──
RESULTS_DIR = Path("benchmark_results")


def _resolve_results_dir() -> Path:
    """优先 CWD 下 benchmark_results，否则回退项目根目录。"""
    cwd = Path.cwd() / "benchmark_results"
    if cwd.is_dir():
        return cwd
    # 尝试项目根
    root = Path(__file__).resolve().parents[2] / "benchmark_results"
    if root.is_dir():
        return root
    cwd.mkdir(parents=True, exist_ok=True)
    return cwd


def run_variant(dataset: str, variant: str, quick: bool = False) -> Path | None:
    """跑一个变体，返回结果文件路径（None 表示无产出）。"""
    env = os.environ.copy()
    env.update(VARIANTS_ENV[variant])
    if "HF_ENDPOINT" not in env:
        env["HF_ENDPOINT"] = "https://hf-mirror.com"
    ts = time.strftime("%Y%m%d_%H%M%S")
    safe_ds = dataset.replace("/", "_")

    if dataset == "golden_qa":
        # golden_qa 不走 run_benchmark（未注册），走专用脚本
        # ⚠️ run_golden_full 无 argparse，--sample 不生效
        cmd = ["python", "-m", "tests.benchmark.tests.run_golden_full"]
        logger.info("运行 variant=%s dataset=%s cmd=%s", variant, dataset, " ".join(cmd))
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("variant=%s 失败: %s", variant, result.stderr[:200])
            return None
        # 拷贝结果
        # golden_qa 输出位置在 tests/benchmark_results/ 下
        src = Path(__file__).resolve().parent / ".." / "benchmark_results" / "golden_qa_full.json"
        src = src.resolve()
        if not src.exists():
            logger.warning("variant=%s 结果文件未找到: %s", variant, src)
            return None
        dst = RESULTS_DIR / f"golden_qa_full_{variant}_{ts}.json"
        shutil.copy2(src, dst)
        logger.info("variant=%s 结果已保存: %s", variant, dst)
        return dst

    # 其它 dataset 走 run_benchmark
    sample_args = ["--sample", "20"] if quick else []
    cmd = [
        "python", "-m", "tests.benchmark.run_benchmark",
        "--datasets", dataset,
        "--scorer", "default",
        "--top-k", "3",
    ] + sample_args
    logger.info("运行 variant=%s dataset=%s cmd=%s", variant, dataset, " ".join(cmd))
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("variant=%s 失败: %s", variant, result.stderr[:200])
        return None

    src = Path("benchmark_results/benchmark_retrieval_default.json")
    if not src.exists():
        logger.warning("variant=%s 结果文件未找到: %s", variant, src)
        return None
    dst = RESULTS_DIR / f"benchmark_retrieval_{safe_ds}_{variant}_{ts}.json"
    shutil.copy2(src, dst)
    logger.info("variant=%s 结果已保存: %s", variant, dst)
    return dst


def _read_hit_at_3(path: Path) -> float | None:
    """从结果 JSON 中提取 Hit@3。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        for ds in data.get("datasets", []):
            ret = ds.get("retrieval") or ds.get("retrieval", {})
            if ret:
                return ret.get("hit_at_3")
        # golden_qa 格式：顶层字段
        return data.get("hit_k_rate") or data.get("hit_at_3")
    except Exception:
        return None


def generate_report(results: dict[str, Path | None], elapsed: float) -> str:
    """生成 MD 格式消融报告。"""
    lines = [
        f"# 消融报告 — {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "| 配置 | Hit@3 | 耗时(s) | vs Baseline |",
        "|------|-------|---------|-------------|",
    ]
    baseline_hit = None
    baseline_path = results.get("off")
    if baseline_path and baseline_path.exists():
        baseline_hit = _read_hit_at_3(baseline_path)

    for variant, path in results.items():
        hit = _read_hit_at_3(path) if path and path.exists() else None
        hit_str = f"{hit*100:.1f}%" if hit is not None else "—"
        delta = ""
        if hit is not None and baseline_hit is not None and variant != "off":
            diff = hit - baseline_hit
            delta = f"{diff*100:+.1f}% {'✅' if diff >= 0 else '❌'}"
        lines.append(f"| {variant} | {hit_str} | {elapsed:.0f} | {delta} |")

    lines.append("")
    lines.append(f"运行耗时: {elapsed:.0f}s")
    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="A Phase 1 消融 runner")
    parser.add_argument("--datasets", default="golden_qa", help="数据集（逗号分隔）")
    parser.add_argument("--variants", default="off,hyde,b2", help="变体（逗号分隔）")
    parser.add_argument("--quick", action="store_true", help="快速模式（--sample 20）")
    args = parser.parse_args()

    datasets = [d.strip() for d in args.datasets.split(",")]
    variants = [v.strip() for v in args.variants.split(",")]

    # 验证变体
    for v in variants:
        if v not in VARIANTS_ENV:
            logger.error("未知变体: %s（可用: %s）", v, list(VARIANTS_ENV.keys()))
            sys.exit(1)

    global RESULTS_DIR
    RESULTS_DIR = _resolve_results_dir()
    t0 = time.perf_counter()

    for dataset in datasets:
        logger.info("===== 数据集: %s =====", dataset)
        all_results: dict[str, Path | None] = {}
        for variant in variants:
            logger.info("--- 变体: %s ---", variant)
            path = run_variant(dataset, variant, quick=args.quick)
            all_results[variant] = path

        elapsed = time.perf_counter() - t0
        report = generate_report(all_results, elapsed)
        report_path = RESULTS_DIR / f"ablation_{dataset.replace('/', '_')}_{time.strftime('%Y%m%d_%H%M%S')}.md"
        report_path.write_text(report, encoding="utf-8")
        logger.info("报告已保存: %s", report_path)
        report_text = "\n" + report + "\n"
        try:
            print(report_text)
        except UnicodeEncodeError:
            sys.stdout.buffer.write(report_text.encode("utf-8"))
            sys.stdout.buffer.write(b"\n")


if __name__ == "__main__":
    main()
