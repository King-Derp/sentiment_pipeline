"""Tests for the monitoring module."""

import unittest
from unittest.mock import MagicMock, patch
import time

from prometheus_client import Counter, Gauge, Histogram

from reddit_scraper.monitoring.metrics import (
    PrometheusExporter,
    SUBMISSIONS_COLLECTED,
    FETCH_OPERATIONS,
    API_ERRORS,
    CONSECUTIVE_5XX_ERRORS,
    REQUEST_DURATION
)


class TestPrometheusExporter(unittest.TestCase):
    """Test cases for the PrometheusExporter class."""
    
    def setUp(self):
        """Set up test environment."""
        self.exporter = PrometheusExporter()
    
    def test_init(self):
        """Test initialization of metrics."""
        # Verify the exporter is initialized correctly
        self.assertEqual(self.exporter.port, 8000)
        self.assertFalse(self.exporter.server_started)
    
    def test_record_submission_collected(self):
        """Test recording submission collection."""
        # Mock the counter
        with patch('reddit_scraper.monitoring.metrics.SUBMISSIONS_COLLECTED') as mock_counter:
            # Record a submission
            self.exporter.record_submission_collected("wallstreetbets")
            
            # Verify counter was incremented
            mock_counter.labels.assert_called_once_with(subreddit="wallstreetbets")
            mock_counter.labels.return_value.inc.assert_called_once()
    
    def test_record_api_error(self):
        """Test recording API errors."""
        # Mock the counter
        with patch('reddit_scraper.monitoring.metrics.API_ERRORS') as mock_counter:
            # Record an error
            self.exporter.record_api_error("5xx")
            
            # Verify counter was incremented
            mock_counter.labels.assert_called_once_with(error_type="5xx")
            mock_counter.labels.return_value.inc.assert_called_once()
    
    def test_start_server(self):
        """Test starting the Prometheus server."""
        with patch('reddit_scraper.monitoring.metrics.start_http_server') as mock_start_server:
            # Start the server
            self.exporter.start_server()
            
            # Verify server was started
            mock_start_server.assert_called_once_with(8000)
            self.assertTrue(self.exporter.server_started)
    
    def test_record_fetch_operation(self):
        """Test recording fetch operations."""
        # Mock the counter
        with patch('reddit_scraper.monitoring.metrics.FETCH_OPERATIONS') as mock_counter:
            # Record a fetch operation
            self.exporter.record_fetch_operation("latest")
            
            # Verify counter was incremented
            mock_counter.labels.assert_called_once_with(operation_type="latest")
            mock_counter.labels.return_value.inc.assert_called_once()
    
    def test_set_consecutive_5xx_errors(self):
        """Test setting consecutive 5xx errors gauge."""
        # Mock the gauge
        with patch('reddit_scraper.monitoring.metrics.CONSECUTIVE_5XX_ERRORS') as mock_gauge:
            # Set the gauge
            self.exporter.set_consecutive_5xx_errors(5)
            
            # Verify gauge was set
            mock_gauge.set.assert_called_once_with(5)
    
    def test_time_request(self):
        """Test request timing."""
        # Use the timer
        with patch('reddit_scraper.monitoring.metrics.REQUEST_DURATION') as mock_histogram:
            with self.exporter.time_request() as timer:
                # Verify timer is initialized
                self.assertIsNotNone(timer.start_time)
                
                # Simulate work
                time.sleep(0.01)
            
            # Verify duration was observed
            mock_histogram.observe.assert_called_once()
    
    def test_update_from_metrics_dict(self):
        """Test updating metrics from a dictionary."""
        # Create a metrics dictionary
        metrics = {
            "latest_fetch_age_sec": 120.5,
            "known_submissions": 1000,
            "csv_size_bytes": 50000
        }
        
        # Mock the gauge methods
        with patch.object(self.exporter, 'set_latest_fetch_age') as mock_set_age, \
             patch.object(self.exporter, 'set_known_submissions') as mock_set_submissions, \
             patch.object(self.exporter, 'set_csv_size') as mock_set_size:
            
            # Update metrics
            self.exporter.update_from_metrics_dict(metrics)
            
            # Verify gauge methods were called
            mock_set_age.assert_called_once_with(120.5)
            mock_set_submissions.assert_called_once_with(1000)
            mock_set_size.assert_called_once_with(50000)


if __name__ == "__main__":
    unittest.main()
