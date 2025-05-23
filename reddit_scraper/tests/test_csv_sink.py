"""Tests for the CSV storage implementation."""

import os
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from reddit_scraper.models.submission import SubmissionRecord
from reddit_scraper.storage.csv_sink import CsvSink


class TestCsvSink(unittest.TestCase):
    """Test cases for the CsvSink class."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.csv_path = os.path.join(self.temp_dir.name, "test.csv")
        
        # Sample records
        self.sample_records: list[SubmissionRecord] = [
            {
                "id": "abc123",
                "created_utc": 1609459200,
                "subreddit": "wallstreetbets",
                "title": "Test Title 1",
                "selftext": "Test Content 1",
                "author": "testuser1",
                "score": 42,
                "upvote_ratio": 0.75,
                "num_comments": 10,
                "url": "https://reddit.com/r/wallstreetbets/comments/abc123/test_title_1",
                "flair_text": "DD",
                "over_18": False
            },
            {
                "id": "def456",
                "created_utc": 1609545600,
                "subreddit": "stocks",
                "title": "Test Title 2",
                "selftext": "Test Content 2",
                "author": "testuser2",
                "score": 100,
                "upvote_ratio": 0.9,
                "num_comments": 20,
                "url": "https://reddit.com/r/stocks/comments/def456/test_title_2",
                "flair_text": "Discussion",
                "over_18": False
            }
        ]

    def tearDown(self):
        """Clean up test environment."""
        self.temp_dir.cleanup()

    def test_append_to_new_file(self):
        """Test appending records to a new CSV file."""
        # Create sink
        sink = CsvSink(self.csv_path)
        
        # Append records
        count = sink.append(self.sample_records)
        
        # Check result
        self.assertEqual(count, 2)
        self.assertTrue(os.path.exists(self.csv_path))
        
        # Check file content
        df = pd.read_csv(self.csv_path)
        self.assertEqual(len(df), 2)
        self.assertEqual(df.iloc[0]["id"], "abc123")
        self.assertEqual(df.iloc[1]["id"], "def456")
        
        # Check column order
        self.assertEqual(list(df.columns), CsvSink.COLUMNS)

    def test_append_to_existing_file(self):
        """Test appending records to an existing CSV file."""
        # Create sink and append first record
        sink = CsvSink(self.csv_path)
        sink.append([self.sample_records[0]])
        
        # Append second record
        count = sink.append([self.sample_records[1]])
        
        # Check result
        self.assertEqual(count, 1)
        
        # Check file content
        df = pd.read_csv(self.csv_path)
        self.assertEqual(len(df), 2)
        self.assertEqual(df.iloc[0]["id"], "abc123")
        self.assertEqual(df.iloc[1]["id"], "def456")

    def test_load_ids_from_empty_file(self):
        """Test loading IDs from a non-existent file."""
        sink = CsvSink(self.csv_path)
        ids = sink.load_ids()
        
        self.assertEqual(len(ids), 0)

    def test_load_ids_from_existing_file(self):
        """Test loading IDs from an existing file."""
        # Create sink and append records
        sink = CsvSink(self.csv_path)
        sink.append(self.sample_records)
        
        # Load IDs
        ids = sink.load_ids()
        
        # Check result
        self.assertEqual(len(ids), 2)
        self.assertIn("abc123", ids)
        self.assertIn("def456", ids)

    def test_append_empty_list(self):
        """Test appending an empty list of records."""
        sink = CsvSink(self.csv_path)
        count = sink.append([])
        
        self.assertEqual(count, 0)
        self.assertFalse(os.path.exists(self.csv_path))


if __name__ == "__main__":
    unittest.main()
