"""Drop and recreate embedding column as VECTOR(512) for BGE-small-zh."""
import asyncio
from app.core.database import engine
from sqlalchemy import text


async def fix():
    async with engine.begin() as conn:
        await conn.execute(text("DROP INDEX IF EXISTS idx_chunk_embedding_hnsw"))
        await conn.execute(text("UPDATE document_chunks SET embedding = NULL"))
        await conn.execute(text("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(512)"))
        await conn.execute(text(
            "CREATE INDEX idx_chunk_embedding_hnsw ON document_chunks "
            "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 200)"
        ))
    print("OK: column changed to VECTOR(512)")


asyncio.run(fix())
