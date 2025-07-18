#!/usr/bin/env python
"""
Pushshift historical scraper for Reddit finance subreddits.

This script uses the Pushshift API to retrieve historical posts from
the early days of each finance subreddit, going back to their creation.
"""

import asyncio
import datetime
import logging
import os
from typing import List, Dict, Any, Optional, Set

import aiohttp
from dateutil.relativedelta import relativedelta

from reddit_scraper.base_scraper import BaseScraper
from reddit_scraper.config import Config
from reddit_scraper.storage.csv_sink import CsvSink
from reddit_scraper.models.submission import SubmissionRecord

logger = logging.getLogger("pushshift_scraper")

# Define subreddit creation dates (approximate)
SUBREDDIT_CREATION_DATES = {
    "wallstreetbets": datetime.datetime(2012, 1, 31, tzinfo=datetime.timezone.utc),  # Created Jan 31, 2012
    "stocks": datetime.datetime(2008, 3, 1, tzinfo=datetime.timezone.utc),           # Early Reddit finance sub
    "investing": datetime.datetime(2008, 9, 1, tzinfo=datetime.timezone.utc),        # Early Reddit finance sub
    "StockMarket": datetime.datetime(2010, 7, 1, tzinfo=datetime.timezone.utc),      # Estimate
    "options": datetime.datetime(2010, 1, 1, tzinfo=datetime.timezone.utc),          # Estimate
    "finance": datetime.datetime(2008, 1, 1, tzinfo=datetime.timezone.utc),          # Early Reddit sub
    "UKInvesting": datetime.datetime(2011, 1, 1, tzinfo=datetime.timezone.utc),      # Estimate
}

# Define time periods to target (in reverse chronological order)
TARGET_PERIODS = [
    # Year ranges with 3-month chunks for more manageable API calls
    (2018, 2020),  # Pre-COVID
    (2016, 2018),  # 2016-2018
    (2014, 2016),  # 2014-2016
    (2012, 2014),  # 2012-2014
    (2010, 2012),  # 2010-2012
    (2008, 2010),  # 2008-2010 (Financial crisis)
    (2006, 2008),  # 2006-2008 (Early Reddit)
]

# Pushshift API endpoint
PUSHSHIFT_API = "https://api.pushshift.io/reddit/search/submission"


class PushshiftHistoricalScraper(BaseScraper):
    """Pushshift historical scraper for Reddit finance subreddits.
    
    Uses the Pushshift API to retrieve historical posts from the early days of each subreddit.
    """
    
    def __init__(self, config: Config):
        """Initialize the Pushshift historical scraper."""
        super().__init__(config)
        self.total_collected = 0
        self.session: Optional[aiohttp.ClientSession] = None

    async def initialize(self) -> None:
        """Initialize the scraper components."""
        await super().initialize()
        # Create aiohttp session for Pushshift API
        self.session = aiohttp.ClientSession()
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        # Close aiohttp session
        if self.session:
            await self.session.close()
        
        # Call parent cleanup to close the Reddit client
        await super().cleanup()
    
    async def fetch_pushshift_data(
        self,
        subreddit: str,
        after: int,
        before: int,
        size: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch data from Pushshift API.
        
        Args:
            subreddit: Subreddit name
            after: Start timestamp (Unix epoch)
            before: End timestamp (Unix epoch)
            size: Number of results to return (max 100)
            
        Returns:
            List of submission data
        """
        params = {
            "subreddit": subreddit,
            "after": after,
            "before": before,
            "size": size,
            "sort": "asc",
            "sort_type": "created_utc",
        }
        
        try:
            async with self.session.get(PUSHSHIFT_API, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data", [])
                else:
                    logger.warning(f"Error fetching data: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Exception fetching data: {str(e)}")
            return []
    
    def pushshift_to_record(self, submission: Dict[str, Any]) -> SubmissionRecord:
        """
        Convert Pushshift submission data to our SubmissionRecord format.
        
        Args:
            submission: Pushshift submission data
            
        Returns:
            SubmissionRecord
        """
        return {
            "id": submission.get("id", ""),
            "created_utc": submission.get("created_utc", 0),
            "subreddit": submission.get("subreddit", "").lower(),
            "title": submission.get("title", ""),
            "selftext": submission.get("selftext", ""),
            "author": submission.get("author", ""),
            "score": submission.get("score", 0),
            "upvote_ratio": submission.get("upvote_ratio", 0.0),
            "num_comments": submission.get("num_comments", 0),
            "url": submission.get("url", ""),
            "flair_text": submission.get("link_flair_text", ""),
            "over_18": submission.get("over_18", False),
        }
    
    async def scrape_time_period(
        self,
        subreddit: str,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        chunk_months: int = 3,
    ) -> int:
        """
        Scrape a specific time period for a subreddit using Pushshift.
        
        Args:
            subreddit: Subreddit name
            start_date: Start date for the period
            end_date: End date for the period
            chunk_months: Size of each time chunk in months
            
        Returns:
            Number of posts collected
        """
        # Skip if subreddit didn't exist during this period
        creation_date = SUBREDDIT_CREATION_DATES.get(subreddit)
        if creation_date and creation_date > end_date:
            logger.info(f"Skipping r/{subreddit} for period {start_date.date()} to {end_date.date()} - subreddit didn't exist yet")
            return 0
        
        logger.info(f"Scraping r/{subreddit} from {start_date.date()} to {end_date.date()}")
        
        # Track total collected
        period_collected = 0
        
        # Break the time period into chunks
        current_start = start_date
        while current_start < end_date:
            # Calculate chunk end (but don't go past end_date)
            current_end = min(current_start + relativedelta(months=chunk_months), end_date)
            
            # Convert to Unix timestamps
            after = int(current_start.timestamp())
            before = int(current_end.timestamp())
            
            # Fetch data
            submissions = await self.fetch_pushshift_data(subreddit, after, before)
            
            # Filter out already seen submissions
            new_submissions = [s for s in submissions if s.get("id") not in self.seen_ids]
            
            if new_submissions:
                # Convert to our record format
                records = [self.pushshift_to_record(s) for s in new_submissions]
                
                # Store records
                await self.store_records(records)
                
                # Update counter
                period_collected += len(records)
                logger.info(f"Collected {len(records)} submissions from r/{subreddit} between {current_start.date()} and {current_end.date()}")
            else:
                logger.info(f"No new submissions from r/{subreddit} between {current_start.date()} and {current_end.date()}")
            
            # Move to next chunk
            current_start = current_end
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(1)
        
        return period_collected

    async def run_for_window(self, subreddit: str, start_date: datetime.datetime, end_date: datetime.datetime) -> int:
        """Run the scraper for a specific subreddit and time window.

        This method is designed for targeted gap-filling. It initializes the
        scraper, scrapes the specified window, and then cleans up resources.

        Args:
            subreddit: The subreddit to scrape.
            start_date: The start of the time window.
            end_date: The end of the time window.

        Returns:
            The number of submissions collected.
        """
        logger.info(f"Starting targeted scrape for r/{subreddit} from {start_date.date()} to {end_date.date()}")
        await self.initialize()
        try:
            collected_count = await self.scrape_time_period(subreddit, start_date, end_date)
            logger.info(f"Completed targeted scrape for r/{subreddit}. Collected {collected_count} submissions.")
            return collected_count
        except Exception as e:
            logger.error(f"An error occurred during targeted scrape for r/{subreddit}: {e}", exc_info=True)
            return 0  # Return 0 if an error occurs
        finally:
            await self.cleanup()

    async def run(self) -> int:
        """Run the Pushshift historical scraper.
        
        Returns:
            Number of submissions collected
        """
        # Track total collected
        self.total_collected = 0
        
        # Process each time period
        for start_year, end_year in TARGET_PERIODS:
            start_date = datetime.datetime(start_year, 1, 1, tzinfo=datetime.timezone.utc)
            end_date = datetime.datetime(end_year, 1, 1, tzinfo=datetime.timezone.utc)
            
            logger.info(f"Processing period: {start_year} to {end_year}")
            period_total = 0
            
            # Process each subreddit for this period
            for subreddit in self.config.subreddits:
                collected = await self.scrape_time_period(
                    subreddit,
                    start_date,
                    end_date,
                    chunk_months=3,
                )
                period_total += collected
            
            logger.info(f"Collected {period_total} submissions from {start_year} to {end_year}")
            self.total_collected += period_total
            
            # Small delay between periods
            await asyncio.sleep(2)
        
        logger.info(f"Pushshift historical scraping complete! Collected {self.total_collected} total submissions")
        return self.total_collected


async def main():
    """Run the Pushshift historical scraper."""
    # Import here to avoid circular imports
    from reddit_scraper.cli import setup_logging
    
    # Use centralized logging setup
    setup_logging(log_level="INFO")
    
    scraper = PushshiftHistoricalScraper()
    await scraper.execute()


if __name__ == "__main__":
    asyncio.run(main())
