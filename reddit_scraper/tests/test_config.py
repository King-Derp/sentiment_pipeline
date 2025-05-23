"""Tests for the configuration module."""

import os
import tempfile
import unittest
from pathlib import Path

import yaml

from reddit_scraper.config import Config, RateLimitConfig


class TestConfig(unittest.TestCase):
    """Test cases for the Config class."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "config.yaml")
        self.env_path = os.path.join(self.temp_dir.name, ".env")
        
        # Sample config
        self.sample_config = {
            "subreddits": ["wallstreetbets", "stocks", "investing"],
            "window_days": 30,
            "csv_path": "data/test.csv",
            "initial_backfill": True,
            "failure_threshold": 5,
            "maintenance_interval_sec": 61,
            "rate_limit": {
                "max_requests_per_minute": 100,
                "min_remaining_calls": 5,
                "sleep_buffer_sec": 2
            }
        }
        
        # Write sample config
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self.sample_config, f)
        
        # Sample env
        with open(self.env_path, "w", encoding="utf-8") as f:
            f.write("REDDIT_CLIENT_ID=test_client_id\n")
            f.write("REDDIT_CLIENT_SECRET=test_client_secret\n")
            f.write("REDDIT_USERNAME=test_username\n")
            f.write("REDDIT_PASSWORD=test_password\n")
            f.write("REDDIT_USER_AGENT=test_user_agent\n")

    def tearDown(self):
        """Clean up test environment."""
        self.temp_dir.cleanup()

    def test_load_from_files(self):
        """Test loading configuration from files."""
        config = Config.from_files(self.config_path, self.env_path)
        
        # Check env values
        self.assertEqual(config.client_id, "test_client_id")
        self.assertEqual(config.client_secret, "test_client_secret")
        self.assertEqual(config.username, "test_username")
        self.assertEqual(config.password, "test_password")
        self.assertEqual(config.user_agent, "test_user_agent")
        
        # Check yaml values
        self.assertEqual(config.subreddits, ["wallstreetbets", "stocks", "investing"])
        self.assertEqual(config.window_days, 30)
        self.assertEqual(config.csv_path, "data/test.csv")
        self.assertEqual(config.initial_backfill, True)
        self.assertEqual(config.failure_threshold, 5)
        self.assertEqual(config.maintenance_interval_sec, 61)
        
        # Check rate limit config
        self.assertEqual(config.rate_limit.max_requests_per_minute, 100)
        self.assertEqual(config.rate_limit.min_remaining_calls, 5)
        self.assertEqual(config.rate_limit.sleep_buffer_sec, 2)

    def test_validate_valid_config(self):
        """Test validation with valid configuration."""
        config = Config.from_files(self.config_path, self.env_path)
        errors = config.validate()
        self.assertEqual(len(errors), 0)

    def test_validate_invalid_config(self):
        """Test validation with invalid configuration."""
        # Create invalid config
        config = Config()
        config.client_id = ""  # Missing client_id
        config.subreddits = []  # Empty subreddits
        config.window_days = 0  # Invalid window_days
        
        errors = config.validate()
        # Check for the core validation errors we care about
        self.assertIn("Missing REDDIT_CLIENT_ID", ' '.join(errors))
        self.assertIn("No subreddits specified", ' '.join(errors))
        self.assertIn("window_days must be greater than 0", ' '.join(errors))
        
        # We don't check the exact number of errors since it may change as we add more validation rules


if __name__ == "__main__":
    unittest.main()
