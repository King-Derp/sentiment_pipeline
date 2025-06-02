"""
Minimal integration test for SQLAlchemyPostgresSink with TimescaleDB.

This test focuses on the core functionality with additional diagnostic output.
"""
import os
import sys
import pytest
import datetime
from datetime import timezone
from typing import Dict, Any, List
from sqlalchemy import select, text, create_engine
from sqlalchemy.orm import sessionmaker, Session

# Adjust the import paths to handle the nested package structure
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# The actual package is in reddit_scraper/reddit_scraper
sys.path.insert(0, os.path.join(project_root, 'reddit_scraper'))

# Now we can import from the reddit_scraper package
from reddit_scraper.storage.sqlalchemy_postgres_sink import SQLAlchemyPostgresSink
from reddit_scraper.models.submission import RawEventORM
from reddit_scraper.config import PostgresConfig
from reddit_scraper.storage import database as reddit_db_module


def test_database_connection(db_engine, db_session):
    """
    Basic test to verify database connection and schema.
    
    Args:
        db_engine: SQLAlchemy engine fixture from conftest.
        db_session: SQLAlchemy session fixture for the current test.
    """
    print("\n=== Testing Database Connection ===")
    
    try:
        # Test basic connection
        result = db_session.execute(text("SELECT 1")).scalar()
        print(f"Basic connection test: {result}")
        assert result == 1
        
        # Check if raw_events table exists
        result = db_session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'raw_events'
            );
        """)).scalar()
        print(f"raw_events table exists: {result}")
        
        if not result:
            print("Creating raw_events table for testing")
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
            """))
            db_session.commit()
            print("raw_events table created successfully")
        
        # Clean the table
        db_session.execute(text("TRUNCATE TABLE raw_events RESTART IDENTITY CASCADE"))
        db_session.commit()
        print("Cleaned raw_events table")
        
        # Test the table structure
        columns = db_session.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'raw_events'
            ORDER BY ordinal_position;
        """)).all()
        
        print("Table structure:")
        for col in columns:
            print(f"  {col[0]}: {col[1]}")
        
        assert len(columns) >= 7, f"Expected at least 7 columns, found {len(columns)}"
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        pytest.fail(f"Database connection test failed: {str(e)}")


def test_simple_write_read(db_engine, db_session):
    """
    Test simple write and read operations with the database.
    
    Args:
        db_engine: SQLAlchemy engine fixture from conftest.
        db_session: SQLAlchemy session fixture for the current test.
    """
    print("\n=== Testing Simple Write/Read ===")
    
    try:
        # Create a sample record
        now = datetime.datetime.now(timezone.utc)
        
        # Create a direct record using the ORM
        test_record = RawEventORM(
            source="test",
            source_id="test123",
            occurred_at=now,
            payload={"title": "Test Record", "content": "This is a test"},
            processed=False
        )
        
        # Add and commit
        db_session.add(test_record)
        db_session.commit()
        print(f"Added test record with id: {test_record.id}")
        
        # Read it back
        record = db_session.execute(
            select(RawEventORM).where(
                RawEventORM.source == "test",
                RawEventORM.source_id == "test123"
            )
        ).scalars().first()
        
        print(f"Retrieved record: {record.id}, {record.source}, {record.source_id}")
        print(f"Payload: {record.payload}")
        
        assert record is not None
        assert record.source == "test"
        assert record.source_id == "test123"
        assert record.payload["title"] == "Test Record"
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        pytest.fail(f"Simple write/read test failed: {str(e)}")


def test_sink_basic_functionality():
    """
    Test the basic functionality of SQLAlchemyPostgresSink.
    """
    print("\n=== Testing SQLAlchemyPostgresSink Basic Functionality ===")
    
    try:
        # Get database configuration from environment variables
        host = os.environ.get("TEST_PG_HOST", "localhost")
        port = int(os.environ.get("TEST_PG_PORT_HOST", 5434))
        user = os.environ.get("TEST_PG_USER", "test_user")
        password = os.environ.get("TEST_PG_PASSWORD", "test_password")
        database_name = os.environ.get("TEST_PG_DB", "sentiment_pipeline_test_db")
        
        print(f"Database config: {host}:{port}/{database_name} (user: {user})")
        
        # Create a direct connection to the database
        db_url = f"postgresql://{user}:{password}@{host}:{port}/{database_name}"
        engine = create_engine(db_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        # Initialize the database module with our session factory
        # This is needed because SQLAlchemyPostgresSink uses the global SessionLocal
        reddit_db_module.SessionLocal = SessionLocal
        
        session = SessionLocal()
        
        # Clean the table
        session.execute(text("TRUNCATE TABLE raw_events RESTART IDENTITY CASCADE"))
        session.commit()
        
        # Create the sink configuration
        config = PostgresConfig(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database_name,
            enabled=True
        )
        
        # Create the sink
        sink = SQLAlchemyPostgresSink(config)
        
        # Create a sample submission record
        now = datetime.datetime.now(timezone.utc).timestamp()
        sample_record = {
            "id": "t3_test123",
            "title": "Test Submission",
            "selftext": "This is a test submission",
            "created_utc": now,
            "author": "test_user",
            "subreddit": "test",
            "score": 10,
            "num_comments": 5,
            "permalink": "/r/test/comments/test123/test_submission/",
            "url": "https://www.reddit.com/r/test/comments/test123/test_submission/",
        }
        
        # Write the record
        result = sink.append([sample_record])
        print(f"Sink append result: {result}")
        
        # Read it back
        records = session.execute(
            select(RawEventORM).where(
                RawEventORM.source == "reddit",
                RawEventORM.source_id == sample_record["id"]
            )
        ).scalars().all()
        
        print(f"Found {len(records)} records")
        for record in records:
            print(f"Record: {record.id}, {record.source}, {record.source_id}")
            print(f"Payload: {record.payload}")
        
        assert len(records) == 1
        assert records[0].source == "reddit"
        assert records[0].source_id == sample_record["id"]
        assert records[0].payload["title"] == sample_record["title"]
        
        # Test idempotency by checking record count before and after second insert
        record_count_before = session.execute(
            text("SELECT COUNT(*) FROM raw_events WHERE source = 'reddit' AND source_id = :source_id")
            .bindparams(source_id=sample_record['id'])
        ).scalar()
        print(f"Record count before second insert: {record_count_before}")
        
        # Perform second insert
        result2 = sink.append([sample_record])
        print(f"Second append result: {result2}")
        
        # Check if record count changed
        record_count_after = session.execute(
            text("SELECT COUNT(*) FROM raw_events WHERE source = 'reddit' AND source_id = :source_id")
            .bindparams(source_id=sample_record['id'])
        ).scalar()
        print(f"Record count after second insert: {record_count_after}")
        
        # Verify idempotency by ensuring no new records were added
        assert record_count_before == record_count_after, "Idempotency check failed: record count changed after second insert"
        
        # Close the session
        session.close()
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        pytest.fail(f"SQLAlchemyPostgresSink test failed: {str(e)}")
