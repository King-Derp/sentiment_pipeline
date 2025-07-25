"""Base scraper class for Reddit data collection.

This module provides a common base class for all Reddit scrapers to reduce code duplication
and standardize the scraping process.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import List, Set, Dict, Optional, Tuple, Any

from reddit_scraper.collector.collector import SubmissionCollector
from reddit_scraper.config import Config
from reddit_scraper.models.submission import SubmissionRecord
from reddit_scraper.storage.composite_sink import CompositeSink
from reddit_scraper.collector.error_handler import ConsecutiveErrorTracker
from reddit_scraper.collector.rate_limiter import RateLimiter
from reddit_scraper.reddit_client import RedditClient

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base class for all Reddit scrapers."""
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the base scraper with configuration.
        
        Args:
            config_path: Path to the configuration file
        """
        self.config_path = config_path
        logger.warning("========== SCRAPER INITIALIZATION BEGIN ==========")
        
        # Log environment variables to diagnose potential issues
        import os
        env_vars = {
            "PG_HOST": os.environ.get("PG_HOST", "[NOT SET]"),
            "PG_PORT": os.environ.get("PG_PORT", "[NOT SET]"),
            "PG_DB": os.environ.get("PG_DB", "[NOT SET]"),
            "PG_USER": os.environ.get("PG_USER", "[NOT SET]"),
            "PG_PASSWORD": "[MASKED]" if os.environ.get("PG_PASSWORD") else "[NOT SET]",
            "USE_POSTGRES": os.environ.get("USE_POSTGRES", "[NOT SET]"),
            "LOGLEVEL": os.environ.get("LOGLEVEL", "[NOT SET]")
        }
        logger.warning(f"Environment variables: {env_vars}")
        
        # Load the configuration
        self.config = Config.from_files(config_path)
        logger.warning("Configuration loaded from file")
        
        # Force set PostgreSQL configuration from environment if available
        # This ensures we're using the Docker environment variables
        if hasattr(self.config, 'postgres'):
            # Update PostgreSQL config from environment variables
            pg_config = self.config.postgres
            
            # Override with environment variables if available
            pg_host = os.environ.get("PG_HOST")
            if pg_host:
                pg_config.host = pg_host
                logger.warning(f"Using PG_HOST from environment: {pg_host}")
                
            pg_port = os.environ.get("PG_PORT")
            if pg_port:
                pg_config.port = int(pg_port)
                logger.warning(f"Using PG_PORT from environment: {pg_port}")
                
            pg_db = os.environ.get("PG_DB")
            if pg_db:
                pg_config.database = pg_db
                logger.warning(f"Using PG_DB from environment: {pg_db}")
                
            pg_user = os.environ.get("PG_USER")
            if pg_user:
                pg_config.user = pg_user
                logger.warning(f"Using PG_USER from environment: {pg_user}")
                
            pg_password = os.environ.get("PG_PASSWORD")
            if pg_password:
                pg_config.password = pg_password
                logger.warning("Using PG_PASSWORD from environment")
                
            # Check USE_POSTGRES environment variable
            use_postgres_env = os.environ.get("USE_POSTGRES")
            if use_postgres_env is not None:
                pg_config.enabled = use_postgres_env.lower() == "true"
                logger.warning(f"Using USE_POSTGRES from environment: {use_postgres_env}")
            
            # Log final PostgreSQL configuration
            logger.warning(f"PostgreSQL config: {pg_config}")
            logger.warning(f"PostgreSQL config type: {type(pg_config)}")
            logger.warning(f"PostgreSQL enabled: {pg_config.enabled}")
            logger.warning(f"PostgreSQL host: {pg_config.host}")
            logger.warning(f"PostgreSQL port: {pg_config.port}")
            logger.warning(f"PostgreSQL database: {pg_config.database}")
            
            # Determine if PostgreSQL should be enabled
            use_postgres = pg_config.enabled
            logger.warning(f"Will use PostgreSQL: {use_postgres}")
        else:
            logger.error("CRITICAL ERROR: PostgreSQL configuration is missing in config!")
            use_postgres = False
        
        # Create composite sink with detailed logging
        try:
            logger.warning(f"Creating CompositeSink with csv_path={self.config.csv_path}, use_postgres={use_postgres}")
            self.data_sink = CompositeSink(
                csv_path=self.config.csv_path,
                use_postgres=use_postgres
            )
            logger.warning("CompositeSink created successfully")
        except Exception as e:
            logger.error(f"ERROR creating CompositeSink: {str(e)}")
            logger.error("CompositeSink creation stack trace:", exc_info=True)
            # Fall back to CSV-only sink
            logger.warning("Falling back to CSV-only storage due to error")
            self.data_sink = CompositeSink(csv_path=self.config.csv_path, use_postgres=False)
        
        logger.warning("========== SCRAPER INITIALIZATION COMPLETE ==========")
        
        self.reddit_client = None
        self.rate_limiter = None
        self.error_tracker = None
        self.collector = None
        self.seen_ids = set()
        
    async def initialize(self) -> None:
        """Initialize the scraper components."""
        # Create components
        self.reddit_client = RedditClient(self.config)
        self.rate_limiter = RateLimiter(self.config.rate_limit)
        self.error_tracker = ConsecutiveErrorTracker(self.config.failure_threshold)
        
        # Initialize Reddit client
        await self.reddit_client.initialize()
        
        # Create collector
        self.collector = SubmissionCollector(self.reddit_client, self.rate_limiter, self.error_tracker)
        
        # Load existing IDs
        self.seen_ids = self.data_sink.load_ids()
        logger.info(f"Loaded {len(self.seen_ids)} existing submission IDs")
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.reddit_client:
            await self.reddit_client.close()
    
    @abstractmethod
    async def run(self) -> int:
        """Run the scraper.
        
        Returns:
            Number of submissions collected
        """
        pass
    
    async def store_records(self, records: List[SubmissionRecord]) -> None:
        """Store records and update seen IDs.
        
        Args:
            records: List of submission records to store
        """
        if not records:
            return
            
        # Add new IDs to seen set
        self.seen_ids.update(r["id"] for r in records)
        
        # Store records
        self.data_sink.append(records)
        
        logger.info(f"Stored {len(records)} new records")
    
    async def execute(self) -> int:
        """Execute the scraper with proper initialization and cleanup.
        
        Returns:
            Number of submissions collected
        """
        total_collected = 0
        
        try:
            await self.initialize()
            total_collected = await self.run()
            logger.info(f"Scraping complete! Collected {total_collected} total submissions")
            
        finally:
            await self.cleanup()
            
        return total_collected
