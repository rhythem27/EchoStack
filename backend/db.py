import asyncpg
from backend.config import settings

_db_pool = None

async def init_db_pool() -> asyncpg.Pool:
    """Initializes the connection pool to the PostgreSQL database."""
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(
            dsn=settings.DATABASE_URL,
            min_size=2,
            max_size=10
        )
    return _db_pool

async def close_db_pool():
    """Closes the connection pool."""
    global _db_pool
    if _db_pool is not None:
        await _db_pool.close()
        _db_pool = None

async def get_db_pool() -> asyncpg.Pool:
    """Retrieves the active pool instance, initializing it if required."""
    global _db_pool
    if _db_pool is None:
        return await init_db_pool()
    return _db_pool
