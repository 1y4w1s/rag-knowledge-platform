"""Add multi-query expansion to stream_workspace_chat_events."""
p = r"D:\MyPrograms\rag-knowledge-platform\backend\app\services\rag\chat.py"
with open(p, "r", encoding="utf-8") as f:
    c = f.read()

old = '    thread_id: UUID | None = None,\n    hide_admin_only: bool = False,\n) -> AsyncIterator[str]:\n    """工作区对话：跨库检索 → gate → SSE（含 kb_name）→ workspace 落库。"""\n    t0 = time.perf_counter()\n    raw_chunks = await retrieve_workspace_chunks(\n        db,\n        query=message,\n        scope=scope,\n        org_scope=org_scope,\n        hide_admin_only=hide_admin_only,\n    )\n    retrieval_duration_ms = int((time.perf_counter() - t0) * 1000)\n    chunks = filter_relevant_chunks(raw_chunks, message)\n    chunks = dedup_and_compress(chunks)\n    citations = [workspace_chunk_to_citation(c) for c in chunks]'

new = '    thread_id: UUID | None = None,\n    hide_admin_only: bool = False,\n) -> AsyncIterator[str]:\n    """工作区对话：跨库检索 → gate → SSE（含 kb_name）→ workspace 落库。"""\n    expanded = await expand_queries(message)\n    all_chunks: list[RetrievedChunk] = []\n    seen_chunk_ids: set[UUID] = set()\n    t0 = time.perf_counter()\n    for eq in expanded:\n        raw = await retrieve_workspace_chunks(\n            db, query=eq, scope=scope,\n            org_scope=org_scope, hide_admin_only=hide_admin_only,\n        )\n        for c in raw:\n            if c.chunk_id not in seen_chunk_ids:\n                seen_chunk_ids.add(c.chunk_id)\n                all_chunks.append(c)\n    retrieval_duration_ms = int((time.perf_counter() - t0) * 1000)\n    chunks = filter_relevant_chunks(all_chunks, message)\n    chunks = dedup_and_compress(chunks)\n    citations = [workspace_chunk_to_citation(c) for c in chunks]'

c = c.replace(old, new)
with open(p, "w", encoding="utf-8") as f:
    f.write(c)
print("OK")
