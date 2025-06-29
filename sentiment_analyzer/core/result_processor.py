"""
Result Processor component for the Sentiment Analysis Service.

This component is responsible for saving the results of sentiment analysis
to the database and updating any relevant aggregated metrics.
It also handles moving failed events to a dead-letter queue.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Dict

from sqlalchemy import select, update # SQLAlchemy 2.0 style
from sqlalchemy.dialects.postgresql import insert as pg_insert # For ON CONFLICT DO UPDATE
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

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
from sentiment_analyzer.models.dtos import SentimentResultDTO
from sentiment_analyzer.utils.db_session import get_db_session_context_manager as get_async_db_session
from sentiment_analyzer.integrations.powerbi import PowerBIClient

logger = logging.getLogger(__name__)

class ResultProcessor:
    """
    Handles saving sentiment analysis results, updating metrics, and managing dead-letter events.
    """
    def __init__(self, session: Optional[AsyncSession] = None, powerbi_client: Optional[PowerBIClient] = None):
        """
        Initializes the ResultProcessor.

        Args:
            session: An optional SQLAlchemy AsyncSession to use for database operations.
                     If None, a new session will be created for each operation.
            powerbi_client: An optional PowerBI client for real-time streaming.
        """
        self._shared_session = session
        self._powerbi_client = powerbi_client

    async def save_sentiment_result(
        self,
        raw_event: RawEventDTO,
        preprocessed_data: PreprocessedText,
        sentiment_output: SentimentAnalysisOutput
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
        session_manager = get_async_db_session(existing_session=self._shared_session)
        async with session_manager as session:
            try:
                new_result_orm = SentimentResultORM(
                    # Use internal numeric id for DB column (BIGINT)
                    event_id=raw_event.id,  # Always use internal numeric id for DB column (BIGINT)
                    occurred_at=raw_event.occurred_at if raw_event.occurred_at else datetime.now(timezone.utc),
                    source=raw_event.source if raw_event.source else "unknown",
                    source_id=raw_event.source_id if raw_event.source_id else "unknown",
                    sentiment_label=sentiment_output.label,
                    sentiment_score=sentiment_output.confidence, # Assuming this is the primary score for the label
                    confidence=sentiment_output.confidence, # Added mapping for the explicit confidence field
                    sentiment_scores_json=sentiment_output.scores,
                    model_version=sentiment_output.model_version,
                    raw_text=preprocessed_data.original_text, # Added, using original_text for raw_text field
                    processed_at=datetime.now(timezone.utc)
                )
                session.add(new_result_orm)
                await session.commit()
                await session.refresh(new_result_orm)
                logger.info(f"Saved sentiment result for raw_event_id: {raw_event.id}")
                
                # Stream to PowerBI if client is available
                if self._powerbi_client:
                    try:
                        # Convert ORM to DTO for PowerBI streaming
                        result_dto = SentimentResultDTO(
                            id=new_result_orm.id,
                            event_id=str(new_result_orm.event_id),  # Convert to string for DTO
                            occurred_at=new_result_orm.occurred_at,
                            source=new_result_orm.source,
                            source_id=new_result_orm.source_id,
                            sentiment_score=new_result_orm.sentiment_score,
                            sentiment_label=new_result_orm.sentiment_label,
                            confidence=new_result_orm.confidence,
                            processed_at=new_result_orm.processed_at,
                            model_version=new_result_orm.model_version,
                            raw_text=new_result_orm.raw_text
                        )
                        
                        # Stream to PowerBI (non-blocking)
                        await self._powerbi_client.push_row(result_dto)
                        logger.debug(f"Streamed sentiment result to PowerBI for event_id: {raw_event.id}")
                    except Exception as powerbi_error:
                        # Don't fail the entire operation if PowerBI streaming fails
                        logger.warning(
                            f"Failed to stream result to PowerBI for event_id {raw_event.id}: {powerbi_error}"
                        )
                
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
        session_manager = get_async_db_session(existing_session=self._shared_session)
        async with session_manager as session:
            try:
                metric_ts = sentiment_result.processed_at.replace(minute=0, second=0, microsecond=0)
                source_id_value = getattr(sentiment_result, "source_id", "unknown")

                existing_stmt = select(SentimentMetricORM).where(
                    (SentimentMetricORM.time_bucket == metric_ts) &
                    (SentimentMetricORM.source == raw_event_source) &
                    (SentimentMetricORM.source_id == source_id_value) &
                    (SentimentMetricORM.label == sentiment_result.sentiment_label)
                )

                existing_metric_result = await session.execute(existing_stmt)
                existing_metric = existing_metric_result.scalars().first()

                if existing_metric:
                    new_count = existing_metric.count + 1
                    new_avg = ((existing_metric.avg_score * existing_metric.count) + sentiment_result.sentiment_score) / new_count

                    await session.execute(
                        update(SentimentMetricORM)
                        .where(
                            (SentimentMetricORM.time_bucket == metric_ts) &
                            (SentimentMetricORM.source == raw_event_source) &
                            (SentimentMetricORM.source_id == source_id_value) &
                            (SentimentMetricORM.label == sentiment_result.sentiment_label)
                        )
                        .values(count=new_count, avg_score=new_avg)
                    )
                else:
                    await session.execute(
                        pg_insert(SentimentMetricORM).values(
                            time_bucket=metric_ts,
                            source=raw_event_source,
                            source_id=source_id_value,
                            label=sentiment_result.sentiment_label,
                            count=1,
                            avg_score=sentiment_result.sentiment_score,
                        )
                    )
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
        failed_stage: str
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
        session_manager = get_async_db_session(existing_session=self._shared_session)
        async with session_manager as session:
            try:
                content_json: Dict = raw_event.model_dump(mode="json") if raw_event else {}

                new_dle_orm = DeadLetterEventORM(
                    event_id=raw_event.event_id if raw_event.event_id is not None else str(raw_event.id),
                    occurred_at=raw_event.occurred_at if raw_event and raw_event.occurred_at else datetime.now(timezone.utc), # Added
                    source=raw_event.source if raw_event and raw_event.source else "unknown", # Added
                    source_id=raw_event.source_id if raw_event and raw_event.source_id else "unknown", # Added
                    event_payload=content_json,
                    error_msg=error_message,  # Corrected: failure_reason to error_msg
                    processing_component=failed_stage,  # Corrected: failed_stage to processing_component
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
