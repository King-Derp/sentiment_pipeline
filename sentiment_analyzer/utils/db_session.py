from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from typing import AsyncGenerator, Optional
from functools import lru_cache
from contextlib import asynccontextmanager

from sentiment_analyzer.config.settings import settings

@lru_cache
def get_async_engine():
    """Returns a cached instance of the async engine."""
    return create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_recycle=3600,
    )

@lru_cache
def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Returns a cached instance of the async session factory."""
    return async_sessionmaker(
        bind=get_async_engine(),
        autoflush=False,
        expire_on_commit=False,
        class_=AsyncSession,
    )

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function that yields an SQLAlchemy async session.

    Ensures the session is closed after use.
    """
    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

@asynccontextmanager
async def get_db_session_context_manager(existing_session: Optional[AsyncSession] = None) -> AsyncGenerator[AsyncSession, None]:
    """
    Provides an SQLAlchemy async session within an asynchronous context manager.

    If an `existing_session` is provided, it yields that session and the caller
    is responsible for its lifecycle (commit, rollback, close).
    Otherwise, it creates a new session, and ensures it is committed on
    successful exit, rolled back on error, and closed regardless.
    """
    if existing_session:
        try:
            yield existing_session
        # No commit, rollback, or close for existing_session; managed by the caller.
        # Minimal finally block for safety during the yield itself.
        finally:
            pass 
        return

    # If no existing_session, create and manage a new one as before.
    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
