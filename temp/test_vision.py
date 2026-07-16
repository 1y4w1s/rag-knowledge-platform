"""Test LM Studio vision model"""
import httpx
try:
    r = httpx.post("http://localhost:1234/v1/chat/completions", json={
        "model": "zai-org/glm-4.6v-flash",
        "messages": [{"role": "user", "content": "Reply with just: vision OK"}],
        "max_tokens": 20,
    }, timeout=120)
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    print(f"Status: {r.status_code}")
    print(f"Response: {content}")
except httpx.TimeoutException:
    print("Timeout - vision model not loaded in GPU memory")
except Exception as e:
    print(f"Error: {e}")
