import subprocess
result = subprocess.run(
    ["docker", "compose", "exec", "api", "sh", "-c",
     "python -c 'open(\"/app/tests/tests/test_retrieval_golden.py\",\"rb\").read().decode(\"utf-8\")' 2>&1"],
    capture_output=True, text=True, timeout=30
)
print("stdout:", result.stdout[:500])
print("stderr:", result.stderr[:500])
print("rc:", result.returncode)
