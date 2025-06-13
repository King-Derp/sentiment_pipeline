import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
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
from sentiment_analyzer.tests.stubs.raw_event_stub import RawEventORM as RawEventStubORM # For creating prerequisite raw_event

# Helper to create a prerequisite raw event in the DB
async def create_raw_event_in_db(
    db_session: AsyncSession, 
    internal_id: int, 
    source: str, 
    event_id_str: str | None = None, 
    source_id_str: str | None = None
) -> RawEventStubORM:
    raw_event = RawEventStubORM(
        id=internal_id,
        event_id=event_id_str if event_id_str else f"stub_ext_id_{internal_id}", # Default if not provided
        source=source,
        source_id=source_id_str if source_id_str else f"stub_src_id_{internal_id}", # Default if not provided
        content='{"text": "Initial raw content for integration test"}',
        occurred_at=datetime.now(timezone.utc) - timedelta(days=1),
        processed=False # Default for stubs, good to be explicit
    )
    db_session.add(raw_event)
    await db_session.commit()
    await db_session.refresh(raw_event)
    return raw_event

@pytest.fixture
def result_processor_instance() -> ResultProcessor:
    return ResultProcessor()

@pytest.fixture
def sample_raw_event_dto(event_id_pk: int = 1, source: str = "integ_test_source") -> RawEventDTO: # Renamed param for clarity
    return RawEventDTO(
        id=event_id_pk,
        event_id=f"test_external_event_id_{event_id_pk}", # Added: Non-null string external ID
        source=source,
        # author="test_author", # Removed: RawEventDTO has no 'author' field
        content="This is integration test content.",
        source_id=f"src_id_{event_id_pk}",
        occurred_at=datetime.now(timezone.utc) - timedelta(hours=1), # Corrected: was created_at_external
        # claimed_at=None, # Removed: RawEventDTO has no 'claimed_at' field
        processed=False, # Corrected: was processing_status="unprocessed"
        processed_at=None
    )

@pytest.fixture
def sample_preprocessed_text_dto() -> PreprocessedText:
    return PreprocessedText(
        original_text="This is integration test content.",
        cleaned_text="integration test content",
        detected_language_code="en",
        is_target_language=True
    )

@pytest.fixture
def sample_sentiment_analysis_output_dto() -> SentimentAnalysisOutput:
    return SentimentAnalysisOutput(
        label="neutral",
        confidence=0.75,
        scores={"positive": 0.1, "negative": 0.15, "neutral": 0.75},
        model_version="test_model_integ_v1"
    )

# --- Tests for save_sentiment_result (Integration) ---
@pytest.mark.asyncio
async def test_save_sentiment_result_integration(
    result_processor_instance: ResultProcessor,
    db_session: AsyncSession, # From conftest.py
    sample_raw_event_dto: RawEventDTO,
    sample_preprocessed_text_dto: PreprocessedText,
    sample_sentiment_analysis_output_dto: SentimentAnalysisOutput,
):
    """Test saving a sentiment result to the live test database."""
    # Ensure a prerequisite raw_event exists in the stub table for FK constraint
    await create_raw_event_in_db(
            db_session, 
            internal_id=sample_raw_event_dto.id, 
            source=sample_raw_event_dto.source,
            event_id_str=sample_raw_event_dto.event_id,
            source_id_str=sample_raw_event_dto.source_id
        )

    saved_orm = await result_processor_instance.save_sentiment_result(
        raw_event=sample_raw_event_dto,
        preprocessed_data=sample_preprocessed_text_dto,
        sentiment_output=sample_sentiment_analysis_output_dto
    )

    assert saved_orm is not None
    assert saved_orm.id is not None # Should be populated by the DB
    assert saved_orm.event_id == sample_raw_event_dto.id
    assert saved_orm.raw_text == sample_preprocessed_text_dto.original_text
    assert saved_orm.sentiment_label == sample_sentiment_analysis_output_dto.label
    assert saved_orm.sentiment_score == sample_sentiment_analysis_output_dto.confidence
    assert saved_orm.model_version == sample_sentiment_analysis_output_dto.model_version

    # Verify by querying the database directly
    stmt = select(SentimentResultORM).where(SentimentResultORM.id == saved_orm.id)
    queried_result = (await db_session.execute(stmt)).scalar_one_or_none()

    assert queried_result is not None
    assert queried_result.event_id == sample_raw_event_dto.id
    assert queried_result.sentiment_label == sample_sentiment_analysis_output_dto.label
 

# --- Tests for update_sentiment_metrics (Integration) ---
@pytest.mark.asyncio
async def test_update_sentiment_metrics_integration_new_and_update(
    result_processor_instance: ResultProcessor,
    db_session: AsyncSession,
    sample_raw_event_dto: RawEventDTO,
    sample_sentiment_analysis_output_dto: SentimentAnalysisOutput
):
    """Test creating and then updating sentiment metrics in the live test database."""
    source = sample_raw_event_dto.source
    label = sample_sentiment_analysis_output_dto.label
    score1 = sample_sentiment_analysis_output_dto.confidence
    score2 = 0.5

    # Define a fixed processed_at time to ensure same time_bucket
    fixed_processed_time = datetime.now(timezone.utc).replace(minute=30, second=0, microsecond=0)
    # This ensures it's in the middle of an hour, less likely to cross hour boundary during test execution.

    # 1. First call: Create new metrics
    raw_event_stub1 = await create_raw_event_in_db(
        db_session,
        internal_id=sample_raw_event_dto.id,
        source=sample_raw_event_dto.source,
        event_id_str=sample_raw_event_dto.event_id,
        source_id_str=sample_raw_event_dto.source_id
    )

    sentiment_result_orm1 = SentimentResultORM(
        event_id=raw_event_stub1.id, # This should be raw_event_stub1.id if it's the PK
        occurred_at=raw_event_stub1.occurred_at,
        source=raw_event_stub1.source,
        source_id=raw_event_stub1.source_id,
        raw_text="test text 1",
        sentiment_label=label,
        sentiment_score=score1,
        model_version="integ_test_v1",
        processed_at=fixed_processed_time # Explicitly set processed_at
    )
    db_session.add(sentiment_result_orm1)
    await db_session.commit()
    # No need to refresh for processed_at if explicitly set, but refresh for ID if it's auto-gen.
    # Assuming ID is set from raw_event_stub1.id, so refresh might not be strictly needed for ID here.
    # However, if SentimentResultORM.id is an autoincrement PK, then refresh is needed for that.
    # Let's assume SentimentResultORM.id is also an autoincrement PK for safety.
    await db_session.refresh(sentiment_result_orm1)


    success1 = await result_processor_instance.update_sentiment_metrics(
        sentiment_result=sentiment_result_orm1,
        raw_event_source=source
    )
    assert success1 is True

    metric_ts1 = sentiment_result_orm1.processed_at.replace(minute=0, second=0, microsecond=0)
    
    metrics_stmt1 = select(SentimentMetricORM).where(
        (SentimentMetricORM.time_bucket == metric_ts1) &
        (SentimentMetricORM.source == source) &
        (SentimentMetricORM.source_id == sentiment_result_orm1.source_id) &
        (SentimentMetricORM.label == label)
    )
    metric_record1 = (await db_session.execute(metrics_stmt1)).scalar_one_or_none()

    assert metric_record1 is not None, "Metric record not found after first call"
    assert metric_record1.count == 1
    assert metric_record1.avg_score == pytest.approx(score1)

    # 2. Second call: Update existing metrics
    raw_event_stub2 = await create_raw_event_in_db(
        db_session,
        internal_id=sample_raw_event_dto.id + 1,
        source=sample_raw_event_dto.source,
        event_id_str=f"{sample_raw_event_dto.event_id}_update",
        source_id_str=sample_raw_event_dto.source_id 
    )
        
    sentiment_result_orm2 = SentimentResultORM(
        event_id=raw_event_stub2.id, # This should be raw_event_stub2.id
        occurred_at=raw_event_stub2.occurred_at,
        source=raw_event_stub2.source, # Source can be from stub2
        source_id=raw_event_stub1.source_id, # CRITICAL: Use source_id from stub1 to match the metric 
        raw_text="test text 2",
        sentiment_label=label,
        sentiment_score=score2,
        model_version="integ_test_v1",
        processed_at=fixed_processed_time # Explicitly set processed_at to the same time
    )
    db_session.add(sentiment_result_orm2)
    await db_session.commit()
    await db_session.refresh(sentiment_result_orm2) # Refresh for ID

    success2 = await result_processor_instance.update_sentiment_metrics(
        sentiment_result=sentiment_result_orm2,
        raw_event_source=source
    )
    assert success2 is True

    # Store the source_id before expiring the object, to avoid lazy-load errors.
    source_id_to_check = sentiment_result_orm1.source_id

    # Expire the session to ensure we get fresh data from the DB,
    # as the update happened in a separate session/transaction.
    db_session.expire_all()

    # metric_ts2 will be the same as metric_ts1 due to fixed_processed_time
    metrics_stmt2 = select(SentimentMetricORM).where(
        (SentimentMetricORM.time_bucket == metric_ts1) & # Query for the original time_bucket
        (SentimentMetricORM.source == source) &
        (SentimentMetricORM.source_id == source_id_to_check) &
        (SentimentMetricORM.label == label)
    )
    metric_record2 = (await db_session.execute(metrics_stmt2)).scalar_one_or_none()

    assert metric_record2 is not None, "Metric record not found after second call"
    assert metric_record2.count == 2 # This should now pass
    
    expected_avg_score = (score1 + score2) / 2.0
    assert metric_record2.avg_score == pytest.approx(expected_avg_score)

# --- Tests for move_to_dead_letter_queue (Integration) ---
@pytest.mark.asyncio
async def test_move_to_dead_letter_queue_integration(
    result_processor_instance: ResultProcessor,
    db_session: AsyncSession,
    sample_raw_event_dto: RawEventDTO # DTO to be 'moved'
):
    """Test moving an event to the dead-letter queue in the live test database."""
    # Ensure a prerequisite raw_event exists in the stub table for FK constraint
    # This is the event that 'failed' and is being moved to DLE.
    await create_raw_event_in_db(
            db_session, 
            internal_id=sample_raw_event_dto.id, 
            source=sample_raw_event_dto.source,
            event_id_str=sample_raw_event_dto.event_id,
            source_id_str=sample_raw_event_dto.source_id
        )

    error_message = "Integration test simulated failure"
    failed_stage = "preprocessing_integ_test"

    moved_dle_orm = await result_processor_instance.move_to_dead_letter_queue(
        raw_event=sample_raw_event_dto,
        error_message=error_message,
        failed_stage=failed_stage
    )

    assert moved_dle_orm is not None
    assert moved_dle_orm.id is not None # DB Populated
    assert moved_dle_orm.event_id == sample_raw_event_dto.event_id
    assert moved_dle_orm.error_msg == error_message
    assert moved_dle_orm.processing_component == failed_stage
    assert moved_dle_orm.event_payload == sample_raw_event_dto.model_dump(mode='json')

    # Verify by querying the database directly
    stmt = select(DeadLetterEventORM).where(DeadLetterEventORM.id == moved_dle_orm.id)
    queried_dle = (await db_session.execute(stmt)).scalar_one_or_none()

    assert queried_dle is not None
    assert queried_dle.event_id == sample_raw_event_dto.event_id
    assert queried_dle.error_msg == error_message
    assert queried_dle.event_payload == sample_raw_event_dto.model_dump(mode='json')
 
