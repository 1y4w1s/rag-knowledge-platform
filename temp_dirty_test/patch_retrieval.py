"""Patch retrieval.py to add ILIKE fallback for special characters"""
import re

path = r"D:\MyPrograms\rag-knowledge-platform\backend\app\services\rag\retrieval.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add helper functions after imports
import_section_end = content.index("\n\n\nasync def")
helpers = """

import re


def _has_special_chars(query: str) -> bool:
    \"\"\"Check if query has chars that plainto_tsquery would strip.\"\"\"
    stripped = re.sub(r"[\\w\\s]", "", query)
    return bool(stripped)


def _escape_ilike(value: str) -> str:
    \"\"\"Escape ILIKE wildcards: %, _, backslash.\"\"\"
    return value.replace("\\\\", "\\\\\\\\").replace("%", "\\\\%").replace("_", "\\\\_")


"""

content = content[:import_section_end] + helpers + content[import_section_end:]

# 2. Replace the FTS query condition to add ILIKE fallback
old_fts = """    ts_query = func.plainto_tsquery(TS_CONFIG, query)
    rank = func.ts_rank_cd(DocumentChunk.content_tsv, ts_query).label("fts_rank")
    stmt = (
        select(DocumentChunk, Document.filename, rank)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(DocumentChunk.kb_id == kb_id)
        .where(DocumentChunk.content_tsv.is_not(None))
        .where(_exclude_parent_chunks())
        .where(DocumentChunk.content_tsv.op("@")(ts_query))
    )"""

new_fts = """    ts_query = func.plainto_tsquery(TS_CONFIG, query)
    rank = func.ts_rank_cd(DocumentChunk.content_tsv, ts_query).label("fts_rank")

    fts_condition = DocumentChunk.content_tsv.op("@@")(ts_query)
    if _has_special_chars(query):
        fts_condition = fts_condition | DocumentChunk.content.ilike(
            f"%{_escape_ilike(query)}%", escape="\\\\"
        )

    stmt = (
        select(DocumentChunk, Document.filename, rank)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(DocumentChunk.kb_id == kb_id)
        .where(DocumentChunk.content_tsv.is_not(None))
        .where(_exclude_parent_chunks())
        .where(fts_condition)
    )"""

content = content.replace(old_fts, new_fts)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("OK")
