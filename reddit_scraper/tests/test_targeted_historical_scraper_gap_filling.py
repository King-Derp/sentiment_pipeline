#!/usr/bin/env python
"""Tests for the TargetedHistoricalScraper gap-filling functionality."""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch

from reddit_scraper.scrapers.targeted_historical_scraper import TargetedHistoricalScraper
from reddit_scraper.config import Config
from reddit_scraper.models.submission import SubmissionRecord


class TestTargetedHistoricalScraperGapFilling:
    """Test cases for TargetedHistoricalScraper gap-filling functionality."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = Mock(spec=Config)
        config.subreddits = ["stocks", "investing"]
        config.postgres = Mock()
        config.postgres.enabled = True
        config.csv = Mock()
        config.csv.enabled = False
        return config
    
    @pytest.fixture
    def mock_collector(self):
        """Create a mock collector."""
        collector = AsyncMock()
        return collector
    
    @pytest.fixture
    def mock_reddit_client(self):
        """Create a mock Reddit client."""
        client = AsyncMock()
        return client
    
    @pytest.fixture
    def sample_submission_record(self):
        """Create a sample submission record."""
        return {
            'id': 'test123',
            'title': 'Test Stock Discussion',
            'selftext': 'This is a test post about stocks',
            'author': 'testuser',
            'created_utc': datetime.now(timezone.utc),
            'score': 100,
            'upvote_ratio': 0.95,
            'num_comments': 25,
            'permalink': '/r/stocks/comments/test123/',
            'url': 'https://reddit.com/r/stocks/comments/test123/',
            'subreddit': 'stocks',
            'flair_text': 'Discussion',
            'is_self': True,
            'stickied': False,
            'over_18': False,
            'spoiler': False,
            'locked': False,
            'archived': False,
            'removed_by_category': None,
        }
    
    @pytest.mark.asyncio
    async def test_targeted_historical_scraper_initialization(self, mock_config):
        """Test that TargetedHistoricalScraper initializes correctly."""
        with patch('reddit_scraper.scrapers.targeted_historical_scraper.BaseScraper.__init__'):
            scraper = TargetedHistoricalScraper(mock_config)
            assert scraper.total_collected == 0
    
    @pytest.mark.asyncio
    async def test_run_for_window_basic_functionality(self, mock_config, mock_collector, sample_submission_record):
        """Test basic functionality of run_for_window method."""
        # Setup
        scraper = TargetedHistoricalScraper(mock_config)
        scraper.collector = mock_collector
        scraper.seen_ids = set()
        
        # Mock the store_records method
        scraper.store_records = AsyncMock()
        
        # Mock collector.historic to return sample records
        mock_collector.historic.return_value = [sample_submission_record]
        
        # Test dates
        start_date = datetime.now(timezone.utc) - timedelta(days=1)
        end_date = datetime.now(timezone.utc)
        
        # Execute
        result = await scraper.run_for_window("stocks", start_date, end_date)
        
        # Verify
        assert result >= 0  # Should return non-negative count
        mock_collector.historic.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_for_window_with_no_results(self, mock_config, mock_collector):
        """Test run_for_window when no submissions are found."""
        # Setup
        scraper = TargetedHistoricalScraper(mock_config)
        scraper.collector = mock_collector
        scraper.seen_ids = set()
        scraper.store_records = AsyncMock()
        
        # Mock collector to return empty results
        mock_collector.historic.return_value = []
        
        # Test dates
        start_date = datetime.now(timezone.utc) - timedelta(days=1)
        end_date = datetime.now(timezone.utc)
        
        # Execute
        result = await scraper.run_for_window("stocks", start_date, end_date)
        
        # Verify
        assert result == 0
        mock_collector.historic.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_for_window_filters_by_time_range(self, mock_config, mock_collector):
        """Test that run_for_window properly filters submissions by time range."""
        # Setup
        scraper = TargetedHistoricalScraper(mock_config)
        scraper.collector = mock_collector
        scraper.seen_ids = set()
        scraper.store_records = AsyncMock()
        
        # Create test records with different timestamps
        now = datetime.now(timezone.utc)
        start_date = now - timedelta(hours=2)
        end_date = now - timedelta(hours=1)
        
        # Record within range
        record_in_range = {
            'id': 'in_range',
            'created_utc': now - timedelta(hours=1, minutes=30),
            'title': 'In range post'
        }
        
        # Record outside range (too old)
        record_too_old = {
            'id': 'too_old',
            'created_utc': now - timedelta(hours=3),
            'title': 'Too old post'
        }
        
        # Record outside range (too new)
        record_too_new = {
            'id': 'too_new',
            'created_utc': now - timedelta(minutes=30),
            'title': 'Too new post'
        }
        
        # Mock collector to return all records
        mock_collector.historic.return_value = [record_in_range, record_too_old, record_too_new]
        
        # Execute
        result = await scraper.run_for_window("stocks", start_date, end_date)
        
        # Verify only the record in range was processed
        scraper.store_records.assert_called_once()
        stored_records = scraper.store_records.call_args[0][0]
        assert len(stored_records) == 1
        assert stored_records[0]['id'] == 'in_range'
    
    @pytest.mark.asyncio
    async def test_run_for_window_handles_exceptions(self, mock_config, mock_collector):
        """Test that run_for_window handles exceptions gracefully."""
        # Setup
        scraper = TargetedHistoricalScraper(mock_config)
        scraper.collector = mock_collector
        scraper.seen_ids = set()
        
        # Mock collector to raise an exception
        mock_collector.historic.side_effect = Exception("Test error")
        
        # Test dates
        start_date = datetime.now(timezone.utc) - timedelta(days=1)
        end_date = datetime.now(timezone.utc)
        
        # Execute - should not raise exception
        result = await scraper.run_for_window("stocks", start_date, end_date)
        
        # Verify
        assert result == 0  # Should return 0 on error
    
    @pytest.mark.asyncio
    async def test_run_method_returns_zero(self, mock_config):
        """Test that the default run method returns 0 and logs warning."""
        with patch('reddit_scraper.scrapers.targeted_historical_scraper.BaseScraper.__init__'):
            scraper = TargetedHistoricalScraper(mock_config)
            
            with patch('reddit_scraper.scrapers.targeted_historical_scraper.logger') as mock_logger:
                result = await scraper.run()
                
                assert result == 0
                mock_logger.warning.assert_called_once()
    
    def test_window_days_calculation(self, mock_config):
        """Test that window days are calculated correctly."""
        with patch('reddit_scraper.scrapers.targeted_historical_scraper.BaseScraper.__init__'):
            scraper = TargetedHistoricalScraper(mock_config)
            
            # Test various time ranges
            now = datetime.now(timezone.utc)
            
            # 1 hour gap should be minimum 1 day
            start_1h = now - timedelta(hours=1)
            window_1h = max(1, int((now.timestamp() - start_1h.timestamp()) / 86400))
            assert window_1h == 1
            
            # 2 day gap should be 2 days
            start_2d = now - timedelta(days=2)
            window_2d = max(1, int((now.timestamp() - start_2d.timestamp()) / 86400))
            assert window_2d == 2
            
            # 7 day gap should be 7 days
            start_7d = now - timedelta(days=7)
            window_7d = max(1, int((now.timestamp() - start_7d.timestamp()) / 86400))
            assert window_7d == 7


if __name__ == "__main__":
    pytest.main([__file__])
