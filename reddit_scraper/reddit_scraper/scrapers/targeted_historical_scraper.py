#!/usr/bin/env python
"""
Targeted historical scraper for Reddit finance subreddits.

This script uses the official Reddit API with specific search queries
to target older posts from finance subreddits.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Set, Dict, Optional, Any, Union

from reddit_scraper.base_scraper import BaseScraper
from reddit_scraper.scraper_utils import search_by_term, search_by_year
from reddit_scraper.models.submission import SubmissionRecord
from reddit_scraper.models.mapping import submission_to_record
from reddit_scraper.config import Config

logger = logging.getLogger("targeted_historical")

# Define specific search terms that were likely used in older posts
# These will help us find historical content
HISTORICAL_SEARCH_TERMS = [
    # Original Market Condition Terms
    "financial crisis",
    "recession",
    "bear market",
    "bull market",
    "stock market crash",
    "housing bubble",
    "lehman brothers",
    "subprime",
    "mortgage",
    "credit default swap",
    "bailout",
    "stimulus",
    "federal reserve",
    "interest rates",
    "inflation",
    "deflation",
    "unemployment",
    "gdp",
    "earnings",
    "dividend",
    "ipo",
    "merger",
    "acquisition",
    "bankruptcy",
    "default",
    "debt",
    "credit",
    "bond",
    "treasury",
    "etf",
    "mutual fund",
    "index fund",
    "401k",
    "roth ira",
    "investment",
    "portfolio",
    "diversification",
    "asset allocation",
    "risk management",
    "technical analysis",
    "fundamental analysis",
    "value investing",
    "growth investing",
    "day trading",
    "swing trading",
    "options trading",
    "futures",
    "commodities",
    "gold",
    "silver",
    "oil",
    "forex",
    
    # Direct Sentiment Terms
    "bullish",
    "bearish",
    "optimistic",
    "pessimistic",
    "confident",
    "worried",
    "fear",
    "greed",
    "panic",
    "euphoria",
    "bubble",
    "crash",
    "correction",
    "rally",
    "recovery",
    "opportunity",
    "risk",
    "overvalued",
    "undervalued",
    "buy the dip",
    "sell off",
    "market bottom",
    "market top",
    
    # Major Companies
    "apple",
    "microsoft",
    "amazon",
    "google",
    "tesla",
    "facebook",
    "meta",
    "netflix",
    "nvidia",
    "amd",
    "intel",
    "jpmorgan",
    "bank of america",
    "goldman sachs",
    "berkshire hathaway",
    "buffett",
    "palantir",
    "shopify",
    "zoom",
    "lucid",
    "rivian"
    
    # Regulatory & Policy
    "sec",
    "fed",
    "federal reserve",
    "jerome powell",
    "yellen",
    "regulation",
    "policy",
    "fiscal",
    "monetary",
    "tax",
    "audit",
    "compliance",
    "oversight",
    "investigation",
    
    # Modern Financial Terms
    "cryptocurrency",
    "bitcoin",
    "ethereum",
    "crypto",
    "blockchain",
    "nft",
    "defi",
    "fintech",
    "spac",
    "meme stock",
    "short squeeze",
    "passive investing",
    "robo advisor",
    "esg",
    "sustainable investing",
    "web3",
    "dao",
    "yield farming",
    "stablecoin",
    "cbdc",
    
    # Market Participants
    "retail investor",
    "institutional investor",
    "hedge fund",
    "short seller",
    "market maker",
    "whale",
    "smart money",
    "dumb money",
    "diamond hands",
    "paper hands",
    
    # Reddit/Social Media Financial Slang
    "yolo",
    "tendies",
    "stonks",
    "to the moon",
    "hodl",
    "bags",
    "bagholder",
    "loss porn",
    "gain porn",
    "dd",
    "due diligence",
    "fomo",
    "fud",
    "ape",
    "rocket",
    "printer go brrr",
    "guh",
    "degenerates",
    "smooth brain",
    "lambos",
    "wendy's",
    "pltr",
    
    # Financial Events & Crises
    "dotcom bubble",
    "great recession",
    "covid crash",
    "black monday",
    "flash crash",
    "taper tantrum",
    "liquidity crisis",
    "credit crunch",
    "gamestop",
    "robinhood",
    "meme stock",
    "amc",
    "short squeeze",
    "evergrand",
    "inflation crisis",
    "supply chain crisis",
    "meme stock squeeze",
    "pfof",
    
    # Economic Indicators
    "cpi",
    "ppi",
    "nonfarm payrolls",
    "jobs report",
    "unemployment rate",
    "fomc",
    "rate hike",
    "rate cut",
    "yield curve",
    "inverted yield",
    "gdp growth",
    "recession indicator",
    "leading indicator",
    "economic data",
    "economic outlook",
    
    # Trading & Investment Terms
    "options",
    "calls",
    "puts",
    "leaps",
    "covered call",
    "thetagang",
    "iron condor",
    "rsu",
    "dca",
    "vwap",
]

# Define specific years to target
TARGET_YEARS = [2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023]


class TargetedHistoricalScraper(BaseScraper):
    """Targeted historical scraper for Reddit finance subreddits.
    
    Uses specific search terms to find historical Reddit posts.
    """
    
    def __init__(self, config: Union[str, Config] = "config.yaml"):
        """Initialize the targeted historical scraper.
        
        Args:
            config: Configuration file path or Config object
        """
        super().__init__(config)
        self.total_collected = 0
    
    async def run(self) -> int:
        """Run the targeted historical scraper.
        
        Returns:
            Number of submissions collected
        """
        # Track total collected
        self.total_collected = 0
        
        # First, search by year for each subreddit
        logger.info("Starting year-specific searches...")
        for year in TARGET_YEARS:
            for subreddit in self.config.subreddits:
                records = await search_by_year(
                    self.collector, 
                    subreddit, 
                    year, 
                    self.seen_ids
                )
                
                if records:
                    await self.store_records(records)
                    self.total_collected += len(records)
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(1)
        
        # Then, search by historical terms
        logger.info("Starting historical term searches...")
        for term in HISTORICAL_SEARCH_TERMS:
            for subreddit in self.config.subreddits:
                records = await search_by_term(
                    self.collector, 
                    subreddit, 
                    term, 
                    self.seen_ids
                )
                
                if records:
                    await self.store_records(records)
                    self.total_collected += len(records)
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(1)
        
        logger.info(f"Targeted historical scraping complete! Collected {self.total_collected} total submissions")
        return self.total_collected
    
    async def run_for_window(self, subreddit: str, start_date: datetime, end_date: datetime) -> int:
        """Fill a specific time gap for a subreddit.
        
        Args:
            subreddit: The subreddit to search (without 'r/' prefix)
            start_date: Start of the time window to fill
            end_date: End of the time window to fill
            
        Returns:
            Number of submissions collected for this gap
        """
        logger.info(f"Starting targeted scrape for r/{subreddit} from {start_date.date()} to {end_date.date()}")
        
        collected_count = 0
        
        try:
            # Initialize if not already done
            if not self.collector:
                await self.initialize()
            
            # Convert dates to timestamps for Reddit API
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int(end_date.timestamp())
            
            # Search for posts in the time window using multiple strategies
            collected_count += await self._search_by_time_range(subreddit, start_timestamp, end_timestamp)
            collected_count += await self._search_by_popular_terms(subreddit, start_timestamp, end_timestamp)
            
            logger.info(f"Completed targeted scrape for r/{subreddit}. Collected {collected_count} submissions.")
            
        except Exception as e:
            logger.error(f"Error during gap filling for r/{subreddit}: {e}", exc_info=True)
            
        return collected_count
    
    async def _search_by_time_range(self, subreddit: str, start_ts: int, end_ts: int) -> int:
        """Search for posts in a time range using the collector's historic method.
        
        Args:
            subreddit: Subreddit name
            start_ts: Start timestamp
            end_ts: End timestamp
            
        Returns:
            Number of posts found
        """
        collected = 0
        
        try:
            # Calculate window in days (minimum 1 day)
            window_seconds = end_ts - start_ts
            window_days = max(1, int(window_seconds / 86400))
            
            # Convert timestamps to readable format for logging
            start_date_str = datetime.fromtimestamp(start_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            end_date_str = datetime.fromtimestamp(end_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            
            logger.info(f"Searching r/{subreddit} from {start_date_str} to {end_date_str} (window: {window_days} days)")
            logger.info(f"CloudSearch query will be: timestamp:{start_ts}..{end_ts}")
            logger.info(f"Current seen_ids count: {len(self.seen_ids)}")
            
            # Use the collector's historic method to get submissions in the time range
            records = await self.collector.historic(
                subreddit_name=subreddit,
                end_epoch=end_ts,
                window_days=window_days,
                seen_ids=self.seen_ids
            )
            
            logger.info(f"Collector returned {len(records)} records from r/{subreddit}")
            
            # Filter records to exact time range (historic method might return broader range)
            filtered_records = []
            for record in records:
                record_ts = int(record['created_utc'].timestamp())
                if start_ts <= record_ts <= end_ts:
                    filtered_records.append(record)
                    self.seen_ids.add(record['id'])
                    logger.debug(f"Accepted record {record['id']} from {datetime.fromtimestamp(record_ts, tz=timezone.utc)}")
                else:
                    logger.debug(f"Filtered out record {record['id']} from {datetime.fromtimestamp(record_ts, tz=timezone.utc)} (outside time range)")
            
            logger.info(f"After time filtering: {len(filtered_records)} records remain")
            
            if filtered_records:
                await self.store_records(filtered_records)
                collected = len(filtered_records)
                logger.info(f"Successfully stored {collected} new submissions from r/{subreddit}")
            else:
                logger.warning(f"No new submissions found for r/{subreddit} in time range {start_date_str} to {end_date_str}")
                logger.warning(f"This could be due to: 1) No posts in this time range, 2) All posts already scraped, 3) Reddit API limitations for historical data")
                    
        except Exception as e:
            logger.error(f"Error in time range search for r/{subreddit}: {e}", exc_info=True)
            
        return collected
    
    async def _search_by_popular_terms(self, subreddit: str, start_ts: int, end_ts: int) -> int:
        """Search using popular financial terms within the time range.
        
        Args:
            subreddit: Subreddit name  
            start_ts: Start timestamp
            end_ts: End timestamp
            
        Returns:
            Number of posts found
        """
        collected = 0
        
        # Use the full HISTORICAL_SEARCH_TERMS list for consistency with broad historical scraping
        gap_fill_terms = HISTORICAL_SEARCH_TERMS
        
        # Convert timestamps to readable format for logging
        start_date_str = datetime.fromtimestamp(start_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        end_date_str = datetime.fromtimestamp(end_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        
        logger.info(f"Starting popular terms search for r/{subreddit} from {start_date_str} to {end_date_str}")
        logger.info(f"Will search using {len(gap_fill_terms)} financial terms")
        
        try:
            # Get subreddit object for direct search
            subreddit_obj = await self.reddit_client.get_subreddit(subreddit)
            logger.info(f"Successfully got subreddit object for r/{subreddit}")
            
            for i, term in enumerate(gap_fill_terms):
                try:
                    # Build CloudSearch query with term and time range
                    query = f"{term} timestamp:{start_ts}..{end_ts}"
                    logger.debug(f"Searching term {i+1}/{len(gap_fill_terms)}: '{term}' with query: {query}")
                    
                    # Use the collector's internal search method
                    submissions = await self.collector._search_submissions(
                        subreddit_obj, query, sort='new', limit=100
                    )
                    
                    logger.debug(f"Term '{term}' returned {len(submissions)} submissions")
                    
                    term_collected = 0
                    # Convert submissions to records and filter by time range
                    for submission in submissions:
                        if submission.id not in self.seen_ids:
                            # Double-check timestamp is in range
                            if start_ts <= submission.created_utc <= end_ts:
                                record = submission_to_record(submission)
                                if record:
                                    await self.store_records([record])
                                    collected += 1
                                    term_collected += 1
                                    self.seen_ids.add(submission.id)
                                    logger.debug(f"Stored new submission {submission.id} from term '{term}'")
                            else:
                                logger.debug(f"Submission {submission.id} outside time range (created: {submission.created_utc})")
                        else:
                            logger.debug(f"Submission {submission.id} already seen, skipping")
                                    
                        # Add small delay between submissions
                        await asyncio.sleep(0.1)
                    
                    if term_collected > 0:
                        logger.info(f"Term '{term}' contributed {term_collected} new submissions")
                    else:
                        logger.debug(f"Term '{term}' found no new submissions")
                        
                    # Delay between different search terms
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.warning(f"Error searching for term '{term}' in r/{subreddit}: {e}")
                    continue
            
            logger.info(f"Popular terms search completed. Total collected: {collected} submissions")
                    
        except Exception as e:
            logger.error(f"Error in term-based search for r/{subreddit}: {e}", exc_info=True)
            
        return collected


async def main():
    """Run the targeted historical scraper."""
    # Import here to avoid circular imports
    from reddit_scraper.cli import setup_logging
    
    # Use centralized logging setup
    setup_logging(log_level="INFO")
    
    scraper = TargetedHistoricalScraper()
    await scraper.execute()


if __name__ == "__main__":
    asyncio.run(main())
