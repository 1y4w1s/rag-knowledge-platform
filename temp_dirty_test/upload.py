"""Upload dirty test files to KBs via API"""
import requests
import os

BASE = "http://localhost:8000/api/v1"
DIR = r"D:\MyPrograms\rag-knowledge-platform\temp_dirty_test"

# Login
login = requests.post(f"{BASE}/auth/login", json={
    "identifier": "testuser_ui",
    "password": "Test@123456"
})
token = login.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

KBS = {
    "315d2072-deab-4e3f-b958-f7f4a2ac8952": [  # 重复与空文档
        "normal_doc.txt", "normal_doc_副本.txt", "normal_doc_微改.txt",
        "empty_file.txt", "only_whitespace.txt", "one_liner.txt",
    ],
    "c3cc5b21-3a19-4704-8d85-217cecd972cd": [  # 编码与乱码
        "gb2312_text.txt", "utf8_bom.txt", "mixed_encoding.txt",
        "unicode_weird.txt", "binary_garbage.txt",
    ],
    "e209d752-4b70-4bcd-84df-1ff1baedf332": [  # 长文本与格式滥用
        "very_long_line.txt",
        "numbers_and_symbols.txt", "5mb_large_file.txt",
        "html_in_text.txt", "markdown_doc.md",
    ],
}

for kb_id, files in KBS.items():
    url = f"{BASE}/knowledge-bases/{kb_id}/documents?workspace=personal"
    for fname in files:
        fpath = os.path.join(DIR, fname)
        if not os.path.isfile(fpath):
            print(f"  SKIP (no file): {fname}")
            continue
        with open(fpath, "rb") as f:
            r = requests.post(url, headers=headers, files={"files": (fname, f)})
        if r.status_code == 201:
            print(f"  OK: {fname} -> {r.json()['documents'][0]['id']}")
        else:
            print(f"  FAIL: {fname} -> {r.status_code} {r.text[:150]}")

print("\n=== 上传完毕 ===")
