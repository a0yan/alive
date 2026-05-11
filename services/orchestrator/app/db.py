import asyncpg
import os

_pool = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            os.getenv("DATABASE_URL", "postgresql://alive:alive@postgres:5432/alive")
        )
    return _pool
