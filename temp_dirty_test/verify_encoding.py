"""Quick test - upload GB2312 file to verify encoding fallback"""
import requests
BASE = "http://localhost:8000/api/v1"
login = requests.post(f"{BASE}/auth/login", json={
    "identifier": "testuser_ui",
    "password": "Test@123456"
})
token = login.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
url = f"{BASE}/knowledge-bases/c3cc5b21-3a19-4704-8d85-217cecd972cd/documents?workspace=personal"
with open(r"D:\MyPrograms\rag-knowledge-platform\temp_dirty_test\gb2312_text.txt", "rb") as f:
    r = requests.post(url, headers=headers, files={"files": ("gb2312_retest.txt", f)})
if r.status_code == 201:
    doc_id = r.json()["documents"][0]["id"]
    print(f"OK: GB2312 file uploaded, doc_id={doc_id}")
else:
    print(f"FAIL: {r.status_code} {r.text[:200]}")
