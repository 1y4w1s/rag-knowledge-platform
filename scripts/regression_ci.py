"""CI 版回归检测（直接运行，不依赖 Docker 容器）"""
import json
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def main():
    args = parse_args()

    # 注入环境变量
    env = {
        "PYTHONPATH": str(BASE_DIR / "backend"),
        "RAG_RATE_LIMIT_MODE": "bypass",
        "QUICK_SAMPLE": str(args.sample),
        "FULL": "true" if args.full else "false",
        "BASELINE_JSON": (BASE_DIR / "docs" / "baseline.json").read_text(encoding="utf-8-sig"),
        "RAG_REAL_EMBEDDING": "0",  # mock 嵌入
    }

    result = subprocess.run(
        [sys.executable, str(BASE_DIR / "scripts" / "regression_kernel.py")],
        capture_output=True, text=True, timeout=600, env={**dict(subprocess.os.environ), **env},
    )

    stdout = result.stdout
    for line in stdout.split("\n"):
        if any(s in line for s in ["Hit@3:", "MRR:", "Status:", "FAIL:", "Diff:"]):
            print(line)

    json_start = stdout.find("JSON_START")
    json_end = stdout.find("JSON_END")
    if json_start >= 0 and json_end >= 0:
        output = json.loads(stdout[json_start + 10:json_end])
        print(f"\n{json.dumps(output, indent=2)}")
        return output.get("exit_code", 1)

    print(f"--- stdout ---\n{stdout[:1000]}")
    return 1


def parse_args():
    import argparse
    p = argparse.ArgumentParser(description="RAG 回归检测（CI 版）")
    p.add_argument("--full", action="store_true")
    p.add_argument("--sample", type=int, default=50)
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(main())
