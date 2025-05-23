"""Tests for the CLI module."""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import typer
from typer.testing import CliRunner

from reddit_scraper.cli import app


class TestCli(unittest.TestCase):
    """Test cases for the CLI interface."""

    def setUp(self):
        """Set up test environment."""
        self.runner = CliRunner()
        
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "config.yaml")
        
        # Create a minimal config file
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write("""
subreddits:
  - wallstreetbets
  - stocks
window_days: 30
csv_path: data/test.csv
initial_backfill: true
failure_threshold: 5
maintenance_interval_sec: 61
            """)

    def tearDown(self):
        """Clean up test environment."""
        self.temp_dir.cleanup()

    @patch("reddit_scraper.cli.run_scraper")
    def test_scrape_command(self, mock_run_scraper):
        """Test the scrape command."""
        # Mock asyncio.run to avoid actually running the scraper
        with patch("asyncio.run") as mock_run:
            # Run the command
            result = self.runner.invoke(app, ["scrape", "--config", self.config_path])
            
            # Check that the command ran successfully
            self.assertEqual(result.exit_code, 0)
            
            # Check that asyncio.run was called with run_scraper
            mock_run.assert_called_once()
            
    @patch("reddit_scraper.cli.run_scraper")
    def test_scrape_command_with_daemon(self, mock_run_scraper):
        """Test the scrape command with daemon mode."""
        # Mock asyncio.run to avoid actually running the scraper
        with patch("asyncio.run") as mock_run:
            # Run the command with daemon flag
            result = self.runner.invoke(app, [
                "scrape", 
                "--config", self.config_path,
                "--daemon"
            ])
            
            # Check that the command ran successfully
            self.assertEqual(result.exit_code, 0)
            
            # Check that asyncio.run was called with run_scraper
            mock_run.assert_called_once()
            
    @patch("reddit_scraper.cli.Config.from_files")
    def test_metrics_command(self, mock_from_files):
        """Test the metrics command."""
        # Mock Config.from_files to return a mock config
        mock_config = MagicMock()
        mock_config.csv_path = "data/test.csv"
        mock_config.subreddits = ["wallstreetbets", "stocks"]
        mock_from_files.return_value = mock_config
        
        # Mock os.path.exists and os.path.getsize
        with patch("os.path.exists", return_value=False):
            with patch("os.path.getsize", return_value=1024):
                # Run the command
                result = self.runner.invoke(app, ["metrics", "--config", self.config_path])
                
                # Check that the command ran successfully
                self.assertEqual(result.exit_code, 0)
                
                # Check that the output contains expected keys
                self.assertIn("timestamp", result.stdout)
                self.assertIn("csv_path", result.stdout)
                self.assertIn("subreddits", result.stdout)


if __name__ == "__main__":
    unittest.main()
