"""Tests for the mapping module."""

import unittest
from unittest.mock import Mock

from reddit_scraper.models.mapping import submission_to_record, submissions_to_records


class TestMapping(unittest.TestCase):
    """Test cases for the mapping functions."""

    def test_submission_to_record(self):
        """Test converting a submission to a record."""
        # Create a mock submission
        submission = Mock()
        submission.id = "abc123"
        submission.created_utc = 1609459200  # 2021-01-01 00:00:00 UTC
        submission.subreddit.display_name = "Wallstreetbets"
        submission.title = "Test Title"
        submission.selftext = "Test Content"
        submission.author.name = "testuser"
        submission.score = 42
        submission.upvote_ratio = 0.75
        submission.num_comments = 10
        submission.url = "https://reddit.com/r/wallstreetbets/comments/abc123/test_title"
        submission.link_flair_text = "DD"
        submission.over_18 = False
        
        # Convert to record
        record = submission_to_record(submission)
        
        # Check record fields
        self.assertEqual(record["id"], "abc123")
        self.assertEqual(record["created_utc"], 1609459200)
        self.assertEqual(record["subreddit"], "wallstreetbets")  # Should be lowercase
        self.assertEqual(record["title"], "Test Title")
        self.assertEqual(record["selftext"], "Test Content")
        self.assertEqual(record["author"], "testuser")
        self.assertEqual(record["score"], 42)
        self.assertEqual(record["upvote_ratio"], 0.75)
        self.assertEqual(record["num_comments"], 10)
        self.assertEqual(record["url"], "https://reddit.com/r/wallstreetbets/comments/abc123/test_title")
        self.assertEqual(record["flair_text"], "DD")
        self.assertEqual(record["over_18"], False)

    def test_submission_to_record_with_deleted_author(self):
        """Test converting a submission with a deleted author."""
        # Create a mock submission with deleted author
        submission = Mock()
        submission.id = "abc123"
        submission.created_utc = 1609459200
        submission.subreddit.display_name = "Wallstreetbets"
        submission.title = "Test Title"
        submission.selftext = "Test Content"
        submission.author = None  # Deleted author
        submission.score = 42
        submission.upvote_ratio = 0.75
        submission.num_comments = 10
        submission.url = "https://reddit.com/r/wallstreetbets/comments/abc123/test_title"
        submission.link_flair_text = None  # No flair
        submission.over_18 = False
        
        # Convert to record
        record = submission_to_record(submission)
        
        # Check record fields
        self.assertEqual(record["author"], "[deleted]")
        self.assertIsNone(record["flair_text"])

    def test_submissions_to_records(self):
        """Test converting multiple submissions to records."""
        # Create mock submissions
        submission1 = Mock()
        submission1.id = "abc123"
        submission1.created_utc = 1609459200
        submission1.subreddit.display_name = "Wallstreetbets"
        submission1.title = "Test Title 1"
        submission1.selftext = "Test Content 1"
        submission1.author.name = "testuser1"
        submission1.score = 42
        submission1.upvote_ratio = 0.75
        submission1.num_comments = 10
        submission1.url = "https://reddit.com/r/wallstreetbets/comments/abc123/test_title_1"
        submission1.link_flair_text = "DD"
        submission1.over_18 = False
        
        submission2 = Mock()
        submission2.id = "def456"
        submission2.created_utc = 1609545600  # 2021-01-02 00:00:00 UTC
        submission2.subreddit.display_name = "Stocks"
        submission2.title = "Test Title 2"
        submission2.selftext = "Test Content 2"
        submission2.author.name = "testuser2"
        submission2.score = 100
        submission2.upvote_ratio = 0.9
        submission2.num_comments = 20
        submission2.url = "https://reddit.com/r/stocks/comments/def456/test_title_2"
        submission2.link_flair_text = "Discussion"
        submission2.over_18 = False
        
        # Convert to records
        records = submissions_to_records([submission1, submission2])
        
        # Check records
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["id"], "abc123")
        self.assertEqual(records[0]["title"], "Test Title 1")
        self.assertEqual(records[1]["id"], "def456")
        self.assertEqual(records[1]["title"], "Test Title 2")

    def test_submissions_to_records_with_error(self):
        """Test handling errors during conversion."""
        # Create mock submissions - one valid, one that raises an exception
        submission1 = Mock()
        submission1.id = "abc123"
        submission1.created_utc = 1609459200
        submission1.subreddit.display_name = "Wallstreetbets"
        submission1.title = "Test Title 1"
        submission1.selftext = "Test Content 1"
        submission1.author.name = "testuser1"
        submission1.score = 42
        submission1.upvote_ratio = 0.75
        submission1.num_comments = 10
        submission1.url = "https://reddit.com/r/wallstreetbets/comments/abc123/test_title_1"
        submission1.link_flair_text = "DD"
        submission1.over_18 = False
        
        submission2 = Mock()
        submission2.id = "def456"
        # This will cause an attribute error when accessing created_utc
        submission2.created_utc = Mock(side_effect=AttributeError("No created_utc"))
        
        # Convert to records - should only get one valid record
        records = submissions_to_records([submission1, submission2])
        
        # Check records
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["id"], "abc123")


if __name__ == "__main__":
    unittest.main()
