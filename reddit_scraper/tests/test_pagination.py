"""
Test for the pagination implementation in the targeted historical scraper.
This uses mock data to avoid needing real Reddit API credentials.
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("pagination_test")


class MockSubmission:
    """Mock submission for testing."""
    
    def __init__(self, id, created_utc, title, content, subreddit_name="wallstreetbets"):
        self.id = id
        self.created_utc = created_utc
        self.title = title
        self.selftext = content
        self.subreddit = MagicMock()
        self.subreddit.display_name = subreddit_name
        self.author = MagicMock()
        self.author.name = "test_user"
        self.score = 100
        self.upvote_ratio = 0.8
        self.num_comments = 20
        self.url = f"https://reddit.com/r/{subreddit_name}/comments/{id}/test_title"
        self.link_flair_text = "DD"
        self.over_18 = False


class MockAsyncIterator:
    """Mock async iterator for testing."""
    
    def __init__(self, items):
        self.items = items
        
    def __aiter__(self):
        return self
        
    async def __anext__(self):
        if not self.items:
            raise StopAsyncIteration
        return self.items.pop(0)


async def test_pagination_implementation():
    """Run a test of the pagination implementation."""
    # Import scraper components
    from reddit_scraper.scrapers.targeted_historical_scraper import TargetedHistoricalScraper
    from reddit_scraper.scraper_utils import search_by_term
    from reddit_scraper.collector.collector import SubmissionCollector
    
    # Setup mock data - create a list of 250 mock submissions to test pagination
    base_ids = [f"test{i:03d}" for i in range(1, 251)]
    
    # First batch of 100 (for first page)
    batch1 = [MockSubmission(id=id, created_utc=1640995200, title=f"Test {id}", content=f"Content for {id}")
             for id in base_ids[:100]]
             
    # Second batch of 100 (for second page)
    batch2 = [MockSubmission(id=id, created_utc=1640908800, title=f"Test {id}", content=f"Content for {id}")
             for id in base_ids[100:200]]
             
    # Third batch (partial, only 50) to test end of pagination
    batch3 = [MockSubmission(id=id, created_utc=1640822400, title=f"Test {id}", content=f"Content for {id}")
             for id in base_ids[200:250]]
    
    # Apply the patch
    with patch('reddit_scraper.reddit_client.RedditClient') as MockRedditClient, \
         patch('reddit_scraper.collector.collector.SubmissionCollector') as MockCollector, \
         patch('reddit_scraper.storage.csv_sink.CsvSink') as MockCsvSink, \
         patch('reddit_scraper.base_scraper.BaseScraper.initialize') as mock_initialize:
        
        # Make BaseScraper.initialize do nothing to avoid actual Reddit API calls
        mock_initialize.return_value = None
        
        # Setup mock collector _search_submissions
        mock_collector_instance = MagicMock()
        MockCollector.return_value = mock_collector_instance
        
        # Setup the mock subreddit
        mock_subreddit = MagicMock()
        
        # Create a side effect function that handles pagination properly
        async def mock_search_submissions(subreddit, query, sort="new", limit=100, after=None):
            logger.info(f"Mock _search_submissions called with after={after}")
            
            if after is None:
                # First page
                return batch1
            elif after == f"t3_{batch1[-1].id}":
                # Second page
                return batch2
            elif after == f"t3_{batch2[-1].id}":
                # Third page (partial)
                return batch3
            else:
                # No more results
                return []
                
        # Assign the mock search_submissions to the collector instance
        mock_collector_instance._search_submissions = AsyncMock(side_effect=mock_search_submissions)
        
        # Setup mock subreddit search method
        mock_subreddit.search.return_value = MockAsyncIterator([])
        
        # Make the get_subreddit return our mock subreddit
        mock_client_instance = MagicMock()
        MockRedditClient.return_value = mock_client_instance
        mock_client_instance.get_subreddit = AsyncMock(return_value=mock_subreddit)
        
        # Mock the data sink to avoid file I/O
        mock_sink_instance = MagicMock()
        MockCsvSink.return_value = mock_sink_instance
        mock_sink_instance.store = AsyncMock()
        
        # Create the scraper
        scraper = TargetedHistoricalScraper()
        
        # Pre-initialize the collector to use our mock
        scraper.collector = mock_collector_instance
        
        # Run the scraper
        logger.info("Starting mock targeted historical scraper run...")
        collected = await scraper.run()
        
        logger.info(f"Completed mock run. Total collected: {collected}")
        
        # Log the calls to _search_submissions to verify pagination
        call_count = mock_collector_instance._search_submissions.call_count
        logger.info(f"Total calls to _search_submissions: {call_count}")
        
        return collected


# Helper function to run the test from command line if needed
async def run_test():
    return await test_pagination_implementation()

if __name__ == "__main__":
    asyncio.run(run_test())
