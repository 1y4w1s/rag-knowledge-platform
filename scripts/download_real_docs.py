"""下载 3 份中文开源文档用于真实文档测试集。"""
import urllib.request, os, json
from pathlib import Path

TARGET = Path("backend/tests/fixtures/real_docs")
TARGET.mkdir(parents=True, exist_ok=True)

docs = {
    "机器学习.md": "https://raw.githubusercontent.com/cirosantilli/china-dictatorship/master/README.md",
    "劳动合同法.md": "https://raw.githubusercontent.com/1y4w1s/rag-knowledge-platform/master/backend/tests/fixtures/golden_handbook.md",
}

# 用 Wikipedia 中文 API 获取页面
import urllib.parse

pages = {
    "机器学习.md": {"title": "机器学习", "lang": "zh"},
    "中国居民膳食指南.md": {"title": "中国居民膳食指南", "lang": "zh"},
    "劳动合同法.md": {"title": "中华人民共和国劳动合同法", "lang": "zh"},
}

for filename, info in pages.items():
    path = TARGET / filename
    if path.exists():
        print(f"[跳过] {filename} 已存在")
        continue
    
    url = f"https://{info['lang']}.wikipedia.org/w/api.php?action=query&titles={urllib.parse.quote(info['title'])}&prop=extracts&explaintext=true&format=json"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read())
            pages_data = data["query"]["pages"]
            for pid, page_data in pages_data.items():
                if pid == "-1":
                    print(f"[失败] {filename}: 页面不存在")
                    break
                content = page_data.get("extract", "")
                if content:
                    path.write_text(content, encoding="utf-8")
                    print(f"[完成] {filename} ({len(content)} 字)")
                else:
                    print(f"[失败] {filename}: 内容为空")
    except Exception as e:
        print(f"[错误] {filename}: {e}")

print(f"\n文档列表：")
for p in sorted(TARGET.glob("*.md")):
    print(f"  {p.name}  ({len(p.read_text(encoding='utf-8'))} 字)")
