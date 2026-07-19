"""从 CRAG 数据提取英文文档"""
import bz2, json
from pathlib import Path

src = Path("/app/data/benchmark/crag/crag_task_1_and_2_dev_v4.jsonl.bz2")
dst = Path("/app/tests/fixtures/crag_english.md")

with bz2.open(src, "rt", encoding="utf-8") as f:
    line = f.readline()
    raw = json.loads(line)

parts = []
for sr in raw.get("search_results", [])[:5]:
    snip = sr.get("page_snippet", "")[:800]
    if snip:
        name = sr.get("page_name", "Source")
        parts.append(f"## {name}\n{snip}")

content = "\n\n---\n\n".join(parts)
dst.write_text(f"# {raw['query']}\n\n{content}", encoding="utf-8")
print(f"Created: {len(content)} chars, from query: {raw['query'][:60]}")
