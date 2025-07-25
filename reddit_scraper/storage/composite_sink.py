"""Composite storage implementation for writing to multiple storage backends."""

import logging
import os
from typing import List, Set, Optional

from reddit_scraper.models.submission import SubmissionRecord
from reddit_scraper.storage.csv_sink import CsvSink

# Import the appropriate PostgreSQL sink based on configuration
# Default to the new SQLAlchemy-based sink
USE_SQLALCHEMY = os.environ.get("USE_SQLALCHEMY", "true").lower() in ("true", "1", "yes")

if USE_SQLALCHEMY:
    from reddit_scraper.storage.sqlalchemy_postgres_sink import SQLAlchemyPostgresSink as PostgresSink
    logger = logging.getLogger(__name__)
    logger.warning("Using SQLAlchemy-based PostgreSQL sink with connection pooling")
else:
    from reddit_scraper.storage.postgres_sink import PostgresSink
    logger = logging.getLogger(__name__)
    logger.warning("Using legacy PostgreSQL sink without connection pooling")

# Logger is initialized above when importing the appropriate PostgreSQL sink


class CompositeSink:
    """
    Composite sink that writes to multiple storage backends.
    
    This class implements the same interface as individual sinks
    but delegates operations to all configured sinks.
    """
    
    def __init__(self, csv_path: str, use_postgres: bool = False):
        """
        Initialize the composite storage sink.
        
        Args:
            csv_path: Path to CSV file
            use_postgres: Whether to use PostgreSQL storage
        """
        # Add detailed logging for initialization
        logger.info(f"Initializing CompositeSink with csv_path={csv_path}, use_postgres={use_postgres}")
        
        self.sinks = []
        
        # Always add CSV sink as primary
        self.csv_sink = CsvSink(csv_path)
        self.sinks.append(self.csv_sink)
        logger.info("CSV sink added as primary storage")
        
        # Optionally add PostgreSQL sink
        self.postgres_sink = None
        if use_postgres:
            logger.warning("========== POSTGRESQL ENABLED ==========")
            logger.warning("Attempting to initialize PostgreSQL sink...")
            try:
                # Log environment variables for debugging
                import os
                pg_env_vars = {
                    "POSTGRES_HOST": os.environ.get("POSTGRES_HOST", "[NOT SET]"),
                    "POSTGRES_PORT": os.environ.get("POSTGRES_PORT", "[NOT SET]"),
                    "POSTGRES_DB": os.environ.get("POSTGRES_DB", "[NOT SET]"),
                    "POSTGRES_USER": os.environ.get("POSTGRES_USER", "[NOT SET]"),
                    "POSTGRES_PASSWORD": "[MASKED]" if os.environ.get("POSTGRES_PASSWORD") else "[NOT SET]",
                    "PG_HOST": os.environ.get("PG_HOST", "[NOT SET]"),
                    "PG_PORT": os.environ.get("PG_PORT", "[NOT SET]"),
                    "PG_DB": os.environ.get("PG_DB", "[NOT SET]"),
                    "PG_USER": os.environ.get("PG_USER", "[NOT SET]"),
                    "PG_PASSWORD": "[MASKED]" if os.environ.get("PG_PASSWORD") else "[NOT SET]",
                    "USE_POSTGRES": os.environ.get("USE_POSTGRES", "[NOT SET]")
                }
                logger.warning(f"PostgreSQL environment variables: {pg_env_vars}")
                
                # Initialize the appropriate PostgreSQL sink based on configuration
                self.postgres_sink = PostgresSink()
                
                sink_type = "SQLAlchemy" if USE_SQLALCHEMY else "Legacy"
                logger.warning(f"{sink_type} PostgreSQL sink initialized successfully!")
                
                self.sinks.append(self.postgres_sink)
                logger.warning("PostgreSQL sink added to active sinks")
                
                if USE_SQLALCHEMY:
                    logger.warning("Using connection pooling for better performance")
                
                logger.warning("========== POSTGRESQL SETUP COMPLETE ==========")
            except Exception as e:
                logger.error(f"Failed to initialize PostgreSQL sink: {str(e)}")
                logger.error("PostgreSQL initialization error details:", exc_info=True)
                logger.warning("Continuing with CSV storage only")
        else:
            logger.warning("========== POSTGRESQL DISABLED ==========")
            logger.warning("PostgreSQL storage is DISABLED by configuration! To enable, check 'postgres.enabled' in config.yaml")
    
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
