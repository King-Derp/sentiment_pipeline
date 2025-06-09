"""
Result Processor component for the Sentiment Analysis Service.

This component is responsible for saving the results of sentiment analysis
to the database and updating any relevant aggregated metrics.
It also handles moving failed events to a dead-letter queue.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Dict

from sqlalchemy import select, update # SQLAlchemy 2.0 stylerom sqlalchemy.dialects.postgresql import insert as pg_insert # For ON CONFLICT DO UPDATE
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from sentiment_analyzer.models.dtos import (
    RawEventDTO,
    PreprocessedText,
    SentimentAnalysisOutput,
)
from sentiment_analyzer.models.orm import (
    SentimentResultORM,
    SentimentMetricORM,
    DeadLetterEventORM,
)
from sentiment_analyzer.utils.db_session import get_async_db_session

logger = logging.getLogger(__name__)

class ResultProcessor:
    """
    Handles saving sentiment analysis results, updating metrics, and managing dead-letter events.
    """

    async def save_sentiment_result(
        self,
        raw_event: RawEventDTO,
        preprocessed_data: PreprocessedText,
        sentiment_output: SentimentAnalysisOutput,
        db_session: Optional[AsyncSession] = None,
    ) -> Optional[SentimentResultORM]:
        """
        Saves a single sentiment analysis result to the database.

        Args:
            raw_event: The original raw event DTO.
            preprocessed_data: The DTO containing preprocessed text and language info.
            sentiment_output: The DTO containing sentiment analysis output.
            db_session: Optional existing database session. If None, a new one is created.

        Returns:
            The saved SentimentResultORM object if successful, else None.
        """
        session_manager = get_async_db_session(existing_session=db_session)
        async with session_manager as session:
            try:
                new_result_orm = SentimentResultORM(
                    raw_event_id=raw_event.id,
                    cleaned_text=preprocessed_data.cleaned_text,
                    detected_language_code=preprocessed_data.detected_language_code,
                    sentiment_label=sentiment_output.label,
                    # Assuming sentiment_output.confidence is the primary score for the label
                    sentiment_score=sentiment_output.confidence, 
                    sentiment_scores_json=sentiment_output.scores,
                    model_version=sentiment_output.model_version,
                    # Ensure raw_text is stored if available and needed by schema/design
                    # raw_text=preprocessed_data.original_text, # Example if needed
                    processed_at=datetime.now(timezone.utc),
                )
                session.add(new_result_orm)
                await session.commit()
                await session.refresh(new_result_orm)
                logger.info(f"Saved sentiment result for raw_event_id: {raw_event.id}")
                return new_result_orm
            except SQLAlchemyError as e:
                logger.error(
                    f"Database error saving sentiment result for raw_event_id {raw_event.id}: {e}",
                    exc_info=True
                )
                await session.rollback()
                return None
            except Exception as e:
                logger.error(
                    f"Unexpected error saving sentiment result for raw_event_id {raw_event.id}: {e}",
                    exc_info=True
                )
                await session.rollback()
                return None

    async def update_sentiment_metrics(
        self,
        sentiment_result: SentimentResultORM,
        raw_event_source: str, # Source from the original RawEventDTO
        db_session: Optional[AsyncSession] = None,
    ) -> bool:
        """
        Updates aggregated sentiment metrics based on a new sentiment result.
        This uses INSERT ... ON CONFLICT DO UPDATE to handle existing metric rows.

        Args:
            sentiment_result: The newly saved SentimentResultORM object.
            raw_event_source: The source of the raw event (e.g., 'reddit', 'twitter').
            db_session: Optional existing database session. If None, a new one is created.

        Returns:
            True if metrics were updated successfully, False otherwise.
        """
        session_manager = get_async_db_session(existing_session=db_session)
        async with session_manager as session:
            try:
                # Truncate timestamp to the hour for hourly aggregation
                metric_ts = sentiment_result.processed_at.replace(
                    minute=0, second=0, microsecond=0
                )

                common_key_fields = {
                    "metric_timestamp": metric_ts,
                    "raw_event_source": raw_event_source,
                    "sentiment_label": sentiment_result.sentiment_label,
                    "model_version": sentiment_result.model_version,
                }

                # 1. Update/Insert count metric
                count_metric_name = "count"
                count_stmt = pg_insert(SentimentMetricORM).values(
                    **common_key_fields,
                    metric_name=count_metric_name,
                    metric_value_int=1,
                    metric_value_float=None # Ensure float is None if int is used
                )
                count_update_stmt = count_stmt.on_conflict_do_update(
                    index_elements=[
                        SentimentMetricORM.metric_timestamp,
                        SentimentMetricORM.raw_event_source,
                        SentimentMetricORM.sentiment_label,
                        SentimentMetricORM.model_version,
                        SentimentMetricORM.metric_name,
                    ],
                    set_=dict(
                        metric_value_int=SentimentMetricORM.metric_value_int + 1
                    )
                )
                await session.execute(count_update_stmt)

                # 2. Update/Insert score_sum metric
                score_sum_metric_name = "score_sum"
                score_sum_stmt = pg_insert(SentimentMetricORM).values(
                    **common_key_fields,
                    metric_name=score_sum_metric_name,
                    metric_value_float=sentiment_result.sentiment_score,
                    metric_value_int=None # Ensure int is None if float is used
                )
                score_sum_update_stmt = score_sum_stmt.on_conflict_do_update(
                    index_elements=[
                        SentimentMetricORM.metric_timestamp,
                        SentimentMetricORM.raw_event_source,
                        SentimentMetricORM.sentiment_label,
                        SentimentMetricORM.model_version,
                        SentimentMetricORM.metric_name,
                    ],
                    set_=dict(
                        metric_value_float=SentimentMetricORM.metric_value_float + sentiment_result.sentiment_score
                    )
                )
                await session.execute(score_sum_update_stmt)
                
                await session.commit()
                logger.info(f"Updated sentiment metrics for result_id: {sentiment_result.id}, source: {raw_event_source}")
                return True
            except SQLAlchemyError as e:
                logger.error(
                    f"Database error updating sentiment metrics for result_id {sentiment_result.id}: {e}",
                    exc_info=True
                )
                await session.rollback()
                return False
            except Exception as e:
                logger.error(
                    f"Unexpected error updating sentiment metrics for result_id {sentiment_result.id}: {e}",
                    exc_info=True
                )
                await session.rollback()
                return False

    async def move_to_dead_letter_queue(
        self,
        raw_event: RawEventDTO,
        error_message: str,
        failed_stage: str,
        db_session: Optional[AsyncSession] = None,
    ) -> Optional[DeadLetterEventORM]:
        """
        Moves a failed event's details to the dead-letter queue.

        Args:
            raw_event: The DTO of the raw event that failed.
            error_message: A description of the error.
            failed_stage: The pipeline stage where the failure occurred.
            db_session: Optional existing database session. If None, a new one is created.

        Returns:
            The saved DeadLetterEventORM object if successful, else None.
        """
        session_manager = get_async_db_session(existing_session=db_session)
        async with session_manager as session:
            try:
                # Ensure raw_event_content_json is serializable
                content_json_str = raw_event.model_dump_json() if raw_event else "{}"

                new_dle_orm = DeadLetterEventORM(
                    raw_event_id=raw_event.id if raw_event else None, # Handle if raw_event could be None
                    raw_event_content_json=content_json_str,
                    failure_reason=error_message,
                    failed_stage=failed_stage,
                    failed_at=datetime.now(timezone.utc),
                )
                session.add(new_dle_orm)
                await session.commit()
                await session.refresh(new_dle_orm)
                logger.info(f"Moved event (raw_event_id: {raw_event.id if raw_event else 'N/A'}) to dead-letter queue. Stage: {failed_stage}")
                return new_dle_orm
            except SQLAlchemyError as e:
                logger.error(
                    f"Database error moving event (raw_event_id: {raw_event.id if raw_event else 'N/A'}) to DLQ: {e}",
                    exc_info=True
                )
                await session.rollback()
                return None
            except Exception as e:
                logger.error(
                    f"Unexpected error moving event (raw_event_id: {raw_event.id if raw_event else 'N/A'}) to DLQ: {e}",
                    exc_info=True
                )
                await session.rollback()
                return None

# Example Usage (for demonstration - requires running async)
async def example_usage():
    logging.basicConfig(level=logging.INFO)
    # Setup (ensure .env is loaded for db connection, etc.)
    from dotenv import load_dotenv
    from pathlib import Path
    SERVICE_ROOT_DIR = Path(__file__).parent.parent.resolve()
    load_dotenv(SERVICE_ROOT_DIR / ".env")
    
    # Mock data for the example
    mock_raw_event = RawEventDTO(
        id=101,
        source="example_source",
        author="example_author",
        content="This is a test content for result processing! It's quite positive.",
        created_at_external=datetime.now(timezone.utc),
        # These would be set by DataFetcher in a real scenario
        claimed_at=None, 
        processed_at=None, 
        processing_status="unprocessed"
    )
    mock_preprocessed = PreprocessedText(
        original_text=mock_raw_event.content,
        cleaned_text="test content result processing positive",
        detected_language_code="en",
        is_target_language=True
    )
    mock_sentiment_out = SentimentAnalysisOutput(
        label="positive",
        confidence=0.95,
        scores={"positive": 0.95, "negative": 0.03, "neutral": 0.02},
        model_version="ProsusAI/finbert-v1.1"
    )

    processor = ResultProcessor()

    # 1. Save sentiment result
    saved_result = await processor.save_sentiment_result(
        raw_event=mock_raw_event,
        preprocessed_data=mock_preprocessed,
        sentiment_output=mock_sentiment_out
    )

    if saved_result:
        logger.info(f"Example: Saved result ID: {saved_result.id}")
        # 2. Update metrics (using the saved result and original source)
        metrics_updated = await processor.update_sentiment_metrics(
            sentiment_result=saved_result,
            raw_event_source=mock_raw_event.source
        )
        logger.info(f"Example: Metrics updated: {metrics_updated}")
    else:
        logger.error("Example: Failed to save sentiment result.")

    # 3. Example: Move to Dead Letter Queue
    failed_event_data = RawEventDTO(
        id=102, # Different ID for DLQ example
        source="another_source",
        author="another_author",
        content="This event failed processing due to some error.",
        created_at_external=datetime.now(timezone.utc),
        claimed_at=None, processed_at=None, processing_status="unprocessed"
    )
    moved_to_dlq = await processor.move_to_dead_letter_queue(
        raw_event=failed_event_data,
        error_message="Simulated processing error in sentiment analysis stage.",
        failed_stage="sentiment_analysis"
    )
    if moved_to_dlq:
        logger.info(f"Example: Moved event to DLQ, DLE ID: {moved_to_dlq.id}")
    else:
        logger.error("Example: Failed to move event to DLQ.")

if __name__ == "__main__":
    import asyncio
    # This is a simplified way to run the async example. 
    # In a real app, you'd use an async framework's entry point.
    try:
        asyncio.run(example_usage())
    except KeyboardInterrupt:
        logger.info("Example usage interrupted.")
