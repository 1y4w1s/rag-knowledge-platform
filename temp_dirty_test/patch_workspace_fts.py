"""Apply ILIKE fallback to workspace FTS function"""
path = r"D:\MyPrograms\rag-knowledge-platform\backend\app\services\rag\retrieval.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old = """    scope_clause = kb_scope_clause(scope, org_scope)
    ts_query = func.plainto_tsquery(TS_CONFIG, query)
    rank = func.ts_rank_cd(DocumentChunk.content_tsv, ts_query).label("fts_rank")
    stmt = (
        select(
            DocumentChunk,
            Document.filename,
            KnowledgeBase.name.label("kb_name"),
            rank,
        )
        .join(Document, DocumentChunk.document_id == Document.id)
        .join(KnowledgeBase, DocumentChunk.kb_id == KnowledgeBase.id)
        .where(scope_clause)
        .where(DocumentChunk.content_tsv.is_not(None))
        .where(_exclude_parent_chunks())
        .where(DocumentChunk.content_tsv.op("@@@")(ts_query))
    )"""

new = """    scope_clause = kb_scope_clause(scope, org_scope)
    ts_query = func.plainto_tsquery(TS_CONFIG, query)
    rank = func.ts_rank_cd(DocumentChunk.content_tsv, ts_query).label("fts_rank")

    fts_condition = DocumentChunk.content_tsv.op("@@")(ts_query)
    if _has_special_chars(query):
        fts_condition = fts_condition | DocumentChunk.content.ilike(
            f"%{_escape_ilike(query)}%", escape="\\\\"
        )

    stmt = (
        select(
            DocumentChunk,
            Document.filename,
            KnowledgeBase.name.label("kb_name"),
            rank,
        )
        .join(Document, DocumentChunk.document_id == Document.id)
        .join(KnowledgeBase, DocumentChunk.kb_id == KnowledgeBase.id)
        .where(scope_clause)
        .where(DocumentChunk.content_tsv.is_not(None))
        .where(_exclude_parent_chunks())
        .where(fts_condition)
    )"""

if old in content:
    content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("OK - workspace FTS patched")
else:
    print("Old string not found!")
    # Debug: print the actual content around the workspace FTS
    import re
    idx = content.find("async def _fts_recall_workspace")
    print(repr(content[idx:idx+700]))
