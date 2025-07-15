"""Tests for the SQLAlchemy PostgreSQL sink implementation."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from reddit_scraper.config import PostgresConfig
from reddit_scraper.models.submission import SubmissionRecord
from reddit_scraper.storage.sqlalchemy_postgres_sink import SQLAlchemyPostgresSink, RawEventORM
from reddit_scraper.storage.database import Base


@pytest.fixture(scope="module")
def engine():
    """Create an in-memory SQLite engine for the test module."""
    return create_engine("sqlite:///:memory:")


@pytest.fixture(scope="module")
def tables(engine):
    """Create database tables for the test module."""
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def dbsession(engine, tables):
    """Create a new database session for a test, with transaction rollback."""
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def mock_get_db(monkeypatch, dbsession):
    """Mock the get_db context manager to return the test session."""

    @contextmanager
    def _mock_get_db():
        yield dbsession

    monkeypatch.setattr("reddit_scraper.storage.sqlalchemy_postgres_sink.get_db", _mock_get_db)


class TestSQLAlchemyPostgresSink:
    """Test cases for the SQLAlchemyPostgresSink class."""

    sample_records: list[SubmissionRecord] = [
        {
            "id": "abc123",
            "created_utc": 1609459200,
            "subreddit": "wallstreetbets",
            "title": "Test Title 1",
            "selftext": "Test Content 1",
            "author": "testuser1",
            "score": 42,
            "upvote_ratio": 0.75,
            "num_comments": 10,
            "url": "https://reddit.com/r/wallstreetbets/comments/abc123/test_title_1",
            "flair_text": "DD",
            "over_18": False,
        },
        {
            "id": "def456",
            "created_utc": 1609545600,
            "subreddit": "stocks",
            "title": "Test Title 2",
            "selftext": "Test Content 2",
            "author": "testuser2",
            "score": 100,
            "upvote_ratio": 0.9,
            "num_comments": 20,
            "url": "https://reddit.com/r/stocks/comments/def456/test_title_2",
            "flair_text": "Discussion",
            "over_18": False,
        },
    ]

    def test_append_records(self, mock_get_db, dbsession):
        """Test appending records to the database."""
        config = PostgresConfig(use_sqlalchemy=True)
        sink = SQLAlchemyPostgresSink(config)

        count = sink.append(self.sample_records)

        assert count == 2
        result = dbsession.query(RawEventORM).count()
        assert result == 2

    def test_load_ids(self, mock_get_db, dbsession):
        """Test loading submission IDs from the database."""
        config = PostgresConfig(use_sqlalchemy=True)
        sink = SQLAlchemyPostgresSink(config)

        sink.append(self.sample_records)
        ids = sink.load_ids()

        assert len(ids) == 2
        assert "abc123" in ids
        assert "def456" in ids
