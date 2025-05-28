# Default Scraper Mechanism

## Overview

The default scraper is the primary data collection mechanism in the Reddit Scraper project. Unlike the specialized scrapers (Targeted, Deep, Hybrid, and Pushshift), the default scraper focuses on maintaining an up-to-date dataset by continuously collecting new submissions from configured subreddits. It operates in two primary modes:

1. **One-shot Backfill Mode**: Collects historical data in a single run
2. **Daemon Maintenance Mode**: Continuously monitors subreddits for new submissions

## Architecture

The default scraper is composed of several key components that work together:

### Core Components

1. **SubmissionCollector**: The central component responsible for fetching submissions from Reddit
2. **BackfillRunner**: Manages historical data collection with sliding time windows
3. **MaintenanceRunner**: Handles continuous monitoring and collection of new submissions
4. **RedditClient**: Provides authenticated access to the Reddit API
5. **RateLimiter**: Ensures compliance with Reddit's API rate limits
6. **ConsecutiveErrorTracker**: Handles error tracking and exponential backoff
7. **CsvSink**: Manages data storage and retrieval

### Component Relationships

┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  BackfillRunner │     │ MaintenanceRunner│     │  RedditClient   │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SubmissionCollector                         │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │     CsvSink     │
                         └─────────────────┘

## Operational Modes

### Backfill Mode

Backfill mode is designed to collect historical data from Reddit. It operates in two phases:

1. **Latest Pass**: Collects the most recent submissions from each subreddit
2. **Historic Backfill**: Uses sliding time windows to collect older submissions

The backfill process continues until one of these conditions is met:
- A configurable number of consecutive empty windows are encountered
- The beginning of Reddit's history is reached (circa 2005)

#### Backfill Algorithm

1. Load existing submission IDs to avoid duplicates
2. Collect latest submissions from each configured subreddit
3. Begin historic backfill with sliding time windows:
   - Start from the current time or specified start date
   - For each subreddit, collect submissions within the current time window
   - Move the window backward in time by the configured window size
   - Track empty windows per subreddit
   - Stop when enough consecutive empty windows are encountered

### Maintenance Mode

Maintenance mode runs continuously to keep the dataset up-to-date with new submissions. It:

1. Polls subreddits at regular intervals (default: 61 seconds)
2. Automatically detects and backfills data gaps when the scraper has been offline
3. Provides real-time metrics for monitoring

#### Maintenance Algorithm

1. Load existing submission IDs and determine the timestamp of the most recent data
2. Run in a continuous loop:
   - Check for data gaps that might need backfilling
   - Collect new submissions from each configured subreddit
   - Store new submissions and update the last data timestamp
   - Sleep until the next maintenance interval
   - Update monitoring metrics

## Data Gap Detection

The default scraper includes an intelligent data gap detection mechanism:

1. Tracks the timestamp of the most recently collected submission
2. When a maintenance cycle runs, it calculates the time difference between the current time and the last data timestamp
3. If this gap exceeds a threshold (default: 10 minutes), it triggers an automatic backfill
4. The backfill starts from the last known data timestamp to ensure continuity

This ensures data completeness even if the scraper is temporarily offline or encounters errors.

## Configuration

The default scraper is highly configurable through the `config.yaml` file:

```yaml
# Core configuration
subreddits:
  - wallstreetbets
  - investing
  - stocks
  # Add more subreddits as needed

# Backfill configuration
window_days: 30  # Size of each backfill time window in days
initial_backfill: true  # Whether to run a backfill when starting in daemon mode

# Maintenance configuration
maintenance_interval_sec: 61  # Interval between maintenance cycles (seconds)
auto_backfill_gap_threshold_sec: 600  # Threshold for detecting data gaps (seconds)

# Rate limiting
rate_limit:
  requests_per_minute: 30  # Maximum requests per minute

# Error handling
failure_threshold: 5  # Number of consecutive failures before backing off

# Data storage
csv_path: "data/submissions.csv"  # Path to store collected data
```

## Monitoring and Metrics

The default scraper provides comprehensive metrics for monitoring:

1. **Collection Statistics**:
   - Total submissions collected
   - Number of maintenance cycles completed
   - Number of backfills performed

2. **Timing Metrics**:
   - Latest fetch time and age
   - Last data timestamp
   - Data gap detection

3. **Prometheus Integration**:
   - Optional Prometheus metrics exporter
   - Configurable alerting thresholds
   - Disk usage monitoring

## Error Handling

The default scraper implements robust error handling:

1. **Exponential Backoff**: Automatically backs off when encountering API errors
2. **Consecutive Error Tracking**: Detects patterns of failures
3. **Rate Limiting**: Ensures compliance with Reddit's API limits
4. **Logging**: Comprehensive logging of all operations and errors

## Usage

The default scraper can be invoked through the CLI:

```bash
# One-shot backfill mode
python -m reddit_scraper.cli scrape

# Daemon maintenance mode
python -m reddit_scraper.cli scrape --daemon

# Backfill from a specific date
python -m reddit_scraper.cli scrape --since 2023-01-01

# Reset backfill (ignore existing IDs)
python -m reddit_scraper.cli scrape --reset-backfill
```

## Comparison with Specialized Scrapers

Unlike the specialized scrapers (Targeted, Deep, Hybrid, and Pushshift), the default scraper:

1. Focuses on maintaining an up-to-date dataset rather than collecting specific historical data
2. Can run continuously in daemon mode
3. Automatically detects and fills data gaps
4. Provides real-time monitoring metrics
5. Uses a simpler collection strategy without specialized search terms or time windows

The default scraper is the recommended choice for ongoing data collection, while specialized scrapers are better suited for one-time historical data collection tasks.

## Graceful Shutdown and Docker Deployment

The default scraper implements proper signal handling to ensure graceful shutdown, which is especially important when running in Docker containers:

### Signal Handling

The scraper responds to the following signals:

1. **SIGTERM**: Standard termination signal sent by Docker when stopping a container
2. **SIGINT**: Sent when pressing Ctrl+C in the terminal

When these signals are received, the scraper:
1. Logs the received signal
2. Initiates a graceful shutdown sequence
3. Stops the maintenance runner if running in daemon mode
4. Closes all network connections and file handles
5. Ensures all data is properly saved before exiting

### Docker Deployment Considerations

When deploying the scraper in a Docker container:

1. The container will properly respond to `docker stop` commands with a graceful shutdown
2. No additional CLI commands are needed to stop the scraper
3. The default grace period (10 seconds) should be sufficient, but can be extended if needed:
   ```bash
   docker stop --time=30 <container_name>
   ```

### Monitoring Shutdown

The scraper logs detailed information during the shutdown process:

```
[INFO] Received SIGTERM signal, initiating graceful shutdown
[INFO] Shutdown event received, stopping maintenance daemon
[INFO] Stopping maintenance daemon
[INFO] Maintenance daemon stopped after 42 cycles, collected 1234 total submissions
```

This logging helps with observability and ensures you can verify that the scraper shut down properly.