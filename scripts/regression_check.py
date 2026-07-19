"""RAG 回归检测入口

用法：
    python scripts/regression_check.py              # 快速检测（50题）
    python scripts/regression_check.py --full       # 全量 296 题
    python scripts/regression_check.py --sample 20  # 指定抽样数
    
返回码：0=PASS  1=WARN  2=FAIL
"""
import json
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def main():
    args = parse_args()
    
    # 读取基线
    baseline = json.loads((BASE_DIR.parent / "docs" / "baseline.json").read_text(encoding="utf-8-sig"))
    baseline_json = json.dumps(baseline, ensure_ascii=False)
    
    # 复制内核脚本到 Docker
    kernel = BASE_DIR / "regression_kernel.py"
    subprocess.run(["docker", "cp", str(kernel), "ruige-api:/app/scripts/regression_kernel.py"],
                   capture_output=True)
    
    # 在 Docker 内执行
    env_vars = [
        "-e", f"BASELINE_JSON={baseline_json}",
        "-e", f"QUICK_SAMPLE={args.sample}",
        "-e", f"FULL={'true' if args.full else 'false'}",
        "-e", "PYTHONPATH=/app",
        "-e", "RAG_REAL_EMBEDDING=0",  # mock 嵌入
    ]
    
    result = subprocess.run(
        ["docker", "exec", "-i"] + env_vars + ["ruige-api", "python", "/app/scripts/regression_kernel.py"],
        capture_output=True, text=True, timeout=600,
    )
    
    # 解析 JSON 输出
    stdout = result.stdout
    json_start = stdout.find("JSON_START")
    json_end = stdout.find("JSON_END")
    
    # 打印输出
    for line in stdout.split("\n"):
        if any(s in line for s in ["Hit@3:", "MRR:", "Status:", "FAIL:", "Diff:"]):
            print(line)
    
    if json_start >= 0 and json_end >= 0:
        output = json.loads(stdout[json_start + 10:json_end])
        print(f"\n{json.dumps(output, indent=2)}")
        return output.get("exit_code", 1)
    
    print(f"\n--- stdout ---\n{stdout[:1000]}")
    print(f"\n--- stderr ---\n{result.stderr[:500]}")
    return 1


def parse_args():
    import argparse
    p = argparse.ArgumentParser(description="RAG 回归检测")
    p.add_argument("--full", action="store_true", help="全量 296 题")
    p.add_argument("--sample", type=int, default=50, help="抽样数")
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(main())
