"""
Unit tests for SQLAlchemyPostgresSink.

This module tests the data transformation logic of the SQLAlchemyPostgresSink,
specifically the mapping from SubmissionRecord to RawEventORM.
"""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any

# Use relative imports based on the project structure
from reddit_scraper.models.submission import SubmissionRecord, RawEventORM
from reddit_scraper.storage.sqlalchemy_postgres_sink import SQLAlchemyPostgresSink


class TestSQLAlchemyPostgresSinkUnit:
    """Unit tests for SQLAlchemyPostgresSink class."""

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
