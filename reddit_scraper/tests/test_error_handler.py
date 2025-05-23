"""Tests for the error handler module."""

import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

from aiohttp.client_exceptions import ClientResponseError

# Create mocks for ClientResponseError testing
class MockResponse:
    def __init__(self, status, headers=None):
        self.status = status
        self.headers = headers or {}

class MockRequestInfo:
    def __init__(self, url="http://example.com"):
        self.real_url = url

from reddit_scraper.collector.error_handler import ConsecutiveErrorTracker, with_exponential_backoff


class TestConsecutiveErrorTracker(unittest.TestCase):
    """Test cases for the ConsecutiveErrorTracker class."""

    def setUp(self):
        """Set up test environment."""
        self.threshold = 5
        self.tracker = ConsecutiveErrorTracker(self.threshold)

    def test_record_error(self):
        """Test recording errors."""
        # Record errors
        self.tracker.record_error()
        self.assertEqual(self.tracker.consecutive_errors, 1)
        
        self.tracker.record_error()
        self.assertEqual(self.tracker.consecutive_errors, 2)

    def test_record_success(self):
        """Test recording a success resets the error counter."""
        # Record errors
        self.tracker.record_error()
        self.tracker.record_error()
        self.assertEqual(self.tracker.consecutive_errors, 2)
        
        # Record success
        self.tracker.record_success()
        self.assertEqual(self.tracker.consecutive_errors, 0)

    def test_should_abort(self):
        """Test should_abort returns True when threshold is reached."""
        # Record errors up to threshold
        for _ in range(self.threshold):
            self.tracker.record_error()
        
        # Should abort
        self.assertTrue(self.tracker.should_abort())
        
        # Record one less than threshold
        self.tracker.record_success()  # Reset counter
        for _ in range(self.threshold - 1):
            self.tracker.record_error()
        
        # Should not abort
        self.assertFalse(self.tracker.should_abort())

    def test_prometheus_integration(self):
        """Test integration with Prometheus metrics."""
        # Create mock Prometheus exporter
        mock_exporter = MagicMock()
        tracker = ConsecutiveErrorTracker(self.threshold, prometheus_exporter=mock_exporter)
        
        # Record error
        tracker.record_error()
        
        # Verify Prometheus metrics were updated
        mock_exporter.set_consecutive_5xx_errors.assert_called_once_with(1)
        mock_exporter.record_api_error.assert_called_once_with("5xx")
        
        # Record success
        tracker.record_success()
        
        # Verify Prometheus metrics were reset
        mock_exporter.set_consecutive_5xx_errors.assert_called_with(0)


class TestWithExponentialBackoff(unittest.TestCase):
    """Test cases for the with_exponential_backoff decorator."""

    async def async_test(self, func, *args, **kwargs):
        """Helper to run async tests."""
        return await func(*args, **kwargs)

    def test_successful_call(self):
        """Test decorator with a successful function call."""
        # Create a mock function that succeeds
        mock_func = AsyncMock(return_value="success")
        
        # Apply decorator
        decorated_func = with_exponential_backoff()(mock_func)
        
        # Call decorated function
        result = asyncio.run(self.async_test(decorated_func, "arg1", "arg2", kwarg="kwarg"))
        
        # Verify function was called once and returned correct result
        mock_func.assert_called_once_with("arg1", "arg2", kwarg="kwarg")
        self.assertEqual(result, "success")

    def test_retry_on_5xx_error(self):
        """Test decorator retries on 5xx errors."""
        # Create a mock function
        mock_func = AsyncMock()
        
        # Create a properly structured ClientResponseError
        mock_request = MockRequestInfo()
        error = ClientResponseError(
            request_info=mock_request,
            history=(),
            status=500,
            message="Server error"
        )
        
        # Set up the side effect to raise an error on first call, then return success
        mock_func.side_effect = [error, "success"]
        
        # Create mock error tracker that doesn't abort
        mock_error_tracker = MagicMock()
        mock_error_tracker.should_abort.return_value = False
        
        # Apply decorator with mock error tracker
        decorated_func = with_exponential_backoff(
            max_retries=3,
            initial_backoff=0.1,  # Short backoff for testing
            error_tracker=mock_error_tracker
        )(mock_func)
        
        # Call decorated function
        with patch('asyncio.sleep', AsyncMock()) as mock_sleep:
            result = asyncio.run(self.async_test(decorated_func))
        
        # Verify sleep was called once with initial backoff
        mock_sleep.assert_called_once_with(0.1)
        
        # Verify error was tracked
        mock_error_tracker.record_error.assert_called_once()
        
        # Verify correct result
        self.assertEqual(result, "success")

    def test_max_retries_exceeded(self):
        """Test decorator raises exception when max retries exceeded."""
        # Create a mock function that always fails with 5xx error
        mock_request = MockRequestInfo()
        
        # Create a mock function that always raises an error
        def side_effect(*args, **kwargs):
            raise ClientResponseError(
                request_info=mock_request,
                history=(),
                status=500,
                message="Server error"
            )
            
        mock_func = AsyncMock(side_effect=side_effect)
        
        # Apply decorator with short backoff
        decorated_func = with_exponential_backoff(
            max_retries=2,
            initial_backoff=0.1,
            backoff_factor=2.0
        )(mock_func)
        
        # Call decorated function
        with patch('asyncio.sleep', AsyncMock()) as mock_sleep:
            with self.assertRaises(ClientResponseError):
                asyncio.run(self.async_test(decorated_func))
        
        # Verify sleep was called with increasing backoff
        calls = [call[0][0] for call in mock_sleep.call_args_list]
        self.assertEqual(len(calls), 2)  # Two sleep calls
        self.assertEqual(calls[0], 0.1)  # First retry
        self.assertEqual(calls[1], 0.2)  # Second retry (0.1 * 2.0)

    def test_handle_429_with_rate_limiter(self):
        """Test decorator handles 429 errors with rate limiter."""
        # Create a mock function
        mock_func = AsyncMock()
        
        # Create a properly structured ClientResponseError for rate limiting
        mock_request = MockRequestInfo()
        error = ClientResponseError(
            request_info=mock_request,
            history=(),
            status=429,
            message="Rate limited"
        )
        error.headers = {"Retry-After": "1"}  # Add Retry-After header
        
        # First call raises error, second call succeeds
        mock_func.side_effect = [error, "success"]
        
        # Create mock rate limiter
        mock_rate_limiter = MagicMock()
        mock_rate_limiter.handle_429 = AsyncMock()
        
        # Apply decorator with mock rate limiter
        decorated_func = with_exponential_backoff(
            rate_limiter=mock_rate_limiter
        )(mock_func)
        
        # Call decorated function
        result = asyncio.run(self.async_test(decorated_func))
        
        # Verify rate limiter was called to handle 429
        mock_rate_limiter.handle_429.assert_called_once()
        
        # Verify correct result
        self.assertEqual(result, "success")


if __name__ == "__main__":
    unittest.main()
