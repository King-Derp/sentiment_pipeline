"""Utility functions for Reddit scrapers.

This module provides common utility functions used across different scraper implementations
to reduce code duplication and standardize operations.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Set, Dict, Optional, Tuple, Any
from dateutil.relativedelta import relativedelta

from asyncpraw.models import Subreddit

from reddit_scraper.collector.collector import SubmissionCollector
from reddit_scraper.models.mapping import submission_to_record
from reddit_scraper.models.submission import SubmissionRecord

logger = logging.getLogger(__name__)


async def search_by_term(
    collector: SubmissionCollector,
    subreddit_name: str,
    search_term: str,
    seen_ids: Set[str],
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    batch_size: int = 100,
    max_results: int = 1000,  # Max results to fetch (Reddit search limit ~1000)
) -> List[SubmissionRecord]:
    """Search for a specific term in a subreddit with optional date range.
    
    Implements pagination to fetch up to max_results (default 1000) submissions.
    
    Args:
        collector: Submission collector
        subreddit_name: Name of the subreddit
        search_term: Term to search for
        seen_ids: Set of already seen submission IDs
        start_date: Optional start date for the search
        end_date: Optional end date for the search
        batch_size: Size of each batch (default: 100)
        max_results: Maximum total results to return (default: 1000)
        
    Returns:
        List of new submission records
    """
    try:
        # Get subreddit
        subreddit = await collector.reddit_client.get_subreddit(subreddit_name)
        
        # Build search query
        query = search_term
        
        # Add timestamp if dates are provided
        if start_date and end_date:
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int(end_date.timestamp())
            date_range = f"timestamp:{start_timestamp}..{end_timestamp}"
            query = f"{query} {date_range}"
            logger.info(f"Searching r/{subreddit_name} for '{search_term}' between {start_date.date()} and {end_date.date()}")
        else:
            logger.info(f"Searching r/{subreddit_name} for '{search_term}'")
        
        # Variables for pagination
        all_submissions = []
        after = None
        max_pages = max_results // batch_size
        
        # Fetch submissions with pagination
        for page in range(max_pages):
            # Get the current batch
            submissions = await collector._search_submissions(
                subreddit, 
                query=query,
                sort="new",
                limit=batch_size,
                after=after,
            )
            
            # Add to our results
            all_submissions.extend(submissions)
            
            # If we got fewer results than the batch size, we've reached the end
            if len(submissions) < batch_size:
                break
                
            # Set the 'after' parameter for the next batch if we got a full batch
            if submissions:
                after = f"t3_{submissions[-1].id}"  # t3_ prefix for submissions
                
                # Add a delay between API calls to avoid rate limiting
                await asyncio.sleep(1)
            else:
                break
                
        # Filter out already seen submissions
        new_submissions = [s for s in all_submissions if s.id not in seen_ids]
        
        # Convert to records
        records = [submission_to_record(s) for s in new_submissions]
        
        logger.info(f"Found {len(records)} new submissions from r/{subreddit_name} for '{search_term}' (from {len(all_submissions)} total fetched)")
        return records
        
    except Exception as e:
        logger.error(f"Failed to search r/{subreddit_name} for '{search_term}': {str(e)}")
        return []


async def search_by_date_range(
    collector: SubmissionCollector,
    subreddit_name: str,
    start_date: datetime,
    end_date: datetime,
    seen_ids: Set[str],
    batch_size: int = 100,
    max_results: int = 1000,  # Max results to fetch (Reddit search limit ~1000)
) -> List[SubmissionRecord]:
    """Search for posts within a specific date range in a subreddit.
    
    Implements pagination to fetch up to max_results (default 1000) submissions.
    
    Args:
        collector: Submission collector
        subreddit_name: Name of the subreddit
        start_date: Start date for the search
        end_date: End date for the search
        seen_ids: Set of already seen submission IDs
        batch_size: Size of each batch (default: 100)
        max_results: Maximum total results to return (default: 1000)
        
    Returns:
        List of new submission records
    """
    try:
        # Get subreddit
        subreddit = await collector.reddit_client.get_subreddit(subreddit_name)
        
        # Convert dates to timestamps
        start_timestamp = int(start_date.timestamp())
        end_timestamp = int(end_date.timestamp())
        
        # Build search query with timestamp
        query = f"timestamp:{start_timestamp}..{end_timestamp}"
        
        logger.info(f"Searching r/{subreddit_name} between {start_date.date()} and {end_date.date()}")
        
        # Variables for pagination
        all_submissions = []
        after = None
        max_pages = max_results // batch_size
        
        # Fetch submissions with pagination
        for page in range(max_pages):
            # Get the current batch
            submissions = await collector._search_submissions(
                subreddit, 
                query=query,
                sort="new",
                limit=batch_size,
                after=after,
            )
            
            # Add to our results
            all_submissions.extend(submissions)
            
            # If we got fewer results than the batch size, we've reached the end
            if len(submissions) < batch_size:
                break
                
            # Set the 'after' parameter for the next batch if we got a full batch
            if submissions:
                after = f"t3_{submissions[-1].id}"  # t3_ prefix for submissions
                
                # Add a delay between API calls to avoid rate limiting
                await asyncio.sleep(1)
            else:
                break
        
        # Filter out already seen submissions
        new_submissions = [s for s in all_submissions if s.id not in seen_ids]
        
        # Convert to records
        records = [submission_to_record(s) for s in new_submissions]
        
        logger.info(f"Found {len(records)} new submissions from r/{subreddit_name} between {start_date.date()} and {end_date.date()} (from {len(all_submissions)} total fetched)")
        return records
        
    except Exception as e:
        logger.error(f"Failed to search r/{subreddit_name} by date range: {str(e)}")
        return []


async def search_by_year(
    collector: SubmissionCollector,
    subreddit_name: str,
    year: int,
    seen_ids: Set[str],
    batch_size: int = 100,
    max_results: int = 1000,
) -> List[SubmissionRecord]:
    """Search for posts from a specific year in a subreddit.
    
    Implements pagination to fetch up to max_results (default 1000) submissions.
    
    Args:
        collector: Submission collector
        subreddit_name: Name of the subreddit
        year: Year to search for
        seen_ids: Set of already seen submission IDs
        batch_size: Size of each batch (default: 100)
        max_results: Maximum total results to return (default: 1000)
        
    Returns:
        List of new submission records
    """
    # Create date range for the year
    start_date = datetime(year, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    
    return await search_by_date_range(
        collector,
        subreddit_name,
        start_date,
        end_date,
        seen_ids,
        batch_size,
        max_results,
    )


def create_time_windows(
    start_year: int,
    end_year: int,
    month_step: int = 1,
) -> List[Tuple[datetime, datetime]]:
    """Create time windows between start and end years with specified month steps.
    
    Args:
        start_year: Start year
        end_year: End year (exclusive)
        month_step: Number of months per window
        
    Returns:
        List of (start_date, end_date) tuples
    """
    windows = []
    
    # Calculate total months in period
    total_months = (end_year - start_year) * 12
    
    # Create windows
    for month_offset in range(0, total_months, month_step):
        # Calculate start and end dates for this chunk using relativedelta
        # This properly handles month boundaries and leap years
        window_start = datetime(start_year, 1, 1, tzinfo=timezone.utc) + relativedelta(months=month_offset)
        window_end = window_start + relativedelta(months=month_step)
        
        # Don't go past the end year
        if window_end.year >= end_year:
            window_end = datetime(end_year, 1, 1, tzinfo=timezone.utc)
        
        # Skip if we're past the end
        if window_start >= window_end:
            continue
            
        windows.append((window_start, window_end))
    
    return windows
