"""下载英文 Wikipedia 'Python (programming language)' 文章"""
import urllib.request, json, re
from pathlib import Path

TARGET = Path("backend/tests/fixtures") / "python_language.md"

# Wikipedia API: get plain text extract
url = "https://en.wikipedia.org/w/api.php?action=query&titles=Python+(programming+language)&prop=extracts&explaintext=true&format=json"
try:
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read())
        for pid, page in data["query"]["pages"].items():
            if pid == "-1":
                print("Page not found")
                break
            content = page.get("extract", "")
            # Clean up
            content = re.sub(r'\n{3,}', '\n\n', content)
            TARGET.write_text(f"# Python (programming language)\n\n{content}", encoding="utf-8")
            print(f"Downloaded: {len(content)} chars")
except Exception as e:
    print(f"Error: {e}")
