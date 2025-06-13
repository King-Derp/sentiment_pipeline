import pytest
from datetime import datetime, timezone
from sqlalchemy import text, select

from unittest.mock import patch
from sentiment_analyzer.core.pipeline import SentimentPipeline
from sentiment_analyzer.models.sentiment_result_orm import SentimentResultORM
from sentiment_analyzer.models.sentiment_metric_orm import SentimentMetricORM
from sentiment_analyzer.tests.stubs.raw_event_stub import RawEventORM # Use stub ORM for integration test
import json # For parsing JSON string to dict


@pytest.fixture
def mock_ml_models():
    """Mock the heavyweight ML models to keep integration tests fast."""
    with patch('spacy.load'), patch('transformers.AutoTokenizer.from_pretrained'), patch('transformers.AutoModelForSequenceClassification.from_pretrained'):
        yield

@pytest.mark.asyncio
async def test_full_pipeline_run_integration(db_session, mock_ml_models, mocker):
    """Test a single event moving through the entire pipeline with a live DB."""
    # 1. Setup: Insert a raw event directly into the test database
    raw_event_content = '{"text": "This company is performing very well."}'
    raw_event = RawEventORM(
        id=1, # Internal PK - Note: Main ORM might have auto-incrementing ID, consider if explicit ID is needed or if DB should assign.
        source='reddit-integration-test',
        source_id='reddit-integ-src-id-1', # Source-specific ID, maps to RawEventORM.source_id
        content=json.loads(raw_event_content), # Provide the content field
        payload=json.loads(raw_event_content), # Use 'payload' and provide a dict
        occurred_at=datetime.now(timezone.utc),
        processed=False, # Explicitly set
        processed_at=None # This is the correct field for the main ORM
    )
    db_session.add(raw_event)
    await db_session.commit()

    # 2. Action: Run the pipeline once
    mocker.patch('sentiment_analyzer.config.settings.settings.EVENT_FETCH_BATCH_SIZE', 10)
    pipeline = SentimentPipeline(db_session=db_session)
    events_processed_count = await pipeline.run_pipeline_once()

    # 3. Assert: Check the outcomes
    assert events_processed_count == 1

    # Verify the raw event was marked as processed
    await db_session.refresh(raw_event)
    assert raw_event.processed_at is not None  # DataFetcher marks it as processed

    # Verify a sentiment result was created
    result_stmt = select(SentimentResultORM).where(SentimentResultORM.event_id == raw_event.id)
    saved_result = (await db_session.execute(result_stmt)).scalar_one_or_none()
    assert saved_result is not None
    # The actual label/score depends on the mocked model, but we can check existence
    assert saved_result.sentiment_label is not None 

    # Verify sentiment metrics were updated
    metrics_stmt = select(SentimentMetricORM).where(SentimentMetricORM.source == 'reddit-integration-test')
    metrics = (await db_session.execute(metrics_stmt)).scalars().all()
    assert len(metrics) == 1, "Expected exactly one metric record to be created"

    metric_record = metrics[0]
    assert metric_record.count == 1
    assert metric_record.avg_score == saved_result.sentiment_score
