import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.exc import SQLAlchemyError

from sentiment_analyzer.core.data_fetcher import fetch_and_claim_raw_events
from sentiment_analyzer.models.dtos import RawEventDTO

# Since data_fetcher uses a standalone function, we patch the session utility it uses.
@pytest.fixture
def mock_db_session():
    """Fixture to mock the database session context manager and session object."""
    with patch('sentiment_analyzer.core.data_fetcher.get_async_db_session') as mock_get_session:
        mock_session = AsyncMock()
        # The context manager returns the session
        mock_get_session.return_value = mock_session
        mock_session.__aenter__.return_value = mock_session
        yield mock_session

@pytest.mark.asyncio
async def test_fetch_and_claim_successful(mock_db_session):
    """Test successfully fetching and claiming a batch of raw events."""
    # Mock the return value of session.execute().scalars().all()
    mock_event_data = [
        (1, '{"text":"event 1"}', 'reddit', '2023-01-01T12:00:00'),
        (2, '{"text":"event 2"}', 'reddit', '2023-01-01T12:01:00')
    ]
    mock_result = MagicMock()
    mock_result.all.return_value = mock_event_data
    mock_db_session.scalars.return_value = mock_result

    batch_size = 5
    events = await fetch_and_claim_raw_events(batch_size=batch_size)

    assert mock_db_session.execute.called
    assert len(events) == 2
    assert all(isinstance(event, RawEventDTO) for event in events)
    assert events[0].id == 1
    assert events[1].id == 2
    assert events[0].source == 'reddit'

@pytest.mark.asyncio
async def test_fetch_and_claim_no_events_found(mock_db_session):
    """Test the case where no new events are available to be fetched."""
    # Mock the database call to return an empty list
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db_session.scalars.return_value = mock_result

    events = await fetch_and_claim_raw_events(batch_size=10)

    assert mock_db_session.execute.called
    assert len(events) == 0

@pytest.mark.asyncio
async def test_fetch_and_claim_db_error(mock_db_session):
    """Test handling of a SQLAlchemyError during the database operation."""
    # Configure the mock session to raise a database error
    mock_db_session.execute.side_effect = SQLAlchemyError("Database connection failed")

    # The function should catch the error, log it, and return an empty list
    events = await fetch_and_claim_raw_events(batch_size=10)

    assert mock_db_session.execute.called
    assert mock_db_session.rollback.called
    assert len(events) == 0

@pytest.mark.asyncio
async def test_fetch_and_claim_unexpected_error(mock_db_session):
    """Test handling of a non-SQLAlchemyError during the operation."""
    mock_db_session.execute.side_effect = Exception("An unexpected error occurred")

    events = await fetch_and_claim_raw_events(batch_size=10)

    assert mock_db_session.execute.called
    assert mock_db_session.rollback.called
    assert len(events) == 0
