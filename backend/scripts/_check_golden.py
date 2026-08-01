"""验证 Golden 门禁当前状态"""
import subprocess, json, sys

# 在容器内跑测试
result = subprocess.run(
    ["docker", "compose", "exec", "api", "env",
     "PYTHONPATH=/app:/app/tests/tests",
     "python", "-m", "pytest",
     "/app/tests/tests/test_retrieval_golden.py",
     "--asyncio-mode=auto", "--tb=line",
     "-k", "not conditional and not multi"],
    capture_output=True, text=True, timeout=180
)

# 提取结果行
for line in result.stdout.split("\n"):
    if "passed" in line and "failed" in line:
        print(line.strip())
    if "FAILED" in line:
        print("  FAIL:", line.strip())

print(f"\nReturn code: {result.returncode}")
