"""Tests for the rate limiter module."""

import asyncio
import time
import unittest
from unittest.mock import patch, MagicMock

from reddit_scraper.collector.rate_limiter import RateLimiter
from reddit_scraper.config import RateLimitConfig


class TestRateLimiter(unittest.TestCase):
    """Test cases for the RateLimiter class."""

    def setUp(self):
        """Set up test environment."""
        self.config = RateLimitConfig(
            max_requests_per_minute=60,  # 1 request per second
            min_remaining_calls=5,
            sleep_buffer_sec=1
        )
        self.rate_limiter = RateLimiter(self.config)

    @patch('time.time')
    @patch('asyncio.sleep')
    async def test_pre_request_absolute_rate_limit(self, mock_sleep, mock_time):
        """Test that pre_request enforces the absolute rate limit."""
        # Setup mock time to simulate requests
        mock_time.side_effect = [100.0, 100.5]  # First call and second call times
        self.rate_limiter.last_request_time = 100.0  # Last request was at t=100

        # Call pre_request - should sleep to enforce 1 req/sec rate limit
        await self.rate_limiter.pre_request()

        # Verify sleep was called with the correct duration
        # We're at t=100.5, but need to wait until t=101.0 (1 sec after last request)
        mock_sleep.assert_called_once_with(0.5)

    @patch('time.time')
    @patch('asyncio.sleep')
    async def test_pre_request_no_sleep_needed(self, mock_sleep, mock_time):
        """Test that pre_request doesn't sleep when not needed."""
        # Setup mock time to simulate requests with enough time between them
        mock_time.side_effect = [100.0, 101.5]  # First call and second call times
        self.rate_limiter.last_request_time = 100.0  # Last request was at t=100

        # Call pre_request - should not sleep as enough time has passed
        await self.rate_limiter.pre_request()

        # Verify sleep was not called
        mock_sleep.assert_not_called()

    @patch('time.time')
    @patch('asyncio.sleep')
    async def test_pre_request_ratelimit_headers(self, mock_sleep, mock_time):
        """Test that pre_request respects X-Ratelimit headers."""
        # Setup mock time
        mock_time.side_effect = [100.0, 100.0, 100.0]
        
        # Setup rate limiter state to simulate approaching rate limit
        self.rate_limiter.remaining_calls = 3  # Below min_remaining_calls (5)
        self.rate_limiter.reset_timestamp = 110.0  # Reset in 10 seconds
        
        # Call pre_request - should sleep until reset + buffer
        await self.rate_limiter.pre_request()
        
        # Verify sleep was called with the correct duration (10s until reset + 1s buffer)
        mock_sleep.assert_called_once_with(11.0)
        
        # Verify rate limit tracking was reset
        self.assertIsNone(self.rate_limiter.remaining_calls)
        self.assertIsNone(self.rate_limiter.reset_timestamp)

    def test_update_from_headers(self):
        """Test updating rate limit tracking from response headers."""
        # Mock headers
        headers = {
            "x-ratelimit-remaining": "42",
            "x-ratelimit-reset": "30"
        }
        
        # Update from headers
        with patch('time.time', return_value=100.0):
            self.rate_limiter.update_from_headers(headers)
        
        # Verify tracking was updated
        self.assertEqual(self.rate_limiter.remaining_calls, 42)
        self.assertEqual(self.rate_limiter.reset_timestamp, 130.0)  # 100 + 30
        self.assertEqual(self.rate_limiter.last_request_time, 100.0)

    def test_update_from_headers_invalid_values(self):
        """Test handling invalid header values."""
        # Mock headers with invalid values
        headers = {
            "x-ratelimit-remaining": "invalid",
            "x-ratelimit-reset": "also-invalid"
        }
        
        # Update from headers
        with patch('time.time', return_value=100.0):
            self.rate_limiter.update_from_headers(headers)
        
        # Verify tracking was not updated
        self.assertIsNone(self.rate_limiter.remaining_calls)
        self.assertIsNone(self.rate_limiter.reset_timestamp)
        self.assertEqual(self.rate_limiter.last_request_time, 100.0)

    @patch('time.time')
    @patch('asyncio.sleep')
    async def test_handle_429_with_retry_after(self, mock_sleep, mock_time):
        """Test handling a 429 response with Retry-After header."""
        mock_time.return_value = 100.0
        
        # Handle 429 with Retry-After: 60
        await self.rate_limiter.handle_429("60")
        
        # Verify sleep was called with correct duration (60s + 1s buffer)
        mock_sleep.assert_called_once_with(61.0)
        
        # Verify rate limit tracking was reset
        self.assertIsNone(self.rate_limiter.remaining_calls)
        self.assertIsNone(self.rate_limiter.reset_timestamp)

    @patch('time.time')
    @patch('asyncio.sleep')
    async def test_handle_429_without_retry_after(self, mock_sleep, mock_time):
        """Test handling a 429 response without Retry-After header."""
        mock_time.return_value = 100.0
        
        # Handle 429 without Retry-After
        await self.rate_limiter.handle_429(None)
        
        # Verify sleep was called with default duration (60s + 1s buffer)
        mock_sleep.assert_called_once_with(61.0)
        
        # Verify rate limit tracking was reset
        self.assertIsNone(self.rate_limiter.remaining_calls)
        self.assertIsNone(self.rate_limiter.reset_timestamp)

    @patch('time.time')
    @patch('asyncio.sleep')
    async def test_handle_429_invalid_retry_after(self, mock_sleep, mock_time):
        """Test handling a 429 response with invalid Retry-After header."""
        mock_time.return_value = 100.0
        
        # Handle 429 with invalid Retry-After
        await self.rate_limiter.handle_429("invalid")
        
        # Verify sleep was called with default duration (60s + 1s buffer)
        mock_sleep.assert_called_once_with(61.0)
        
        # Verify rate limit tracking was reset
        self.assertIsNone(self.rate_limiter.remaining_calls)
        self.assertIsNone(self.rate_limiter.reset_timestamp)


if __name__ == "__main__":
    unittest.main()
