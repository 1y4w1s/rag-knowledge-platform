import httpx
r = httpx.get("http://localhost:1234/v1/models", timeout=5)
for m in r.json()["data"]:
    print(f"  {m['id']}")
