# Reddit Finance-Subreddits Scraper

A Python 3.10+ tool that continuously harvests submission data from key finance-oriented subreddits, stores it in a single CSV, and keeps the dataset current with minimal manual intervention.

## Purpose

This tool collects Reddit submissions from finance-related subreddits to support downstream sentiment analysis and market-behavior research.

## Features

*   **Comprehensive Data Collection:** Gathers detailed information about Reddit submissions, including title, score, author, comments, and more.
*   **Configurable Scraping:** Allows users to specify target subreddits, keywords, and scraping frequency through a `config.yaml` file.
*   **Dual Storage Support:**
    *   **Primary:** Writes data directly to a TimescaleDB/PostgreSQL database for robust, time-series storage and analysis.
    *   **Secondary:** Saves data to local CSV files (in `../data/raw/reddit_scraper/`) for backup, quick local access, or alternative workflows.
*   **Efficient Data Handling:** Uses `asyncpraw` for asynchronous API calls, improving performance and reducing wait times.
*   **Connection Pooling:** Leverages SQLAlchemy's built-in connection pooling for efficient database interactions. Support for external poolers like PgBouncer can be configured if advanced pooling strategies are required.
*   **Idempotent Writes:** Designed to avoid duplicate entries when writing to the database (e.g., using `ON CONFLICT DO NOTHING` or similar, as per `scraper_implementation_rule.md`).
*   **Graceful Shutdown:** Handles `SIGINT` and `SIGTERM` signals for a clean shutdown process.
*   **Standardized Logging:** Implements consistent logging practices for monitoring and debugging.
*   **Adherence to Project Rules:** Follows the guidelines outlined in the main `scraper_implementation_rule.md`.
*   **Flexible PostgreSQL Sink Strategy:** Offers two mechanisms for writing to PostgreSQL:
    *   `SQLAlchemyPostgresSink`: Utilizes SQLAlchemy ORM (with the `RawEventORM` model) for type-safe, batched database operations. This is the recommended approach and aligns with using Alembic for schema management.
    *   `PostgresSink`: Uses direct `psycopg2` calls for database interaction. This option might be considered for specific scenarios but bypasses the ORM layer.
    *   The choice between these sinks is controlled by the `postgres.use_sqlalchemy` boolean flag in the `config.yaml` file.

## Target Subreddits

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
- Docker and Docker Compose (optional, for containerized deployment)

All dependencies are managed through Poetry and defined in the pyproject.toml file, including:
- asyncpraw (Reddit API client)
- aiohttp (HTTP client)
- python-dateutil (for accurate date calculations)
- prometheus-client (for metrics)
- pyyaml (for configuration)
- typer (CLI interface)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/reddit-finance-scraper.git
   cd reddit-finance-scraper
   ```

2. Set up a virtual environment and install dependencies using Poetry:
   ```bash
   pip install poetry
   poetry install
   ```
   This will create a poetry.lock file that ensures consistent dependency versions across all environments.

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

The scraper offers multiple specialized scraper types, each with a different approach to collecting Reddit data. All scrapers now feature pagination support to retrieve up to 1000 submissions per search query (10x the default Reddit API limit):

#### Main Scraper

The main scraper can be run in two modes:

1. **One-shot mode** (backfill only):
   ```bash
   poetry run python -m reddit_scraper.cli scrape --config config.yaml
   # Or using the script shortcut:
   poetry run scrape --config config.yaml
   ```

2. **Daemon mode** (continuous maintenance with auto-backfill):
   ```bash
   poetry run python -m reddit_scraper.cli scrape --daemon --loglevel INFO
   # Or using the script shortcut:
   poetry run scrape --daemon --loglevel INFO
   ```
   
   The daemon mode now automatically detects and backfills missing data when the client has been offline. It works by:
   - Tracking the timestamp of the last collected submission
   - Detecting significant gaps in the data (10 minutes or more)
   - Automatically running a targeted backfill from the last data timestamp when gaps are detected
   - Running maintenance cycles every 61 seconds for near real-time data collection

#### Specialized Historical Scrapers

Specialized historical scrapers are available for one-time historical data collection strategies. These scrapers are designed for specific backfill operations and do not support daemon mode. All scrapers feature **enhanced pagination support** to retrieve up to 1000 results per search query (10x the default Reddit API limit):

1. **Targeted Historical Scraper** - Focuses on specific finance-related terms and years of interest:
   - Uses an extensive collection of 200+ finance-related search terms categorized by:
     - Market conditions (recession, bear market, bull market, etc.)
     - Companies (Apple, Tesla, Palantir, etc.)
     - Financial events (dotcom bubble, great recession, etc.)
     - Reddit financial slang (yolo, tendies, stonks, etc.)
     - Trading terms (options, theta gang, iron condor, etc.)
   - Implements pagination to fetch up to 1000 results per search
   - Searches across years from 2008 to present
   ```bash
   poetry run python -m reddit_scraper.cli scraper targeted
   # Or using the script shortcut:
   poetry run targeted
   ```

2. **Deep Historical Scraper** - **(DEPRECATED)**
   - ~~Digs deep into the early days of each subreddit~~
   - ~~Uses monthly time windows for granular data collection~~
   - ~~Implements pagination to fetch up to 1000 results per time window~~

3. **Hybrid Historical Scraper** - **(DEPRECATED)**
   - ~~Combines approaches from both targeted and deep scrapers~~
   - ~~Utilizes both search terms and time windows~~
   - ~~Implements pagination for comprehensive data collection~~

4. **Pushshift Historical Scraper** - **(DEPRECATED)**
   - ~~Uses the Pushshift API for historical data collection~~

> **Note:** For historical data collection, use the default scraper with date parameters instead:
> ```bash
> poetry run python -m reddit_scraper.cli scrape --since 2023-01-01 --config config.yaml
> # Or using the script shortcut:
> poetry run scrape --since 2023-01-01 --config config.yaml
> ```

Detailed documentation for specialized scrapers can be found in [docs/specialized_scrapers.md](docs/specialized_scrapers.md).

**Note**: For continuous scraping with near real-time updates, always use the main scraper in daemon mode as shown above.

### Getting Started

#### First-Time Usage

For first-time users, the recommended command is:

```bash
poetry run python -m reddit_scraper.cli scrape --config config.yaml
# Or using the script shortcut:
poetry run scrape --config config.yaml
```

This will:
1. Run the main scraper in one-shot mode
2. Perform an initial backfill based on the configuration in `config.yaml`
3. Collect historical data for all configured subreddits (default: last 30 days)
4. Store the data in CSV files at the path specified in the config

#### Returning Users

For returning users who want continuous updates:

```bash
poetry run python -m reddit_scraper.cli scrape --daemon --loglevel INFO
# Or using the script shortcut:
poetry run scrape --daemon --loglevel INFO
```

This will:
1. Run the scraper in daemon mode
2. Automatically detect any data gaps since the last run
3. Backfill those gaps if they exceed the configured threshold (default 10 minutes)
4. Continue collecting new submissions every 61 seconds
5. Provide INFO level logging to monitor the process

#### Adding Subreddits

To add additional subreddits:

1. Open the `config.yaml` file
2. Add your desired subreddits to the `subreddits` list:
   ```yaml
   # List of subreddits to scrape
   subreddits:
     - wallstreetbets
     - stocks
     - investing
     # Add your new subreddits below
     - newSubreddit1
     - newSubreddit2
   ```
3. Save the file
4. Run the one-shot mode command to backfill historical data for the new subreddits:
   ```bash
   poetry run python -m reddit_scraper.cli scrape --config config.yaml
   # Or using the script shortcut:
   poetry run scrape --config config.yaml
   ```
5. After the initial backfill completes, you can switch to daemon mode for continuous updates:
   ```bash
   poetry run python -m reddit_scraper.cli scrape --daemon --loglevel INFO
   # Or using the script shortcut:
   poetry run scrape --daemon --loglevel INFO
   ```

**Note**: If you only want to backfill a specific time period for the new subreddits, you can use the `--since` option:
```bash
poetry run python -m reddit_scraper.cli scrape --since 2025-04-01 --config config.yaml
# Or using the script shortcut:
poetry run scrape --since 2025-04-01 --config config.yaml
```

#### When to Use Specialized Scrapers

The specialized scrapers are designed for specific historical data collection needs that go beyond the standard backfill:

1. **Targeted Historical Scraper** - Use when:
   - You need to collect data around specific keywords or events
   - You want to focus on particular years or time periods
   - You're conducting research on specific topics within subreddits
   ```bash
   python -m reddit_scraper.cli scraper targeted --config config.yaml
   ```

2. **Deep Historical Scraper** - **(DEPRECATED)**
   - ~~Use when you need to collect data from the early days of subreddits~~
   - ~~Use when you want to ensure comprehensive coverage across all time periods~~
   - ~~Use when you're building a complete historical dataset~~

3. **Hybrid Historical Scraper** - **(DEPRECATED)**
   - ~~Use when you need both keyword targeting and comprehensive time coverage~~
   - ~~Use when you want to focus on specific terms but across all time periods~~
   - ~~Use when you're conducting research that requires both approaches~~

4. **Pushshift Historical Scraper** - **(DEPRECATED)**
   - ~~Use when you need to access archived Reddit content not available via the standard API~~
   - ~~Use when you're researching very old submissions (pre-2015)~~
   - ~~Use when you need to bypass Reddit API limitations for historical data~~

> **Note:** For all historical data collection needs, use the main scraper with date parameters:
> ```bash
> python -m reddit_scraper.cli scrape --since YYYY-MM-DD --config config.yaml
> ```

**Important**: After using any specialized scraper for historical data collection, switch to the main scraper in daemon mode for continuous updates:
```bash
python -m reddit_scraper.cli scrape --daemon --loglevel INFO
```

### CLI Options

#### Main Scraper Options (`scrape` command)

- `--config`, `-c`: Path to configuration file (default: config.yaml)
- `--daemon`, `-d`: Run in daemon mode (continuous maintenance with 61-second interval)
- `--reset-backfill`, `-r`: Reset backfill (ignore existing IDs)
- `--since`, `-s`: Date to start backfill from (YYYY-MM-DD)
- `--loglevel`, `-l`: Logging level (default: INFO)
- `--verbose`, `-v`: Enable verbose output

#### Historical Scraper Options (`scraper` subcommands)

- `--config`, `-c`: Path to configuration file (default: config.yaml)
- `--loglevel`, `-l`: Logging level (default: INFO)
- `--verbose`, `-v`: Enable verbose output

### Docker Deployment

The project includes a Dockerfile and docker-compose.yml for containerized deployment. The Docker image uses Alpine Linux for a smaller, more secure container footprint.

#### Prerequisites

- Docker and Docker Compose installed on your system
- Reddit API credentials in a `.env` file (see [Reddit API Credentials](#reddit-api-credentials))
- Configuration in `config.yaml` (use the existing one or create your own)

#### Data Storage

The Docker setup stores all data on your local machine through volume mounts:
- **Data files**: Stored in the `./data` directory in your project folder
- **Log files**: Stored in the `./logs` directory in your project folder
- **Configuration**: Your local `config.yaml` and `.env` files are mounted into the container

### PostgreSQL Integration

The scraper supports dual storage modes - CSV files and PostgreSQL database:

#### Configuration

1. Set the following environment variables in your `.env` file or Docker environment:
   ```
   PG_HOST=market_pgbouncer
   PG_PORT=6432
   PG_DB=marketdb
   PG_USER=market_user
   PG_PASSWORD=your_password
   USE_POSTGRES=true
   USE_SQLALCHEMY=true
   ```

2. Ensure the `postgres` section is properly configured in your `config.yaml`:
   ```yaml
   postgres:
     enabled: true
     host: market_pgbouncer
     port: 6432
     database: marketdb
     user: market_user
     password: your_password
     use_sqlalchemy: true
   ```

#### Connection Pooling with PgBouncer

The scraper uses PgBouncer for efficient connection pooling, which provides:
- Reduced connection overhead
- Better performance under load
- More efficient resource utilization

The scraper connects to PgBouncer on port 6432, which then manages connections to the actual PostgreSQL database.

#### SQLAlchemy ORM

The PostgreSQL integration uses SQLAlchemy ORM for:
- Type-safe database operations
- Efficient batch processing
- Connection pooling
- Proper transaction management

For more details, see the [SQLAlchemy Implementation Summary](sqlalchemy_implementation_summary.md).

This ensures that your data persists even if the container is stopped, removed, or rebuilt.

#### Building and Running

1. Build the Docker image:
   ```bash
   docker-compose build
   ```

2. Run the container in the foreground (view logs in real-time):
   ```bash
   docker-compose up
   ```

3. Run the container in the background (daemon mode):
   ```bash
   docker-compose up -d
   ```

4. Check container logs when running in background:
   ```bash
   docker-compose logs -f
   ```

5. Stop the container:
   ```bash
   docker-compose down
   ```

#### Customizing the Docker Setup

The default Docker configuration runs the main scraper in daemon mode with near real-time updates (61-second interval). To customize this behavior:

1. Edit the `command` in `docker-compose.yml` to use a different scraper or options:
   ```yaml
   command: ["scraper", "targeted", "--config", "config.yaml", "--loglevel", "INFO"]
   ```
   
   Or to run a one-shot backfill instead of daemon mode:
   ```yaml
   command: ["scrape", "--config", "config.yaml", "--loglevel", "INFO"]
   ```

2. Or override the command when starting the container:
   ```bash
   docker-compose run --rm reddit-scraper scrape --since 2025-01-01 --config config.yaml
   ```

The Docker configuration uses the main scraper in daemon mode by default and mounts the local `.env` file for credentials and the `data` directory for persistent storage. This provides continuous near real-time data collection with the 61-second maintenance interval, ensuring your data stays up-to-date with minimal intervention.

## Configuration

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

## Monitoring and Observability

### Basic Metrics

To check the current status of the scraper:

```bash
python -m reddit_scraper.cli metrics
```

This will output metrics in JSON format, including CSV size and column information.

Options:
- `--output`, `-o`: Output file for metrics (default: stdout)
- `--format`, `-f`: Output format (json or prometheus)

### Prometheus Integration

The scraper includes Prometheus metrics for monitoring and alerting. To run a standalone Prometheus metrics server:

```bash
python -m reddit_scraper.cli prometheus_server
```

This will start a server on port 8000 (configurable) that exposes metrics at `/metrics` for Prometheus to scrape.

Options:
- `--port`, `-p`: Port to run the Prometheus server on (overrides config)

### Available Metrics

- `reddit_scraper_submissions_collected_total`: Total number of Reddit submissions collected (by subreddit)
- `reddit_scraper_fetch_operations_total`: Number of fetch operations performed (by type)
- `reddit_scraper_api_errors_total`: Number of API errors encountered (by type)
- `reddit_scraper_consecutive_5xx_errors`: Number of consecutive 5XX errors encountered
- `reddit_scraper_latest_fetch_age_seconds`: Seconds since the last successful fetch operation
- `reddit_scraper_data_gap_seconds`: Seconds since the last collected submission (detects offline periods)
- `reddit_scraper_backfills_performed_total`: Number of auto-backfills performed
- `reddit_scraper_backfill_collected_total`: Number of submissions collected via auto-backfill
- `reddit_scraper_csv_size_bytes`: Size of the CSV file in bytes
- `reddit_scraper_known_submissions`: Number of known submission IDs
- `reddit_scraper_request_duration_seconds`: Duration of API requests in seconds (histogram)

### Alerts

The system monitors for the following alert conditions:

- Consecutive 5XX errors exceeding the configured threshold
- Latest fetch age exceeding 20 minutes (configurable)
- Disk usage exceeding 90% (configurable)

## Documentation

For detailed specifications, see the [Product Requirements Document](prd.md).

## Architecture

### Scraper Architecture

The scraper has been refactored to use a unified architecture with the following components:

#### BaseScraper

The `BaseScraper` class in `reddit_scraper/base_scraper.py` provides a foundation for all scrapers with common functionality:

- Configuration loading
- Reddit client initialization and cleanup
- Data storage and ID tracking
- Execution flow management
- Error handling

#### Utility Functions

Common scraping patterns are implemented in `reddit_scraper/scraper_utils.py`:

- `search_by_term()`: Search for a specific term in a date range
- `search_by_year()`: Search for submissions in a specific year
- `create_time_windows()`: Create time windows for breaking up large date ranges using dateutil.relativedelta for accurate month calculations

#### Specialized Scrapers

All specialized scrapers are now organized in the `reddit_scraper/scrapers` package. Each scraper extends the `BaseScraper` class and implements its own strategy:

1. **TargetedHistoricalScraper**: Focuses on specific terms and years of interest
2. ~~**DeepHistoricalScraper**: Digs deep into the early days of each subreddit~~ **(DEPRECATED)**
3. ~~**HybridHistoricalScraper**: Combines approaches from both targeted and deep scrapers~~ **(DEPRECATED)**
4. ~~**PushshiftHistoricalScraper**: Uses the Pushshift API for accessing archived Reddit content~~ **(DEPRECATED)**

> **Note:** For historical data collection, use the main scraper with the `--since` parameter instead of the deprecated scrapers.

### Data Flow

1. **Configuration Loading**: Load settings from config.yaml and .env
2. **Setup**: Initialize Reddit client, data sink, and other components
3. **Data Collection**: Execute the scraper-specific search strategy
4. **Data Processing**: Filter out already seen submissions
5. **Data Storage**: Store new records in the CSV file
6. **Cleanup**: Release resources and close connections

## Database Interaction and Schema Management

**Schema Management:**

This scraper **does not** create or manage the database schema (tables, hypertables, extensions). It assumes that the required database schema is already in place and managed externally, typically through **Alembic** migrations run from the project root or a dedicated migrations service. Refer to the main project `README.md` for details on applying database migrations.

**Data Ingestion:**

The scraper connects to the TimescaleDB/PostgreSQL database using connection details provided via environment variables (see `timescaledb_integration_guide.md` in the project root). It uses SQLAlchemy ORM for database interactions.

## Data Storage

The scraper supports dual data storage mechanisms:

1.  **TimescaleDB/PostgreSQL Database (Primary):**
    *   All successfully fetched and processed Reddit submissions are written to the configured TimescaleDB/PostgreSQL database.
    *   This is the primary data store for analytical queries and long-term storage.
    *   The schema (e.g., `raw_events` table, its hypertable configuration, and primary key) is managed by Alembic migrations (see main project `README.md`). *(Note: The specific primary key for `raw_events` should be documented here once confirmed; it is expected to be a composite key including the time partitioning column `occurred_at`.)*

2.  **CSV Files (Secondary/Backup):**
    *   As a fallback or for local operational use, data is also appended to CSV files.
    *   Files are organized by subreddit and date, located in `../data/raw/reddit_scraper/<subreddit_name>/<YYYY-MM-DD>.csv`.
    *   This ensures data is captured even if database connectivity issues occur temporarily and provides an easily accessible local copy.

## Development

See the [To-Do List](todo.md) for implementation steps.

### For Developers

#### Managing Dependencies

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

This project can be easily containerized using Docker. The poetry.lock file ensures consistent dependencies in your Docker environment.

Example Dockerfile:
```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev

COPY . .

CMD ["python", "-m", "reddit_scraper.cli", "scrape", "--daemon"]
```

Alternatively, for a smaller image, you can use a multi-stage build:
```dockerfile
FROM python:3.10-slim as builder

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && \
    poetry export -f requirements.txt > requirements.txt

FROM python:3.10-slim
WORKDIR /app
COPY --from=builder /app/requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "-m", "reddit_scraper.cli", "scrape", "--daemon"]
```

## License

[MIT](LICENSE)
