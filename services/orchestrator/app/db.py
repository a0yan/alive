import asyncpg
import os

_pool = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        user = os.getenv("POSTGRES_USER", "alive")
        password = os.getenv("POSTGRES_PASSWORD", "alive")
        host = os.getenv("POSTGRES_HOST", "postgres")
        port = os.getenv("POSTGRES_PORT", "5432")
        db = os.getenv("POSTGRES_DB", "alive")
        dsn = f"postgresql://{user}:{password}@{host}:{port}/{db}"
        _pool = await asyncpg.create_pool(dsn)
    return _pool
