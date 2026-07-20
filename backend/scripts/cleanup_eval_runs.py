"""evaluation_runs 定期清理：删除 90 天前的记录。"""
import asyncio, sys
sys.path.insert(0, "backend")

async def main():
    from app.core.database import engine
    from sqlalchemy import text

    async with engine.connect() as conn:
        result = await conn.execute(
            text("DELETE FROM evaluation_runs WHERE created_at < NOW() - INTERVAL '90 days'")
        )
        await conn.commit()
        print(f"Deleted {result.rowcount} old evaluation_runs records")

if __name__ == "__main__":
    asyncio.run(main())
