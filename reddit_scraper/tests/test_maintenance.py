"""Tests for the maintenance module, including auto-backfill functionality."""

import asyncio
import os
import tempfile
import time
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

import pandas as pd

from reddit_scraper.collector.maintenance import MaintenanceRunner
from reddit_scraper.config import Config


class TestMaintenanceRunner(unittest.TestCase):
    """Tests for the MaintenanceRunner class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary CSV file
        self.temp_dir = tempfile.TemporaryDirectory()
        self.csv_path = os.path.join(self.temp_dir.name, "test_data.csv")
        
        # Create a mock config
        self.config = MagicMock(spec=Config)
        self.config.csv_path = self.csv_path
        self.config.maintenance_interval_sec = 61  # 61 seconds for near real-time data
        self.config.auto_backfill_gap_threshold_sec = 600  # 10 minutes threshold for backfill
        self.config.subreddits = ["test_subreddit"]
        
        # Create mocks for collector and data_sink
        self.collector = MagicMock()
        self.collector.latest = AsyncMock(return_value=[])
        
        self.data_sink = MagicMock()
        self.data_sink.load_ids = MagicMock(return_value=set())
        self.data_sink.append = MagicMock(return_value=0)
        
        # Create the maintenance runner
        self.runner = MaintenanceRunner(
            config=self.config,
            collector=self.collector,
            data_sink=self.data_sink
        )
        
    def tearDown(self):
        """Tear down test fixtures."""
        self.temp_dir.cleanup()
    
    @patch('reddit_scraper.collector.maintenance.BackfillRunner')
    async def test_check_for_data_gap_no_gap(self, mock_backfill):
        """Test that no gap is detected when timestamps are close."""
        # Set the last data timestamp to be recent
        now = time.time()
        self.runner.last_data_timestamp = now - 300  # 5 minutes ago
        
        # Check for gap
        gap_exists, _ = await self.runner._check_for_data_gap()
        
        # Assert no gap was detected
        self.assertFalse(gap_exists)
    
    @patch('reddit_scraper.collector.maintenance.BackfillRunner')
    async def test_check_for_data_gap_with_gap(self, mock_backfill):
        """Test that a gap is detected when timestamps are far apart."""
        # Set the last data timestamp to be old
        now = time.time()
        # Use a gap just slightly larger than the configured threshold
        self.runner.last_data_timestamp = now - (self.config.auto_backfill_gap_threshold_sec + 60)  # threshold + 1 minute
        
        # Check for gap
        gap_exists, gap_start = await self.runner._check_for_data_gap()
        
        # Assert gap was detected
        self.assertTrue(gap_exists)
        self.assertEqual(gap_start, self.runner.last_data_timestamp)
    
    @patch('reddit_scraper.collector.maintenance.BackfillRunner')
    async def test_get_last_data_timestamp_empty_file(self, mock_backfill):
        """Test getting last timestamp from an empty file."""
        # Ensure file doesn't exist
        if os.path.exists(self.csv_path):
            os.remove(self.csv_path)
        
        # Get timestamp
        timestamp = await self.runner._get_last_data_timestamp()
        
        # Assert timestamp is 0
        self.assertEqual(timestamp, 0.0)
    
    @patch('reddit_scraper.collector.maintenance.BackfillRunner')
    async def test_get_last_data_timestamp_with_data(self, mock_backfill):
        """Test getting last timestamp from a file with data."""
        # Create a test CSV with some data
        now = time.time()
        test_data = pd.DataFrame({
            'id': ['1', '2', '3'],
            'created_utc': [now - 3600, now - 1800, now - 900]  # 1 hour, 30 min, 15 min ago
        })
        test_data.to_csv(self.csv_path, index=False)
        
        # Get timestamp
        timestamp = await self.runner._get_last_data_timestamp()
        
        # Assert timestamp is the most recent one
        self.assertEqual(timestamp, now - 900)
    
    @patch('reddit_scraper.collector.maintenance.BackfillRunner')
    async def test_run_backfill(self, mock_backfill_class):
        """Test running a backfill."""
        # Mock the backfill runner
        mock_backfill = MagicMock()
        mock_backfill.run = AsyncMock(return_value=10)  # 10 submissions collected
        mock_backfill_class.return_value = mock_backfill
        
        # Set up seen IDs
        self.runner.seen_ids = {'id1', 'id2'}
        
        # Run backfill
        start_timestamp = time.time() - 3600  # 1 hour ago
        collected = await self.runner._run_backfill(start_timestamp)
        
        # Assert backfill was run with correct timestamp
        mock_backfill_class.assert_called_once_with(self.config, self.collector, self.data_sink)
        mock_backfill.run.assert_called_once_with(int(start_timestamp))
        
        # Assert stats were updated
        self.assertEqual(collected, 10)
        self.assertEqual(self.runner.stats["backfills_performed"], 1)
        self.assertEqual(self.runner.stats["backfill_collected"], 10)
    
    @patch('reddit_scraper.collector.maintenance.BackfillRunner')
    @patch.object(MaintenanceRunner, '_check_for_data_gap')
    @patch.object(MaintenanceRunner, '_run_backfill')
    async def test_run_once_with_gap(self, mock_run_backfill, mock_check_gap, mock_backfill_class):
        """Test that run_once detects and fills gaps."""
        # Mock gap detection
        mock_check_gap.return_value = (True, time.time() - 3600)  # Gap exists, starting 1 hour ago
        
        # Mock backfill
        mock_run_backfill.return_value = 15  # 15 submissions collected in backfill
        
        # Mock latest collection
        self.collector.latest.return_value = [{'id': 'new1'}, {'id': 'new2'}]  # 2 new submissions
        
        # Run once
        collected = await self.runner.run_once()
        
        # Assert gap was checked and backfill was run
        mock_check_gap.assert_called_once()
        mock_run_backfill.assert_called_once()
        
        # Assert both backfill and latest submissions were collected
        self.assertEqual(collected, 17)  # 15 from backfill + 2 from latest


if __name__ == '__main__':
    unittest.main()
