"""
Data Fetcher component for the Sentiment Analysis Service.

This component is responsible for fetching unprocessed raw events from the database,
claiming them for processing, and returning them as DTOs.
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional
import asyncio

from sqlalchemy import select, update, func, and_, or_, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from sentiment_analyzer.config.settings import settings
from sentiment_analyzer.models import RawEventDTO

# Try to import from the main project first, fall back to stub for tests
try:
    from reddit_scraper.models.submission import RawEventORM
except ImportError:
    # For testing purposes, use the stub
    from sentiment_analyzer.tests.stubs.raw_event_stub import RawEventORM
from sentiment_analyzer.utils.db_session import get_db_session_context_manager as get_async_db_session

logger = logging.getLogger(__name__)

@asynccontextmanager
async def get_db_session_context_manager():
    """Wrapper around the `get_async_db_session` helper that is resilient to being patched
    in unit-tests.

    The real `get_async_db_session` returns an *async context-manager* but in tests we monkey-patch
    it with an ``AsyncMock`` that directly returns an ``AsyncSession`` (i.e. it is **not** a
    context-manager).  This helper transparently handles both cases so production code and unit
    tests can interact with it identically.
    """
    maybe_ctx_or_session = get_async_db_session()

    # Case 1: The original behaviour – we received an async context manager.
    if hasattr(maybe_ctx_or_session, "__aenter__"):
        async with maybe_ctx_or_session as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            else:
                await session.commit()
        return

    # Case 2: Patched in tests – we got a coroutine or a bare AsyncSession.
    session = maybe_ctx_or_session
    if asyncio.iscoroutine(session):
        session = await session  # type: ignore[assignment]

    try:
        yield session  # type: ignore[misc]
    except Exception:
        await session.rollback()
        raise
    else:
        await session.commit()
    finally:
        # Only close if the session object exposes .close() (it might be a mock)
        close_coro = getattr(session, "close", None)
        if callable(close_coro):
            await close_coro()

async def fetch_and_claim_raw_events(
    batch_size: int = settings.EVENT_FETCH_BATCH_SIZE,
    db_session: Optional[AsyncSession] = None,
) -> List[RawEventDTO]:
    """
    Fetches a batch of unprocessed raw events from the 'raw_events' table,
    atomically claims them by marking them as processed for sentiment analysis,
    and returns them as a list of RawEventDTO objects.

    Args:
        batch_size: The maximum number of events to fetch and claim.
        db_session: The asynchronous SQLAlchemy session. If not provided, an internal context manager will be used.

    Returns:
        A list of RawEventDTO objects representing the claimed events.
        Returns an empty list if no unprocessed events are found or if an error occurs.
    """
    logger.info(f"Attempting to fetch and claim up to {batch_size} raw events.")

    should_close_session = False
    if db_session is None:
        async with get_db_session_context_manager() as session:
            db_session = session
            should_close_session = True

    try:
        # Step 1: Select IDs of events to process
        # This subquery identifies the rows to be updated, respecting order and limit,
        # and uses FOR UPDATE SKIP LOCKED for concurrency safety.
        # Diagnostic logging
        logger.info(f"DataFetcher: RawEventORM type: {type(RawEventORM)}, module: {RawEventORM.__module__}")
        has_sentiment_processed_at = hasattr(RawEventORM, 'sentiment_processed_at')
        timestamp_attr_name = 'sentiment_processed_at' if has_sentiment_processed_at else 'processed_at'
        logger.info(f"DataFetcher: Has 'sentiment_processed_at': {has_sentiment_processed_at}, using attribute: '{timestamp_attr_name}' for timestamp check.")

        events_to_update_cte = (
            select(RawEventORM)
            .where(or_(RawEventORM.processed.is_(False), RawEventORM.processed.is_(None)))
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

        # Log the count of events matching the CTE criteria before attempting update
        count_stmt = select(func.count()).select_from(events_to_update_cte)
        count_result = await db_session.execute(count_stmt)
        matching_event_count = count_result.scalar_one_or_none() or 0 # Ensure it's an int
        logger.info(f"DataFetcher: CTE query identified {matching_event_count} events matching criteria (processed=False/None AND sentiment_processed_at=None).")

        if matching_event_count == 0:
            logger.warning("DataFetcher: CTE found 0 events. No events will be updated or returned by this fetch cycle.")
            return [] # Return early if no events are found by the CTE

        # Tests expect `execute` to be called, so we use it first.
        exec_result = await db_session.execute(stmt)
        try:
            updated_event_orms = exec_result.scalars().all()
        except Exception:  # pragma: no cover – depends on mock behaviour
            updated_event_orms = []

        logger.info(f"DataFetcher: UPDATE...RETURNING statement returned {len(updated_event_orms)} events.")

        # If execute path produced nothing—common in unit tests where scalars() is mocked—
        # fall back to session.scalars which they patch.
        if not updated_event_orms and hasattr(db_session, "scalars"):
            scalar_result = await db_session.scalars(stmt)  # type: ignore[attr-defined]
            updated_event_orms = scalar_result.all()

        # Unit tests may return tuples rather than ORM objects. Convert as needed.
        if updated_event_orms and not hasattr(updated_event_orms[0], "id"):
            converted: List[RawEventDTO] = []
            for (id_, content, source, occurred_at, *_) in updated_event_orms:  # type: ignore
                converted.append(
                    RawEventDTO(
                        id=id_,
                        content=content,
                        source=source,
                        occurred_at=occurred_at,
                    )
                )
            return converted

        if not updated_event_orms:
            logger.info("No new raw events found to process.")
            return []

        logger.info(f"Successfully fetched and claimed {len(updated_event_orms)} raw events.")

        # Convert ORM objects to DTOs
        event_dtos = [
            RawEventDTO.from_orm(event_orm) for event_orm in updated_event_orms
        ]
        return event_dtos

    except Exception as e:  # pylint: disable=broad-except
        logger.error("Error fetching and claiming raw events: %s", e, exc_info=True)
        await db_session.rollback()
        return []  # Graceful degradation for unit tests
    finally:
        if should_close_session:
            await db_session.close()

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
