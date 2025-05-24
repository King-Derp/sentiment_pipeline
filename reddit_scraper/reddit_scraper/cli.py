print("DEBUG: cli.py TOP LEVEL EXECUTION", flush=True)

"""Command-line interface for the Reddit Finance Scraper."""

import asyncio
import json
import logging
import logging.config
import os
import shutil
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

import typer
from typing_extensions import Annotated

from reddit_scraper.collector.backfill import BackfillRunner
from reddit_scraper.collector.collector import SubmissionCollector
from reddit_scraper.collector.error_handler import ConsecutiveErrorTracker
from reddit_scraper.collector.maintenance import MaintenanceRunner
from reddit_scraper.collector.rate_limiter import RateLimiter
from reddit_scraper.config import Config, PostgresConfig
from reddit_scraper.monitoring.metrics import PrometheusExporter
from reddit_scraper.reddit_client import RedditClient
from reddit_scraper.storage.csv_sink import CsvSink
from reddit_scraper.storage.composite_sink import CompositeSink
from reddit_scraper.storage.postgres_sink import PostgresSink
from reddit_scraper.storage.sqlalchemy_postgres_sink import SQLAlchemyPostgresSink

# Import scraper classes
from reddit_scraper.base_scraper import BaseScraper
from reddit_scraper.scrapers.targeted_historical_scraper import TargetedHistoricalScraper
from reddit_scraper.scrapers.deep_historical_scraper import DeepHistoricalScraper
from reddit_scraper.scrapers.hybrid_historical_scraper import HybridHistoricalScraper
from reddit_scraper.scrapers.pushshift_historical_scraper import PushshiftHistoricalScraper

print("DEBUG: cli.py before app = typer.Typer()", flush=True)
app = typer.Typer(help="Reddit Finance Scraper - Collect submissions from finance subreddits")
print("DEBUG: cli.py after app = typer.Typer()", flush=True)

logger = logging.getLogger(__name__)

# Create subcommands for different scraper types
# Note: Most historical scrapers are deprecated except for the targeted scraper
print("DEBUG: cli.py before scraper_app = typer.Typer()", flush=True)
scraper_app = typer.Typer(help="Specialized scrapers for historical data collection")
print("DEBUG: cli.py after scraper_app = typer.Typer()", flush=True)

print("DEBUG: cli.py before app.add_typer(scraper_app)", flush=True)
app.add_typer(scraper_app, name="scraper")
print("DEBUG: cli.py after app.add_typer(scraper_app)", flush=True)


# Import and include database management commands
print("DEBUG: cli.py before from reddit_scraper.cli_db import app as db_app", flush=True)
from reddit_scraper.cli_db import app as db_app
print("DEBUG: cli.py after from reddit_scraper.cli_db import app as db_app", flush=True)

print("DEBUG: cli.py before app.add_typer(db_app)", flush=True)
app.add_typer(db_app, name="db", help="Manage PostgreSQL database")
print("DEBUG: cli.py after app.add_typer(db_app)", flush=True)


# Global reference to the maintenance runner for signal handling
_maintenance_runner = None
_shutdown_event = None

def setup_logging(log_level: str = "INFO") -> None:
    """
    Set up logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": log_level,
                "formatter": "standard",
                "filename": "logs/scraper.log",
                "maxBytes": 10485760,  # 10 MB
                "backupCount": 5,
                "encoding": "utf8",
            },
        },
        "loggers": {
            "": {
                "handlers": ["console", "file"],
                "level": log_level,
                "propagate": True
            },
            "asyncio": {
                "level": "WARNING",
            },
            "asyncpraw": {
                "level": "WARNING",
            },
        }
    }
    
    logging.config.dictConfig(log_config)


def parse_date(date_str: str) -> int:
    """
    Parse a date string into a Unix timestamp.
    
    Args:
        date_str: Date string in YYYY-MM-DD format
        
    Returns:
        Unix timestamp (seconds since epoch)
        
    Raises:
        ValueError: If the date format is invalid
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD")


async def run_scraper(
    config_path: str,
    daemon: bool = False,
    reset_backfill: bool = False,
    since_date: Optional[str] = None,
    verbose: bool = False,
) -> None:
    """
    Run the Reddit scraper with the specified options.
    
    Args:
        config_path: Path to the configuration file
        daemon: Whether to run in daemon mode (continuous maintenance)
        reset_backfill: Whether to reset the backfill (ignore existing IDs)
        since_date: Date to start backfill from (YYYY-MM-DD)
        verbose: Whether to enable verbose logging
    """
    global _maintenance_runner, _shutdown_event
    
    # Create shutdown event
    _shutdown_event = asyncio.Event()
    
    # Load configuration
    config = Config.from_files(config_path)
    validation_errors = config.validate()
    
    if validation_errors:
        for error in validation_errors:
            logger.error(f"Configuration error: {error}")
        logger.critical("Invalid configuration, aborting")
        sys.exit(1)
    
    # Create components
    # Use CompositeSink to enable both CSV and PostgreSQL storage
    sinks = [CsvSink(config.csv_path)] # Always include CSVSink
    
    if config.postgres and config.postgres.enabled:
        try:
            if config.postgres.use_sqlalchemy:
                logger.info("Using SQLAlchemy PostgreSQL sink.")
                pg_sink = SQLAlchemyPostgresSink(config.postgres)
            else:
                logger.info("Using direct connection PostgreSQL sink.")
                pg_sink = PostgresSink(config.postgres)
            sinks.append(pg_sink)
            logger.info("PostgreSQL sink enabled and initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL sink: {e}. Proceeding with CSV sink only.")
    else:
        logger.info("PostgreSQL sink is not enabled in the configuration.")
        
    data_sink = CompositeSink(sinks)
    # logger.info(f"Using {'PostgreSQL and ' if use_postgres else ''}CSV storage") # Old logging
    
    active_sinks_names = [type(s).__name__ for s in data_sink.sinks]
    logger.info(f"Data will be written to: {', '.join(active_sinks_names)}")

    reddit_client = RedditClient(config)
    rate_limiter = RateLimiter(config.rate_limit)
    error_tracker = ConsecutiveErrorTracker(config.failure_threshold)
    
    # Set up Prometheus exporter if enabled
    prometheus_exporter = None
    if config.monitoring.enable_prometheus:
        prometheus_exporter = PrometheusExporter(port=config.monitoring.prometheus_port)
        prometheus_exporter.start_server()
    
    # Initialize Reddit client
    try:
        await reddit_client.initialize()
    except ValueError as e:
        logger.critical(f"Failed to initialize Reddit client: {str(e)}")
        sys.exit(1)
    
    try:
        # Create collector and maintenance runner
        collector = SubmissionCollector(reddit_client, rate_limiter, error_tracker, prometheus_exporter)
        maintenance = MaintenanceRunner(config, collector, data_sink, prometheus_exporter)
        
        # Store reference for signal handling if in daemon mode
        if daemon:
            _maintenance_runner = maintenance
        
        # Determine mode and run
        if daemon:
            # Run in maintenance mode
            await maintenance.initialize()
            
            # Optionally do initial backfill
            if config.initial_backfill:
                logger.info("Running initial backfill before maintenance mode")
                backfill = BackfillRunner(config, collector, data_sink)
                await backfill.initialize()
                
                since_timestamp = None
                if since_date:
                    since_timestamp = parse_date(since_date)
                
                await backfill.run(since_timestamp)
            
            # Run maintenance daemon until shutdown event is set
            await asyncio.gather(
                maintenance.run_daemon(),
                wait_for_shutdown()
            )
        else:
            # Run in one-shot backfill mode
            backfill = BackfillRunner(config, collector, data_sink)
            
            if not reset_backfill:
                await backfill.initialize()
            else:
                logger.warning("Reset backfill enabled - ignoring existing IDs")
            
            since_timestamp = None
            if since_date:
                since_timestamp = parse_date(since_date)
            
            await backfill.run(since_timestamp)
            
    finally:
        # Clean up
        if _maintenance_runner:
            _maintenance_runner.stop()
            _maintenance_runner = None
        
        await reddit_client.close()
        
        if prometheus_exporter and hasattr(prometheus_exporter, 'stop_server'):
            prometheus_exporter.stop_server()


async def wait_for_shutdown():
    """Wait for the shutdown event to be set."""
    global _shutdown_event
    await _shutdown_event.wait()
    logger.info("Shutdown event received, stopping maintenance daemon")
    if _maintenance_runner:
        _maintenance_runner.stop()


def handle_shutdown_signal(signum, frame):
    """Handle shutdown signals (SIGTERM, SIGINT)."""
    signal_name = signal.Signals(signum).name
    logger.info(f"Received {signal_name} signal, initiating graceful shutdown")
    
    if _shutdown_event and not _shutdown_event.is_set():
        # Use asyncio to set the event from the main thread
        if asyncio.get_event_loop().is_running():
            asyncio.get_event_loop().call_soon_threadsafe(_shutdown_event.set)
        else:
            # If we're not in an event loop, just stop the maintenance runner directly
            if _maintenance_runner:
                _maintenance_runner.stop()


@app.command()
def scrape(
    config: Annotated[str, typer.Option("--config", "-c", help="Path to configuration file")] = "config.yaml",
    daemon: Annotated[bool, typer.Option("--daemon", "-d", help="Run in daemon mode (continuous maintenance)")] = False,
    reset_backfill: Annotated[bool, typer.Option("--reset-backfill", "-r", help="Reset backfill (ignore existing IDs)")] = False,
    since: Annotated[Optional[str], typer.Option("--since", "-s", help="Date to start backfill from (YYYY-MM-DD)")] = None,
    loglevel: Annotated[str, typer.Option("--loglevel", "-l", help="Logging level")] = "INFO",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output")] = False,
) -> None:
    """
    Scrape submissions from finance subreddits.
    
    Run in one-shot mode for backfill or daemon mode for continuous updates.
    """
    print("DEBUG: scrape command started.", flush=True)
    # Set up logging
    log_level = "DEBUG" if verbose else loglevel
    setup_logging(log_level)
    
    logger.info(f"Starting Reddit Finance Scraper (daemon={daemon}, reset={reset_backfill})")
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, handle_shutdown_signal)
    signal.signal(signal.SIGINT, handle_shutdown_signal)
    
    try:
        # Run the scraper
        asyncio.run(run_scraper(
            config_path=config,
            daemon=daemon,
            reset_backfill=reset_backfill,
            since_date=since,
            verbose=verbose,
        ))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.critical(f"Unhandled exception: {str(e)}", exc_info=True)
        sys.exit(1)


@scraper_app.command("targeted")
def run_targeted_scraper(
    config: Annotated[str, typer.Option("--config", "-c", help="Path to configuration file")] = "config.yaml",
    loglevel: Annotated[str, typer.Option("--loglevel", "-l", help="Logging level")] = "INFO",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output")] = False,
) -> None:
    """
    Run the targeted historical scraper.
    
    This scraper uses specific search terms to find historical Reddit posts.
    """
    # Set up logging
    log_level = "DEBUG" if verbose else loglevel
    setup_logging(log_level)
    
    logger.info("Starting Targeted Historical Scraper")
    
    try:
        # Create and run the scraper
        scraper = TargetedHistoricalScraper(config_path=config)
        asyncio.run(scraper.execute())
        logger.info("Targeted Historical Scraper completed successfully")
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.critical(f"Unhandled exception: {str(e)}", exc_info=True)
        sys.exit(1)


@scraper_app.command("deep", deprecated=True)
def run_deep_scraper(
    config: Annotated[str, typer.Option("--config", "-c", help="Path to configuration file")] = "config.yaml",
    loglevel: Annotated[str, typer.Option("--loglevel", "-l", help="Logging level")] = "INFO",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output")] = False,
) -> None:
    """
    Run the deep historical scraper.
    
    This scraper targets specific time periods to retrieve posts from the early days of each subreddit.
    
    DEPRECATED: For historical data collection, use the main scraper with date parameters instead:
    python -m reddit_scraper.cli scrape --since YYYY-MM-DD --config config.yaml
    """
    # Set up logging
    log_level = "DEBUG" if verbose else loglevel
    setup_logging(log_level)
    
    logger.info("Starting Deep Historical Scraper")
    
    try:
        # Create and run the scraper
        scraper = DeepHistoricalScraper(config_path=config)
        asyncio.run(scraper.execute())
        logger.info("Deep Historical Scraper completed successfully")
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.critical(f"Unhandled exception: {str(e)}", exc_info=True)
        sys.exit(1)


@scraper_app.command("hybrid", deprecated=True)
def run_hybrid_scraper(
    config: Annotated[str, typer.Option("--config", "-c", help="Path to configuration file")] = "config.yaml",
    loglevel: Annotated[str, typer.Option("--loglevel", "-l", help="Logging level")] = "INFO",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output")] = False,
) -> None:
    """
    Run the hybrid historical scraper.
    
    This scraper combines approaches from both targeted and deep historical scrapers
    to maximize data collection from historical Reddit posts.
    
    DEPRECATED: For historical data collection, use the main scraper with date parameters instead:
    python -m reddit_scraper.cli scrape --since YYYY-MM-DD --config config.yaml
    """
    # Set up logging
    log_level = "DEBUG" if verbose else loglevel
    setup_logging(log_level)
    
    logger.info("Starting Hybrid Historical Scraper")
    
    try:
        # Create and run the scraper
        scraper = HybridHistoricalScraper(config)
        asyncio.run(scraper.execute())
        
    except Exception as e:
        logger.error(f"Error running hybrid historical scraper: {str(e)}")
        if verbose:
            logger.exception(e)
        sys.exit(1)


@scraper_app.command("pushshift", deprecated=True)
def run_pushshift_scraper(
    config: Annotated[str, typer.Option("--config", "-c", help="Path to configuration file")] = "config.yaml",
    loglevel: Annotated[str, typer.Option("--loglevel", "-l", help="Logging level")] = "INFO",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output")] = False,
) -> None:
    """
    Run the Pushshift historical scraper.
    
    This scraper uses the Pushshift API to retrieve historical posts from
    the early days of each finance subreddit, going back to their creation.
    
    DEPRECATED: For historical data collection, use the main scraper with date parameters instead:
    python -m reddit_scraper.cli scrape --since YYYY-MM-DD --config config.yaml
    """
    # Set up logging
    log_level = "DEBUG" if verbose else loglevel
    setup_logging(log_level)
    
    logger.info("Starting Pushshift Historical Scraper")
    
    try:
        # Create and run the scraper
        scraper = PushshiftHistoricalScraper(config)
        asyncio.run(scraper.execute())
        
    except Exception as e:
        logger.error(f"Error running Pushshift historical scraper: {str(e)}")
        if verbose:
            logger.exception(e)
        sys.exit(1)


@app.command()
def metrics(
    config: Annotated[str, typer.Option("--config", "-c", help="Path to configuration file")] = "config.yaml",
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output file for metrics (default: stdout)")] = None,
    format: Annotated[str, typer.Option("--format", "-f", help="Output format (json or prometheus)")] = "json",
) -> None:
    """
    Output current metrics for monitoring.
    
    This is used for observability and can be called while the daemon is running.
    """
    # Load configuration
    config_obj = Config.from_files(config)
    
    # Collect basic metrics
    metrics_data = collect_metrics(config_obj)
    
    # Format output
    if format.lower() == "prometheus":
        output_text = format_prometheus(metrics_data)
    else:  # default to json
        output_text = json.dumps(metrics_data, indent=2)
    
    # Output metrics
    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(output_text)
    else:
        print(output_text)


def collect_metrics(config: Config) -> Dict[str, Any]:
    """
    Collect metrics about the scraper and dataset.
    
    Args:
        config: Application configuration
        
    Returns:
        Dictionary of metrics
    """
    metrics = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "csv_path": config.csv_path,
        "csv_size_bytes": os.path.getsize(config.csv_path) if os.path.exists(config.csv_path) else 0,
        "subreddits": config.subreddits,
    }
    
    # Add disk usage metrics
    if os.path.exists(config.csv_path):
        try:
            csv_dir = os.path.dirname(os.path.abspath(config.csv_path)) or "."
            total, used, free = shutil.disk_usage(csv_dir)
            metrics["disk_total_bytes"] = total
            metrics["disk_used_bytes"] = used
            metrics["disk_free_bytes"] = free
            metrics["disk_usage_percent"] = (used / total) * 100
            
            # Check if disk usage exceeds threshold
            if (used / total) * 100 > config.monitoring.alerts.max_disk_usage_percent:
                metrics["alerts"] = metrics.get("alerts", [])
                metrics["alerts"].append({
                    "type": "disk_usage",
                    "message": f"Disk usage ({(used / total) * 100:.1f}%) exceeds threshold ({config.monitoring.alerts.max_disk_usage_percent}%)"
                })
        except Exception as e:
            metrics["disk_error"] = str(e)
    
    # Add CSV statistics if file exists
    if os.path.exists(config.csv_path):
        try:
            import pandas as pd
            df = pd.read_csv(config.csv_path, nrows=1)
            metrics["csv_columns"] = list(df.columns)
            
            # Get row count (this can be slow for large files)
            try:
                with open(config.csv_path, 'r', encoding='utf-8') as f:
                    metrics["csv_rows"] = sum(1 for _ in f) - 1  # Subtract header row
            except Exception:
                # Fall back to pandas if line counting fails
                metrics["csv_rows"] = len(pd.read_csv(config.csv_path))
                
        except Exception as e:
            metrics["csv_error"] = str(e)
    
    return metrics


def format_prometheus(metrics: Dict[str, Any]) -> str:
    """
    Format metrics in Prometheus text format.
    
    Args:
        metrics: Dictionary of metrics
        
    Returns:
        Prometheus formatted metrics
    """
    lines = []
    
    # Add basic metrics
    if "csv_size_bytes" in metrics:
        lines.append(f"# HELP reddit_scraper_csv_size_bytes Size of the CSV file in bytes")
        lines.append(f"# TYPE reddit_scraper_csv_size_bytes gauge")
        lines.append(f"reddit_scraper_csv_size_bytes {metrics['csv_size_bytes']}")
    
    if "csv_rows" in metrics:
        lines.append(f"# HELP reddit_scraper_csv_rows Number of rows in the CSV file")
        lines.append(f"# TYPE reddit_scraper_csv_rows gauge")
        lines.append(f"reddit_scraper_csv_rows {metrics['csv_rows']}")
    
    if "disk_usage_percent" in metrics:
        lines.append(f"# HELP reddit_scraper_disk_usage_percent Disk usage percentage")
        lines.append(f"# TYPE reddit_scraper_disk_usage_percent gauge")
        lines.append(f"reddit_scraper_disk_usage_percent {metrics['disk_usage_percent']}")
    
    # Add timestamp as a gauge
    lines.append(f"# HELP reddit_scraper_last_check_timestamp_seconds Unix timestamp of the last metrics check")
    lines.append(f"# TYPE reddit_scraper_last_check_timestamp_seconds gauge")
    lines.append(f"reddit_scraper_last_check_timestamp_seconds {int(time.time())}")
    
    return "\n".join(lines)


@app.command()
def prometheus_server(
    config: Annotated[str, typer.Option("--config", "-c", help="Path to configuration file")] = "config.yaml",
    port: Annotated[Optional[int], typer.Option("--port", "-p", help="Port to run the Prometheus server on (overrides config)")] = None,
) -> None:
    """
    Run a Prometheus metrics server.
    
    This will expose metrics at /metrics for Prometheus to scrape.
    """
    # Load configuration
    config_obj = Config.from_files(config)
    
    # Use port from command line if provided, otherwise from config
    server_port = port if port is not None else config_obj.monitoring.prometheus_port
    
    # Create and start the Prometheus exporter
    exporter = PrometheusExporter(port=server_port)
    exporter.start_server()
    
    logger.info(f"Started Prometheus metrics server on port {server_port}")
    logger.info("Press Ctrl+C to stop the server")
    
    try:
        # Keep the server running until interrupted
        while True:
            # Update metrics periodically
            metrics_data = collect_metrics(config_obj)
            
            # Update Prometheus metrics from collected data
            if "csv_size_bytes" in metrics_data:
                exporter.set_csv_size(metrics_data["csv_size_bytes"])
                
            if "disk_usage_percent" in metrics_data:
                # Alert if disk usage exceeds threshold
                if metrics_data["disk_usage_percent"] > config_obj.monitoring.alerts.max_disk_usage_percent:
                    logger.warning(
                        f"Disk usage ({metrics_data['disk_usage_percent']:.1f}%) exceeds threshold "
                        f"({config_obj.monitoring.alerts.max_disk_usage_percent}%)"
                    )
            
            time.sleep(60)  # Update metrics every minute
            
    except KeyboardInterrupt:
        logger.info("Prometheus server stopped")


def main() -> None:
    """Entry point for the CLI."""
    print("DEBUG: main function started.", flush=True)
    app()


if __name__ == "__main__":
    main()
