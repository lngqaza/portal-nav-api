from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
import logging

from app.core.config import settings

engine = None
SessionLocal = None


async def init_db():
    global engine, SessionLocal
    url = settings.DATABASE_URL
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(url, pool_size=5, max_overflow=10, echo=False)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    logging.info("Database initialized with pgvector extension")


async def get_session():
    async with SessionLocal() as session:
        yield session


async def check_connection() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def get_hot_path_count() -> int:
    try:
        async with SessionLocal() as s:
            result = await s.execute(text("SELECT COUNT(*) FROM nav_hot_paths"))
            return result.scalar() or 0
    except Exception:
        return 0
