"""
Main Pipeline Orchestrator for the Sentiment Analysis Service.

Coordinates the sequential execution of data fetching, preprocessing, 
sentiment analysis, and result processing for batches of events.
"""
import asyncio
import json
import logging
from typing import List, Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession # Only for type hinting if passed around

from sentiment_analyzer.config.settings import settings
from sentiment_analyzer.core.data_fetcher import fetch_and_claim_raw_events
from sentiment_analyzer.core.preprocessor import Preprocessor
from sentiment_analyzer.core.sentiment_analyzer_component import SentimentAnalyzerComponent
from sentiment_analyzer.core.result_processor import ResultProcessor
from sentiment_analyzer.models.dtos import RawEventDTO
from sentiment_analyzer.models.sentiment_result_orm import SentimentResultORM
from sentiment_analyzer.models.dead_letter_event_orm import DeadLetterEventORM
from sentiment_analyzer.utils.db_session import get_db_session_context_manager
# get_async_db_session is used by ResultProcessor internally if no session is passed.

logger = logging.getLogger(__name__)

class SentimentPipeline:
    """
    Orchestrates the sentiment analysis pipeline.
    """
    def __init__(self, db_session: Optional[AsyncSession] = None):
        """
        Initializes all necessary components for the pipeline.
        """
        logger.info("Initializing Sentiment Pipeline components...")
        self._shared_session = db_session
        self.preprocessor = Preprocessor()
        self.sentiment_analyzer = SentimentAnalyzerComponent()
        self.result_processor = ResultProcessor(session=self._shared_session)
        # Use the configured batch size; maintain backward-compat alias for tests.
        self.batch_size = getattr(settings, "EVENT_FETCH_BATCH_SIZE", 100)
        logger.info("Sentiment Pipeline components initialized.")

    async def process_single_event(
        self, raw_event: RawEventDTO
    ) -> Union[SentimentResultORM, DeadLetterEventORM, None]:
        """
        Processes a single raw event: analyzes sentiment and saves the result.
        Manages its own database session to ensure transactional integrity per event.

        Args:
            raw_event: The raw event to process.

        Returns:
            The ORM object for the saved result or dead-letter event, or None on failure.
        """
        logger.info(
            f"Starting processing for raw_event_id: {raw_event.id}, source: {raw_event.source}"
        )
        try:
            # 1. Preprocess Text
            text_to_process = ""
            # First, try to get text from raw_event.content
            if isinstance(raw_event.content, dict):
                text_to_process = raw_event.content.get("text", "")
                logger.debug(f"Event {raw_event.id}: Attempted to extract text from raw_event.content (dict). Found: '{bool(text_to_process)}'")
            elif isinstance(raw_event.content, str):
                try:
                    # Attempt to parse the string as JSON
                    content_json = json.loads(raw_event.content)
                    if isinstance(content_json, dict):
                        text_to_process = content_json.get("text", "")
                        logger.debug(f"Event {raw_event.id}: Successfully parsed raw_event.content as JSON dict. Found text: '{bool(text_to_process)}'")
                    else:
                        # The JSON is valid but not a dict, treat the original string as text
                        text_to_process = raw_event.content
                        logger.debug(f"Event {raw_event.id}: Parsed raw_event.content as JSON, but it's not a dict. Using raw string.")
                except json.JSONDecodeError:
                    # Not a JSON string, treat as plain text
                    text_to_process = raw_event.content
                    logger.debug(f"Event {raw_event.id}: raw_event.content is a non-JSON string. Using raw string.")
            else:
                logger.debug(f"Event {raw_event.id}: raw_event.content is neither dict nor str (type: {type(raw_event.content)}). Will check payload.")

            # If text is still empty or only whitespace, try to get it from raw_event.payload
            if not text_to_process.strip():
                logger.debug(f"Event {raw_event.id}: Text from raw_event.content is empty. Checking raw_event.payload.")
                if isinstance(raw_event.payload, dict):
                    text_to_process = raw_event.payload.get("text", "")
                    logger.debug(f"Event {raw_event.id}: Attempted to extract text from raw_event.payload (dict). Found: '{bool(text_to_process)}'")
                else:
                    logger.debug(f"Event {raw_event.id}: raw_event.payload is not a dict (type: {type(raw_event.payload)}). Cannot extract text.")
            
            # Validate extracted text
            if not text_to_process.strip():
                logger.warning(f"Event {raw_event.id}: Extracted text content is empty or None after checking content and payload. Moving to DLQ.")
                async with get_db_session_context_manager() as session:
                    return await self.result_processor.move_to_dead_letter_queue(
                        raw_event=raw_event,
                        error_message="Extracted text content is empty or None after checking content and payload.",
                        failed_stage="preprocessing_input_validation",
                        db_session=session,
                    )

            logger.info(f"Event {raw_event.id}: Successfully extracted text for processing: '{text_to_process[:100]}...'" )
            preprocessed_data = self.preprocessor.preprocess(text_to_process)

            if not preprocessed_data.is_target_language:
                logger.info(f"Event {raw_event.id}: Language '{preprocessed_data.detected_language_code}' is not target '{self.preprocessor.target_language}'. Skipping sentiment analysis.")
                # Optionally, save a record indicating it was skipped due to language.
                # For now, consider this a successful 'processing' of the event (by skipping).
                # If this state needs to be recorded, ResultProcessor could have a method for it.
                return True 

            if not preprocessed_data.cleaned_text:
                logger.warning(f"Event {raw_event.id}: Preprocessing resulted in empty text for target language '{preprocessed_data.detected_language_code}'. Defaulting sentiment or moving to DLQ.")
                # Current Preprocessor/SentimentAnalyzer returns default neutral. If this is an error state:
                # await self.result_processor.move_to_dead_letter_queue(
                #     raw_event=raw_event,
                #     error_message="Preprocessing resulted in empty cleaned text for target language.",
                #     failed_stage="preprocessing_output_validation"
                # )
                # return False
                # For now, we let it flow to sentiment analyzer which gives default neutral.

            # 2. Perform Sentiment Analysis
            logger.debug(f"Event {raw_event.id}: Performing sentiment analysis on: '{preprocessed_data.cleaned_text[:100]}...'" )
            sentiment_output = self.sentiment_analyzer.analyze(preprocessed_data.cleaned_text)
            logger.debug(f"Event {raw_event.id}: Sentiment analysis result: {sentiment_output.label} (Conf: {sentiment_output.confidence:.2f})")

            # 3. Save Result and Update Metrics
            # ResultProcessor methods handle their own session management if None is passed.
            async with get_db_session_context_manager() as session:
                saved_result_orm = await self.result_processor.save_sentiment_result(
                    raw_event=raw_event,
                    preprocessed_data=preprocessed_data,
                    sentiment_output=sentiment_output,
                    db_session=session
                )

                if not saved_result_orm:
                    logger.error(f"Event {raw_event.id}: Failed to save sentiment result. Moving to DLQ.")
                    # The save_sentiment_result already rolled back, so we just move to DLQ
                    return await self.result_processor.move_to_dead_letter_queue(
                        raw_event=raw_event,
                        error_message="Failed to save sentiment result to database",
                        failed_stage="save_sentiment_result",
                        db_session=session, # Use the same session for the DLQ entry
                    )

                await self.result_processor.update_sentiment_metrics(
                    sentiment_result=saved_result_orm,
                    raw_event_source=raw_event.source,
                    db_session=session,
                )

                await session.commit() # Commit the transaction for this single event
                logger.info(f"Successfully processed and saved sentiment for raw_event_id: {raw_event.id}")
                return saved_result_orm

        except Exception as e:
            logger.critical(
                f"Critical error processing raw_event_id {raw_event.id}: {e}", exc_info=True
            )
            # When a critical error occurs, move the event to the dead-letter queue
            async with get_db_session_context_manager() as dlq_session:
                return await self.result_processor.move_to_dead_letter_queue(
                    raw_event=raw_event,
                    error_message=str(e),
                    failed_stage="process_single_event",
                    db_session=dlq_session,
                )

    async def run_pipeline_once(self) -> int:
        """
        Runs one cycle of the sentiment analysis pipeline.
        1. Fetches and claims a batch of raw events in a transaction.
        2. Concurrently processes each event in its own transaction.
        3. Logs the outcome of the batch processing.

        Returns:
            The number of events successfully processed.
        """
        events_attempted = 0
        fetched_events: List[RawEventDTO] = []
        results = []

        # Step 1: Fetch and claim events in a single, short transaction.
        try:
            async with get_db_session_context_manager() as session:
                fetched_events = await fetch_and_claim_raw_events(
                    db_session=session, batch_size=self.batch_size
                )
                await session.commit()

            if not fetched_events:
                logger.info("No new events to process in this cycle.")
                return 0

            events_attempted = len(fetched_events)
            logger.info(f"Fetched and claimed {events_attempted} events to process.")

            # Step 2: Process each event concurrently, each in its own transaction.
            tasks = [self.process_single_event(event) for event in fetched_events]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.critical(f"An unexpected error occurred in the pipeline fetch stage: {e}", exc_info=True)
            # If fetching fails, we can't do much else, so we return.
            return 0

        # Step 3: Log the results of the processing batch.
        successful_count = sum(1 for r in results if r and not isinstance(r, (Exception, BaseException)))
        failed_count = events_attempted - successful_count

        logger.info(
            f"Pipeline run finished. Processed: {successful_count}, Failed: {failed_count}"
        )

        return successful_count

async def main_loop():
    """
    Main application loop to run the pipeline continuously.
    """
    pipeline = SentimentPipeline()
    run_interval_seconds = settings.PIPELINE_RUN_INTERVAL_SECONDS
    
    logger.info(f"Sentiment Analysis Pipeline starting. Run interval: {run_interval_seconds}s")
    
    try:
        while True:
            logger.info("Starting new pipeline processing cycle.")
            events_attempted = await pipeline.run_pipeline_once()
            
            # Determine sleep duration
            # If a full batch was processed, there might be more data, so a shorter sleep could be an option.
            # For simplicity, using a fixed interval unless no events were found.
            current_sleep_interval = run_interval_seconds
            if events_attempted == 0:
                logger.info(f"No events found. Sleeping for {current_sleep_interval} seconds.")
            else:
                logger.info(f"Processed a batch of {events_attempted} events. Sleeping for {current_sleep_interval} seconds.")
            
            await asyncio.sleep(current_sleep_interval)
            
    except asyncio.CancelledError:
        logger.info("Pipeline main loop cancelled. Shutting down.")
    except Exception as e:
        logger.critical(f"Critical error in pipeline main_loop: {e}. Pipeline will exit.", exc_info=True)
        # In a real deployment, this might trigger alerts or a restart mechanism.
        raise # Re-raise to allow process managers to handle it.

if __name__ == "__main__":
    # This setup is for standalone execution.
    # In a larger application (e.g., FastAPI), pipeline might be a background task.
    from pathlib import Path
    from dotenv import load_dotenv
    # Assuming setup_logging is available and configured correctly.
    # It should be called once at the application's entry point.
    try:
        from sentiment_analyzer.utils.logging_config import setup_logging
        setup_logging() # Initialize logging from config
    except ImportError:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logger.warning("Could not import setup_logging from utils. Using basicConfig for logging.")

    SERVICE_ROOT_DIR = Path(__file__).resolve().parent.parent # sentiment_analyzer directory
    env_path = SERVICE_ROOT_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"Loaded .env file from: {env_path}")
    else:
        logger.info("No .env file found. Relying on environment variables or defaults.")

    logger.info("Starting Sentiment Analysis Pipeline (standalone execution)...")
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logger.info("Sentiment Analysis Pipeline execution stopped by user (KeyboardInterrupt).")
    except Exception as e:
        logger.critical(f"Sentiment Analysis Pipeline failed to start or crashed: {e}", exc_info=True)
