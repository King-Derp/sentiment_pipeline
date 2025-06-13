import sys
import os
import pytest_asyncio

# Add project root to path to allow alembic to find the sentiment_analyzer package
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from dotenv import load_dotenv

# Load test environment variables from .env.test in the project root
dotenv_path = os.path.join(project_root, '.env.test')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)

import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command
import os

# This assumes that tests are run from the root of the 'sentiment_analyzer' directory
# or that the path is otherwise discoverable.
ALEMBIC_CONFIG_PATH = os.path.join(os.path.dirname(__file__), '../../alembic.ini')

# Use environment variables for test database connection, with defaults
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", 
    "postgresql+asyncpg://testuser:testpassword@localhost:5433/testdb"
)

# Ensure the asyncpg driver is used for async SQLAlchemy engine
if TEST_DATABASE_URL.startswith("postgresql://"):
    TEST_DATABASE_URL = TEST_DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif TEST_DATABASE_URL.startswith("postgresql+psycopg2://"):
    TEST_DATABASE_URL = TEST_DATABASE_URL.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)

# Patch global application settings to ensure the async test DB is used everywhere
from sentiment_analyzer.config.settings import settings as _app_settings
_app_settings.DATABASE_URL = TEST_DATABASE_URL  # type: ignore

# Clear cached engines/session factories to pick up new URL
from sentiment_analyzer.utils.db_session import get_async_engine, get_async_session_factory
get_async_engine.cache_clear()  # type: ignore[attr-defined]
get_async_session_factory.cache_clear()  # type: ignore[attr-defined]

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """Yield a SQLAlchemy engine for the test database, created once per session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    yield engine
    await engine.dispose()

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database(db_engine):
    """Create all tables from SQLAlchemy metadata before tests run, and drop them after."""
    # Import all necessary ORM models to ensure their metadata is collected
    from sentiment_analyzer.models.base import Base as AppBase
    from sentiment_analyzer.tests.stubs.raw_event_stub import Base as RawEventStubBase

    all_metadata = [AppBase.metadata, RawEventStubBase.metadata]

    async with db_engine.begin() as conn:
        for metadata in all_metadata:
            await conn.run_sync(metadata.drop_all)
            await conn.run_sync(metadata.create_all)
    
    yield
    
    async with db_engine.begin() as conn:
        for metadata in all_metadata:
            await conn.run_sync(metadata.drop_all)

@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    """Provide a transactional database session for each test function."""
    connection = await db_engine.connect()
    await connection.begin()

    async_session_factory = sessionmaker(
        bind=connection, class_=AsyncSession, expire_on_commit=False
    )
    session = async_session_factory()

    yield session

    await session.close()
    await connection.rollback() # Rollback any changes made during the test
    await connection.close()
