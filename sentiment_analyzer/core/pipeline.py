"""
Main Pipeline Orchestrator for the Sentiment Analysis Service.

Coordinates the sequential execution of data fetching, preprocessing, 
sentiment analysis, and result processing for batches of events.
"""
import asyncio
import logging
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession # Only for type hinting if passed around

from sentiment_analyzer.config.settings import settings
from sentiment_analyzer.core.data_fetcher import fetch_and_claim_raw_events
from sentiment_analyzer.core.preprocessor import Preprocessor
from sentiment_analyzer.core.sentiment_analyzer_component import SentimentAnalyzerComponent
from sentiment_analyzer.core.result_processor import ResultProcessor
from sentiment_analyzer.models.dtos import RawEventDTO
# get_async_db_session is used by ResultProcessor internally if no session is passed.

logger = logging.getLogger(__name__)

class SentimentPipeline:
    """
    Orchestrates the sentiment analysis pipeline.
    """
    def __init__(self):
        """
        Initializes all necessary components for the pipeline.
        """
        logger.info("Initializing Sentiment Pipeline components...")
        self.preprocessor = Preprocessor()
        self.sentiment_analyzer = SentimentAnalyzerComponent()
        self.result_processor = ResultProcessor()
        self.batch_size = settings.DATA_FETCHER_BATCH_SIZE
        logger.info("Sentiment Pipeline components initialized.")

    async def process_single_event(self, raw_event: RawEventDTO) -> bool:
        """
        Processes a single raw event through the full analysis pipeline.

        Args:
            raw_event: The RawEventDTO to process.

        Returns:
            True if the event was successfully processed (including intentional skips),
            False if a critical error occurred and it was moved to DLQ.
        """
        try:
            logger.info(f"Starting processing for raw_event_id: {raw_event.id}, source: {raw_event.source}")

            # 1. Preprocess Text
            if raw_event.content is None or not raw_event.content.strip():
                logger.warning(f"Event {raw_event.id}: Content is empty or None. Moving to DLQ.")
                await self.result_processor.move_to_dead_letter_queue(
                    raw_event=raw_event,
                    error_message="Raw event content is empty or None.",
                    failed_stage="preprocessing_input_validation"
                )
                return False
            
            preprocessed_data = self.preprocessor.preprocess(raw_event.content)

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
            saved_result_orm = await self.result_processor.save_sentiment_result(
                raw_event=raw_event,
                preprocessed_data=preprocessed_data,
                sentiment_output=sentiment_output
            )

            if not saved_result_orm:
                logger.error(f"Event {raw_event.id}: Failed to save sentiment result. Moving to DLQ.")
                await self.result_processor.move_to_dead_letter_queue(
                    raw_event=raw_event,
                    error_message="Failed to save sentiment result to database.",
                    failed_stage="result_saving"
                )
                return False

            metrics_updated = await self.result_processor.update_sentiment_metrics(
                sentiment_result=saved_result_orm,
                raw_event_source=raw_event.source
            )
            if not metrics_updated:
                logger.warning(f"Event {raw_event.id}: Failed to update sentiment metrics for result_id {saved_result_orm.id}. This does not prevent event success.")
            
            logger.info(f"Successfully processed and saved sentiment for raw_event_id: {raw_event.id}")
            return True

        except Exception as e:
            logger.error(f"Critical error processing raw_event_id {raw_event.id}: {e}", exc_info=True)
            await self.result_processor.move_to_dead_letter_queue(
                raw_event=raw_event,
                error_message=f"Unhandled pipeline exception: {str(e)}",
                failed_stage="pipeline_event_processing"
            )
            return False

    async def run_pipeline_once(self) -> int:
        """
        Runs one iteration of the sentiment analysis pipeline: fetches a batch
        of events and processes them.

        Returns:
            int: The number of events fetched for processing. Returns 0 if no events were fetched.
        """
        logger.info(f"Starting pipeline run. Configured batch size: {self.batch_size}")
        
        # DataFetcher handles its own session for atomic fetch and claim.
        fetched_events: List[RawEventDTO] = await fetch_and_claim_raw_events(batch_size=self.batch_size)

        if not fetched_events:
            logger.info("No new events fetched to process in this iteration.")
            return 0
        
        event_count = len(fetched_events)
        logger.info(f"Fetched {event_count} events for processing.")

        # Process events concurrently
        # Each call to process_single_event is independent in terms of its DB transactions for saving results/DLQ.
        tasks = [self.process_single_event(event) for event in fetched_events]
        results = await asyncio.gather(*tasks, return_exceptions=False) # exceptions in tasks will stop gather if not handled in task

        successful_processing_count = sum(1 for res in results if res is True)
        failed_dlq_count = event_count - successful_processing_count
        
        logger.info(f"Pipeline run finished for batch of {event_count} events. "
                    f"Successfully processed (or skipped appropriately): {successful_processing_count}. "
                    f"Failed and moved to DLQ: {failed_dlq_count}.")
        return event_count

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
