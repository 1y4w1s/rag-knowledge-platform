"""Test golden handbook ingestion directly"""
import asyncio, httpx

BASE = "http://localhost:8000/api/v1"

r = httpx.post(f"{BASE}/auth/login", json={"identifier": "testuser_ui", "password": "Test@123456"})
token = r.json()["access_token"]
H = {"Authorization": f"Bearer {token}"}

# Create KB
r = httpx.post(f"{BASE}/knowledge-bases?workspace=personal", json={"name": "golden-test"}, headers=H)
kb = r.json()["id"]
print(f"KB: {kb}")

# Upload golden_handbook.md
with open(r"D:\MyPrograms\rag-knowledge-platform\backend\tests\fixtures\golden_handbook.md", "rb") as f:
    r = httpx.post(f"{BASE}/knowledge-bases/{kb}/documents?workspace=personal", files={"files": ("golden_handbook.md", f)}, headers=H)
print(f"Upload: {r.status_code}")
if r.status_code == 201:
    doc_id = r.json()["documents"][0]["id"]
    print(f"Doc ID: {doc_id}")

    # Poll for completion
    for i in range(15):
        r = httpx.get(f"{BASE}/knowledge-bases/{kb}?workspace=personal", headers=H)
        d = r.json()
        dc = d.get("document_count", 0)
        pc = d.get("processing_count", 0)
        fc = d.get("failed_count", 0)
        print(f"  [{i}] docs={dc} processing={pc} failed={fc}")
        if dc > 0 and pc == 0:
            print("Ingestion complete!")
            break
        import time
        time.sleep(5)
    else:
        print("Timed out waiting for ingestion")

    # Check doc status
    r = httpx.get(f"{BASE}/knowledge-bases/{kb}/documents?workspace=personal", headers=H)
    docs = r.json().get("items", [])
    for d in docs:
        print(f"  {d.get('filename')}: status={d.get('status')} error={d.get('error_message','')[:200]}")
