"""
Tests for the raw_events table in TimescaleDB.

These tests verify that the raw_events table correctly enforces constraints,
data types, and relationships in TimescaleDB.
"""
import os
import pytest
import datetime
import json
from sqlalchemy import text # create_engine will come from conftest

pytestmark = pytest.mark.usefixtures("initialize_test_db")


@pytest.fixture(autouse=True)
def clean_raw_events_table(db_session):
    """Cleans the raw_events table before each test in this module/class."""
    db_session.execute(text("DELETE FROM raw_events"))
    db_session.commit() # Ensure cleanup is committed before test runs


class TestRawEventORM:
    """Tests for the RawEventORM model."""
    
    def test_create_raw_event(self, db_session):
        """Test creating a single record in the raw_events table."""
        # Create a test event
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # Insert directly using SQL for more reliable testing
        db_session.execute(
            text("""
            INSERT INTO raw_events (source, source_id, occurred_at, payload, processed)
            VALUES (:source, :source_id, :occurred_at, :payload, :processed)
            """),
            {
                "source": "test",
                "source_id": "test_id_1",
                "occurred_at": now,
                "payload": json.dumps({"test": "data"}),
                "processed": False
            }
        )
        
        # Query to verify
        result = db_session.execute(
            text("SELECT * FROM raw_events WHERE source_id = :source_id"),
            {"source_id": "test_id_1"}
        ).fetchone()
        
        assert result is not None
        assert result.source == "test"
        assert result.source_id == "test_id_1"
        # Compare timestamps with a small tolerance due to potential precision differences
        time_diff = abs((result.occurred_at - now).total_seconds())
        assert time_diff < 1.0
        assert result.processed is False
    
    def test_composite_primary_key(self, db_session):
        """Test that the composite primary key (id, occurred_at) works correctly."""
        # Create test events with different timestamps
        now = datetime.datetime.now(datetime.timezone.utc)
        later = now + datetime.timedelta(hours=1)
        
        # Insert first record
        db_session.execute(
            text("""
            INSERT INTO raw_events (source, source_id, occurred_at, payload, processed)
            VALUES (:source, :source_id, :occurred_at, :payload, :processed)
            """),
            {
                "source": "test",
                "source_id": "test_id_2",
                "occurred_at": now,
                "payload": json.dumps({"test": "data1"}),
                "processed": False
            }
        )
        
        # Insert second record with same source_id but different occurred_at
        db_session.execute(
            text("""
            INSERT INTO raw_events (source, source_id, occurred_at, payload, processed)
            VALUES (:source, :source_id, :occurred_at, :payload, :processed)
            """),
            {
                "source": "test",
                "source_id": "test_id_2",
                "occurred_at": later,
                "payload": json.dumps({"test": "data2"}),
                "processed": False
            }
        )
        
        # Query to verify both records exist
        results = db_session.execute(
            text("SELECT * FROM raw_events WHERE source_id = :source_id ORDER BY occurred_at"),
            {"source_id": "test_id_2"}
        ).fetchall()
        
        assert len(results) == 2
        
        # Verify the IDs are different (auto-incremented)
        assert results[0].id != results[1].id
    
    def test_unique_constraint(self, db_session):
        """Test the unique constraint on (source, source_id, occurred_at)."""
        # Create a test event
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # Insert first record
        db_session.execute(
            text("""
            INSERT INTO raw_events (source, source_id, occurred_at, payload, processed)
            VALUES (:source, :source_id, :occurred_at, :payload, :processed)
            """),
            {
                "source": "test",
                "source_id": "test_id_3",
                "occurred_at": now,
                "payload": json.dumps({"test": "data1"}),
                "processed": False
            }
        )
        
        # Try to insert a duplicate record with the same source, source_id, and occurred_at
        # This should fail due to the unique constraint
        with pytest.raises(Exception) as excinfo:
            db_session.execute(
                text("""
                INSERT INTO raw_events (source, source_id, occurred_at, payload, processed)
                VALUES (:source, :source_id, :occurred_at, :payload, :processed)
                """),
                {
                    "source": "test",
                    "source_id": "test_id_3",
                    "occurred_at": now,  # Same timestamp
                    "payload": json.dumps({"test": "data2"}),
                    "processed": False
                }
            )
        
        # Verify that the error is related to a unique constraint violation
        error_msg = str(excinfo.value).lower()
        assert "unique" in error_msg or "duplicate" in error_msg or "violates" in error_msg
    
    def test_not_null_constraints(self, db_session):
        """Test that NOT NULL constraints are enforced."""
        # Test each NOT NULL constraint
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # Test missing source
        with pytest.raises(Exception) as excinfo:
            db_session.execute(
                text("""
                INSERT INTO raw_events (source_id, occurred_at, payload, processed)
                VALUES (:source_id, :occurred_at, :payload, :processed)
                """),
                {
                    "source_id": "test_id_4",
                    "occurred_at": now,
                    "payload": json.dumps({"test": "data"}),
                    "processed": False
                }
            )
            error_msg = str(excinfo.value).lower()
            assert "null" in error_msg or "not-null" in error_msg or "violates" in error_msg
        
        # Test missing source_id
        with pytest.raises(Exception) as excinfo:
            db_session.execute(
                text("""
                INSERT INTO raw_events (source, occurred_at, payload, processed)
                VALUES (:source, :occurred_at, :payload, :processed)
                """),
                {
                    "source": "test",
                    "occurred_at": now,
                    "payload": json.dumps({"test": "data"}),
                    "processed": False
                }
            )
            error_msg = str(excinfo.value).lower()
            assert "null" in error_msg or "not-null" in error_msg or "violates" in error_msg
        
        # Test missing occurred_at
        with pytest.raises(Exception) as excinfo:
            db_session.execute(
                text("""
                INSERT INTO raw_events (source, source_id, payload, processed)
                VALUES (:source, :source_id, :payload, :processed)
                """),
                {
                    "source": "test",
                    "source_id": "test_id_4",
                    "payload": json.dumps({"test": "data"}),
                    "processed": False
                }
            )
            error_msg = str(excinfo.value).lower()
            assert "null" in error_msg or "not-null" in error_msg or "violates" in error_msg
        
        # Test missing payload
        with pytest.raises(Exception) as excinfo:
            db_session.execute(
                text("""
                INSERT INTO raw_events (source, source_id, occurred_at, processed)
                VALUES (:source, :source_id, :occurred_at, :processed)
                """),
                {
                    "source": "test",
                    "source_id": "test_id_4_payload",
                    "occurred_at": now,
                    "processed": False
                }
            )
            error_msg = str(excinfo.value).lower()
            assert "null" in error_msg or "not-null" in error_msg or "violates" in error_msg
    
    def test_timestamp_handling(self, db_session):
        """Test that timestamps are handled correctly."""
        now_ts = datetime.datetime.now(datetime.timezone.utc)
        
        db_session.execute(
            text("""
            INSERT INTO raw_events (source, source_id, occurred_at, payload, processed)
            VALUES (:source, :source_id, :occurred_at, :payload, :processed)
            """),
            {
                "source": "test",
                "source_id": "test_id_5",
                "occurred_at": now_ts,
                "payload": json.dumps({"test": "data"}),
                "processed": False
            }
        )
        
        result = db_session.execute(
            text("SELECT occurred_at FROM raw_events WHERE source_id = :source_id"),
            {"source_id": "test_id_5"}
        ).fetchone()
        
        assert result is not None
        time_diff = abs((result.occurred_at - now_ts).total_seconds())
        assert time_diff < 1.0

    def test_json_payload(self, db_session):
        """Test that JSON payloads are handled correctly."""
        now_jp = datetime.datetime.now(datetime.timezone.utc)
        payload_data = {"key": "value", "number": 123, "nested": {"a": "b"}}
        
        db_session.execute(
            text("""
            INSERT INTO raw_events (source, source_id, occurred_at, payload, processed)
            VALUES (:source, :source_id, :occurred_at, :payload, :processed)
            """),
            {
                "source": "test",
                "source_id": "test_id_6",
                "occurred_at": now_jp,
                "payload": json.dumps(payload_data),
                "processed": False
            }
        )
        
        result = db_session.execute(
            text("SELECT payload FROM raw_events WHERE source_id = :source_id"),
            {"source_id": "test_id_6"}
        ).fetchone()
        
        assert result is not None
        retrieved_payload = result.payload
        if isinstance(retrieved_payload, str):
             retrieved_payload = json.loads(retrieved_payload)
        assert retrieved_payload == payload_data

    def test_default_values(self, db_session):
        """Test that default values are applied correctly."""
        now_dv = datetime.datetime.now(datetime.timezone.utc)
        
        db_session.execute(
            text("""
            INSERT INTO raw_events (source, source_id, occurred_at, payload)
            VALUES (:source, :source_id, :occurred_at, :payload) 
            """),
            {
                "source": "test",
                "source_id": "test_id_7",
                "occurred_at": now_dv,
                "payload": json.dumps({"test": "default_test"})
            }
        )
        
        result = db_session.execute(
            text("SELECT processed FROM raw_events WHERE source_id = :source_id"),
            {"source_id": "test_id_7"}
        ).fetchone()
        
        assert result is not None
        assert result.processed is False
                
# Additional test classes can be added for other TimescaleDB components
