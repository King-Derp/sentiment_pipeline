import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from pytest_mock import MockerFixture
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timezone, timedelta

from sentiment_analyzer.core.result_processor import ResultProcessor
from sentiment_analyzer.models.dtos import (
    RawEventDTO,
    PreprocessedText,
    SentimentAnalysisOutput,
)
from sentiment_analyzer.models import (
    SentimentResultORM,
    SentimentMetricORM,
    DeadLetterEventORM,
)

# Mock data for tests
@pytest.fixture
def mock_raw_event_dto():
    return RawEventDTO(
        id=1,  # Internal DB ID for the raw event record
        event_id="ext_event_123", # External event identifier
        source="test_source",
        source_id="test_source_id_from_dto", # Added source_id
        content="This is a test content.",
        occurred_at=datetime.now(timezone.utc) - timedelta(hours=1), # Renamed from created_at_external
        payload={"original_field": "original_value"},
        processed_at=None,
        processed=False
    )

@pytest.fixture
def mock_preprocessed_text_dto():
    return PreprocessedText(
        original_text="This is a test content.",
        cleaned_text="test content",
        detected_language_code="en",
        is_target_language=True
    )

@pytest.fixture
def mock_sentiment_analysis_output_dto():
    return SentimentAnalysisOutput(
        label="positive",
        confidence=0.9,
        scores={"positive": 0.9, "negative": 0.05, "neutral": 0.05},
        model_version="test_model_v1"
    )

@pytest.fixture
def mock_sentiment_result_orm(mock_raw_event_dto: RawEventDTO, mock_preprocessed_text_dto: PreprocessedText, mock_sentiment_analysis_output_dto: SentimentAnalysisOutput):
    return SentimentResultORM(
        id=1, # Usually set by DB
        event_id=mock_raw_event_dto.event_id, # Changed from raw_event_id, using DTO's event_id
        occurred_at=mock_raw_event_dto.occurred_at, # Added
        source=mock_raw_event_dto.source, # Added
        source_id=mock_raw_event_dto.source_id, # Added
        raw_text=mock_preprocessed_text_dto.original_text, # Changed from cleaned_text
        sentiment_label=mock_sentiment_analysis_output_dto.label,
        sentiment_score=mock_sentiment_analysis_output_dto.confidence,
        confidence=mock_sentiment_analysis_output_dto.confidence, # Added confidence field
        sentiment_scores_json=mock_sentiment_analysis_output_dto.scores,
        model_version=mock_sentiment_analysis_output_dto.model_version,
        processed_at=datetime.now(timezone.utc)
        # removed detected_language_code as it's not in SentimentResultORM
    )

@pytest.fixture
def mock_db_session_for_processor():
    """Fixture to mock the database session context manager for ResultProcessor."""
    # Path to the get_async_db_session used within result_processor.py
    with patch('sentiment_analyzer.core.result_processor.get_async_db_session') as mock_get_session:
        # Create a mock session that has the necessary async methods
        # Using spec=AsyncSession makes the mock stricter
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Explicitly define session methods as AsyncMocks
        mock_session.add = MagicMock()  # session.add is synchronous
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.refresh = AsyncMock()
        # If your code uses other session methods like flush, add them here too:
        # mock_session.flush = AsyncMock()
        
        # Mock the async context manager behavior
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        # Ensure __aexit__ handles exceptions appropriately if needed,
        # for example, by returning False to re-raise them.
        mock_context_manager.__aexit__.return_value = None 
        
        mock_get_session.return_value = mock_context_manager
        # It's important to yield the mock_session that has the methods,
        # as this is what the tests will interact with.
        yield mock_session

@pytest.fixture
def result_processor_instance():
    return ResultProcessor()

# --- Tests for save_sentiment_result --- 
@pytest.mark.asyncio
async def test_save_sentiment_result_success(
    result_processor_instance: ResultProcessor,
    mock_db_session_for_processor: AsyncMock,
    mock_raw_event_dto: RawEventDTO,
    mock_preprocessed_text_dto: PreprocessedText,
    mock_sentiment_analysis_output_dto: SentimentAnalysisOutput,
):
    """Test successful saving of a sentiment result."""
    saved_result = await result_processor_instance.save_sentiment_result(
        raw_event=mock_raw_event_dto,
        preprocessed_data=mock_preprocessed_text_dto,
        sentiment_output=mock_sentiment_analysis_output_dto,
    )

    mock_db_session_for_processor.add.assert_called_once()
    added_object = mock_db_session_for_processor.add.call_args[0][0]
    assert isinstance(added_object, SentimentResultORM)
    assert added_object.event_id == mock_raw_event_dto.id # Check against internal numeric id
    assert added_object.source == mock_raw_event_dto.source # Added assertion for source
    assert added_object.source_id == mock_raw_event_dto.source_id # Added assertion for source_id
    assert added_object.raw_text == mock_preprocessed_text_dto.original_text # Check raw_text against original_text
    assert added_object.sentiment_label == mock_sentiment_analysis_output_dto.label

    mock_db_session_for_processor.commit.assert_awaited_once()
    mock_db_session_for_processor.refresh.assert_awaited_once_with(added_object)
    mock_db_session_for_processor.rollback.assert_not_called()
    assert saved_result is not None
    assert saved_result == added_object # after refresh, it should be the same object

@pytest.mark.asyncio
async def test_save_sentiment_result_sqlalchemy_error(
    result_processor_instance: ResultProcessor,
    mock_db_session_for_processor: AsyncMock,
    mock_raw_event_dto: RawEventDTO,
    mock_preprocessed_text_dto: PreprocessedText,
    mock_sentiment_analysis_output_dto: SentimentAnalysisOutput,
):
    """Test SQLAlchemyError during saving of a sentiment result."""
    mock_db_session_for_processor.commit.side_effect = SQLAlchemyError("DB commit failed")

    saved_result = await result_processor_instance.save_sentiment_result(
        raw_event=mock_raw_event_dto,
        preprocessed_data=mock_preprocessed_text_dto,
        sentiment_output=mock_sentiment_analysis_output_dto,
    )

    mock_db_session_for_processor.add.assert_called_once()
    mock_db_session_for_processor.commit.assert_awaited_once()
    mock_db_session_for_processor.refresh.assert_not_called()
    mock_db_session_for_processor.rollback.assert_awaited_once()
    assert saved_result is None

@pytest.mark.asyncio
async def test_save_sentiment_result_exception(
    result_processor_instance: ResultProcessor,
    mock_db_session_for_processor: AsyncMock,
    mock_raw_event_dto: RawEventDTO,
    mock_preprocessed_text_dto: PreprocessedText,
    mock_sentiment_analysis_output_dto: SentimentAnalysisOutput,
):
    """Test generic Exception during saving of a sentiment result."""
    mock_db_session_for_processor.commit.side_effect = Exception("Unexpected error")

    saved_result = await result_processor_instance.save_sentiment_result(
        raw_event=mock_raw_event_dto,
        preprocessed_data=mock_preprocessed_text_dto,
        sentiment_output=mock_sentiment_analysis_output_dto,
    )

    mock_db_session_for_processor.add.assert_called_once()
    mock_db_session_for_processor.commit.assert_awaited_once()
    mock_db_session_for_processor.refresh.assert_not_called()
    mock_db_session_for_processor.rollback.assert_awaited_once()
    assert saved_result is None
 

# --- Tests for update_sentiment_metrics ---
@pytest.mark.asyncio
async def test_update_sentiment_metrics_success(
    result_processor_instance: ResultProcessor,
    mock_db_session_for_processor: AsyncMock,
    mock_raw_event_dto: RawEventDTO,
    mocker: MockerFixture  # Added mocker
):
    """Test successful update of sentiment metrics."""
    # Create a controlled mock for SentimentResultORM
    mock_sr_orm = mocker.MagicMock(spec=SentimentResultORM)
    mock_sr_orm.id = 123
    mock_sr_orm.processed_at = datetime.now(timezone.utc)
    mock_sr_orm.sentiment_label = "positive"
    mock_sr_orm.model_version = "test_model_v1"
    mock_sr_orm.sentiment_score = 0.95

    # Mock the execute method for the upsert
    mock_db_session_for_processor.execute.return_value = MagicMock()

    success = await result_processor_instance.update_sentiment_metrics(
        sentiment_result=mock_sr_orm,  # Use the controlled mock
        raw_event_source=mock_raw_event_dto.source,
    )

    assert mock_db_session_for_processor.execute.await_count == 2  # Expect two execute calls: 1 for SELECT, 1 for INSERT/UPDATE
    mock_db_session_for_processor.commit.assert_awaited_once()
    mock_db_session_for_processor.rollback.assert_not_called()
    assert success is True

@pytest.mark.asyncio
async def test_update_sentiment_metrics_sqlalchemy_error(
    result_processor_instance: ResultProcessor,
    mock_db_session_for_processor: AsyncMock,
    mock_raw_event_dto: RawEventDTO,
    mocker: MockerFixture
):
    """Test SQLAlchemyError during update of sentiment metrics."""
    # Create a controlled mock for SentimentResultORM
    mock_sr_orm = mocker.MagicMock(spec=SentimentResultORM)
    mock_sr_orm.id = 124
    mock_sr_orm.processed_at = datetime.now(timezone.utc)
    mock_sr_orm.sentiment_label = "negative"
    mock_sr_orm.model_version = "test_model_v1"
    mock_sr_orm.sentiment_score = 0.15

    mock_db_session_for_processor.execute.side_effect = SQLAlchemyError("DB error on update")

    success = await result_processor_instance.update_sentiment_metrics(
        sentiment_result=mock_sr_orm, # Use the controlled mock
        raw_event_source=mock_raw_event_dto.source,
    )

    # Execute will be called for the first metric (count), then fail
    mock_db_session_for_processor.execute.assert_awaited_once() 
    mock_db_session_for_processor.commit.assert_not_called()
    mock_db_session_for_processor.rollback.assert_awaited_once()
    assert success is False

@pytest.mark.asyncio
async def test_update_sentiment_metrics_exception(
    result_processor_instance: ResultProcessor,
    mock_db_session_for_processor: AsyncMock,
    mock_raw_event_dto: RawEventDTO,
    mocker: MockerFixture
):
    """Test generic Exception during update of sentiment metrics."""
    # Create a controlled mock for SentimentResultORM
    mock_sr_orm = mocker.MagicMock(spec=SentimentResultORM)
    mock_sr_orm.id = 125
    mock_sr_orm.processed_at = datetime.now(timezone.utc)
    mock_sr_orm.sentiment_label = "neutral"
    mock_sr_orm.model_version = "test_model_v1"
    mock_sr_orm.sentiment_score = 0.5

    mock_db_session_for_processor.execute.side_effect = Exception("Unexpected error on update")

    success = await result_processor_instance.update_sentiment_metrics(
        sentiment_result=mock_sr_orm, # Use the controlled mock
        raw_event_source=mock_raw_event_dto.source,
    )

    # Execute will be called for the first metric (count), then fail
    mock_db_session_for_processor.execute.assert_awaited_once()
    mock_db_session_for_processor.commit.assert_not_called()
    mock_db_session_for_processor.rollback.assert_awaited_once()
    assert success is False
 
# --- Tests for move_to_dead_letter_queue ---
@pytest.mark.asyncio
async def test_move_to_dead_letter_queue_success(
    result_processor_instance: ResultProcessor,
    mock_db_session_for_processor: AsyncMock,
    mock_raw_event_dto: RawEventDTO,
):
    """Test successful moving of an event to the dead-letter queue."""
    error_message = "Test error"
    failed_stage = "test_stage"

    moved_event = await result_processor_instance.move_to_dead_letter_queue(
        raw_event=mock_raw_event_dto,
        error_message=error_message,
        failed_stage=failed_stage,
    )

    mock_db_session_for_processor.add.assert_called_once()
    added_object = mock_db_session_for_processor.add.call_args[0][0]
    assert isinstance(added_object, DeadLetterEventORM)
    assert added_object.event_id == mock_raw_event_dto.event_id # Check against external event_id
    assert added_object.source_id == mock_raw_event_dto.source_id # This assertion is now valid
    assert added_object.error_msg == error_message
    assert added_object.processing_component == failed_stage
    assert added_object.event_payload == mock_raw_event_dto.model_dump(mode="json") # Check if payload is correctly stored as JSON-compatible dict

    mock_db_session_for_processor.commit.assert_awaited_once()
    mock_db_session_for_processor.refresh.assert_awaited_once_with(added_object)
    mock_db_session_for_processor.rollback.assert_not_called()
    assert moved_event is not None
    assert moved_event == added_object

@pytest.mark.asyncio
async def test_move_to_dead_letter_queue_sqlalchemy_error(
    result_processor_instance: ResultProcessor,
    mock_db_session_for_processor: AsyncMock,
    mock_raw_event_dto: RawEventDTO,
):
    """Test SQLAlchemyError during moving an event to the dead-letter queue."""
    mock_db_session_for_processor.commit.side_effect = SQLAlchemyError("DB commit failed for DLQ")

    moved_event = await result_processor_instance.move_to_dead_letter_queue(
        raw_event=mock_raw_event_dto,
        error_message="Test error",
        failed_stage="test_stage",
    )

    mock_db_session_for_processor.add.assert_called_once()
    mock_db_session_for_processor.commit.assert_awaited_once()
    mock_db_session_for_processor.refresh.assert_not_called()
    mock_db_session_for_processor.rollback.assert_awaited_once()
    assert moved_event is None

@pytest.mark.asyncio
async def test_move_to_dead_letter_queue_exception(
    result_processor_instance: ResultProcessor,
    mock_db_session_for_processor: AsyncMock,
    mock_raw_event_dto: RawEventDTO,
):
    """Test generic Exception during moving an event to the dead-letter queue."""
    mock_db_session_for_processor.commit.side_effect = Exception("Unexpected error during DLQ move")

    moved_event = await result_processor_instance.move_to_dead_letter_queue(
        raw_event=mock_raw_event_dto,
        error_message="Test error",
        failed_stage="test_stage",
    )

    mock_db_session_for_processor.add.assert_called_once()
    mock_db_session_for_processor.commit.assert_awaited_once()
    mock_db_session_for_processor.refresh.assert_not_called()
    mock_db_session_for_processor.rollback.assert_awaited_once()
    assert moved_event is None
 
