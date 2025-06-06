# Sentiment Pipeline Architecture

**Version:** 1.0
**Date:** 2025-05-28

## 1. Introduction

The Sentiment Pipeline project is designed to scrape data from various sources (initially Reddit), store it efficiently, and prepare it for downstream sentiment analysis and other data processing tasks. The architecture emphasizes scalability, maintainability, and robust data management.

## 2. Core Components

### 2.1. Reddit Scraper (`reddit_scraper` service)

*   **Purpose:** Collects posts and comments from specified subreddits using the Reddit API (`asyncpraw`).
*   **Functionality:**
    *   Configurable target subreddits and scraping parameters (e.g., number of posts, timeframes).
    *   Handles Reddit API rate limits and error conditions.
    *   Transforms raw API data into a standardized `RawEventDTO` format.
    *   Sends data to the Data Ingestion Pipeline.
*   **Key Technologies:** Python, `asyncpraw`, `aiohttp`.

### 2.2. Data Storage (TimescaleDB)

*   **Purpose:** Provides a scalable and efficient time-series database for storing all raw event data.
*   **Technology:** TimescaleDB (an extension for PostgreSQL), run as a Docker container (`timescaledb_service`).
*   **Key Features Utilized:**
    *   **Hypertables:** The primary data table (`raw_events`) is a TimescaleDB hypertable, automatically partitioned by time.
    *   **Time-based Partitioning:** Data is partitioned based on the `occurred_at` timestamp, enabling efficient time-series queries and data management.
    *   **SQL Interface:** Standard PostgreSQL interface for data access and management.

### 2.3. Data Ingestion Pipeline

*   **Purpose:** Manages the flow of data from scrapers to the database and secondary storage.
*   **Components:**
    *   **`RawEventDTO` (Data Transfer Object):** A Pydantic model defining the structure of data records passed from scrapers to sinks. This ensures data consistency before it reaches the storage layer.
    *   **Sinks:** Responsible for writing data to storage systems.
        *   **`SQLAlchemyPostgresSink`:** The primary sink, responsible for writing `RawEventDTO` data to the `raw_events` table in TimescaleDB. It uses SQLAlchemy Core for efficient bulk inserts and handles idempotency using `ON CONFLICT DO NOTHING` based on a unique constraint.
        *   **`CsvSink`:** A secondary sink that writes data to CSV files, typically organized by source, subreddit, and date. This serves as a backup or for specific offline analysis needs.
    *   **`RawEventORM` (SQLAlchemy Model):** Defines the mapping between Python objects and the `raw_events` database table. Used by the `SQLAlchemyPostgresSink`.

## 3. Data Model

### 3.1. `raw_events` Table (TimescaleDB Hypertable)

*   **Purpose:** Stores all raw events collected from various sources.
*   **Schema:**
    *   `id` (TEXT): The unique identifier of the event from its source (e.g., Reddit's base36 ID for submissions/comments). Part of the composite primary key.
    *   `occurred_at` (TIMESTAMPTZ): The timestamp when the event originally occurred (e.g., post creation time). This is timezone-aware (UTC) and used for hypertable partitioning. Part of the composite primary key.
    *   `source` (TEXT): The origin of the data (e.g., "reddit", "twitter").
    *   `source_id` (TEXT): A secondary identifier from the source, if applicable (e.g., subreddit name for Reddit events).
    *   `event_type` (TEXT): Type of event (e.g., "submission", "comment").
    *   `payload` (JSONB): The raw data payload from the source, stored as a JSON object.
    *   `ingested_at` (TIMESTAMPTZ): Timestamp when the event was ingested into the pipeline (defaults to `NOW()`).
    *   `processed` (BOOLEAN): Flag indicating if the event has been processed by sentiment analysis (defaults to `FALSE`).
    *   `processed_at` (TIMESTAMPTZ): Timestamp when sentiment analysis was completed for this event (NULL until processed).
*   **Primary Key (Composite):** (`id`, `occurred_at`)
*   **Unique Constraint:** (`source`, `source_id`, `event_type`, `id`, `occurred_at`) - This ensures idempotency for records. *Note: The exact fields in the unique constraint might vary slightly based on the latest Alembic migration but generally cover these to uniquely identify an event from a source.*
*   **Hypertable Partitioning Column:** `occurred_at`
*   **Indexes:** 
    * Appropriate indexes are defined on `occurred_at`, (`source`, `source_id`), and other frequently queried columns as per Alembic migrations.
    * Specialized index `ix_raw_events_processed_occurred_at` on (`processed`, `occurred_at`) with `WHERE processed = FALSE` for efficiently fetching unprocessed events for sentiment analysis.

### 3.2. `RawEventORM` (SQLAlchemy Model)

*   Located in `common/models/raw_event.py` (or similar path).
*   Defines the SQLAlchemy ORM mapping for the `raw_events` table, used by `SQLAlchemyPostgresSink`.
*   Includes `__table_args__` for defining the composite primary key, unique constraint, and TimescaleDB-specific options if necessary (though hypertable creation is typically handled by Alembic raw SQL).

### 3.3. `RawEventDTO` (Pydantic Model)

*   Located in `common/dto/raw_event.py` (or similar path).
*   Defines the structure and validation rules for data records before they are processed by sinks. Ensures data quality and consistency from different scrapers.
*   Fields typically mirror the `raw_events` table but may omit auto-generated fields like `ingested_at` or `processed` if these are handled by the sink/database.

## 4. Schema Management (Alembic)

*   **Purpose:** Manages all database schema changes (creating tables, adding columns, defining indexes, creating hypertables).
*   **Workflow:**
    1.  SQLAlchemy models (like `RawEventORM`) define the desired state.
    2.  `alembic revision --autogenerate -m "description"` generates a migration script.
    3.  Developers edit the script to add TimescaleDB-specific commands (e.g., `CREATE EXTENSION IF NOT EXISTS timescaledb;`, `SELECT create_hypertable(...);`).
    4.  `alembic upgrade head` applies migrations to the database.
*   **Configuration:**
    *   `alembic.ini`: Main configuration file for Alembic.
    *   `alembic/env.py`: Configures database connection (reads from `.env`) and `target_metadata` (from `RawEventORM`'s `Base.metadata`).
*   **Location:** `alembic/` directory in the project root.

## 5. Configuration

*   **`.env` file:** Located in the project root, stores sensitive information and environment-specific settings (database credentials, API keys, service configurations). Not committed to version control.
*   **`docker-compose.yml`:** Defines services, networks, volumes, and how environment variables from `.env` are passed to containers.
*   **Service-specific configurations:** Some services (like the Reddit scraper) might have their own YAML configuration files for non-sensitive parameters (e.g., target subreddits).

## 6. Deployment

*   **Docker:** All services (Reddit Scraper, TimescaleDB, potentially future services) are containerized using Docker.
*   **Docker Compose:** Used to orchestrate multi-container deployment for local development and testing. Defines service dependencies, networks, and volumes.

## 7. Data Flow Summary

1.  **Scraping:** `reddit_scraper` fetches data from Reddit.
2.  **DTO Creation:** Raw data is transformed into `RawEventDTO` objects.
3.  **Sink Processing:** `RawEventDTOs` are passed to the `CompositeSink`.
    *   `SQLAlchemyPostgresSink` maps DTOs to `RawEventORM` objects and batch-inserts them into the `raw_events` table in TimescaleDB.
    *   `CsvSink` writes DTO data to CSV files.
4.  **Database Storage:** Data is persisted in TimescaleDB, partitioned by `occurred_at`.
5.  **Downstream Access:** Other services can query TimescaleDB for `raw_events` data for analysis, processing, etc.

## 8. Monitoring & Testing

*   **Monitoring:** Basic monitoring via Docker logs. `timescaledb/sql_perf_query.md` provides queries for DB performance. Advanced monitoring (e.g., Prometheus) is a future consideration.
*   **Testing:** Pytest is used for unit and integration tests. Test plans like `timescaledb/tests_implementation_plan.md` and `common/tests/comment_scraper_test_plan.md` outline strategies for testing database interactions and scraper components. (Note: These plans may need updates to align with this consolidated architecture document).
