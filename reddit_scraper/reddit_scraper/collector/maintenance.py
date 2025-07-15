"""Maintenance loop for continuously collecting new Reddit submissions."""

import asyncio
import logging
import time
import pandas as pd
import os
from datetime import datetime, timezone, timedelta
from typing import Set, Dict, Optional, Tuple

from reddit_scraper.collector.collector import SubmissionCollector
from reddit_scraper.collector.backfill import BackfillRunner
from reddit_scraper.config import Config
from reddit_scraper.storage.csv_sink import CsvSink as DataSink

logger = logging.getLogger(__name__)


class MaintenanceRunner:
    """
    Runner for continuous maintenance collection of new Reddit submissions.
    
    Polls subreddits at regular intervals to keep the dataset current.
    Automatically detects and backfills missing data when client has been offline.
    """
    
    def __init__(
        self,
        config: Config,
        collector: SubmissionCollector,
        data_sink: DataSink,
        prometheus_exporter = None,
    ):
        """
        Initialize the maintenance runner.
        
        Args:
            config: Application configuration
            collector: Submission collector
            data_sink: Data storage sink
            prometheus_exporter: Optional Prometheus metrics exporter
        """
        self.config = config
        self.collector = collector
        self.data_sink = data_sink
        self.prometheus_exporter = prometheus_exporter
        self.seen_ids: Set[str] = set()
        self.running = False
        self.latest_fetch_time = 0.0
        self.last_data_timestamp = 0.0  # Timestamp of the last collected submission
        self.stats: Dict[str, int] = {
            "total_collected": 0,
            "runs_completed": 0,
            "runs_with_data": 0,
            "backfills_performed": 0,
            "backfill_collected": 0,
        }
        
    async def initialize(self) -> None:
        """Initialize the runner by loading existing submission IDs and last data timestamp."""
        self.seen_ids = self.data_sink.load_ids()
        self.last_data_timestamp = await self._get_last_data_timestamp()
        logger.info(f"Initialized maintenance runner with {len(self.seen_ids)} known submission IDs")
        logger.info(f"Last data timestamp: {datetime.fromtimestamp(self.last_data_timestamp, tz=timezone.utc) if self.last_data_timestamp > 0 else 'None'}")
        
    async def _get_last_data_timestamp(self) -> float:
        """Get the timestamp of the last collected submission.
        
        Returns:
            Unix timestamp of the last collected submission, or 0 if no data exists
        """
        if not os.path.exists(self.config.csv_path) or os.path.getsize(self.config.csv_path) == 0:
            return 0.0
            
        try:
            # Read the last row of the CSV file to get the latest timestamp
            df = pd.read_csv(self.config.csv_path, usecols=["created_utc"])
            if df.empty:
                return 0.0
                
            # Get the maximum timestamp
            last_timestamp = df["created_utc"].max()
            return float(last_timestamp)
            
        except Exception as e:
            logger.error(f"Failed to get last data timestamp: {str(e)}")
            return 0.0
            
    async def _check_for_data_gap(self) -> Tuple[bool, float]:
        """Check if there's a significant gap in the data that needs backfilling.
        
        Returns:
            Tuple of (gap_exists, gap_start_timestamp)
        """
        # If we don't have a last timestamp, no gap to fill
        if self.last_data_timestamp == 0.0:
            return False, 0.0
            
        # Get current time
        now = time.time()
        
        # Calculate time difference
        time_diff = now - self.last_data_timestamp
        
        # Check if the gap exceeds the configured threshold
        # Default is 10 minutes (600 seconds) to ensure we don't miss data
        threshold = getattr(self.config, 'auto_backfill_gap_threshold_sec', 600)
        significant_gap = time_diff >= threshold
        
        if significant_gap:
            logger.info(f"Detected data gap of {timedelta(seconds=time_diff)} since last submission")
            return True, self.last_data_timestamp
        
        return False, 0.0
        
    async def _run_backfill(self, since_timestamp: float) -> int:
        """Run a backfill to collect missing data.
        
        Args:
            since_timestamp: Timestamp to start backfill from
            
        Returns:
            Number of submissions collected during backfill
        """
        logger.info(f"Starting backfill from {datetime.fromtimestamp(since_timestamp, tz=timezone.utc)}")
        
        # Create a backfill runner
        backfill = BackfillRunner(self.config, self.collector, self.data_sink)
        
        # Initialize with our current seen IDs
        backfill.seen_ids = self.seen_ids.copy()
        
        # Run the backfill
        collected = await backfill.run(int(since_timestamp))
        
        # Update our seen IDs with any new ones from the backfill
        self.seen_ids.update(backfill.seen_ids)
        
        # Update the last data timestamp
        self.last_data_timestamp = await self._get_last_data_timestamp()
        
        # Update stats
        self.stats["backfills_performed"] += 1
        self.stats["backfill_collected"] += collected
        
        logger.info(f"Backfill complete, collected {collected} submissions")
        return collected
        
    async def run_once(self) -> int:
        """
        Run a single maintenance collection cycle.
        
        Returns:
            Number of new submissions collected
        """
        cycle_start = time.time()
        self.latest_fetch_time = cycle_start
        
        # Update latest fetch age in Prometheus if available
        if self.prometheus_exporter:
            self.prometheus_exporter.set_latest_fetch_age(0.0)  # Reset to 0 at start of cycle
        
        logger.info(f"Starting maintenance cycle at {datetime.fromtimestamp(cycle_start, tz=timezone.utc)}")
        
        # Check for data gaps and run backfill if needed
        backfill_collected = 0
        gap_exists, gap_start = await self._check_for_data_gap()
        if gap_exists:
            logger.info("Detected data gap - running automatic backfill")
            backfill_collected = await self._run_backfill(gap_start)
            logger.info(f"Auto-backfill collected {backfill_collected} submissions")
        
        total_collected = 0
        
        # Collect latest from each subreddit
        for subreddit in self.config.subreddits:
            records = await self.collector.latest(subreddit, self.seen_ids)
            
            if records:
                # Add new IDs to seen set
                self.seen_ids.update(r["id"] for r in records)
                
                # Store records
                self.data_sink.append(records)
                
                total_collected += len(records)
                logger.info(f"Collected {len(records)} new submissions from r/{subreddit}")
            else:
                logger.info(f"No new submissions from r/{subreddit}")
        
        # Update the last data timestamp
        self.last_data_timestamp = await self._get_last_data_timestamp()
        
        # Update stats
        self.stats["total_collected"] += total_collected
        self.stats["runs_completed"] += 1
        if total_collected > 0:
            self.stats["runs_with_data"] += 1
            
        # Update Prometheus metrics if available
        if self.prometheus_exporter:
            self.prometheus_exporter.set_known_submissions(len(self.seen_ids))
        
        cycle_duration = time.time() - cycle_start
        logger.info(
            f"Maintenance cycle completed in {cycle_duration:.2f}s, "
            f"collected {total_collected} submissions (plus {backfill_collected} from auto-backfill)"
        )
        
        return total_collected + backfill_collected
        
    async def run_daemon(self) -> None:
        """Run the maintenance loop continuously."""
        self.running = True
        
        logger.info(
            f"Starting maintenance daemon with {len(self.config.subreddits)} subreddits, "
            f"interval: {self.config.maintenance_interval_sec}s"
        )
        
        try:
            while self.running:
                cycle_start = time.time()
                
                try:
                    await self.run_once()
                except Exception as e:
                    logger.error(f"Error in maintenance cycle: {str(e)}")
                
                # Calculate sleep time
                elapsed = time.time() - cycle_start
                sleep_time = max(0, self.config.maintenance_interval_sec - elapsed)
                
                if sleep_time > 0:
                    logger.info(f"Sleeping for {sleep_time:.2f}s until next cycle")
                    await asyncio.sleep(sleep_time)
                
        except asyncio.CancelledError:
            logger.info("Maintenance daemon cancelled")
            self.running = False
        except Exception as e:
            logger.error(f"Maintenance daemon error: {str(e)}")
            self.running = False
            raise
        finally:
            logger.info(
                f"Maintenance daemon stopped after {self.stats['runs_completed']} cycles, "
                f"collected {self.stats['total_collected']} total submissions"
            )
    
    def stop(self) -> None:
        """Stop the maintenance loop."""
        logger.info("Stopping maintenance daemon")
        self.running = False
    
    def get_metrics(self) -> Dict[str, any]:
        """
        Get current metrics for monitoring.
        
        Returns:
            Dictionary of metrics
        """
        now = time.time()
        
        metrics = {
            "total_collected": self.stats["total_collected"],
            "runs_completed": self.stats["runs_completed"],
            "runs_with_data": self.stats["runs_with_data"],
            "backfills_performed": self.stats["backfills_performed"],
            "backfill_collected": self.stats["backfill_collected"],
            "latest_fetch_age_sec": now - self.latest_fetch_time if self.latest_fetch_time > 0 else None,
            "latest_fetch_time": datetime.fromtimestamp(self.latest_fetch_time, tz=timezone.utc).isoformat() if self.latest_fetch_time > 0 else None,
            "last_data_timestamp": datetime.fromtimestamp(self.last_data_timestamp, tz=timezone.utc).isoformat() if self.last_data_timestamp > 0 else None,
            "data_gap_sec": now - self.last_data_timestamp if self.last_data_timestamp > 0 else None,
            "known_submissions": len(self.seen_ids),
            "is_running": self.running,
        }
        
        # Update Prometheus metrics if available
        if self.prometheus_exporter and self.latest_fetch_time > 0:
            fetch_age = now - self.latest_fetch_time
            self.prometheus_exporter.set_latest_fetch_age(fetch_age)
            
            # Check if fetch age exceeds threshold
            if fetch_age > self.config.monitoring.alerts.max_fetch_age_sec:
                logger.warning(
                    f"Latest fetch age ({fetch_age:.1f}s) exceeds threshold "
                    f"({self.config.monitoring.alerts.max_fetch_age_sec}s)"
                )
            
            # Add data gap metrics if available    
            if self.last_data_timestamp > 0:
                data_gap = now - self.last_data_timestamp
                if hasattr(self.prometheus_exporter, 'set_data_gap'):
                    self.prometheus_exporter.set_data_gap(data_gap)
                
            self.prometheus_exporter.set_known_submissions(len(self.seen_ids))
            
        return metrics
