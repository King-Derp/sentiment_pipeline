"""
Pytest fixtures for TimescaleDB tests.
"""
import os
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Add the project root to the Python path so that modules can be imported
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import models as needed
# from timescaledb.models import Base, RawEventORM


@pytest.fixture(scope="session")
def test_db_url():
    """
    Returns the database URL for testing.
    
    By default, uses the same URL as in the environment but with a test-specific database name.
    This can be overridden by setting the TEST_DATABASE_URL environment variable.
    """
    # Use a dedicated test database URL if provided
    if "TEST_DATABASE_URL" in os.environ:
        return os.environ["TEST_DATABASE_URL"]
    
    # Otherwise, derive from the main DATABASE_URL_LOCAL but with a test suffix
    base_url = os.environ.get("DATABASE_URL_LOCAL", 
                             "postgresql://test_user:test_password@localhost:5434/sentiment_pipeline_test_db")
    
    # Replace the database name with a test-specific one
    if "?" in base_url:
        connection_string, params = base_url.split("?", 1)
        base = connection_string.rsplit("/", 1)[0]
        return f"{base}/sentiment_pipeline_test_db?{params}"
    else:
        base = base_url.rsplit("/", 1)[0]
        return f"{base}/sentiment_pipeline_test_db"


@pytest.fixture(scope="session")
def db_engine(test_db_url):
    """
    Creates a SQLAlchemy engine connected to the test database.
    """
    engine = create_engine(test_db_url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def db_session_factory(db_engine):
    """
    Creates a factory for SQLAlchemy sessions.
    """
    return sessionmaker(bind=db_engine)


@pytest.fixture(scope="function")
def db_session(db_session_factory):
    """
    Creates a new SQLAlchemy session for a test.
    
    The session is rolled back after the test completes.
    """
    session = db_session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="session")
def initialize_test_db(db_engine):
    """
    Ensures the test database engine is available.
    Migrations are handled by the test execution script (run_docker_tests.ps1).
    """
    # The db_engine fixture already creates the engine.
    # Migrations are handled by the run_docker_tests.ps1 script.
    # This fixture now primarily serves as a dependency marker if needed
    # and ensures that db_engine is ready.
    yield db_engine
    
    # Cleanup can be added here if needed
    # For example, dropping the test database or specific tables
