"""验证 BGE-large-zh 推理服务是否就绪（Xinference 格式）。

用法：
    python scripts/check_bge_service.py

正常输出：
    ✅ BGE 服务可用: dim=1024, latency=42.3ms

失败输出：
    ❌ BGE 服务不可用: Connection refused
"""

import json
import sys
import time
import urllib.request

BGE_API_URL = "http://localhost:9997/v1/embeddings"
BGE_MODEL = "bge-large-zh-v1.5"
TEST_TEXT = "员工年满一年后每年享有10天年假。"


def check_bge_service() -> dict:
    payload = {
        "model": BGE_MODEL,
        "input": TEST_TEXT,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BGE_API_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=10) as resp:
        elapsed = (time.perf_counter() - t0) * 1000
        result = json.loads(resp.read().decode("utf-8"))
    vector = result["data"][0]["embedding"]
    return {"dim": len(vector), "latency_ms": round(elapsed, 1), "vector_sample": vector[:5]}


if __name__ == "__main__":
    try:
        info = check_bge_service()
        print(f"✅ BGE 服务可用: dim={info['dim']}, latency={info['latency_ms']}ms")
        print(f"   向量前5维: {info['vector_sample']}")
        sys.exit(0)
    except Exception as e:
        print(f"❌ BGE 服务不可用: {e}")
        print(f"\n请先启动 Xinference:\n  xinference launch --model-name {BGE_MODEL} --model-type embedding")
        sys.exit(1)
