"""
Basic integration test for TimescaleDB Docker test environment.

This test verifies that the Docker test environment is properly set up and
that we can connect to the TimescaleDB instance.
"""
import os
import pytest
import sqlalchemy
from sqlalchemy import create_engine, text
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env.test file
env_file = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))) / '.env.test'
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
    print(f"Loaded environment variables from {env_file}")
else:
    print(f"Warning: .env.test file not found at {env_file}")


# Create a pytest fixture for the database connection
@pytest.fixture(scope="module")
def db_engine():
    """Create a SQLAlchemy engine for the Docker test database."""
    # Get the database URL from environment variables
    db_url = os.environ.get(
        "TEST_DATABASE_URL", 
        "postgresql://test_user:test_password@localhost:5434/sentiment_pipeline_test_db"
    )
    
    # Create the engine
    engine = create_engine(db_url)
    
    # Verify connection
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"Successfully connected to database: {db_url}")
    except Exception as e:
        pytest.skip(f"Could not connect to database: {e}")
    
    yield engine
    
    # Clean up
    engine.dispose()


@pytest.fixture(scope="function")
def db_connection(db_engine):
    """Create a SQLAlchemy connection for the Docker test database."""
    with db_engine.connect() as conn:
        # Start a transaction
        transaction = conn.begin()
        yield conn
        # Roll back the transaction after the test
        transaction.rollback()


class TestDockerIntegration:
    """Tests for verifying the Docker test environment setup."""
    
    def test_database_connection(self, db_connection):
        """
        Test that we can connect to the TimescaleDB Docker instance.
        
        Args:
            db_connection: SQLAlchemy connection to the Docker test database.
        """
        # Execute a simple query to verify connection
        result = db_connection.execute(text("SELECT 1 AS test_value")).scalar()
        assert result == 1, "Failed to connect to the Docker test database"
        
    def test_timescaledb_extension(self, db_connection):
        """
        Test that the TimescaleDB extension is installed.
        
        Args:
            db_connection: SQLAlchemy connection to the Docker test database.
        """
        # Check if TimescaleDB extension is installed
        result = db_connection.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'timescaledb'")
        ).scalar()
        assert result == 'timescaledb', "TimescaleDB extension is not installed"
        
    def test_environment_variables(self):
        """Test that the required environment variables are set."""
        assert os.environ.get('TEST_DATABASE_URL'), "TEST_DATABASE_URL environment variable is not set"
        
    def test_create_hypertable(self, db_connection):
        """
        Test that we can create a TimescaleDB hypertable.
        
        Args:
            db_connection: SQLAlchemy connection to the Docker test database.
        """
        # Create a test table
        db_connection.execute(text("""
            CREATE TABLE IF NOT EXISTS test_metrics (
                time TIMESTAMPTZ NOT NULL,
                device_id TEXT NOT NULL,
                value DOUBLE PRECISION NULL
            )
        """))
        
        # Convert it to a hypertable
        result = db_connection.execute(text("""
            SELECT create_hypertable('test_metrics', 'time', if_not_exists => TRUE)
        """)).scalar()
        
        # Verify that the hypertable was created
        assert result is not None, "Failed to create hypertable"
