"""
Data Fetcher component for the Sentiment Analysis Service.

This component is responsible for fetching unprocessed raw events from the database,
claiming them for processing, and returning them as DTOs.
"""
import logging
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select, update, func, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from sentiment_analyzer.config.settings import settings
from sentiment_analyzer.models import RawEventDTO # RawEventORM removed from here
from reddit_scraper.models.submission import RawEventORM # Added import for RawEventORM
from sentiment_analyzer.utils.db_session import get_db_session_context_manager

logger = logging.getLogger(__name__)

async def fetch_and_claim_raw_events(
    db_session: AsyncSession,
    batch_size: int = settings.EVENT_FETCH_BATCH_SIZE
) -> List[RawEventDTO]:
    """
    Fetches a batch of unprocessed raw events from the 'raw_events' table,
    atomically claims them by marking them as processed for sentiment analysis,
    and returns them as a list of RawEventDTO objects.

    Args:
        db_session: The asynchronous SQLAlchemy session.
        batch_size: The maximum number of events to fetch and claim.

    Returns:
        A list of RawEventDTO objects representing the claimed events.
        Returns an empty list if no unprocessed events are found.
    """
    logger.info(f"Attempting to fetch and claim up to {batch_size} raw events.")

    try:
        # Step 1: Select IDs of events to process
        # This subquery identifies the rows to be updated, respecting order and limit,
        # and uses FOR UPDATE SKIP LOCKED for concurrency safety.
        events_to_update_cte = (
            select(RawEventORM)
            .where(RawEventORM.processed == False)
            .order_by(RawEventORM.occurred_at.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
            .cte("events_to_update_cte")
        )

        # Step 2: Update the selected events and return their full data
        # The update statement targets rows whose IDs are in the CTE.
        # `func.now()` is preferred for setting timestamps by the database server's clock.
        stmt = (
            update(RawEventORM)
            .where(RawEventORM.id.in_(
                select(events_to_update_cte.c.id)
            ))
            .values(
                processed=True,
                processed_at=func.now()
            )
            .returning(RawEventORM)
            .execution_options(populate_existing=True)
        )

        result = await db_session.execute(stmt)
        updated_event_orms = result.scalars().all()
        
        await db_session.commit()

        if not updated_event_orms:
            logger.info("No new raw events found to process.")
            return []

        logger.info(f"Successfully fetched and claimed {len(updated_event_orms)} raw events.")

        # Convert ORM objects to DTOs
        event_dtos = [
            RawEventDTO.from_orm(event_orm) for event_orm in updated_event_orms
        ]
        return event_dtos

    except Exception as e:
        logger.error(f"Error fetching and claiming raw events: {e}", exc_info=True)
        await db_session.rollback()
        raise # Re-raise the exception to be handled by the caller

# Example usage (for testing or a standalone script)
async def main_test():
    """Example usage function for testing the data fetcher."""
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting data fetcher test...")
    
    # It's important that the database is populated with some raw_events
    # where is_sentiment_processed = False for this test to fetch anything.

    async with get_db_session_context_manager() as session:
        try:
            fetched_events = await fetch_and_claim_raw_events(session, batch_size=5)
            if fetched_events:
                logger.info(f"Fetched {len(fetched_events)} events:")
                for event_dto in fetched_events:
                    logger.info(
                        f"  ID: {event_dto.id}, EventID: {event_dto.event_id}, Source: {event_dto.source}, "
                        f"Sentiment Processed: {event_dto.is_sentiment_processed} at {event_dto.sentiment_processed_at}"
                    )
            else:
                logger.info("No events were fetched in this run.")
        except Exception as e:
            logger.error(f"An error occurred during the test: {e}", exc_info=True)

if __name__ == "__main__":
    import asyncio
    # This is a basic example. In a real app, ensure the event loop is managed correctly.
    # Ensure your .env file is correctly set up for DB connection for this to run.
    # You would also need to have the raw_events table created (e.g. via Alembic migrations)
    # and populated with some test data.
    asyncio.run(main_test())
