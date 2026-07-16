"""Fix duplicate code in workspace FTS recall function"""
path = r"D:\MyPrograms\rag-knowledge-platform\backend\app\services\rag\retrieval.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Lines 422-448 have broken duplicate code
# Keep lines 0-421 (up to the fts_condition block)
# Lines 449+ have the proper continuation

new_lines = lines[:422]  # Keep the good part (fts_condition block complete)

# Add properly formed stmt block
new_lines.append("    stmt = (\n")
new_lines.append("        select(\n")
new_lines.append("            DocumentChunk,\n")
new_lines.append("            Document.filename,\n")
new_lines.append('            KnowledgeBase.name.label("kb_name"),\n')
new_lines.append("            rank,\n")
new_lines.append("        )\n")
new_lines.append("        .join(Document, DocumentChunk.document_id == Document.id)\n")
new_lines.append("        .join(KnowledgeBase, DocumentChunk.kb_id == KnowledgeBase.id)\n")
new_lines.append("        .where(scope_clause)\n")

# Add the rest from line 449 onwards (the good old code)
for i in range(448, len(lines)):
    new_lines.append(lines[i])

with open(path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("OK - removed duplicate, rebuilt stmt block")
