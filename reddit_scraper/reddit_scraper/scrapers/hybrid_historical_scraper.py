#!/usr/bin/env python
"""
Hybrid historical scraper for Reddit finance subreddits.

This script combines the approaches of both targeted and deep historical scrapers
to maximize data collection from historical Reddit posts.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Set, Dict, Optional, Tuple, Any
from dateutil.relativedelta import relativedelta

from reddit_scraper.base_scraper import BaseScraper
from reddit_scraper.scraper_utils import search_by_term
from reddit_scraper.models.submission import SubmissionRecord

logger = logging.getLogger("hybrid_historical")

# Define specific search terms that were likely used in older posts
# These will help us find historical content
HISTORICAL_SEARCH_TERMS = [
    # High-priority terms most likely to get results
    "market",
    "stock",
    "invest",
    "trading",
    "finance",
    "money",
    "portfolio",
    "bull",
    "bear",
    "crash",
    "rally",
    "earnings",
    
    # Reddit-specific financial terms
    "yolo",
    "tendies",
    "stonks",
    "dd",
    "ape",
    "moon",
    "diamond hands",
    "paper hands",
    "wsb",
    
    # Major market events
    "financial crisis",
    "recession",
    "covid",
    "pandemic",
    "inflation",
    "interest rates",
    "fed",
    "housing",
    "unemployment",
]

# Define time periods to target (in reverse chronological order)
# Each period is (start_year, end_year, month_step)
TARGET_PERIODS = [
    (2023, 2025, 1),  # Recent data, 1-month steps
    (2020, 2023, 2),  # COVID era, 2-month steps
    (2015, 2020, 3),  # Pre-COVID, 3-month steps
    (2010, 2015, 4),  # Older data, 4-month steps
    (2008, 2010, 2),  # Financial crisis, 2-month steps
]

class HybridHistoricalScraper(BaseScraper):
    """Hybrid historical scraper for Reddit finance subreddits.
    
    Combines the approaches of both targeted and deep historical scrapers
    to maximize data collection from historical Reddit posts.
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the hybrid historical scraper.
        
        Args:
            config_path: Path to the configuration file
        """
        super().__init__(config_path)
        self.total_collected = 0

    async def run(self) -> int:
        """Run the hybrid historical scraper.
        
        Returns:
            Number of submissions collected
        """
        # Track total collected
        self.total_collected = 0
        
        # Process each time period
        for start_year, end_year, month_step in TARGET_PERIODS:
            logger.info(f"Processing period: {start_year} to {end_year}")
            period_total = 0
            
            # Create time windows for this period
            windows = []
            
            # Calculate total months in period
            total_months = (end_year - start_year) * 12
            
            # Process each month range within the period
            for month_offset in range(0, total_months, month_step):
                # Calculate start and end dates for this chunk using relativedelta
                # This properly handles month boundaries and leap years
                chunk_start = datetime(start_year, 1, 1, tzinfo=timezone.utc) + relativedelta(months=month_offset)
                chunk_end = chunk_start + relativedelta(months=month_step)
                
                # Don't go past the end year
                if chunk_end.year > end_year:
                    chunk_end = datetime(end_year, 1, 1, tzinfo=timezone.utc)
                
                # Skip if we're past the end
                if chunk_start >= chunk_end:
                    continue
                    
                windows.append((chunk_start, chunk_end))
            
            # Process each window
            for chunk_start, chunk_end in windows:
                logger.info(f"Processing chunk: {chunk_start.date()} to {chunk_end.date()}")
                
                # Process each subreddit
                for subreddit in self.config.subreddits:
                    # Process each search term
                    for term in HISTORICAL_SEARCH_TERMS:
                        records = await search_by_term(
                            self.collector, 
                            subreddit, 
                            term, 
                            self.seen_ids,
                            chunk_start,
                            chunk_end
                        )
                        
                        if records:
                            await self.store_records(records)
                            period_total += len(records)
                            self.total_collected += len(records)
                        
                        # Small delay to avoid rate limiting
                        await asyncio.sleep(1)
            
            logger.info(f"Collected {period_total} submissions from {start_year} to {end_year}")
            
            # Small delay between periods
            await asyncio.sleep(2)
        
        logger.info(f"Hybrid historical scraping complete! Collected {self.total_collected} total submissions")
        return self.total_collected


async def main():
    """Run the hybrid historical scraper."""
    # Import here to avoid circular imports
    from reddit_scraper.cli import setup_logging
    
    # Use centralized logging setup
    setup_logging(log_level="INFO")
    
    scraper = HybridHistoricalScraper()
    await scraper.execute()


if __name__ == "__main__":
    asyncio.run(main())
