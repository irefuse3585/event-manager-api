from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import async_sessionmaker  # new in SQLAlchemy 2.0
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings

# Create async engine for PostgreSQL (using asyncpg driver)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
)

# Create an async session factory
# async_sessionmaker is designed for AsyncSession + AsyncEngine
AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,  # objects won't be expired after commit
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an AsyncSession.
    Ensures that session is closed after request.

    Yields:
        AsyncSession: async session bound to the engine
    """
    async with AsyncSessionLocal() as session:
        yield session
