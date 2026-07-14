import asyncio
from app.core.database import SessionLocal
from sqlalchemy import text

async def check():
    async with SessionLocal() as db:
        for tbl in ["users", "knowledge_bases", "documents", "document_chunks"]:
            r = await db.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
            c = r.scalar()
            print(f"  {tbl}: {c}")
        r = await db.execute(text("SELECT email FROM users WHERE email='admin@test.com'"))
        print(f"  Seed user found: {r.scalar() is not None}")
        r = await db.execute(text("SELECT name FROM knowledge_bases"))
        for row in r:
            print(f"  KB: {row[0]}")

asyncio.run(check())
