"""验证 025 migration 是否成功：检查 knowledge_bases 表是否有 updated_at 列。"""
import asyncio
from sqlalchemy import text
from app.core.database import engine


async def check():
    async with engine.connect() as conn:
        r = await conn.execute(
            text(
                "SELECT column_name, is_nullable, column_default "
                "FROM information_schema.columns "
                "WHERE table_name = 'knowledge_bases' AND column_name = 'updated_at'"
            )
        )
        row = r.fetchone()
        if row:
            print(f"✅ Column exists: {row[0]}, nullable: {row[1]}, default: {row[2]}")
        else:
            print("❌ Column NOT FOUND")

        r2 = await conn.execute(
            text(
                "SELECT COUNT(*), "
                "COUNT(updated_at), "
                "COUNT(CASE WHEN updated_at = created_at THEN 1 END) "
                "FROM knowledge_bases"
            )
        )
        row2 = r2.fetchone()
        print(f"Total rows: {row2[0]}, non-null updated_at: {row2[1]}, updated_at=created_at: {row2[2]}")


asyncio.run(check())
