#!/usr/bin/env python
"""
Deep historical scraper for Reddit finance subreddits.

This script targets specific historical time periods to retrieve posts
from the early days of each subreddit.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Set, Dict, Optional, Tuple, Any

from reddit_scraper.base_scraper import BaseScraper
from reddit_scraper.scraper_utils import search_by_date_range, search_by_term, create_time_windows
from reddit_scraper.models.submission import SubmissionRecord

logger = logging.getLogger("deep_historical_scraper")

# Define subreddit creation dates (approximate)
# These are the earliest dates we'll try to scrape from
SUBREDDIT_CREATION_DATES = {
    "wallstreetbets": datetime(2012, 1, 31, tzinfo=timezone.utc),  # Created Jan 31, 2012
    "stocks": datetime(2008, 3, 1, tzinfo=timezone.utc),           # Early Reddit finance sub
    "investing": datetime(2008, 9, 1, tzinfo=timezone.utc),        # Early Reddit finance sub
    "StockMarket": datetime(2010, 7, 1, tzinfo=timezone.utc),      # Estimate
    "options": datetime(2010, 1, 1, tzinfo=timezone.utc),          # Estimate
    "finance": datetime(2008, 1, 1, tzinfo=timezone.utc),          # Early Reddit sub
    "UKInvesting": datetime(2011, 1, 1, tzinfo=timezone.utc),      # Estimate
}

# Define time periods to target (in reverse chronological order)
# Each period is (start_year, end_year)
TARGET_PERIODS = [
    (2023, 2025),  # 2023-2025 (Most recent data)
    (2021, 2023),  # 2021-2023 (Post-COVID recovery)
    (2020, 2021),  # 2020-2021 (COVID market crash)
    (2018, 2020),  # 2018-2020 (Pre-COVID)
    (2016, 2018),  # 2016-2018
    (2014, 2016),  # 2014-2016
    (2012, 2014),  # 2012-2014
    (2010, 2012),  # 2010-2012
    (2008, 2010),  # 2008-2010 (Financial crisis)
]


class DeepHistoricalScraper(BaseScraper):
    """Deep historical scraper for Reddit finance subreddits.
    
    Targets specific time periods to retrieve posts from the early days of each subreddit.
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the deep historical scraper.
        
        Args:
            config_path: Path to the configuration file
        """
        super().__init__(config_path)
        self.total_collected = 0

    async def scrape_time_period(
        self,
        subreddit: str,
        start_date: datetime,
        end_date: datetime,
        window_days: int = 7,  # Reduced window size for more granular fetching
    ) -> int:
        """
        Scrape a specific time period for a subreddit.
        
        Args:
            subreddit: Subreddit name
            start_date: Start date for the period
            end_date: End date for the period
            window_days: Window size in days
            
        Returns:
            Number of posts collected
        """
        # Skip if subreddit didn't exist during this period
        creation_date = SUBREDDIT_CREATION_DATES.get(subreddit)
        if creation_date and creation_date > end_date:
            logger.info(f"Skipping r/{subreddit} for period {start_date.date()} to {end_date.date()} - subreddit didn't exist yet")
            return 0
        
        logger.info(f"Scraping r/{subreddit} from {start_date.date()} to {end_date.date()}")
        
        # Calculate number of windows needed
        period_days = (end_date - start_date).days
        num_windows = max(1, period_days // window_days)
        
        # Limit the number of windows to avoid excessive API calls
        num_windows = min(num_windows, 12)  # Process at most 12 windows per period
        
        # Track total collected
        period_collected = 0
        
        # Create time windows
        windows = []
        for i in range(num_windows):
            # Calculate window end (start from the end and move backward)
            window_end = end_date - timedelta(days=i * window_days)
            window_start = window_end - timedelta(days=window_days)
            
            # Ensure we don't go before the start date
            if window_start < start_date:
                window_start = start_date
                
            # Skip if window is invalid
            if window_start >= window_end:
                continue
                
            windows.append((window_start, window_end))
        
        # Process each window
        for window_start, window_end in windows:
            logger.info(f"Processing window {window_start.date()} to {window_end.date()} for r/{subreddit}")
            
            # Search by date range
            records = await search_by_date_range(
                self.collector,
                subreddit,
                window_start,
                window_end,
                self.seen_ids
            )
            
            # If no results and window is not too small, try with keywords
            if not records and (window_end - window_start).days >= 3:
                logger.info("No results for timestamp search, trying keyword search")
                
                # Use finance-related search terms
                search_terms = ["market", "stock", "invest", "trading", "finance"]
                
                for term in search_terms:
                    # Try search with term and date range
                    term_records = await search_by_term(
                        self.collector,
                        subreddit,
                        term,
                        self.seen_ids,
                        window_start,
                        window_end
                    )
                    
                    if term_records:
                        records.extend(term_records)
                        logger.info(f"Found {len(term_records)} posts with term '{term}'")
                        break
            
            if records:
                await self.store_records(records)
                period_collected += len(records)
                logger.info(f"Collected {len(records)} submissions from r/{subreddit} for window ending {window_end.date()}")
            else:
                logger.info(f"No submissions from r/{subreddit} for window ending {window_end.date()}")
                
            # Small delay to avoid rate limiting
            await asyncio.sleep(1)
        
        return period_collected
    
    async def run(self) -> int:
        """Run the deep historical scraper.
        
        Returns:
            Number of submissions collected
        """
        # Track total collected
        self.total_collected = 0
        
        # Process each time period
        for start_year, end_year in TARGET_PERIODS:
            start_date = datetime(start_year, 1, 1, tzinfo=timezone.utc)
            end_date = datetime(end_year, 1, 1, tzinfo=timezone.utc)
            
            logger.info(f"Processing period: {start_year} to {end_year}")
            period_total = 0
            
            # Process each subreddit for this period
            for subreddit in self.config.subreddits:
                collected = await self.scrape_time_period(
                    subreddit,
                    start_date,
                    end_date,
                    window_days=self.config.window_days,
                )
                period_total += collected
            
            logger.info(f"Collected {period_total} submissions from {start_year} to {end_year}")
            self.total_collected += period_total
            
            # Small delay between periods
            await asyncio.sleep(2)
        
        logger.info(f"Deep historical scraping complete! Collected {self.total_collected} total submissions")
        return self.total_collected


async def main():
    """Run the deep historical scraper."""
    # Import here to avoid circular imports
    from reddit_scraper.cli import setup_logging
    
    # Use centralized logging setup
    setup_logging(log_level="INFO")
    
    scraper = DeepHistoricalScraper()
    await scraper.execute()


if __name__ == "__main__":
    asyncio.run(main())
