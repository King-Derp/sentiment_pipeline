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
*   **Primary Sink:** Uses `SQLAlchemyPostgresSink` with the `RawEventORM` model for type-safe, batched database operations into the `raw_events` table. This is the standard and recommended approach.
*   **Flexible Storage Sinks:** Supports two PostgreSQL sink implementations for writing to the `raw_events` table:
    *   `SQLAlchemyPostgresSink` (default and recommended): Uses SQLAlchemy ORM for robust, type-safe, and batched database operations. Aligns with the `RawEventORM` model.
    *   `PostgresSink` (legacy): Uses direct `psycopg2` connections. This option is available for specific use cases or backward compatibility but is not recommended for new deployments due to its direct SQL management and lack of ORM benefits.
    *   The choice of sink is controlled by the `postgres.use_sqlalchemy` flag in `config.yaml` (see Configuration section).

## Target Subreddits (Default)

- wallstreetbets
- stocks
- investing
- StockMarket
- options
- finance
- UKInvesting

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

The primary way to run the scraper is via its command-line interface. The scraper can perform an initial backfill and then run in a continuous daemon mode.

**Example: Initial Backfill & Continuous Daemon Mode**

This is the typical command for continuous operation:

```bash
poetry run python -m reddit_scraper.cli scrape --config config.yaml --daemon --loglevel INFO
# Or using the script shortcut (if configured in pyproject.toml):
# poetry run scrape --daemon --loglevel INFO
```

This command will:
1.  Load configuration from `config.yaml` and `.env`.
2.  Connect to the Reddit API and the TimescaleDB database.
3.  Perform an initial backfill for configured subreddits (e.g., last 30 days, or as specified by `--since`).
4.  After backfill, enter daemon mode, periodically checking for new submissions and comments.
5.  Store data as `RawEventDTO` objects into the `raw_events` table in TimescaleDB and optionally to CSV files (as per `scraper_implementation_rule.md`).

**Example: One-off Historical Backfill**

To run a one-off historical backfill for a specific period without entering daemon mode:

```bash
poetry run python -m reddit_scraper.cli scrape --config config.yaml --since YYYY-MM-DD --until YYYY-MM-DD --loglevel INFO
# Example: --since 2024-01-01 --until 2024-01-31
```

**Note on Deprecated Scrapers:** Previous versions of this README mentioned specialized historical scrapers (DeepHistoricalScraper, HybridHistoricalScraper, PushshiftHistoricalScraper). These are **DEPRECATED**. All scraping logic is now consolidated into the main `scrape` command, using options like `--since` and `--until` for historical data collection.

#### Scraper CLI Options (`scrape` command)

- `--config CONFIG_PATH`: Path to configuration file (default: `config.yaml`).
- `--loglevel LOGLEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL. Default: INFO).
- `--daemon`: Run in daemon mode for continuous monitoring after initial backfill.
- `--since SINCE_DATE`: Optional. Start date for historical backfill (YYYY-MM-DD). If not provided, defaults to a period defined in `config.yaml` or a standard lookback (e.g., 30 days).
- `--until UNTIL_DATE`: Optional. End date for historical backfill (YYYY-MM-DD). Defaults to now if not specified.
- `--subreddits SUBREDDITS`: Optional. Comma-separated list of subreddits to scrape, overrides `config.yaml`.

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
    command: ["python", "-m", "reddit_scraper.cli", "scrape", "--config", "config.yaml", "--daemon", "--loglevel", "INFO"]
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
- `postgres`:
  - `use_sqlalchemy` (boolean): Defaults to `true`. If `true`, uses the `SQLAlchemyPostgresSink`. If `false`, uses the legacy `PostgresSink` (direct `psycopg2`).

## Monitoring

For a comprehensive understanding of how this scraper fits into the overall project, including monitoring and alerting strategies, please refer to the main project [ARCHITECTURE.md](../../ARCHITECTURE.md) and [scraper_implementation_rule.md](../../scraper_implementation_rule.md).

## Data Flow, Storage, and Database Interaction

For a comprehensive understanding of how this scraper fits into the overall project, including:
*   The detailed data flow from scraping to storage.
*   The `RawEventDTO` structure.
*   The `raw_events` table schema in TimescaleDB.
*   The role of `SQLAlchemyPostgresSink` and `RawEventORM`.
*   Database schema management with Alembic.
*   Primary (TimescaleDB) and secondary (CSV) storage strategies.

Please refer to the main project [ARCHITECTURE.md](../../ARCHITECTURE.md) and [scraper_implementation_rule.md](../../scraper_implementation_rule.md).

This scraper adheres to those architectural patterns, using `SQLAlchemyPostgresSink` to write `RawEventDTO` data to the `raw_events` table.

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
