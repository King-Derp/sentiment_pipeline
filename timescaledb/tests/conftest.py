"""
Pytest fixtures for TimescaleDB tests.
"""
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

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
                             "postgresql://test_user:test_password@localhost:5433/sentiment_pipeline_db")
    
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
    Initializes the test database with the required schema.
    
    This fixture should be used by test modules that require a database.
    It will run Alembic migrations to set up the schema.
    """
    # Import here to avoid circular imports
    import subprocess
    import sys
    
    # Run Alembic migrations on the test database
    # Note: This assumes alembic.ini is in the project root
    alembic_ini_path = os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini")
    
    # Create a custom alembic.ini for testing if needed
    # For now, we'll just override the URL via environment variable
    os.environ["ALEMBIC_DATABASE_URL"] = db_engine.url.render_as_string(hide_password=False)
    
    # Run the migration
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", alembic_ini_path, "upgrade", "head"],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"Alembic migration output: {result.stdout}")
    except subprocess.CalledProcessError as e:
        print(f"Error running Alembic migrations: {e.stderr}")
        raise
    
    yield
    
    # Cleanup can be added here if needed
    # For example, dropping the test database or specific tables
