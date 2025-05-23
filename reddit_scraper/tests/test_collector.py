"""Tests for the collector module."""

import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

from reddit_scraper.collector.collector import SubmissionCollector
from reddit_scraper.collector.error_handler import ConsecutiveErrorTracker
from reddit_scraper.collector.rate_limiter import RateLimiter
from reddit_scraper.reddit_client import RedditClient


# Helper class for mocking async iterators
class AsyncIterator:
    def __init__(self, items):
        self.items = items
        self.index = 0
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item


class TestSubmissionCollector(unittest.TestCase):
    """Test cases for the SubmissionCollector class."""

    def setUp(self):
        """Set up test environment."""
        # Create mocks for dependencies
        self.mock_reddit_client = MagicMock(spec=RedditClient)
        self.mock_rate_limiter = MagicMock(spec=RateLimiter)
        self.mock_error_tracker = MagicMock(spec=ConsecutiveErrorTracker)
        self.mock_prometheus_exporter = MagicMock()
        
        # Create collector with mocks
        self.collector = SubmissionCollector(
            self.mock_reddit_client,
            self.mock_rate_limiter,
            self.mock_error_tracker,
            self.mock_prometheus_exporter
        )
        
        # Setup async methods
        self.mock_rate_limiter.pre_request = AsyncMock()
        self.mock_reddit_client.get_subreddit = AsyncMock()

    async def async_test(self, func, *args, **kwargs):
        """Helper to run async tests."""
        return await func(*args, **kwargs)

    def test_init(self):
        """Test initialization of collector."""
        self.assertEqual(self.collector.reddit_client, self.mock_reddit_client)
        self.assertEqual(self.collector.rate_limiter, self.mock_rate_limiter)
        self.assertEqual(self.collector.error_tracker, self.mock_error_tracker)
        self.assertEqual(self.collector.prometheus_exporter, self.mock_prometheus_exporter)

    def test_get_new_submissions(self):
        """Test fetching new submissions."""
        # Create mock subreddit
        mock_subreddit = MagicMock()
        
        # Create mock submissions
        mock_submission1 = MagicMock()
        mock_submission1.id = "abc123"
        mock_submission2 = MagicMock()
        mock_submission2.id = "def456"
        
        # Setup mock subreddit.new to return an async iterator of submissions
        mock_submissions = [mock_submission1, mock_submission2]
        mock_subreddit.new = MagicMock(return_value=AsyncIterator(mock_submissions))
        
        # Call _get_new_submissions
        result = asyncio.run(self.async_test(
            self.collector._get_new_submissions, mock_subreddit
        ))
        
        # Verify rate limiter was called
        self.mock_rate_limiter.pre_request.assert_called_once()
        
        # Verify prometheus metrics were recorded
        self.mock_prometheus_exporter.record_fetch_operation.assert_called_once_with("latest")
        
        # Verify correct submissions were returned
        self.assertEqual(result, mock_submissions)

    def test_search_submissions(self):
        """Test searching for submissions."""
        # Create mock subreddit
        mock_subreddit = MagicMock()
        
        # Create mock submissions
        mock_submission1 = MagicMock()
        mock_submission1.id = "abc123"
        mock_submission2 = MagicMock()
        mock_submission2.id = "def456"
        
        # Setup mock subreddit.search to return an async iterator of submissions
        mock_submissions = [mock_submission1, mock_submission2]
        mock_subreddit.search = MagicMock(return_value=AsyncIterator(mock_submissions))
        
        # Call _search_submissions
        result = asyncio.run(self.async_test(
            self.collector._search_submissions,
            mock_subreddit,
            query="test query",
            sort="new",
            limit=100
        ))
        
        # Verify rate limiter was called
        self.mock_rate_limiter.pre_request.assert_called_once()
        
        # Verify subreddit.search was called with correct parameters
        # Updated to match the new implementation using params dictionary
        mock_subreddit.search.assert_called_once_with(
            "test query", sort="new", params={"limit": 100}
        )
        
        # Verify prometheus metrics were recorded
        self.mock_prometheus_exporter.record_fetch_operation.assert_called_once_with("historic")
        
        # Verify correct submissions were returned
        self.assertEqual(result, mock_submissions)

    def test_latest(self):
        """Test collecting latest submissions."""
        # Create mock subreddit
        mock_subreddit = MagicMock()
        self.mock_reddit_client.get_subreddit.return_value = mock_subreddit
        
        # Create mock submissions
        mock_submission1 = MagicMock()
        mock_submission1.id = "abc123"
        mock_submission1.created_utc = 1609459200
        mock_submission1.subreddit.display_name = "Wallstreetbets"
        mock_submission1.title = "Test Title 1"
        mock_submission1.selftext = "Test Content 1"
        mock_submission1.author.name = "testuser1"
        mock_submission1.score = 42
        mock_submission1.upvote_ratio = 0.75
        mock_submission1.num_comments = 10
        mock_submission1.url = "https://reddit.com/r/wallstreetbets/comments/abc123/test_title_1"
        mock_submission1.link_flair_text = "DD"
        mock_submission1.over_18 = False
        
        mock_submission2 = MagicMock()
        mock_submission2.id = "def456"
        mock_submission2.created_utc = 1609545600
        mock_submission2.subreddit.display_name = "Stocks"
        mock_submission2.title = "Test Title 2"
        mock_submission2.selftext = "Test Content 2"
        mock_submission2.author.name = "testuser2"
        mock_submission2.score = 100
        mock_submission2.upvote_ratio = 0.9
        mock_submission2.num_comments = 20
        mock_submission2.url = "https://reddit.com/r/stocks/comments/def456/test_title_2"
        mock_submission2.link_flair_text = "Discussion"
        mock_submission2.over_18 = False
        
        # Setup mock for _get_new_submissions
        self.collector._get_new_submissions = AsyncMock()
        self.collector._get_new_submissions.return_value = [mock_submission1, mock_submission2]
        
        # Call latest with a seen ID to filter one submission
        seen_ids = {"def456"}
        result = asyncio.run(self.async_test(
            self.collector.latest, "wallstreetbets", seen_ids
        ))
        
        # Verify get_subreddit was called
        self.mock_reddit_client.get_subreddit.assert_called_once_with("wallstreetbets")
        
        # Verify _get_new_submissions was called
        self.collector._get_new_submissions.assert_called_once_with(mock_subreddit)
        
        # Verify prometheus metrics were recorded for each new submission
        self.mock_prometheus_exporter.record_submission_collected.assert_called_once_with("wallstreetbets")
        
        # Verify one record was returned (one was filtered out as already seen)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "abc123")

    def test_historic(self):
        """Test collecting historic submissions."""
        # Create mock subreddit
        mock_subreddit = MagicMock()
        self.mock_reddit_client.get_subreddit.return_value = mock_subreddit
        
        # Create mock submissions
        mock_submission1 = MagicMock()
        mock_submission1.id = "abc123"
        mock_submission1.created_utc = 1609459200
        mock_submission1.subreddit.display_name = "Wallstreetbets"
        mock_submission1.title = "Test Title 1"
        mock_submission1.selftext = "Test Content 1"
        mock_submission1.author.name = "testuser1"
        mock_submission1.score = 42
        mock_submission1.upvote_ratio = 0.75
        mock_submission1.num_comments = 10
        mock_submission1.url = "https://reddit.com/r/wallstreetbets/comments/abc123/test_title_1"
        mock_submission1.link_flair_text = "DD"
        mock_submission1.over_18 = False
        
        mock_submission2 = MagicMock()
        mock_submission2.id = "def456"
        mock_submission2.created_utc = 1609545600
        mock_submission2.subreddit.display_name = "Stocks"
        mock_submission2.title = "Test Title 2"
        mock_submission2.selftext = "Test Content 2"
        mock_submission2.author.name = "testuser2"
        mock_submission2.score = 100
        mock_submission2.upvote_ratio = 0.9
        mock_submission2.num_comments = 20
        mock_submission2.url = "https://reddit.com/r/stocks/comments/def456/test_title_2"
        mock_submission2.link_flair_text = "Discussion"
        mock_submission2.over_18 = False
        
        # Setup mock for _search_submissions
        self.collector._search_submissions = AsyncMock()
        self.collector._search_submissions.return_value = [mock_submission1, mock_submission2]
        
        # Call historic with a seen ID to filter one submission
        seen_ids = {"def456"}
        end_epoch = 1609632000  # 2021-01-03 00:00:00 UTC
        window_days = 7
        
        result = asyncio.run(self.async_test(
            self.collector.historic, "wallstreetbets", end_epoch, window_days, seen_ids
        ))
        
        # Verify get_subreddit was called
        self.mock_reddit_client.get_subreddit.assert_called_once_with("wallstreetbets")
        
        # Verify _search_submissions was called with correct query
        # Start epoch should be end_epoch - (window_days * 86400)
        start_epoch = end_epoch - (window_days * 86400)
        expected_query = f"timestamp:{start_epoch}..{end_epoch}"
        
        self.collector._search_submissions.assert_called_once_with(
            mock_subreddit, query=expected_query, sort="new", limit=1000
        )
        
        # Verify prometheus metrics were recorded for each new submission
        self.mock_prometheus_exporter.record_submission_collected.assert_called_once_with("wallstreetbets")
        
        # Verify one record was returned (one was filtered out as already seen)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "abc123")

    def test_error_handling(self):
        """Test error handling in collector methods."""
        # Setup mock to raise exception
        self.mock_reddit_client.get_subreddit.side_effect = Exception("Test error")
        
        # Call latest - should handle the exception and return empty list
        result = asyncio.run(self.async_test(
            self.collector.latest, "wallstreetbets", set()
        ))
        
        # Verify empty list was returned
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
