"""Apply precise, targeted changes to pipeline.py"""
import re

path = r"D:\MyPrograms\rag-knowledge-platform\backend\app\services\ingestion\pipeline.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

changes = 0

# 1. Add semaphore import/definition after "import logging"
content = content.replace(
    "import asyncio\nimport logging\n\n\n",
    "import asyncio\nimport logging\n\n_INGESTION_SEMAPHORE = asyncio.Semaphore(5)\n\n\n",
    1
)
changes += 1

# 2. Add segment_cjk import after the config import
content = content.replace(
    "from app.core.config import settings\nfrom app.core.exceptions import", 
    "from app.core.config import settings\nfrom app.services.rag.cjk import segment_cjk\nfrom app.core.exceptions import",
    1
)
changes += 1

# 3. Wrap process_document_ingestion body with semaphore
# Find: "async def process_document_ingestion" then indent the body
old_func_start = 'async def process_document_ingestion(document_id: UUID) -> None:\n\n    """BackgroundTask 入口：完整入库管道。"""\n\n    started_at'
new_func_start = 'async def process_document_ingestion(document_id: UUID) -> None:\n\n    """BackgroundTask 入口：完整入库管道。"""\n    async with _INGESTION_SEMAPHORE:\n        started_at'
content = content.replace(old_func_start, new_func_start, 1)
changes += 1

# 4. Indent the body under the semaphore (from started_at through the try block)
# The body after the semaphore needs to be indented by 4 more spaces
# Find the pattern and fix it
old_body = '        started_at = datetime.now(timezone.utc)\n\n\n    async with SessionLocal() as db:\n\n        doc = await db.get(Document, document_id)\n\n        if doc is None:\n\n            logger.warning("ingestion: document %s not found", document_id)\n\n            return\n\n\n\n        storage_path = doc.storage_path'
new_body = '        started_at = datetime.now(timezone.utc)\n\n        async with SessionLocal() as db:\n\n            doc = await db.get(Document, document_id)\n\n            if doc is None:\n\n                logger.warning("ingestion: document %s not found", document_id)\n\n                return\n\n\n\n            storage_path = doc.storage_path'
content = content.replace(old_body, new_body, 1)
changes += 1

# 5. Add processing status guard after the doc is None check
old_guard = '                return\n\n\n\n            storage_path'
new_guard = '                return\n\n            if doc.status == DocumentStatus.processing:\n                logger.warning("ingestion: document %s already processing, skipped", document_id)\n                return\n\n\n            storage_path'
content = content.replace(old_guard, new_guard, 1)
changes += 1

# 6. Fix try/except in _write_chunks for StopIteration  
old_try = '            embedding = next(vector_iter)\n            embed_model = current_embedding_model()'
new_try = '            try:\n                embedding = next(vector_iter)\n                embed_model = current_embedding_model()\n            except StopIteration:\n                pass'
content = content.replace(old_try, new_try, 1)
changes += 1

# 7. Add segment_cjk to tsvector source
old_tsv = "        tsv_source = ' '.join("
new_tsv = "        tsv_source = segment_cjk(tsv_source)\n        tsv_source = ' '.join("
content = content.replace(old_tsv, new_tsv, 1)
changes += 1

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Applied {changes} changes to pipeline.py")
