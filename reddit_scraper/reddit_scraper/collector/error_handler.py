"""Error handling and retry logic for Reddit API requests."""

import asyncio
import logging
import time
from contextlib import nullcontext
from datetime import datetime, timezone
from functools import wraps
from typing import TypeVar, Callable, Any, Optional, Awaitable, cast

from aiohttp.client_exceptions import ClientResponseError

from reddit_scraper.collector.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

T = TypeVar("T")
AsyncFunc = Callable[..., Awaitable[T]]


class ConsecutiveErrorTracker:
    """Tracker for consecutive errors with threshold checking."""
    
    def __init__(self, threshold: int, prometheus_exporter = None):
        """
        Initialize the error tracker.
        
        Args:
            threshold: Maximum number of consecutive errors allowed
            prometheus_exporter: Optional Prometheus exporter for metrics
        """
        self.threshold = threshold
        self.consecutive_errors = 0
        self.prometheus_exporter = prometheus_exporter
    
    def record_error(self) -> None:
        """Record an error occurrence and increment the counter."""
        self.consecutive_errors += 1
        logger.warning(f"Consecutive errors: {self.consecutive_errors}/{self.threshold}")
        
        # Update Prometheus metrics if available
        if self.prometheus_exporter:
            self.prometheus_exporter.set_consecutive_5xx_errors(self.consecutive_errors)
            self.prometheus_exporter.record_api_error("5xx")
    
    def record_success(self) -> None:
        """Record a successful request, resetting the consecutive error count."""
        if self.consecutive_errors > 0:
            logger.info(f"Resetting consecutive 5xx counter (was {self.consecutive_errors})")
            self.consecutive_errors = 0
            
            # Update Prometheus metrics if available
            if self.prometheus_exporter:
                self.prometheus_exporter.set_consecutive_5xx_errors(0)
    
    def should_abort(self) -> bool:
        """
        Check if we should abort due to too many consecutive errors.
        
        Returns:
            True if the failure threshold has been reached
        """
        return self.consecutive_errors >= self.threshold


def with_exponential_backoff(
    max_retries: int = 5,
    initial_backoff: float = 1.0,
    max_backoff: float = 32.0,
    backoff_factor: float = 2.0,
    error_tracker: Optional[ConsecutiveErrorTracker] = None,
    rate_limiter: Optional[RateLimiter] = None,
) -> Callable[[AsyncFunc[T]], AsyncFunc[T]]:
    """
    Decorator for retrying async functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_backoff: Initial backoff time in seconds
        max_backoff: Maximum backoff time in seconds
        backoff_factor: Multiplier for backoff time between retries
        error_tracker: Optional tracker for consecutive 5xx errors
        rate_limiter: Optional rate limiter for handling 429 responses
        
    Returns:
        Decorator function
    """
    def decorator(func: AsyncFunc[T]) -> AsyncFunc[T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            retries = 0
            backoff = initial_backoff
            
            while True:
                try:
                    result = await func(*args, **kwargs)
                    
                    # Record successful request if we're tracking errors
                    if error_tracker:
                        error_tracker.record_success()
                        
                    return result
                    
                except ClientResponseError as e:
                    # Handle rate limiting (429)
                    if e.status == 429 and rate_limiter:
                        logger.warning(f"Rate limited (429): {e}")
                        await rate_limiter.handle_429(e.headers.get("Retry-After"))
                        # Don't count this as a retry, just respect the rate limit and try again
                        continue
                        
                    # Handle server errors (5xx)
                    elif 500 <= e.status < 600:
                        # Track consecutive 5xx errors
                        if error_tracker:
                            error_tracker.record_error()
                            if error_tracker.should_abort():
                                logger.critical(
                                    f"Aborting after {error_tracker.consecutive_errors} "
                                    f"consecutive 5xx errors"
                                )
                                raise
                        
                        # Check if we've exceeded retry attempts
                        if retries >= max_retries:
                            logger.error(f"Max retries ({max_retries}) exceeded: {e}")
                            raise
                            
                        # Exponential backoff
                        logger.warning(
                            f"Server error {e.status}: {e}. "
                            f"Retrying in {backoff:.2f}s ({retries+1}/{max_retries})"
                        )
                        await asyncio.sleep(backoff)
                        retries += 1
                        backoff = min(backoff * backoff_factor, max_backoff)
                        continue
                        
                    # Other client errors, just log and raise
                    else:
                        logger.warning(f"Client error {e.status}: {e}")
                        raise
                        
                except Exception as e:
                    # For non-HTTP errors, retry with backoff
                    if retries >= max_retries:
                        logger.error(f"Max retries ({max_retries}) exceeded: {e}")
                        raise
                        
                    logger.warning(
                        f"Error: {e}. "
                        f"Retrying in {backoff:.2f}s ({retries+1}/{max_retries})"
                    )
                    await asyncio.sleep(backoff)
                    retries += 1
                    backoff = min(backoff * backoff_factor, max_backoff)
                    continue
                    
        return cast(AsyncFunc[T], wrapper)
    return decorator
