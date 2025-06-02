"""
Integration tests for SQLAlchemyPostgresSink with TimescaleDB.

These tests verify that the SQLAlchemyPostgresSink correctly writes Reddit data
to the raw_events table in TimescaleDB.
"""
import os
import pytest
import datetime
from datetime import timezone
from typing import Dict, Any, List
from sqlalchemy import select, text

# Import the necessary components
import sys
import os

# Adjust the import paths to handle the nested package structure
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# The actual package is in reddit_scraper/reddit_scraper
sys.path.insert(0, os.path.join(project_root, 'reddit_scraper'))

# Now we can import from the reddit_scraper package
from reddit_scraper.storage.sqlalchemy_postgres_sink import SQLAlchemyPostgresSink
from reddit_scraper.models.submission import RawEventORM # This model is used by the sink for its operations
from reddit_scraper.config import PostgresConfig
from reddit_scraper.storage import database as reddit_db_module


@pytest.fixture(autouse=True)
def ensure_raw_events_table(db_session, db_engine):
    """
    Ensure the raw_events table exists and is clean before each test.
    This fixture runs automatically before each test.
    """
    try:
        # First check if the table exists
        result = db_session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'raw_events'
            );
        """))
        table_exists = result.scalar()
        
        if not table_exists:
            # Create the table if it doesn't exist
            db_session.execute(text("""
                CREATE TABLE raw_events (
                    id BIGSERIAL NOT NULL,
                    source TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    occurred_at TIMESTAMPTZ NOT NULL,
                    payload JSONB NOT NULL,
                    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    processed BOOLEAN NOT NULL DEFAULT FALSE,
                    PRIMARY KEY (id, occurred_at),
                    UNIQUE (source, source_id, occurred_at)
                );
                
                CREATE INDEX ix_raw_events_occurred_at ON raw_events (occurred_at);
                CREATE INDEX ix_raw_events_source_source_id ON raw_events (source, source_id);
                
                -- Try to make it a hypertable if TimescaleDB extension is available
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
                        PERFORM create_hypertable('raw_events', 'occurred_at', if_not_exists => TRUE);
                    END IF;
                EXCEPTION WHEN OTHERS THEN
                    -- Ignore errors if TimescaleDB is not available
                    RAISE NOTICE 'TimescaleDB extension not available';
                END $$;
            """))
            db_session.commit()
            print("Created raw_events table for testing")
        
        # Clean the table
        db_session.execute(text("TRUNCATE TABLE raw_events RESTART IDENTITY CASCADE"))
        db_session.commit()
        print("Cleaned raw_events table for testing")
    except Exception as e:
        db_session.rollback()
        pytest.skip(f"Could not setup raw_events table: {str(e)}")
    yield


@pytest.fixture
def sample_submission_record() -> Dict[str, Any]:
    """
    Creates a sample SubmissionRecord for testing.
    
    Returns:
        Dict[str, Any]: A dictionary representing a Reddit submission.
    """
    now = datetime.datetime.now(timezone.utc).timestamp()
    return {
        "id": "t3_sample1",
        "title": "Test Submission",
        "selftext": "This is a test submission",
        "created_utc": now,  # Using timestamp as per implementation plan discussion
        "author": "test_user",
        "subreddit": "test",
        "score": 10,
        "num_comments": 5,
        "permalink": "/r/test/comments/sample1/test_submission/",
        "url": "https://www.reddit.com/r/test/comments/sample1/test_submission/",
    }


@pytest.fixture
def sample_submission_records() -> List[Dict[str, Any]]:
    """
    Creates multiple sample SubmissionRecords for testing.
    
    Returns:
        List[Dict[str, Any]]: A list of dictionaries representing Reddit submissions.
    """
    base_time = datetime.datetime.now(timezone.utc).timestamp()
    records = []
    
    for i in range(5):
        records.append({
            "id": f"t3_sample{i}",
            "title": f"Test Submission {i}",
            "selftext": f"This is test submission {i}",
            "created_utc": base_time - (i * 3600),  # Submissions 1 hour apart
            "author": f"test_user_{i}",
            "subreddit": "test",
            "score": 10 + i,
            "num_comments": 5 + i,
            "permalink": f"/r/test/comments/sample{i}/test_submission_{i}/",
            "url": f"https://www.reddit.com/r/test/comments/sample{i}/test_submission_{i}/",
        })
    
    return records


@pytest.fixture
def sqlalchemy_postgres_sink(db_engine, db_session_factory, db_session):
    """
    Creates a SQLAlchemyPostgresSink instance configured for testing.

    Args:
        db_engine: SQLAlchemy engine fixture from conftest.
        db_session_factory: SQLAlchemy session factory fixture from conftest.
        db_session: SQLAlchemy session fixture for the current test.

    Returns:
        SQLAlchemyPostgresSink: Configured sink instance.
    """
    # Test if the database is available
    try:
        db_session.execute(text("SELECT 1"))
    except Exception as e:
        pytest.skip(f"Database connection not available: {str(e)}")
    
    original_engine = reddit_db_module.engine
    original_session_local = reddit_db_module.SessionLocal

    # Temporarily override the global engine and SessionLocal in the reddit_scraper.storage.database module
    # with the test-specific ones from timescaledb/tests/conftest.py.
    # This ensures that SQLAlchemyPostgresSink uses the test database setup.
    reddit_db_module.engine = db_engine
    reddit_db_module.SessionLocal = db_session_factory

    try:
        # Get test database configuration from environment variables
        host = os.environ.get("TEST_PG_HOST", "localhost")
        port = int(os.environ.get("TEST_PG_PORT_HOST", 5434))
        user = os.environ.get("TEST_PG_USER", "test_user")
        password = os.environ.get("TEST_PG_PASSWORD", "test_password")
        database_name = os.environ.get("TEST_PG_DB", "sentiment_pipeline_test_db")

        config = PostgresConfig(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database_name,
            enabled=True  # Ensure the sink is enabled
        )
        
        # Create the sink with the test configuration
        sink = SQLAlchemyPostgresSink(config)
        
        # Override the session to use our test session
        sink._session = db_session
        
        yield sink

    finally:
        # Restore the original engine and SessionLocal
        reddit_db_module.engine = original_engine
        reddit_db_module.SessionLocal = original_session_local


class TestSQLAlchemyPostgresSinkIntegration:
    """Integration tests for SQLAlchemyPostgresSink with TimescaleDB."""
    
    def test_successful_single_record_write(self, sqlalchemy_postgres_sink, sample_submission_record, db_session):
        """
        Test that a single record is successfully written to the database.
        
        Args:
            sqlalchemy_postgres_sink: The sink instance.
            sample_submission_record: A sample Reddit submission.
            db_session: SQLAlchemy session.
        """
        # Write the record
        result = sqlalchemy_postgres_sink.append([sample_submission_record])
        
        # Verify the result
        assert result == 1, "Expected 1 record to be written"
        
        # Query the database to verify the record
        records = db_session.execute(
            select(RawEventORM).where(
                RawEventORM.source == "reddit",
                RawEventORM.source_id == sample_submission_record["id"]
            )
        ).scalars().all()
        
        # Verify we have exactly one record
        assert len(records) == 1, f"Expected 1 record, found {len(records)}"
        record = records[0]
        
        # Verify the record has the correct data
        assert record.source == "reddit"
        assert record.source_id == sample_submission_record["id"]
        assert record.payload["title"] == sample_submission_record["title"]
        assert record.payload["selftext"] == sample_submission_record["selftext"]
        assert record.payload["author"] == sample_submission_record["author"]
        assert record.processed is False
        assert record.ingested_at is not None
    
    def test_successful_batch_record_write(self, sqlalchemy_postgres_sink, sample_submission_records, db_session):
        """
        Test that multiple records are successfully written to the database.
        
        Args:
            sqlalchemy_postgres_sink: The sink instance.
            sample_submission_records: Multiple sample Reddit submissions.
            db_session: SQLAlchemy session.
        """
        # Write the records
        result = sqlalchemy_postgres_sink.append(sample_submission_records)
        
        # Verify the result
        assert result == len(sample_submission_records)
        
        # Query the database to verify the records
        for record in sample_submission_records:
            db_records = db_session.execute(
                select(RawEventORM).where(
                    RawEventORM.source == "reddit",
                    RawEventORM.source_id == record["id"]
                )
            ).scalars().all()
            
            # Verify we have exactly one record for each submission
            assert len(db_records) == 1, f"Expected 1 record for {record['id']}, found {len(db_records)}"
            db_record = db_records[0]
            
            # Verify the record data
            assert db_record.source == "reddit"
            assert db_record.source_id == record["id"]
            assert db_record.payload["title"] == record["title"]
            assert db_record.payload["selftext"] == record["selftext"]
            assert db_record.payload["author"] == record["author"]
            assert db_record.processed is False
            assert db_record.ingested_at is not None
    
    def test_idempotency(self, sqlalchemy_postgres_sink, sample_submission_record, db_session):
        """
        Test that writing the same record twice doesn't create duplicates.
        
        Args:
            sqlalchemy_postgres_sink: The sink instance.
            sample_submission_record: A sample Reddit submission.
            db_session: SQLAlchemy session.
        """
        # Write the record once
        result1 = sqlalchemy_postgres_sink.append([sample_submission_record])
        
        # Check record count after first insert
        records_after_first_insert = db_session.execute(
            select(RawEventORM).where(
                RawEventORM.source == "reddit",
                RawEventORM.source_id == sample_submission_record["id"]
            )
        ).scalars().all()
        
        # First write should insert 1 record
        assert result1 == 1
        assert len(records_after_first_insert) == 1
        
        # Write the same record again
        result2 = sqlalchemy_postgres_sink.append([sample_submission_record])
        
        # Query the database to verify only one record still exists
        records_after_second_insert = db_session.execute(
            select(RawEventORM).where(
                RawEventORM.source == "reddit",
                RawEventORM.source_id == sample_submission_record["id"]
            )
        ).scalars().all()
        
        # Verify only one record exists (no duplicates)
        assert len(records_after_second_insert) == 1
        
        # Note: The sink's append method returns the count of records in the batch,
        # not the count of records actually inserted. This is why result2 is 1
        # even though no new records were inserted due to the ON CONFLICT DO NOTHING clause.
    
    def test_not_null_constraints(self, sqlalchemy_postgres_sink, sample_submission_record, db_session):
        """
        Test that NOT NULL constraints are enforced.
        
        Args:
            sqlalchemy_postgres_sink: The sink instance.
            sample_submission_record: A sample Reddit submission.
            db_session: SQLAlchemy session.
        """
        # Test with missing id
        invalid_record = sample_submission_record.copy()
        invalid_record.pop("id")
        
        # The sink should skip invalid records and return 0 for records inserted
        result = sqlalchemy_postgres_sink.append([invalid_record])
        assert result == 0, "Expected 0 records to be inserted when 'id' is missing"
        
        # Test with missing created_utc
        invalid_record = sample_submission_record.copy()
        invalid_record.pop("created_utc")
        
        # The sink should skip invalid records and return 0 for records inserted
        result = sqlalchemy_postgres_sink.append([invalid_record])
        assert result == 0, "Expected 0 records to be inserted when 'created_utc' is missing"
    
    def test_timestamp_and_timezone_handling(self, sqlalchemy_postgres_sink, sample_submission_record, db_session):
        """
        Test that timestamps and timezones are handled correctly.
        
        Args:
            sqlalchemy_postgres_sink: The sink instance.
            sample_submission_record: A sample Reddit submission.
            db_session: SQLAlchemy session.
        """
        # Write the record
        sqlalchemy_postgres_sink.append([sample_submission_record])
        
        # Query the database to verify the record
        records = db_session.execute(
            select(RawEventORM).where(
                RawEventORM.source == "reddit",
                RawEventORM.source_id == sample_submission_record["id"]
            )
        ).scalars().all()
        
        # Verify we have exactly one record
        assert len(records) == 1, f"Expected 1 record, found {len(records)}"
        record = records[0]
        
        # Verify the timestamp was converted correctly
        assert isinstance(record.occurred_at, datetime.datetime)
        # Verify timezone awareness
        assert record.occurred_at.tzinfo is not None
        
        # Convert the original timestamp back to datetime for comparison
        original_dt = datetime.datetime.fromtimestamp(sample_submission_record["created_utc"], timezone.utc)
        
        # Compare timestamps (allowing for small differences due to float precision)
        time_diff = abs((record.occurred_at - original_dt).total_seconds())
        assert time_diff < 1.0  # Less than 1 second difference
    
    def test_load_ids_method(self, sqlalchemy_postgres_sink, sample_submission_records, db_session):
        """
        Test that the load_ids method returns the correct set of source_ids.
        
        Args:
            sqlalchemy_postgres_sink: The sink instance.
            sample_submission_records: Multiple sample Reddit submissions.
            db_session: SQLAlchemy session.
        """
        # Write the records first
        sqlalchemy_postgres_sink.append(sample_submission_records)
        
        # Get the source IDs using the load_ids method
        source_ids = sqlalchemy_postgres_sink.load_ids()
        
        # Verify all expected IDs are present
        expected_ids = {record["id"] for record in sample_submission_records}
        assert expected_ids.issubset(source_ids)
        
        # Verify the method returns the correct type
        assert isinstance(source_ids, set)
