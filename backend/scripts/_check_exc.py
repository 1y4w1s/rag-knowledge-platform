"""检查 asyncpg 异常类型是否被 OperationalError handler 捕获"""
import sqlalchemy.exc
import asyncpg.exceptions

print("ConnectionDoesNotExistError MRO:")
for c in asyncpg.exceptions.ConnectionDoesNotExistError.__mro__:
    print(f"  {c}")

print()
is_sub = issubclass(
    asyncpg.exceptions.ConnectionDoesNotExistError,
    sqlalchemy.exc.OperationalError
)
print(f"Is subclass of OperationalError? {is_sub}")
