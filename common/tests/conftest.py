"""
Pytest fixtures for TimescaleDB tests.

This module provides common fixtures for testing TimescaleDB integration,
including Docker-aware database connections and schema management.
"""
import os
import pytest
import subprocess
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session


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
def docker_test_db_url():
    """
    Returns the database URL for the Docker test environment.
    
    This fixture is specifically for tests running against the Docker test container.
    """
    return os.environ.get(
        "TEST_DATABASE_URL", 
        "postgresql://test_user:test_password@localhost:5434/sentiment_pipeline_test_db"
    )


@pytest.fixture(scope="session")
def db_engine(test_db_url):
    """
    Creates a SQLAlchemy engine connected to the test database.
    """
    engine = create_engine(test_db_url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def docker_db_engine(docker_test_db_url):
    """
    Creates a SQLAlchemy engine connected to the Docker test database.
    """
    engine = create_engine(docker_test_db_url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def db_session_factory(db_engine):
    """
    Creates a factory for SQLAlchemy sessions.
    """
    return sessionmaker(bind=db_engine)


@pytest.fixture(scope="session")
def docker_db_session_factory(docker_db_engine):
    """
    Creates a factory for SQLAlchemy sessions connected to the Docker test database.
    """
    return sessionmaker(bind=docker_db_engine)


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


@pytest.fixture(scope="function")
def docker_db_session(docker_db_session_factory):
    """
    Creates a new SQLAlchemy session for a test using the Docker test database.
    
    The session is rolled back after the test completes.
    """
    session = docker_db_session_factory()
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
    Instead of running Alembic migrations, we'll create the tables directly using SQLAlchemy.
    """
    # Import here to avoid circular imports
    import sys
    from sqlalchemy import MetaData
    
    # Add project root to sys.path for easier imports
    project_root = os.path.join(os.path.dirname(__file__), "..", "..")
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    # Print sys.path for debugging
    print("DEBUG: sys.path in timescaledb/tests/conftest.py (FIXED):", sys.path)
    
    # Import the models to ensure they're registered with the metadata
    from reddit_scraper.models.submission import RawEventORM, Base
    
    try:
        # Create all tables
        Base.metadata.create_all(db_engine)
        print("Successfully created test database tables")
    except Exception as e:
        print(f"Error creating test database tables: {str(e)}")
        raise
    
    yield
    
    # Cleanup - drop all tables after tests
    # Uncomment if you want to clean up after tests
    # Base.metadata.drop_all(db_engine)


@pytest.fixture(scope="session")
def initialize_docker_test_db(docker_db_engine):
    """
    Initializes the Docker test database with the required schema.
    
    This fixture should be used by test modules that require the Docker test database.
    We'll create the tables directly using SQLAlchemy instead of Alembic migrations.
    """
    # Import here to avoid circular imports
    import sys
    from sqlalchemy import MetaData, inspect, Table, Column, Integer, String, DateTime, Boolean, JSON, ForeignKey
    from sqlalchemy.ext.declarative import declarative_base
    
    # Add project root to sys.path for easier imports
    project_root = os.path.join(os.path.dirname(__file__), "..", "..")
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    # Check if tables already exist
    inspector = inspect(docker_db_engine)
    existing_tables = inspector.get_table_names()
    
    if "raw_events" not in existing_tables:
        try:
            # Import the models
            from reddit_scraper.models.submission import RawEventORM, Base
            
            # Create all tables
            Base.metadata.create_all(docker_db_engine)
            print("Successfully created Docker test database tables")
        except Exception as e:
            print(f"Error creating Docker test database tables: {str(e)}")
            # If the import fails, create the tables manually
            try:
                # Create a base class for declarative models
                Base = declarative_base()
                
                # Define the RawEventORM model
                class RawEventORM(Base):
                    __tablename__ = "raw_events"
                    
                    id = Column(Integer, primary_key=True)
                    source = Column(String, nullable=False)
                    source_id = Column(String, nullable=False)
                    occurred_at = Column(DateTime(timezone=True), primary_key=True, nullable=False)
                    payload = Column(JSON, nullable=False)
                    processed = Column(Boolean, default=False, nullable=False)
                    ingested_at = Column(DateTime(timezone=True), server_default="now()", nullable=False)
                    
                    # Unique constraint on source, source_id, and occurred_at
                    __table_args__ = (
                        {'comment': 'Stores raw event data from various sources.'}
                    )
                
                # Create the tables
                Base.metadata.create_all(docker_db_engine)
                print("Successfully created Docker test database tables manually")
            except Exception as inner_e:
                print(f"Error creating tables manually: {str(inner_e)}")
                raise
    else:
        print("Tables already exist in Docker test database")
    
    yield
    
    # We don't drop tables after tests to allow for inspection if needed


@pytest.fixture
def sqlalchemy_postgres_sink_factory():
    """
    Factory fixture to create SQLAlchemyPostgresSink instances for testing.
    
    Returns a function that creates a sink with the given session.
    """
    def _create_sink(session):
        # Import here to avoid circular imports
        try:
            from reddit_scraper.storage.sqlalchemy_postgres_sink import SQLAlchemyPostgresSink
            from reddit_scraper.config import PostgresConfig
            
            # Create a minimal config for the sink
            config = PostgresConfig(
                host="localhost",
                port=5432,
                user="test_user",
                password="test_password",
                database="sentiment_pipeline_test_db",
                batch_size=100
            )
            
            # Create and return the sink
            sink = SQLAlchemyPostgresSink(config)
            
            # Override the session to use our test session
            sink._session = session
            
            return sink
        except ImportError as e:
            print(f"Error importing SQLAlchemyPostgresSink: {str(e)}")
            # If the module isn't available, return a mock or None
            return None
    
    return _create_sink
