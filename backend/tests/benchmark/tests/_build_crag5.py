"""从 CRAG 数据提取 5 条真实英文查询+文档"""
import bz2, json
from pathlib import Path

src = Path("/app/data/benchmark/crag/crag_task_1_and_2_dev_v4.jsonl.bz2")
doc_dir = Path("/app/tests/fixtures/crag_en")
doc_dir.mkdir(exist_ok=True)

qa_cases = []

with bz2.open(src, "rt", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if i >= 5:
            break
        raw = json.loads(line)
        query = raw["query"]
        answer = raw.get("answer", "")
        
        # Build document from search results
        parts = []
        for sr in raw.get("search_results", [])[:5]:
            snip = sr.get("page_snippet", "")[:600]
            if snip:
                name = sr.get("page_name", "Source")
                parts.append(f"## {name}\n{snip}")
        
        doc_content = "\n\n---\n\n".join(parts)
        doc_path = doc_dir / f"crag_en_{i+1}.md"
        doc_path.write_text(f"# {query}\n\n{doc_content}", encoding="utf-8")
        
        # Create QA entry
        qa_cases.append({
            "case_id": f"CRAG-{i+1}",
            "difficulty": "L2",
            "tags": ["en", "crag", "real"],
            "query": query,
            "source": "md",
            "expect": {"content_contains": answer[:60]},
            "source_docs": [doc_path.name],
        })
        print(f"[{i+1}] {query[:50]} -> {answer[:40]}")

# Write QA file
qa = {
    "version": "1.0",
    "description": "CRAG English 5 题迷你测试集（真实维基百科文章）",
    "hit_k": 3,
    "cases": qa_cases,
}
Path("/app/tests/fixtures/crag_en_qa.json").write_text(json.dumps(qa, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nSaved: {len(qa_cases)} cases")
