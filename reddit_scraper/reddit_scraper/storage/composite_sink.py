"""Composite storage implementation for writing to multiple storage backends."""

import logging
import os
from typing import List, Set, Optional

from reddit_scraper.models.submission import SubmissionRecord
from reddit_scraper.storage.csv_sink import CsvSink, DataSink
from reddit_scraper.storage.sqlalchemy_postgres_sink import SQLAlchemyPostgresSink as PostgresSink
from reddit_scraper.storage.postgres_sink import PostgresSink as LegacyPostgresSink

# Import the appropriate PostgreSQL sink based on configuration
# Default to the new SQLAlchemy-based sink
USE_SQLALCHEMY = os.environ.get("USE_SQLALCHEMY", "true").lower() in ("true", "1", "yes")

if USE_SQLALCHEMY:
    logger = logging.getLogger(__name__)
    logger.warning("Using SQLAlchemy-based PostgreSQL sink with connection pooling")
else:
    logger = logging.getLogger(__name__)
    logger.warning("Using legacy PostgreSQL sink without connection pooling")

# Logger is initialized above when importing the appropriate PostgreSQL sink


class CompositeSink:
    """
    Composite sink that writes to multiple storage backends.
    
    This class implements the same interface as individual sinks
    but delegates operations to all configured sinks.
    """
    
    def __init__(self, configured_sinks: List[DataSink]):
        """
        Initialize the composite storage sink with pre-configured sink instances.
        
        Args:
            configured_sinks: A list of already initialized DataSink objects.
        """
        logger.info(f"Initializing CompositeSink with {len(configured_sinks)} pre-configured sinks.")
        
        self.sinks: List[DataSink] = configured_sinks
        
        self.csv_sink: Optional[CsvSink] = None
        self.postgres_sink: Optional[PostgresSink] = None 

        for sink in self.sinks:
            if isinstance(sink, CsvSink):
                self.csv_sink = sink
                logger.info(f"Identified CsvSink, path: {getattr(sink, 'csv_path', 'N/A')}")
            # PostgresSink is an alias, so this will catch both types
            elif isinstance(sink, (PostgresSink, LegacyPostgresSink)):
                self.postgres_sink = sink
                sink_type = "SQLAlchemyPostgresSink" if USE_SQLALCHEMY else "PostgresSink (legacy)"
                logger.info(f"Identified {sink_type}.")

        if not self.sinks:
            logger.warning("CompositeSink initialized with no data sinks.")
        elif not self.csv_sink:
             logger.warning("CompositeSink does not have a CsvSink. Ensure at least one sink is primary or handling is adjusted.")

    def append(self, records: List[SubmissionRecord]) -> int:
        """
        Append records to all configured storage backends.
        
        Args:
            records: List of submission records to append
            
        Returns:
            Number of records successfully appended to primary storage
        """
        if not records:
            logger.debug("No records to append to storage")
            return 0
            
        logger.info(f"Appending {len(records)} records to {len(self.sinks)} storage backends")
            
        # Track success count from primary sink (first in the list)
        primary_count = 0
        
        for i, sink in enumerate(self.sinks):
            sink_name = sink.__class__.__name__
            try:
                logger.info(f"Writing to {sink_name} (sink {i+1} of {len(self.sinks)})")
                count = sink.append(records)
                logger.info(f"Successfully wrote {count} records to {sink_name}")
                if i == 0:  # Primary sink (CSV)
                    primary_count = count
            except Exception as e:
                logger.error(f"Error in {sink_name}.append: {str(e)}")
                logger.error(f"Stack trace for {sink_name} error:", exc_info=True)
                if i == 0:  # If primary sink fails, report 0 successful inserts
                    primary_count = 0
        
        return primary_count
    
    def load_ids(self) -> Set[str]:
        """
        Load existing submission IDs from all storage backends.
        
        Returns:
            Combined set of submission IDs from all storage backends
        """
        all_ids = set()
        
        for sink in self.sinks:
            try:
                ids = sink.load_ids()
                all_ids.update(ids)
            except Exception as e:
                name = sink.__class__.__name__
                logger.error(f"Error in {name}.load_ids: {str(e)}")
        
        return all_ids
