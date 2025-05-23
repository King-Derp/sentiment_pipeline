"""
Mock test for the refactored scrapers.
This script patches the Reddit client to avoid making real API calls.
"""

import asyncio
import logging
from unittest.mock import patch, AsyncMock, MagicMock

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import the scrapers
from reddit_scraper.scrapers.targeted_historical_scraper import TargetedHistoricalScraper
from reddit_scraper.scrapers.deep_historical_scraper import DeepHistoricalScraper
from reddit_scraper.scrapers.hybrid_historical_scraper import HybridHistoricalScraper
from reddit_scraper.reddit_client import RedditClient


async def test_targeted_scraper():
    """Test the targeted historical scraper with mocked Reddit client."""
    logger.info("Testing TargetedHistoricalScraper...")
    
    # Create a mock for the Reddit client
    with patch.object(RedditClient, 'initialize', new_callable=AsyncMock) as mock_init, \
         patch.object(RedditClient, 'get_subreddit', new_callable=AsyncMock) as mock_get_sub, \
         patch('reddit_scraper.collector.collector.SubmissionCollector._search_submissions', new_callable=AsyncMock, return_value=[]):
        
        # Configure the mocks
        mock_init.return_value = MagicMock()
        mock_get_sub.return_value = MagicMock()
        
        # Create and run the scraper
        scraper = TargetedHistoricalScraper("config.yaml")
        result = await scraper.execute()
        
        logger.info(f"TargetedHistoricalScraper completed with {result} records")
        return result


async def test_deep_scraper():
    """Test the deep historical scraper with mocked Reddit client."""
    logger.info("Testing DeepHistoricalScraper...")
    
    # Create a mock for the Reddit client
    with patch.object(RedditClient, 'initialize', new_callable=AsyncMock) as mock_init, \
         patch.object(RedditClient, 'get_subreddit', new_callable=AsyncMock) as mock_get_sub, \
         patch('reddit_scraper.collector.collector.SubmissionCollector._search_submissions', new_callable=AsyncMock, return_value=[]):
        
        # Configure the mocks
        mock_init.return_value = MagicMock()
        mock_get_sub.return_value = MagicMock()
        
        # Create and run the scraper
        scraper = DeepHistoricalScraper("config.yaml")
        result = await scraper.execute()
        
        logger.info(f"DeepHistoricalScraper completed with {result} records")
        return result


async def test_hybrid_scraper():
    """Test the hybrid historical scraper with mocked Reddit client."""
    logger.info("Testing HybridHistoricalScraper...")
    
    # Create a mock for the Reddit client
    with patch.object(RedditClient, 'initialize', new_callable=AsyncMock) as mock_init, \
         patch.object(RedditClient, 'get_subreddit', new_callable=AsyncMock) as mock_get_sub, \
         patch('reddit_scraper.collector.collector.SubmissionCollector._search_submissions', new_callable=AsyncMock, return_value=[]):
        
        # Configure the mocks
        mock_init.return_value = MagicMock()
        mock_get_sub.return_value = MagicMock()
        
        # Create and run the scraper
        scraper = HybridHistoricalScraper("config.yaml")
        result = await scraper.execute()
        
        logger.info(f"HybridHistoricalScraper completed with {result} records")
        return result


async def main():
    """Run all tests."""
    logger.info("Starting mock tests for refactored scrapers...")
    
    # Test each scraper
    await test_targeted_scraper()
    await test_deep_scraper()
    await test_hybrid_scraper()
    
    logger.info("All tests completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
