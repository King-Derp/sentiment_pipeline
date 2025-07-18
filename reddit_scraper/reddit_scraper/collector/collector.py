"""Core collector functionality for fetching Reddit submissions."""

import asyncio
import logging
import time
from contextlib import nullcontext
from datetime import datetime, timezone
from typing import List, Set, Optional, Dict, Any

from asyncpraw.models import Subreddit, Submission
from asyncpraw.exceptions import PRAWException
from aiohttp.client_exceptions import ClientResponseError

from reddit_scraper.collector.error_handler import with_exponential_backoff, ConsecutiveErrorTracker
from reddit_scraper.collector.rate_limiter import RateLimiter
from reddit_scraper.models.mapping import submission_to_record
from reddit_scraper.models.submission import SubmissionRecord
from reddit_scraper.reddit_client import RedditClient

logger = logging.getLogger(__name__)


class SubmissionCollector:
    """Collector for Reddit submissions with rate limiting and error handling."""
    
    def __init__(
        self, 
        reddit_client: RedditClient,
        rate_limiter: RateLimiter,
        error_tracker: ConsecutiveErrorTracker,
        prometheus_exporter = None,
    ):
        """
        Initialize the submission collector.
        
        Args:
            reddit_client: Authenticated Reddit client
            rate_limiter: Rate limiter for API requests
            error_tracker: Tracker for consecutive errors
        """
        self.reddit_client = reddit_client
        self.rate_limiter = rate_limiter
        self.error_tracker = error_tracker
        self.prometheus_exporter = prometheus_exporter
    
    @with_exponential_backoff(error_tracker=None, rate_limiter=None)
    async def _get_new_submissions(
        self, 
        subreddit: Subreddit,
        limit: Optional[int] = None,
    ) -> List[Submission]:
        """
        Get new submissions from a subreddit.
        
        Args:
            subreddit: Subreddit to fetch from
            limit: Maximum number of submissions to fetch (None for all available)
            
        Returns:
            List of submissions
        """
        await self.rate_limiter.pre_request()
        
        # Record fetch operation in metrics if available
        if self.prometheus_exporter:
            self.prometheus_exporter.record_fetch_operation("latest")
            timer = self.prometheus_exporter.time_request()
        else:
            timer = None
            
        try:
            with timer if timer else nullcontext():
                submissions = []
                async for submission in subreddit.new(limit=limit):
                    submissions.append(submission)
                
                return submissions
        except ClientResponseError as e:
            # Record API error in metrics if available
            if self.prometheus_exporter:
                error_type = "5xx" if 500 <= e.status < 600 else str(e.status)
                self.prometheus_exporter.record_api_error(error_type)
            raise
    
    @with_exponential_backoff(error_tracker=None, rate_limiter=None)
    async def _search_submissions(
        self,
        subreddit: Subreddit,
        query: str,
        sort: str = "new",
        limit: int = 100,  # Default batch size of 100
        after: Optional[str] = None,  # For pagination
    ) -> List[Submission]:
        """
        Search for submissions in a subreddit.
        
        Args:
            subreddit: Subreddit to search in
            query: Search query (CloudSearch syntax)
            sort: Sort order for results
            limit: Maximum number of results per batch (default: 100)
            after: Fullname of a submission to fetch the next batch after
            
        Returns:
            List of matching submissions
        """
        await self.rate_limiter.pre_request()
        
        # Record fetch operation in metrics if available
        if self.prometheus_exporter:
            self.prometheus_exporter.record_fetch_operation("historic")
            timer = self.prometheus_exporter.time_request()
        else:
            timer = None
            
        try:
            with timer if timer else nullcontext():
                submissions = []
                # Use params to pass after for pagination
                params = {"limit": limit}
                if after:
                    params["after"] = after
                    
                async for submission in subreddit.search(
                    query, 
                    sort=sort, 
                    syntax='cloudsearch',  # Explicitly use CloudSearch syntax for timestamp queries
                    params=params
                ):
                    submissions.append(submission)
                
                return submissions
        except ClientResponseError as e:
            # Record API error in metrics if available
            if self.prometheus_exporter:
                error_type = "5xx" if 500 <= e.status < 600 else str(e.status)
                self.prometheus_exporter.record_api_error(error_type)
            raise
    
    async def latest(
        self, 
        subreddit_name: str, 
        seen_ids: Set[str],
    ) -> List[SubmissionRecord]:
        """
        Collect the latest submissions from a subreddit that haven't been seen before.
        
        Args:
            subreddit_name: Name of the subreddit
            seen_ids: Set of already seen submission IDs
            
        Returns:
            List of new submission records
        """
        logger.info(f"Collecting latest submissions from r/{subreddit_name}")
        
        try:
            # Get subreddit
            subreddit = await self.reddit_client.get_subreddit(subreddit_name)
            
            # Fetch submissions
            submissions = await self._get_new_submissions(subreddit)
            
            # Filter out already seen submissions
            new_submissions = [s for s in submissions if s.id not in seen_ids]
            
            # Convert to records
            records = [submission_to_record(s) for s in new_submissions]
            
            # Record metrics if available
            if self.prometheus_exporter and records:
                for _ in range(len(records)):
                    self.prometheus_exporter.record_submission_collected(subreddit_name)
            
            logger.info(f"Collected {len(records)} new submissions from r/{subreddit_name}")
            return records
            
        except Exception as e:
            logger.error(f"Failed to collect latest from r/{subreddit_name}: {str(e)}")
            return []
    
    async def historic(
        self,
        subreddit_name: str,
        end_epoch: int,
        window_days: int,
        seen_ids: Set[str],
    ) -> List[SubmissionRecord]:
        """
        Collect historic submissions from a subreddit within a time window.
        
        Args:
            subreddit_name: Name of the subreddit
            end_epoch: End timestamp (Unix epoch)
            window_days: Number of days to look back from end_epoch
            seen_ids: Set of already seen submission IDs
            
        Returns:
            List of new submission records
        """
        # Calculate start timestamp
        start_epoch = end_epoch - (window_days * 86400)
        
        # Format timestamps for CloudSearch
        start_str = datetime.fromtimestamp(start_epoch, tz=timezone.utc).strftime("%Y-%m-%d")
        end_str = datetime.fromtimestamp(end_epoch, tz=timezone.utc).strftime("%Y-%m-%d")
        
        logger.info(
            f"Collecting historic submissions from r/{subreddit_name} "
            f"between {start_str} and {end_str}"
        )
        
        try:
            # Get subreddit
            subreddit = await self.reddit_client.get_subreddit(subreddit_name)
            logger.info(f"Successfully got subreddit object for r/{subreddit_name}")
            
            # Build CloudSearch query for the time window
            query = f"timestamp:{start_epoch}..{end_epoch}"
            logger.info(f"CloudSearch query: {query}")
            logger.info(f"Searching with sort='new', limit=1000, syntax='cloudsearch' (subreddit-restricted by default)")
            logger.info(f"Current seen_ids count: {len(seen_ids)}")
            logger.info(f"Epoch range: {start_epoch} to {end_epoch} (duration: {end_epoch - start_epoch} seconds)")
            
            # Fetch submissions
            submissions = await self._search_submissions(
                subreddit, 
                query=query,
                sort="new",
                limit=1000,
            )
            
            logger.info(f"Reddit API returned {len(submissions)} total submissions")
            
            # Filter out already seen submissions
            new_submissions = [s for s in submissions if s.id not in seen_ids]
            logger.info(f"After filtering seen IDs: {len(new_submissions)} new submissions")
            
            # Log sample of submission IDs and timestamps for debugging
            if new_submissions:
                logger.info("Sample of new submissions:")
                for i, sub in enumerate(new_submissions[:5]):  # Show first 5
                    sub_time = datetime.fromtimestamp(sub.created_utc, tz=timezone.utc)
                    logger.info(f"  {i+1}. ID: {sub.id}, Created: {sub_time}, Title: {sub.title[:50]}...")
            else:
                logger.warning("No new submissions found after filtering")
                if submissions:
                    logger.warning("All returned submissions were already in seen_ids")
                    # Log sample of filtered submissions
                    logger.info("Sample of filtered submissions (already seen):")
                    for i, sub in enumerate(submissions[:3]):
                        sub_time = datetime.fromtimestamp(sub.created_utc, tz=timezone.utc)
                        logger.info(f"  {i+1}. ID: {sub.id}, Created: {sub_time}, Title: {sub.title[:50]}...")
                else:
                    logger.warning("Reddit API returned no submissions for this query")
                    logger.warning("This could indicate: 1) No posts in time range, 2) CloudSearch limitations, 3) API rate limiting")
            
            # Convert to records
            records = [submission_to_record(s) for s in new_submissions]
            
            # Record metrics if available
            if self.prometheus_exporter and records:
                for _ in range(len(records)):
                    self.prometheus_exporter.record_submission_collected(subreddit_name)
            
            logger.info(
                f"Collected {len(records)} new historic submissions from r/{subreddit_name} "
                f"between {start_str} and {end_str}"
            )
            return records
            
        except Exception as e:
            logger.error(
                f"Failed to collect historic from r/{subreddit_name} "
                f"between {start_str} and {end_str}: {str(e)}", exc_info=True
            )
            return []
