"""Prometheus metrics for monitoring the Reddit Finance Scraper."""

import logging
import time
from typing import Dict, Any, Optional

from prometheus_client import Counter, Gauge, Histogram, start_http_server

logger = logging.getLogger(__name__)

# Define metrics
SUBMISSIONS_COLLECTED = Counter(
    "reddit_scraper_submissions_collected_total",
    "Total number of Reddit submissions collected",
    ["subreddit"],
)

FETCH_OPERATIONS = Counter(
    "reddit_scraper_fetch_operations_total",
    "Number of fetch operations performed",
    ["operation_type"],
)

API_ERRORS = Counter(
    "reddit_scraper_api_errors_total",
    "Number of API errors encountered",
    ["error_type"],
)

CONSECUTIVE_5XX_ERRORS = Gauge(
    "reddit_scraper_consecutive_5xx_errors",
    "Number of consecutive 5XX errors encountered",
)

LATEST_FETCH_AGE = Gauge(
    "reddit_scraper_latest_fetch_age_seconds",
    "Seconds since the last successful fetch operation",
)

CSV_SIZE_BYTES = Gauge(
    "reddit_scraper_csv_size_bytes",
    "Size of the CSV file in bytes",
)

KNOWN_SUBMISSIONS = Gauge(
    "reddit_scraper_known_submissions",
    "Number of known submission IDs",
)

REQUEST_DURATION = Histogram(
    "reddit_scraper_request_duration_seconds",
    "Duration of API requests in seconds",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)


class PrometheusExporter:
    """Prometheus metrics exporter for the Reddit Finance Scraper."""

    def __init__(self, port: int = 8000):
        """
        Initialize the Prometheus exporter.
        
        Args:
            port: Port to expose metrics on
        """
        self.port = port
        self.server_started = False
        
    def start_server(self) -> None:
        """Start the Prometheus metrics server."""
        if not self.server_started:
            try:
                start_http_server(self.port)
                self.server_started = True
                logger.info(f"Started Prometheus metrics server on port {self.port}")
            except Exception as e:
                logger.error(f"Failed to start Prometheus metrics server: {str(e)}")
        
    def record_submission_collected(self, subreddit: str) -> None:
        """
        Record a submission collection.
        
        Args:
            subreddit: Subreddit the submission was collected from
        """
        SUBMISSIONS_COLLECTED.labels(subreddit=subreddit).inc()
        
    def record_fetch_operation(self, operation_type: str) -> None:
        """
        Record a fetch operation.
        
        Args:
            operation_type: Type of fetch operation (e.g., 'latest', 'historic')
        """
        FETCH_OPERATIONS.labels(operation_type=operation_type).inc()
        
    def record_api_error(self, error_type: str) -> None:
        """
        Record an API error.
        
        Args:
            error_type: Type of API error (e.g., '5xx', '429', 'connection')
        """
        API_ERRORS.labels(error_type=error_type).inc()
        
    def set_consecutive_5xx_errors(self, count: int) -> None:
        """
        Set the consecutive 5XX errors gauge.
        
        Args:
            count: Number of consecutive 5XX errors
        """
        CONSECUTIVE_5XX_ERRORS.set(count)
        
    def set_latest_fetch_age(self, age_seconds: float) -> None:
        """
        Set the latest fetch age gauge.
        
        Args:
            age_seconds: Seconds since the last successful fetch
        """
        LATEST_FETCH_AGE.set(age_seconds)
        
    def set_csv_size(self, size_bytes: int) -> None:
        """
        Set the CSV size gauge.
        
        Args:
            size_bytes: Size of the CSV file in bytes
        """
        CSV_SIZE_BYTES.set(size_bytes)
        
    def set_known_submissions(self, count: int) -> None:
        """
        Set the known submissions gauge.
        
        Args:
            count: Number of known submission IDs
        """
        KNOWN_SUBMISSIONS.set(count)
        
    def time_request(self) -> "RequestTimer":
        """
        Create a context manager for timing API requests.
        
        Returns:
            RequestTimer context manager
        """
        return RequestTimer()
        
    def update_from_metrics_dict(self, metrics: Dict[str, Any]) -> None:
        """
        Update metrics from a metrics dictionary.
        
        Args:
            metrics: Dictionary of metrics
        """
        if "latest_fetch_age_sec" in metrics and metrics["latest_fetch_age_sec"] is not None:
            self.set_latest_fetch_age(metrics["latest_fetch_age_sec"])
            
        if "known_submissions" in metrics:
            self.set_known_submissions(metrics["known_submissions"])
            
        if "csv_size_bytes" in metrics:
            self.set_csv_size(metrics["csv_size_bytes"])


class RequestTimer:
    """Context manager for timing API requests."""
    
    def __init__(self):
        """Initialize the request timer."""
        self.start_time: Optional[float] = None
        
    def __enter__(self) -> "RequestTimer":
        """Start timing the request."""
        self.start_time = time.time()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Stop timing the request and record the duration.
        
        Args:
            exc_type: Exception type if an exception was raised
            exc_val: Exception value if an exception was raised
            exc_tb: Exception traceback if an exception was raised
        """
        if self.start_time is not None:
            duration = time.time() - self.start_time
            REQUEST_DURATION.observe(duration)
