# Reddit Finance-Subreddits Scraper

A Python 3.10+ tool that continuously harvests submission data from key finance-oriented subreddits. This scraper is a component of the larger Sentiment Pipeline project.

For overall project architecture, data models (`RawEventDTO`, `RawEventORM`, `raw_events` table), and other shared components, please refer to the main project [README.md](../../README.md) and [ARCHITECTURE.md](../../ARCHITECTURE.md).
This document focuses on the specifics of the Reddit Scraper.

## Purpose

This tool collects Reddit submissions and comments from configured finance-related subreddits to feed into the Sentiment Pipeline.

## Features

*   **Configurable Scraping:** Allows users to specify target subreddits and scraping parameters via `config.yaml`.
*   **Efficient Data Handling:** Uses `asyncpraw` for asynchronous API calls.
*   **Standardized Data Output:** Produces `RawEventDTO` objects for ingestion, as detailed in `ARCHITECTURE.md`.
*   **Adherence to Project Rules:** Follows guidelines from `scraper_implementation_rule.md` and `ARCHITECTURE.md` regarding database interaction, logging, and error handling.
*   **Flexible Storage Sinks:** Persists data using configurable output sinks. The storage strategy is controlled via the `--sink` command-line option.
    *   **PostgreSQL Sink (`--sink postgres`):** The primary and recommended sink. It uses `SQLAlchemyPostgresSink` to write data in batches to the `raw_events` hypertable in TimescaleDB. This sink is robust, type-safe, and handles database conflicts gracefully.
    *   **CSV Sink (`--sink csv`):** A simple sink that appends data to a local CSV file. Useful for backups, local analysis, or development.
    *   **Composite Sink (`--sink composite`):** A powerful option that writes data to *both* the PostgreSQL and CSV sinks simultaneously, providing data redundancy.

## Target Subreddits (Default)

- wallstreetbets
- stocks
- investing
- StockMarket
- options
- finance
- UKInvesting
- Banking
- CryptoCurrency

## Setup

### Prerequisites

- Python 3.10 or higher
- [Poetry](https://python-poetry.org/) for dependency management
- Reddit API credentials (see below)
- Access to a configured TimescaleDB instance (see project root `README.md` and `ARCHITECTURE.md` for setup).
- Docker and Docker Compose (for containerized deployment)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/reddit-finance-scraper.git
   cd reddit-finance-scraper
   ```

2. Navigate to the project root directory (e.g., `sentiment_pipeline/`).
3. Set up a virtual environment and install dependencies using Poetry (this will use the `pyproject.toml` at the project root):
   ```bash
   # Ensure you are in the project root directory (e.g., sentiment_pipeline/)
   pip install poetry  # If not already installed globally or in your environment
   poetry install
   ```
   This will use the `pyproject.toml` and create/update `poetry.lock` in the project root, managing dependencies for the entire project, including the Reddit Scraper.

3. Create a `.env` file with your Reddit API credentials:
   ```bash
   cp .env.example .env
   # Edit .env with your Reddit API credentials
   ```

4. Create the data directory:
   ```bash
   mkdir -p data logs
   ```

### Reddit API Credentials

To use this scraper, you need to create a Reddit application:

1. Go to https://www.reddit.com/prefs/apps
2. Click "create app" at the bottom
3. Fill in the details:
   - Name: finance_scraper
   - Type: script
   - Description: Finance subreddits data collection
   - About URL: (leave blank)
   - Redirect URI: http://localhost:8080
4. Click "create app"
5. Copy the client ID (the string under the app name) and client secret to your `.env` file

## Usage

### Command Line Interface

The primary way to run the scraper is via its command-line interface, which supports two main operational modes: backfill and daemon. The data destination is controlled by the `--sink` option.

**CLI Examples**

1.  **Run a historical backfill and save to TimescaleDB:**
    This command fetches data from a specific date to the present and stores it directly in the database.

    ```bash
    poetry run python -m reddit_scraper.cli scrape --since-date "2023-01-01" --sink postgres
    ```

2.  **Run in continuous daemon mode, saving to both database and CSV:**
    This is the recommended command for continuous, resilient operation. It monitors for new submissions and saves them to both sinks.

    ```bash
    poetry run python -m reddit_scraper.cli scrape --daemon --sink composite
    ```

3.  **Run a backfill saving only to a CSV file (the default sink):**
    Useful for quick local data dumps without database interaction.

    ```bash
    poetry run python -m reddit_scraper.cli scrape --since-date "2023-01-01"
    # Note: --sink csv is the default and can be omitted.
    ```

#### Scraper CLI Options (`scrape` command)

- `--sink TEXT`: The data sink to use. Options: `postgres`, `csv`, `composite`. **Default: `csv`**.
- `--daemon`: If set, runs the scraper in continuous daemon mode to fetch new posts.
- `--since-date TEXT`: The start date (YYYY-MM-DD) for a historical backfill. If not provided, the scraper runs in daemon mode unless `--daemon` is explicitly set.
- `--reset-backfill`: If set, ignores previously scraped submission IDs and re-fetches all data within the time window. Use with caution.
- `--config CONFIG_PATH`: Path to the configuration file. Default: `config.yaml`.
- `--loglevel LOGLEVEL`: Logging level (e.g., `INFO`, `DEBUG`). Default: `INFO`.
### Database and Maintenance Commands

The scraper includes commands for database maintenance, such as finding and filling data gaps.

1.  **Find Data Gaps in TimescaleDB:**
    This command queries the `submissions` table to find time gaps longer than a specified duration.

    ```bash
    python -m reddit_scraper.cli db find-gaps --min-duration 600 --output gaps.json
    ```
    - `--min-duration`: Minimum gap duration in seconds to report. Default: 600 (10 minutes).
    - `--output`: Optional file path to save the JSON output. If not provided, output is printed to the console.

2.  **Fill Data Gaps:**
    This command automates the process of finding and filling data gaps. It uses the `PushshiftHistoricalScraper` to backfill missing data for each identified gap.

    ```bash
    python -m reddit_scraper.cli fill-gaps --min-duration 600
    ```
    - `--min-duration`: Minimum gap duration in seconds to fill. Default: 600.
    - `--dry-run`: If set, the command will find and list gaps without actually running the scraper to fill them. This is useful for safely previewing the work to be done.

### Docker Deployment

The project includes a `Dockerfile` and can be orchestrated using the main project `docker-compose.yml`.

#### Configuration in Docker

*   Ensure the `reddit_scraper` service in `docker-compose.yml` has the necessary environment variables mounted from your `.env` file (for Reddit API keys and database credentials).
*   The `config.yaml` for the scraper should be volume-mounted into the container.
*   The command for the Docker container can be adjusted in `docker-compose.yml` to run the scraper with desired CLI options (e.g., daemon mode).

Example `docker-compose.yml` service definition snippet for `reddit_scraper`:

```yaml
services:
  reddit_scraper:
    build:
      context: ./reddit_scraper
      dockerfile: Dockerfile
    container_name: reddit_scraper_service
    env_file:
      - .env
    volumes:
      - ./reddit_scraper/config.yaml:/app/config.yaml
      - ./data:/app/data # For CSV output
      - ./logs:/app/logs # For log files
    command: ["python", "-m", "reddit_scraper.cli", "scrape", "--daemon", "--sink", "composite", "--loglevel", "INFO"]
    depends_on:
      timescaledb_service: # Or your TimescaleDB service name
        condition: service_healthy
      # alembic_migration_service: # If you have a separate migration job
      #   condition: service_completed_successfully
    networks:
      - sentiment_pipeline_network # Your common Docker network
```

**Note on PgBouncer:** While PgBouncer can be used for advanced connection pooling, the default setup relies on SQLAlchemy's built-in pooling. If PgBouncer is introduced project-wide, ensure `PG_HOST` and `PG_PORT` environment variables point to PgBouncer instead of directly to TimescaleDB.

## Configuration (`config.yaml` and `.env`)

The `config.yaml` file contains the following settings:

- `subreddits`: List of subreddits to scrape
- `window_days`: Historic search window in days
- `csv_path`: Path to CSV storage file
- `initial_backfill`: Whether to perform initial backfill on startup
- `failure_threshold`: Number of consecutive 5xx errors before aborting
- `maintenance_interval_sec`: Interval in seconds between maintenance runs
- `rate_limit`: Rate limiting settings
- `monitoring`: Monitoring and alerting settings
  - `enable_prometheus`: Whether to enable Prometheus metrics
  - `prometheus_port`: Port for Prometheus metrics server
  - `alerts`: Alert thresholds
    - `max_fetch_age_sec`: Maximum age of latest fetch in seconds
    - `max_disk_usage_percent`: Maximum disk usage percentage for CSV


## Monitoring

For a comprehensive understanding of how this scraper fits into the overall project, including monitoring and alerting strategies, please refer to the main project [ARCHITECTURE.md](../../ARCHITECTURE.md) and [scraper_implementation_rule.md](../../scraper_implementation_rule.md).

## Data Flow, Storage, and Database Integration

### Overview

This scraper integrates with the larger Sentiment Pipeline project by:
1. **Collecting** Reddit submissions from configured finance subreddits
2. **Converting** them to `RawEventDTO` objects with standardized structure
3. **Storing** them in both TimescaleDB (primary) and CSV files (secondary)
4. **Enabling** downstream processing by the sentiment_analyzer service

### Data Models

#### RawEventDTO Structure
The scraper produces `RawEventDTO` objects with these key fields:
- `event_id`: UUID primary key
- `event_type`: Always "reddit_submission" for this scraper
- `source`: Always "reddit"
- `source_id`: Reddit's base36 submission ID (e.g., "abc123")
- `occurred_at`: Submission creation timestamp
- `payload`: Complete Reddit submission data (JSON)
- `content`: **Computed field** that extracts text for sentiment analysis from `payload.title` and `payload.selftext`

#### Database Storage (Primary)
- Uses `SQLAlchemyPostgresSink` to write to TimescaleDB `raw_events` hypertable
- Leverages `RawEventORM` model for database operations
- Handles deduplication via `ON CONFLICT DO NOTHING`
- Supports batch processing for performance

#### CSV Storage (Secondary)
- **Current Implementation**: Single CSV file at `/app/data/reddit_finance.csv` (Docker) or `data/reddit_finance.csv` (local)
- **Format**: Each row represents a `RawEventDTO` with `payload` as JSON string
- **Purpose**: Local backup, quick inspection, resilience during DB outages
- **Note**: The PRD originally specified per-subreddit/per-date files, but current implementation uses a single consolidated file

### Integration with Sentiment Analyzer

The sentiment_analyzer service processes events from the `raw_events` table:
1. **Event Claiming**: Uses `processed` boolean field (not `processing_status` string as mentioned in some older docs)
2. **Content Extraction**: Relies on the `RawEventDTO.content` computed field for text analysis
3. **Result Storage**: Saves sentiment results to `sentiment_results` table with reference to original event

### Database Schema

The scraper expects the following `raw_events` table structure (managed via Alembic migrations):
- `id`: Internal database ID (auto-increment)
- `event_id`: UUID (matches `RawEventDTO.event_id`)
- `event_type`: String ("reddit_submission")
- `source`: String ("reddit")
- `source_id`: String (Reddit submission ID)
- `occurred_at`: Timestamp (when submission was created)
- `ingested_at`: Timestamp (when scraper processed it)
- `processed`: Boolean (for sentiment analyzer claiming)
- `processed_at`: Timestamp (when sentiment analysis completed)
- `payload`: JSONB (complete Reddit submission data)

**Important**: The scraper does not create or modify database schema - it relies on externally managed Alembic migrations.

## Development

Refer to the main project `TASK.md` for current development tasks.

### For Developers

#### Managing Dependencies with Poetry

- Add a new dependency:
  ```bash
  poetry add package-name
  ```

- Add a development dependency:
  ```bash
  poetry add --group dev package-name
  ```

- Update dependencies:
  ```bash
  poetry update
  ```

- View the dependency tree:
  ```bash
  poetry show --tree
  ```

### Docker Integration

This project can be easily containerized using Docker. The `poetry.lock` file ensures consistent dependencies in your Docker environment.

See `reddit_scraper/Dockerfile` for the Docker build instructions.

## License

[MIT](../../LICENSE)
