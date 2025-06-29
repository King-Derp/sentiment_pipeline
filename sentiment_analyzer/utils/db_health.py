"""Database health check utilities for startup scripts."""

from sentiment_analyzer.utils.db_session import get_async_engine


async def test_db_connection() -> bool:
    """
    Test database connection for startup health checks.
    
    Returns:
        bool: True if connection successful, False otherwise.
    """
    try:
        engine = get_async_engine()
        async with engine.begin() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception:
        return False
