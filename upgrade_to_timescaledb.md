# Feature: TimescaleDB Sink for Reddit Scraper

**Last Updated:** 2025-07-06

## 1. Summary

The Reddit scraper has been upgraded to support direct data ingestion into a TimescaleDB database, replacing the previous CSV-based backfill mechanism. This enhancement improves data integrity, reduces manual data loading steps, and centralizes data storage for the entire sentiment analysis pipeline.

The command-line interface (CLI) has been updated with a `--sink` option, allowing users to select the desired data destination (`postgres`, `csv`, or `composite`) for both real-time scraping and historical backfills.

## 2. Implementation Details

The upgrade involved the following key changes:

*   **`SQLAlchemyPostgresSink` Enhancement**: The existing sink was adapted to handle bulk inserts and load existing submission IDs efficiently, making it suitable for large-scale backfills. It now uses dialect-aware `INSERT` statements to support both PostgreSQL (production) and SQLite (testing).
*   **CLI Refactoring**: The `reddit_scraper/cli.py` was modified to include a `--sink` option for the `scrape` command. This allows dynamic selection of the data sink at runtime.
*   **Unit Testing**: Comprehensive unit tests were developed for the `SQLAlchemyPostgresSink` to verify record insertion and ID loading functionality using an in-memory SQLite database.
*   **Model Consolidation**: Redundant and legacy ORM model definitions were removed to prevent conflicts and improve code clarity.

## 3. How to Use the `--sink` Option

The `--sink` option has been added to the `scrape` command in the Reddit scraper CLI.

**Syntax:**

```bash
poetry run python -m reddit_scraper.cli scrape [OPTIONS] --sink [csv|postgres|composite]
```

**Available Sinks:**

*   `csv`: (Default) Saves data to a CSV file, as per the original behavior.
*   `postgres`: Saves data directly to the TimescaleDB database.
*   `composite`: Saves data to both CSV and TimescaleDB simultaneously.

### Examples

**1. Run a backfill saving directly to PostgreSQL:**

This command runs a one-shot backfill, fetching data since the specified date and saving it to TimescaleDB.

```bash
poetry run python -m reddit_scraper.cli scrape --since-date "2023-01-01" --sink postgres
```

**2. Run the scraper in daemon mode, saving to both CSV and PostgreSQL:**

This command starts the scraper as a continuous background process, saving all new data to both sinks.

```bash
poetry run python -m reddit_scraper.cli scrape --daemon --sink composite
```

**3. Run a backfill using the default CSV sink:**

If the `--sink` option is omitted, it defaults to `csv`.

```bash
poetry run python -m reddit_scraper.cli scrape --since-date "2023-01-01"
```

## 4. Testing and Validation

The new implementation was validated through:

*   **Unit Tests**: A suite of `pytest` unit tests was created for `SQLAlchemyPostgresSink`, mocking the database session to ensure isolated and repeatable tests. All tests are passing.
*   **Integration Testing**: The backfill and scrape commands were run manually against a local TimescaleDB instance to confirm end-to-end functionality.

This upgrade makes the data ingestion process more robust and scalable, laying a solid foundation for the sentiment analysis pipeline.
