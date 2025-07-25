"""Reddit API client wrapper for authenticated access."""

import asyncio
import logging
from typing import Optional

import asyncpraw
from asyncpraw.models import Subreddit

from reddit_scraper.config import Config

logger = logging.getLogger(__name__)


class RedditClient:
    """Wrapper for the Reddit API client with authentication handling."""

    def __init__(self, config: Config):
        """
        Initialize the Reddit client with configuration.
        
        Args:
            config: Application configuration with Reddit credentials
        """
        self.config = config
        self._reddit: Optional[asyncpraw.Reddit] = None
        self._subreddit_cache = {}

    async def initialize(self) -> asyncpraw.Reddit:
        """
        Initialize and authenticate the Reddit client.
        
        Returns:
            Authenticated asyncpraw.Reddit instance
        
        Raises:
            ValueError: If authentication fails
        """
        if not self._reddit:
            logger.info("Initializing Reddit client")
            
            # Validate credentials
            if not all([
                self.config.client_id,
                self.config.client_secret,
                self.config.username,
                self.config.password
            ]):
                raise ValueError("Missing Reddit API credentials")
            
            # Create Reddit instance
            self._reddit = asyncpraw.Reddit(
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                username=self.config.username,
                password=self.config.password,
                user_agent=self.config.user_agent,
            )
            
            # Verify authentication
            try:
                me = await self._reddit.user.me()
                logger.info(f"Authenticated as {me.name}")
            except Exception as e:
                self._reddit = None
                logger.error(f"Authentication failed: {str(e)}")
                raise ValueError(f"Reddit authentication failed: {str(e)}") from e
                
        return self._reddit

    async def get_subreddit(self, subreddit_name: str) -> Subreddit:
        """
        Get a subreddit instance by name, with caching.
        
        Args:
            subreddit_name: Name of the subreddit
            
        Returns:
            Subreddit instance
            
        Raises:
            ValueError: If the client is not initialized or subreddit is invalid
        """
        if not self._reddit:
            raise ValueError("Reddit client not initialized")
            
        if subreddit_name not in self._subreddit_cache:
            logger.debug(f"Fetching subreddit: {subreddit_name}")
            self._subreddit_cache[subreddit_name] = await self._reddit.subreddit(subreddit_name)
            
        return self._subreddit_cache[subreddit_name]

    async def close(self) -> None:
        """Close the Reddit client and release resources."""
        if self._reddit:
            logger.info("Closing Reddit client")
            await self._reddit.close()
            self._reddit = None
            self._subreddit_cache = {}
