"""Test encoding fallback with a fresh file that has mixed encodings"""
import requests
BASE = "http://localhost:8000/api/v1"
login = requests.post(f"{BASE}/auth/login", json={
    "identifier": "testuser_ui",
    "password": "Test@123456"
})
token = login.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Create a test file that can only be read by GBK, not UTF-8
import os
test_dir = r"D:\MyPrograms\rag-knowledge-platform\temp_dirty_test"
test_file = os.path.join(test_dir, "encoding_test_gbk.txt")
# Write GBK bytes directly
with open(test_file, "wb") as f:
    f.write("这是一段GBK编码的中文文本。含有无法被UTF-8解析的字节：\xa1\xa1\xa1\xa2".encode("gbk"))

# Upload to KB1 (重复与空文档 KB)
url = f"{BASE}/knowledge-bases/315d2072-deab-4e3f-b958-f7f4a2ac8952/documents?workspace=personal"
with open(test_file, "rb") as f:
    r = requests.post(url, headers=headers, files={"files": ("encoding_test_gbk.txt", f)})
if r.status_code == 201:
    doc_id = r.json()["documents"][0]["id"]
    print(f"OK: encoding_test_gbk uploaded, doc_id={doc_id}")
elif r.status_code == 409:
    print(f"DUPLICATE: {r.text[:200]}")
else:
    print(f"RESULT: {r.status_code} {r.text[:200]}")
