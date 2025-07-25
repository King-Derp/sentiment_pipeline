#!/usr/bin/env python
"""
Targeted historical scraper for Reddit finance subreddits.

This script uses the official Reddit API with specific search queries
to target older posts from finance subreddits.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Set, Dict, Optional, Any

from reddit_scraper.base_scraper import BaseScraper
from reddit_scraper.scraper_utils import search_by_term, search_by_year
from reddit_scraper.models.submission import SubmissionRecord

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
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the targeted historical scraper.
        
        Args:
            config_path: Path to the configuration file
        """
        super().__init__(config_path)
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
