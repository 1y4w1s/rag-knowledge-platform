"""检查 DB 断连时的实际异常类型"""
import asyncio
from app.core.database import SessionLocal

async def test():
    try:
        async with SessionLocal() as db:
            r = await db.execute("SELECT 1")
            print("OK:", r.scalar())
    except Exception as e:
        print("Type:", type(e).__name__)
        print("Module:", type(e).__module__)
        print("Msg:", str(e)[:200])
        for cls in type(e).__mro__:
            if cls.__module__.startswith("sqlalchemy") or cls.__module__.startswith("asyncpg"):
                print(f"  MRO: {cls}")

asyncio.run(test())
