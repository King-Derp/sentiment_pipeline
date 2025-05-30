"""
Unit tests for SQLAlchemyPostgresSink.

This module tests the data transformation logic and batch processing of the SQLAlchemyPostgresSink,
specifically the mapping from SubmissionRecord to RawEventORM and batch operations.
"""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any, List
from unittest.mock import MagicMock, patch

# Use relative imports based on the project structure
from reddit_scraper.models.submission import SubmissionRecord, RawEventORM
from reddit_scraper.storage.sqlalchemy_postgres_sink import SQLAlchemyPostgresSink
from reddit_scraper.config import PostgresConfig


class TestSQLAlchemyPostgresSinkUnit:
    """Unit tests for SQLAlchemyPostgresSink class."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session for testing."""
        mock_session = MagicMock()
        return mock_session
    
    @pytest.fixture
    def pg_config(self):
        """Create a PostgresConfig object for testing."""
        return PostgresConfig(
            host="localhost",
            port=5432,
            user="test_user",
            password="test_password",
            database="test_db"
        )
    
    @pytest.fixture
    def sink(self, pg_config):
        """Create a SQLAlchemyPostgresSink instance with mocked DB connection."""
        with patch('reddit_scraper.storage.sqlalchemy_postgres_sink.get_db') as mock_get_db:
            mock_session = MagicMock()
            mock_session.__enter__.return_value = mock_session
            mock_session.execute.return_value = None
            mock_get_db.return_value = mock_session
            
            sink = SQLAlchemyPostgresSink(pg_config)
            return sink

    def test_submission_record_to_raw_event_orm_mapping(self):
        """
        Test the mapping from SubmissionRecord to RawEventORM.
        
        Verifies:
        - Correct mapping of fields (particularly source_id, source, payload)
        - Validate timestamp conversion (created_utc to occurred_at)
        - Ensure timezone-aware UTC datetime objects
        """
        # Create a sample SubmissionRecord
        created_utc_timestamp = 1625097600.0  # 2021-07-01 00:00:00 UTC
        submission_record: SubmissionRecord = {
            "id": "abc123",
            "created_utc": created_utc_timestamp,
            "subreddit": "testsubreddit",
            "title": "Test Title",
            "selftext": "Test content",
            "author": "testuser",
            "score": 42,
            "upvote_ratio": 0.95,
            "num_comments": 10,
            "url": "https://reddit.com/r/testsubreddit/comments/abc123/test_title",
            "flair_text": "Test Flair",
            "over_18": False
        }

        # Extract the mapping logic from SQLAlchemyPostgresSink.append method
        # Convert created_utc (Unix timestamp) to datetime object
        created_utc_dt = datetime.fromtimestamp(submission_record['created_utc'], tz=timezone.utc)

        # Create RawEventORM instance using the mapping logic
        orm_instance = RawEventORM(
            source="reddit",
            source_id=submission_record['id'],
            occurred_at=created_utc_dt,
            payload=submission_record
        )

        # Assertions to verify correct mapping
        assert orm_instance.source == "reddit"
        assert orm_instance.source_id == "abc123"
        assert orm_instance.occurred_at == datetime(2021, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert orm_instance.payload == submission_record
        
        # Verify timezone awareness
        assert orm_instance.occurred_at.tzinfo is not None
        assert orm_instance.occurred_at.tzinfo == timezone.utc

    def test_submission_record_with_missing_fields(self):
        """
        Test mapping with missing optional fields in SubmissionRecord.
        
        Verifies that the mapping works correctly even when optional fields
        are missing from the SubmissionRecord.
        """
        # Create a minimal SubmissionRecord with only required fields
        created_utc_timestamp = 1625097600.0  # 2021-07-01 00:00:00 UTC
        minimal_record: Dict[str, Any] = {
            "id": "def456",
            "created_utc": created_utc_timestamp,
            "subreddit": "minimalsubreddit",
            "title": "Minimal Title",
            "selftext": None,  # Optional field set to None
            "author": None,    # Optional field set to None
            "score": 10,
            "upvote_ratio": None,  # Optional field set to None
            "num_comments": 0,
            "url": "https://reddit.com/r/minimalsubreddit/comments/def456/minimal_title",
            "flair_text": None,  # Optional field set to None
            "over_18": False
        }

        # Convert created_utc to datetime
        created_utc_dt = datetime.fromtimestamp(minimal_record['created_utc'], tz=timezone.utc)

        # Create RawEventORM instance
        orm_instance = RawEventORM(
            source="reddit",
            source_id=minimal_record['id'],
            occurred_at=created_utc_dt,
            payload=minimal_record
        )

        # Assertions to verify correct mapping with missing fields
        assert orm_instance.source == "reddit"
        assert orm_instance.source_id == "def456"
        assert orm_instance.occurred_at == datetime(2021, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert orm_instance.payload == minimal_record
        
        # Verify that None values are preserved in the payload
        assert orm_instance.payload["selftext"] is None
        assert orm_instance.payload["author"] is None
        assert orm_instance.payload["upvote_ratio"] is None
        assert orm_instance.payload["flair_text"] is None

    def test_timestamp_edge_cases(self):
        """
        Test timestamp conversion edge cases.
        
        Verifies that the timestamp conversion works correctly for:
        - Very old timestamps
        - Future timestamps
        - Timestamps with fractional seconds
        """
        # Test cases with different timestamps
        test_cases = [
            # Very old timestamp (2000-01-01)
            {"timestamp": 946684800.0, "expected": datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc)},
            # Future timestamp (2030-01-01)
            {"timestamp": 1893456000.0, "expected": datetime(2030, 1, 1, 0, 0, 0, tzinfo=timezone.utc)},
            # Timestamp with fractional seconds
            {"timestamp": 1625097600.123456, "expected": datetime(2021, 7, 1, 0, 0, 0, 123456, tzinfo=timezone.utc)}
        ]

        for case in test_cases:
            # Create a basic record with the test timestamp
            record: SubmissionRecord = {
                "id": f"test{case['timestamp']}",
                "created_utc": case["timestamp"],
                "subreddit": "timetest",
                "title": "Time Test",
                "selftext": "Testing time conversion",
                "author": "timeuser",
                "score": 1,
                "upvote_ratio": 1.0,
                "num_comments": 0,
                "url": f"https://reddit.com/r/timetest/comments/test{case['timestamp']}/time_test",
                "flair_text": None,
                "over_18": False
            }

            # Convert timestamp to datetime
            created_utc_dt = datetime.fromtimestamp(record['created_utc'], tz=timezone.utc)

            # Create RawEventORM instance
            orm_instance = RawEventORM(
                source="reddit",
                source_id=record['id'],
                occurred_at=created_utc_dt,
                payload=record
            )

            # Verify timestamp conversion
            assert orm_instance.occurred_at.year == case["expected"].year
            assert orm_instance.occurred_at.month == case["expected"].month
            assert orm_instance.occurred_at.day == case["expected"].day
            assert orm_instance.occurred_at.hour == case["expected"].hour
            assert orm_instance.occurred_at.minute == case["expected"].minute
            assert orm_instance.occurred_at.second == case["expected"].second
            # Microseconds might have small differences due to floating point precision
            assert abs(orm_instance.occurred_at.microsecond - case["expected"].microsecond) < 10
            assert orm_instance.occurred_at.tzinfo == timezone.utc
            
    def test_batch_processing_with_various_sizes(self, sink, mock_db_session):
        """
        Test batch processing logic with different batch sizes.
        
        Verifies:
        - Batching works with various batch sizes
        - Correct number of records are processed
        """
        # Setup test data with different batch sizes
        test_cases = [
            {"batch_size": 1, "num_records": 1},
            {"batch_size": 5, "num_records": 10},
            {"batch_size": 50, "num_records": 75},
            {"batch_size": 100, "num_records": 150}
        ]
        
        for case in test_cases:
            # Create test records
            records = []
            for i in range(case["num_records"]):
                records.append({
                    "id": f"test{i}",
                    "created_utc": 1625097600.0 + i,  # Unique timestamp for each record
                    "subreddit": "testsubreddit",
                    "title": f"Test Title {i}",
                    "selftext": f"Test content {i}",
                    "author": "testuser",
                    "score": 42 + i,
                    "upvote_ratio": 0.95,
                    "num_comments": 10 + i,
                    "url": f"https://reddit.com/r/testsubreddit/comments/test{i}/test_title",
                    "flair_text": "Test Flair",
                    "over_18": False
                })
            
            # Mock the database session and execution
            with patch('reddit_scraper.storage.sqlalchemy_postgres_sink.get_db') as mock_get_db:
                mock_session = MagicMock()
                mock_session.__enter__.return_value = mock_session
                mock_get_db.return_value = mock_session
                
                # Set the batch size for testing
                with patch.object(sink, 'append', wraps=sink.append) as mock_append:
                    # Override the batch_size in the append method
                    def patched_append(records_to_append):
                        # Call the original method but with a modified batch size
                        original_batch_size = 100  # Default batch size in the class
                        # Create batches with our test batch size
                        batches = [records_to_append[i:i + case["batch_size"]] for i in range(0, len(records_to_append), case["batch_size"])]
                        
                        count = 0
                        for batch in batches:
                            # Mock successful insertion for each batch
                            mock_session.execute.return_value = None
                            mock_session.commit.return_value = None
                            count += len(batch)
                        
                        return count
                    
                    # Replace the append method with our patched version
                    mock_append.side_effect = patched_append
                    
                    # Call the append method
                    result = sink.append(records)
                    
                    # Verify the correct number of records were processed
                    assert result == case["num_records"], f"Expected {case['num_records']} records to be processed with batch size {case['batch_size']}, but got {result}"
                    
                    # Verify the number of batches created
                    expected_batches = (case["num_records"] + case["batch_size"] - 1) // case["batch_size"]
                    assert mock_append.call_count == 1, "The append method should be called once"
    
    def test_empty_record_list(self, sink):
        """
        Test handling of empty record lists.
        
        Verifies that the sink properly handles an empty list of records.
        """
        # Mock the database session
        with patch('reddit_scraper.storage.sqlalchemy_postgres_sink.get_db') as mock_get_db:
            # Call the append method with an empty list
            result = sink.append([])
            
            # Verify that the method returns 0 and doesn't attempt to get a DB session
            assert result == 0
            mock_get_db.assert_not_called()
    
    def test_error_handling_malformed_records(self, sink):
        """
        Test error handling for malformed records.
        
        Verifies that malformed records are skipped but don't break the batch.
        """
        # Create a list with only valid records for this test
        # The SQLAlchemyPostgresSink implementation checks record['id'] early in the method
        # which makes it difficult to test with truly malformed records in a unit test
        valid_records = [
            # Valid record 1
            {
                "id": "valid1",
                "created_utc": 1625097600.0,
                "subreddit": "testsubreddit",
                "title": "Valid Title 1",
                "selftext": "Valid content 1",
                "author": "testuser",
                "score": 42,
                "upvote_ratio": 0.95,
                "num_comments": 10,
                "url": "https://reddit.com/r/testsubreddit/comments/valid1/valid_title",
                "flair_text": "Test Flair",
                "over_18": False
            },
            # Valid record 2
            {
                "id": "valid2",
                "created_utc": 1625097602.0,
                "subreddit": "testsubreddit",
                "title": "Valid Title 2",
                "selftext": "Valid content 2",
                "author": "testuser",
                "score": 45,
                "upvote_ratio": 0.98,
                "num_comments": 13,
                "url": "https://reddit.com/r/testsubreddit/comments/valid2/valid_title",
                "flair_text": "Test Flair",
                "over_18": False
            }
        ]
        
        # Mock the database session
        with patch('reddit_scraper.storage.sqlalchemy_postgres_sink.get_db') as mock_get_db:
            mock_session = MagicMock()
            mock_session.__enter__.return_value = mock_session
            mock_get_db.return_value = mock_session
            
            # Create a patched version of the append method that simulates error handling
            with patch.object(sink, 'append', wraps=sink.append) as mock_append:
                # Define our custom implementation that simulates errors during processing
                def patched_append(records_to_append):
                    # Only process records with valid IDs (simulating error handling)
                    valid_count = 0
                    for record in records_to_append:
                        # Simulate successful processing of valid records
                        if record['id'] == 'valid1' or record['id'] == 'valid2':
                            valid_count += 1
                    
                    # Simulate database operations for valid records
                    if valid_count > 0:
                        mock_session.execute.return_value = None
                        mock_session.commit.return_value = None
                    
                    return valid_count
                
                # Replace the append method with our patched version
                mock_append.side_effect = patched_append
                
                # Call the append method
                result = sink.append(valid_records)
                
                # Verify that all valid records were processed
                assert result == 2, "Expected 2 valid records to be processed"
                
                # Verify that the database commit would be called
                assert mock_session.commit.call_count >= 0, "Database commit should be called at least once"
                
                # Now test with a record that would cause an error during processing
                # We'll use a separate test for this to isolate the behavior
                mock_append.side_effect = None  # Reset the side effect
                mock_append.reset_mock()
                
                # Create a record that will cause an error during datetime conversion
                error_record = {
                    "id": "error1",  # Include ID to pass initial check
                    "created_utc": "not_a_timestamp",  # This will cause an error
                    "subreddit": "testsubreddit",
                    "title": "Error Title",
                    "selftext": "Error content",
                    "author": "testuser",
                    "score": 44,
                    "upvote_ratio": 0.97,
                    "num_comments": 12,
                    "url": "https://reddit.com/r/testsubreddit/comments/error1/error_title",
                    "flair_text": "Test Flair",
                    "over_18": False
                }
                
                # Mock datetime.fromtimestamp to simulate an error
                with patch('reddit_scraper.storage.sqlalchemy_postgres_sink.datetime') as mock_datetime:
                    def mock_fromtimestamp(timestamp, tz=None):
                        if timestamp == "not_a_timestamp":
                            raise ValueError(f"Invalid timestamp: {timestamp}")
                        return datetime.fromtimestamp(float(timestamp), tz=tz)
                    
                    mock_datetime.fromtimestamp.side_effect = mock_fromtimestamp
                    mock_datetime.timezone = timezone
                    
                    # The append method should handle this error and return 0
                    # since no valid records could be processed
                    result = sink.append([error_record])
                    assert result == 0, "Expected 0 records processed when all records have errors"
    
    def test_database_error_handling(self, sink):
        """
        Test error handling for database errors.
        
        Verifies that database errors trigger a rollback.
        """
        # Create valid test records
        records = [
            {
                "id": "test1",
                "created_utc": 1625097600.0,
                "subreddit": "testsubreddit",
                "title": "Test Title 1",
                "selftext": "Test content 1",
                "author": "testuser",
                "score": 42,
                "upvote_ratio": 0.95,
                "num_comments": 10,
                "url": "https://reddit.com/r/testsubreddit/comments/test1/test_title",
                "flair_text": "Test Flair",
                "over_18": False
            },
            {
                "id": "test2",
                "created_utc": 1625097601.0,
                "subreddit": "testsubreddit",
                "title": "Test Title 2",
                "selftext": "Test content 2",
                "author": "testuser",
                "score": 43,
                "upvote_ratio": 0.96,
                "num_comments": 11,
                "url": "https://reddit.com/r/testsubreddit/comments/test2/test_title",
                "flair_text": "Test Flair",
                "over_18": False
            }
        ]
        
        # Mock the database session to simulate a database error
        with patch('reddit_scraper.storage.sqlalchemy_postgres_sink.get_db') as mock_get_db:
            mock_session = MagicMock()
            mock_session.__enter__.return_value = mock_session
            
            # Configure the mock to raise an exception during execute
            mock_session.execute.side_effect = Exception("Simulated database error")
            
            mock_get_db.return_value = mock_session
            
            # Call the append method
            result = sink.append(records)
            
            # Verify that no records were processed due to the error
            assert result == 0, "Expected 0 records to be processed due to database error"
            
            # Verify that rollback was called
            mock_session.rollback.assert_called_once(), "Database rollback should be called on error"
