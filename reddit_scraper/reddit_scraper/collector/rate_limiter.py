"""Rate limiting functionality for Reddit API requests."""

import asyncio
import logging
import time
from typing import Optional, Dict, Any

import aiohttp

from reddit_scraper.config import RateLimitConfig

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter for Reddit API requests.
    
    Monitors X-Ratelimit headers and enforces rate limits to avoid 429 errors.
    """
    
    def __init__(self, config: RateLimitConfig):
        """
        Initialize the rate limiter with configuration.
        
        Args:
            config: Rate limiting configuration
        """
        self.config = config
        self.remaining_calls: Optional[int] = None
        self.reset_timestamp: Optional[float] = None
        self.last_request_time = 0.0
        
        # Absolute rate limit calculation
        self.min_interval = 60.0 / self.config.max_requests_per_minute
    
    async def pre_request(self) -> None:
        """
        Check rate limits before making a request and sleep if necessary.
        
        This should be called before each Reddit API request.
        """
        # Enforce absolute rate limit
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        
        # Check if we need to wait for reset based on X-Ratelimit headers
        if (self.remaining_calls is not None and 
            self.reset_timestamp is not None and 
            self.remaining_calls < self.config.min_remaining_calls):
            
            wait_time = self.reset_timestamp - time.time() + self.config.sleep_buffer_sec
            if wait_time > 0:
                logger.info(f"Rate limit approaching: {self.remaining_calls} calls remaining. "
                           f"Sleeping for {wait_time:.2f}s until reset.")
                await asyncio.sleep(wait_time)
                # Reset our tracking after sleeping
                self.remaining_calls = None
                self.reset_timestamp = None
    
    def update_from_headers(self, headers: Dict[str, Any]) -> None:
        """
        Update rate limit tracking based on Reddit API response headers.
        
        Args:
            headers: Response headers from a Reddit API request
        """
        self.last_request_time = time.time()
        
        # Extract rate limit information from headers
        if "x-ratelimit-remaining" in headers:
            try:
                self.remaining_calls = int(float(headers["x-ratelimit-remaining"]))
            except (ValueError, TypeError):
                logger.warning("Failed to parse x-ratelimit-remaining header")
        
        if "x-ratelimit-reset" in headers:
            try:
                reset_seconds = float(headers["x-ratelimit-reset"])
                self.reset_timestamp = time.time() + reset_seconds
            except (ValueError, TypeError):
                logger.warning("Failed to parse x-ratelimit-reset header")
        
        # Log rate limit status if values are available
        if self.remaining_calls is not None and self.reset_timestamp is not None:
            reset_in = self.reset_timestamp - time.time()
            logger.debug(f"Rate limit status: {self.remaining_calls} calls remaining, "
                        f"reset in {reset_in:.2f}s")
    
    async def handle_429(self, retry_after: Optional[str] = None) -> None:
        """
        Handle a 429 Too Many Requests response.
        
        Args:
            retry_after: Value of the Retry-After header, if available
        """
        if retry_after:
            try:
                wait_seconds = float(retry_after)
            except (ValueError, TypeError):
                # Default to 60 seconds if we can't parse the header
                wait_seconds = 60.0
        else:
            # Default wait time if no Retry-After header
            wait_seconds = 60.0
        
        # Add a buffer to be safe
        wait_seconds += self.config.sleep_buffer_sec
        
        logger.warning(f"Rate limited (429). Waiting for {wait_seconds:.2f}s before retrying.")
        await asyncio.sleep(wait_seconds)
        
        # Reset our tracking after sleeping
        self.remaining_calls = None
        self.reset_timestamp = None
