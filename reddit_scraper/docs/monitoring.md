# Reddit Scraper Monitoring

This document describes the monitoring tools and techniques used to ensure the Reddit scraper is functioning correctly and collecting data as expected.

## Table of Contents
- [Data Collection Gap Analysis](#data-collection-gap-analysis)
- [Prometheus Metrics](#prometheus-metrics)
- [Log Monitoring](#log-monitoring)
- [Troubleshooting](#troubleshooting)

## Data Collection Gap Analysis

The `check_gaps.py` script is a utility for analyzing the Reddit finance dataset for gaps in data collection. This is particularly useful for verifying that the scraper's auto-backfill mechanism is working correctly.

### Running the Script

```bash
python check_gaps.py
```

### Script Logic

The script performs the following analysis:

1. **Data Loading and Preparation**
   - Loads the CSV file containing Reddit submissions
   - Converts Unix timestamps to Python datetime objects
   - Sorts the data chronologically by creation time

2. **Time Difference Calculation**
   - Creates a new column `time_diff` containing the time difference (in seconds) between each submission and the previous one
   - Uses pandas' `diff()` function to calculate the difference between consecutive rows

3. **Gap Detection**
   - Identifies gaps larger than 10 minutes (600 seconds)
   - This threshold aligns with the scraper's `auto_backfill_gap_threshold_sec` configuration

4. **Largest Gaps Analysis**
   - Shows the top 10 largest gaps in the dataset
   - Displays the gap size in hours, timestamp, and subreddit

5. **Recent Data Analysis**
   - Focuses on data from the last 24 hours
   - Identifies any recent gaps exceeding the 10-minute threshold
   - Shows the 5 most recent submissions to verify current collection

### Interpreting the Results

- **Historical Gaps**: Large gaps in historical data (especially from years ago) are expected and not concerning
- **Recent Gaps**: Gaps in recent data should be minimal
  - Small gaps (10-30 minutes) are normal due to Reddit posting patterns
  - Larger or frequent gaps may indicate issues with the scraper
- **Auto-backfill Effectiveness**: If the auto-backfill is working correctly, there should be few gaps exceeding the configured threshold (10 minutes)

### Example Output

```
Loading data...
Total records: 66885
Date range: 2008-03-18 19:43:24 to 2025-05-03 10:22:17

Found 45046 gaps > 10 minutes out of 66885 records

Top 10 largest gaps:
Gap of 4173.6 hours between 2008-09-08 17:19:32 (finance) and previous record
Gap of 2747.0 hours between 2009-01-25 18:17:34 (finance) and previous record
...

Records in last 24 hours: 375
Gaps > 10 minutes in last 24 hours: 32

Recent gaps:
Gap of 87.0 minutes at 2025-05-03 05:34:28 (investing)
Gap of 40.9 minutes at 2025-05-03 01:52:39 (options)
...

Most recent 5 records:
2025-05-03 10:22:17 - cryptocurrency - If you have this crypto or know someone that has i...
2025-05-03 10:18:30 - cryptocurrency - ZachXBT reveals $7M of the OG holder's stolen Bitc...
...
```

## Prometheus Metrics

The Reddit scraper includes built-in Prometheus metrics for monitoring the health and performance of the scraper.

### Available Metrics

- `reddit_scraper_csv_size_bytes`: Size of the CSV file in bytes
- `reddit_scraper_csv_rows`: Number of rows in the CSV file
- `reddit_scraper_disk_usage_percent`: Disk usage percentage
- `reddit_scraper_last_check_timestamp_seconds`: Unix timestamp of the last metrics check
- `reddit_scraper_latest_fetch_age_seconds`: Age of the latest fetch operation
- `reddit_scraper_known_submissions`: Number of known submission IDs
- `reddit_scraper_data_gap_seconds`: Gap between now and the last data timestamp

### Starting the Prometheus Server

```bash
python -m reddit_scraper.cli prometheus_server
```

This will start a metrics server on the port specified in `config.yaml` (default: 8000).

### Configuring Prometheus

Add the following to your Prometheus configuration:

```yaml
scrape_configs:
  - job_name: 'reddit_scraper'
    static_configs:
      - targets: ['localhost:8000']
```

## Log Monitoring

The scraper logs detailed information about its operations to `logs/scraper.log`. Key log entries to monitor include:

### Normal Operation Logs

- `Starting maintenance cycle at [timestamp]`: Indicates the start of a maintenance cycle
- `Maintenance cycle completed in [seconds], collected [count] submissions`: Successful completion
- `Collected [count] new submissions from r/[subreddit]`: Successful data collection

### Warning Signs

- `Failed to collect latest from r/[subreddit]`: API or network errors
- `Empty window ending at [timestamp] ([count]/[max])`: Multiple empty windows may indicate API issues
- `Disk usage ([percent]%) exceeds threshold`: Storage issues
- `Latest fetch age ([seconds]s) exceeds threshold`: Scraper falling behind

## Troubleshooting

### Common Issues and Solutions

#### No New Data Being Collected

1. Check if the scraper process is running:
   ```bash
   Get-Process | Where-Object { $_.ProcessName -like "*python*" }
   ```

2. Verify Reddit API credentials in `.env` file:
   ```
   REDDIT_CLIENT_ID=your_client_id
   REDDIT_CLIENT_SECRET=your_client_secret
   REDDIT_USERNAME=your_username
   REDDIT_PASSWORD=your_password
   ```

3. Check for API rate limiting in logs:
   ```bash
   grep "rate limit" logs/scraper.log
   ```

#### Large Gaps in Data

1. Verify the auto-backfill configuration in `config.yaml`:
   ```yaml
   # Minimum time gap in seconds to trigger auto-backfill
   auto_backfill_gap_threshold_sec: 600
   ```

2. Run a manual backfill:
   ```bash
   python -m reddit_scraper.cli scrape --reset-backfill
   ```

#### High API Error Rate

1. Check for Reddit API status issues
2. Verify rate limiting configuration in `config.yaml`:
   ```yaml
   rate_limit:
     max_requests_per_minute: 100
     min_remaining_calls: 5
     sleep_buffer_sec: 2
   ```

3. Consider decreasing `max_requests_per_minute` if errors persist