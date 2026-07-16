"""Debug LM Studio API response"""
import httpx

try:
    r = httpx.post("http://localhost:1234/v1/chat/completions", json={
        "model": "qwen/qwen3.5-9b",
        "messages": [{"role": "user", "content": "Say 'ok' in one word."}],
        "max_tokens": 5,
    }, timeout=30)
    print(f"Status: {r.status_code}")
    print(f"Headers: {dict(r.headers)}")
    print(f"Body: {r.text[:500]}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
