from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from typing import AsyncGenerator

from sentiment_analyzer.config.settings import settings

# Create an asynchronous SQLAlchemy engine
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # Log SQL queries if DEBUG is True
    pool_pre_ping=True,
    pool_recycle=3600, # Optional: recycle connections periodically
)

# Create an asynchronous session factory
AsyncSessionFactory = async_sessionmaker(
    bind=async_engine,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function that yields an SQLAlchemy async session.

    Ensures the session is closed after use.
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit() # Commit remaining changes if any, though typically handled in crud
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def get_db_session_context_manager() -> AsyncSession:
    """
    Returns an SQLAlchemy async session for use with a context manager.
    """
    return AsyncSessionFactory()
