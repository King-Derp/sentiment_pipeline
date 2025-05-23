import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import os

from reddit_scraper.scrapers.targeted_historical_scraper import TargetedHistoricalScraper
from reddit_scraper.scrapers.deep_historical_scraper import DeepHistoricalScraper
from reddit_scraper.scrapers.hybrid_historical_scraper import HybridHistoricalScraper
from reddit_scraper.base_scraper import BaseScraper


class TestScrapers(unittest.TestCase):
    """Tests for the refactored scrapers."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock config file path
        self.config_path = "mock_config.yaml"
        
        # Create patches for the BaseScraper methods
        self.init_patch = patch.object(BaseScraper, '__init__', return_value=None)
        self.execute_patch = patch.object(BaseScraper, 'execute', new_callable=AsyncMock)
        self.store_records_patch = patch.object(BaseScraper, 'store_records', new_callable=AsyncMock)
        
        # Start the patches
        self.mock_init = self.init_patch.start()
        self.mock_execute = self.execute_patch.start()
        self.mock_store_records = self.store_records_patch.start()
        
    def tearDown(self):
        """Tear down test fixtures."""
        # Stop the patches
        self.init_patch.stop()
        self.execute_patch.stop()
        self.store_records_patch.stop()
    
    def test_targeted_scraper_initialization(self):
        """Test that TargetedHistoricalScraper initializes correctly."""
        scraper = TargetedHistoricalScraper(self.config_path)
        self.mock_init.assert_called_once_with(self.config_path)
        self.assertIsInstance(scraper, TargetedHistoricalScraper)
    
    def test_deep_scraper_initialization(self):
        """Test that DeepHistoricalScraper initializes correctly."""
        scraper = DeepHistoricalScraper(self.config_path)
        self.mock_init.assert_called_once_with(self.config_path)
        self.assertIsInstance(scraper, DeepHistoricalScraper)
    
    def test_hybrid_scraper_initialization(self):
        """Test that HybridHistoricalScraper initializes correctly."""
        scraper = HybridHistoricalScraper(self.config_path)
        self.mock_init.assert_called_once_with(self.config_path)
        self.assertIsInstance(scraper, HybridHistoricalScraper)
    
    @patch('targeted_historical_scraper.search_by_term', new_callable=AsyncMock, return_value=[])
    @patch('targeted_historical_scraper.search_by_year', new_callable=AsyncMock, return_value=[])
    async def test_targeted_scraper_run(self, mock_search_by_year, mock_search_by_term):
        """Test that TargetedHistoricalScraper.run works correctly."""
        # Create a scraper with mocked dependencies
        scraper = TargetedHistoricalScraper()
        scraper.collector = MagicMock()
        scraper.config = MagicMock()
        scraper.config.subreddits = ["test_subreddit"]
        scraper.seen_ids = set()
        
        # Run the scraper
        result = await scraper.run()
        
        # Check that the search methods were called
        self.assertTrue(mock_search_by_term.called or mock_search_by_year.called)
        self.assertEqual(result, 0)  # No records collected in our mock
    
    @patch('deep_historical_scraper.search_by_term', new_callable=AsyncMock, return_value=[])
    @patch('deep_historical_scraper.create_time_windows', return_value=[])
    async def test_deep_scraper_run(self, mock_create_time_windows, mock_search_by_term):
        """Test that DeepHistoricalScraper.run works correctly."""
        # Create a scraper with mocked dependencies
        scraper = DeepHistoricalScraper()
        scraper.collector = MagicMock()
        scraper.config = MagicMock()
        scraper.config.subreddits = ["test_subreddit"]
        scraper.seen_ids = set()
        
        # Run the scraper
        result = await scraper.run()
        
        # Check that the time windows were created
        mock_create_time_windows.assert_called_once()
        self.assertEqual(result, 0)  # No records collected in our mock
    
    @patch('hybrid_historical_scraper.search_by_term', new_callable=AsyncMock, return_value=[])
    async def test_hybrid_scraper_run(self, mock_search_by_term):
        """Test that HybridHistoricalScraper.run works correctly."""
        # Create a scraper with mocked dependencies
        scraper = HybridHistoricalScraper()
        scraper.collector = MagicMock()
        scraper.config = MagicMock()
        scraper.config.subreddits = ["test_subreddit"]
        scraper.seen_ids = set()
        
        # Run the scraper
        result = await scraper.run()
        
        # Check that search_by_term was called
        mock_search_by_term.assert_called()
        self.assertEqual(result, 0)  # No records collected in our mock


if __name__ == '__main__':
    unittest.main()
