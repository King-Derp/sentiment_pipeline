"""Backfill engine for collecting historical Reddit submissions."""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import List, Set, Dict, Optional

import tqdm
import tqdm.asyncio

from reddit_scraper.collector.collector import SubmissionCollector
from reddit_scraper.config import Config
from reddit_scraper.models.submission import SubmissionRecord
from reddit_scraper.storage.csv_sink import DataSink

logger = logging.getLogger(__name__)


class BackfillRunner:
    """
    Runner for backfilling historical Reddit submissions.
    
    Drives the collection process across multiple subreddits and time windows.
    """
    
    def __init__(
        self,
        config: Config,
        collector: SubmissionCollector,
        data_sink: DataSink,
    ):
        """
        Initialize the backfill runner.
        
        Args:
            config: Application configuration
            collector: Submission collector
            data_sink: Data storage sink
        """
        self.config = config
        self.collector = collector
        self.data_sink = data_sink
        self.seen_ids: Set[str] = set()
        
    async def initialize(self) -> None:
        """Initialize the runner by loading existing submission IDs."""
        self.seen_ids = self.data_sink.load_ids()
        logger.info(f"Initialized backfill runner with {len(self.seen_ids)} known submission IDs")
        
    async def run(self, since_timestamp: Optional[int] = None) -> int:
        """
        Run the backfill process.
        
        Args:
            since_timestamp: Optional timestamp to start backfill from (defaults to now)
            
        Returns:
            Total number of new submissions collected
        """
        # Start from current time if not specified
        if since_timestamp is None:
            since_timestamp = int(time.time())
            
        logger.info(f"Starting backfill from {datetime.fromtimestamp(since_timestamp, tz=timezone.utc)}")
        
        # Track empty windows per subreddit
        empty_windows: Dict[str, int] = {subreddit: 0 for subreddit in self.config.subreddits}
        
        # Track total submissions collected
        total_collected = 0
        
        # First, collect the latest submissions from each subreddit
        for subreddit in tqdm.tqdm(self.config.subreddits, desc="Latest pass"):
            records = await self.collector.latest(subreddit, self.seen_ids)
            
            if records:
                # Add new IDs to seen set
                self.seen_ids.update(r["id"] for r in records)
                
                # Store records
                self.data_sink.append(records)
                
                total_collected += len(records)
                logger.info(f"Collected {len(records)} latest submissions from r/{subreddit}")
            else:
                logger.info(f"No new latest submissions from r/{subreddit}")
        
        # Then do the historic backfill with sliding windows
        window_end = since_timestamp
        consecutive_empty_windows = 0
        max_consecutive_empty = len(self.config.subreddits) * 2  # Termination threshold
        
        with tqdm.tqdm(desc="Historic backfill") as pbar:
            while consecutive_empty_windows < max_consecutive_empty:
                window_collected = 0
                
                # Process each subreddit
                for subreddit in self.config.subreddits:
                    # Skip if this subreddit has had too many empty windows
                    if empty_windows[subreddit] >= 3:
                        continue
                        
                    # Collect for this window
                    records = await self.collector.historic(
                        subreddit,
                        window_end,
                        self.config.window_days,
                        self.seen_ids,
                    )
                    
                    if records:
                        # Add new IDs to seen set
                        self.seen_ids.update(r["id"] for r in records)
                        
                        # Store records
                        self.data_sink.append(records)
                        
                        # Update counters
                        window_collected += len(records)
                        total_collected += len(records)
                        empty_windows[subreddit] = 0  # Reset empty window counter
                        
                        logger.info(
                            f"Collected {len(records)} historic submissions from r/{subreddit} "
                            f"ending at {datetime.fromtimestamp(window_end, tz=timezone.utc)}"
                        )
                    else:
                        # Increment empty window counter for this subreddit
                        empty_windows[subreddit] += 1
                        logger.info(
                            f"No historic submissions from r/{subreddit} "
                            f"ending at {datetime.fromtimestamp(window_end, tz=timezone.utc)} "
                            f"({empty_windows[subreddit]} empty windows)"
                        )
                
                # Update progress
                pbar.update(1)
                pbar.set_postfix({
                    "total": total_collected,
                    "window": window_collected,
                    "end_date": datetime.fromtimestamp(window_end, tz=timezone.utc).strftime("%Y-%m-%d"),
                })
                
                # Check if this entire window was empty across all subreddits
                if window_collected == 0:
                    consecutive_empty_windows += 1
                    logger.info(
                        f"Empty window ending at {datetime.fromtimestamp(window_end, tz=timezone.utc)} "
                        f"({consecutive_empty_windows}/{max_consecutive_empty})"
                    )
                else:
                    consecutive_empty_windows = 0
                
                # Move window back in time
                window_end -= self.config.window_days * 86400
                
                # No time limit - continue until we find enough empty windows
                # or reach Reddit's beginning (2005)
        
        logger.info(f"Backfill complete, collected {total_collected} total submissions")
        return total_collected
