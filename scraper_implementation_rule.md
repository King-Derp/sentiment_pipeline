# Scraper Implementation Rules

**Version:** 1.0
**Date:** 2025-05-23

This document outlines the mandatory rules and best practices for creating or modifying scraper services within the Sentiment Pipeline project. Adhering to these rules ensures consistency, data integrity, and maintainability across all data sources.

## 1. Timestamp Standardization

*   **Rule:** All scraper services **MUST** standardize timestamps before sending data to any storage sink (e.g., TimescaleDB, CSV).
*   **Details:**
    *   **Source Parsing:** Each scraper is responsible for parsing the native timestamp format provided by its specific data source (e.g., Reddit API, Twitter API, news feeds).
    *   **Conversion to UTC:** After parsing, the timestamp **MUST** be converted to a timezone-aware Python `datetime` object in **UTC** (Coordinated Universal Time).
    *   **Storage Format:** 
        *   When preparing data for TimescaleDB (via `PostgresSink`), if the target database column is of type `TIMESTAMP WITH TIME ZONE` (TIMESTAMPTZ), the UTC `datetime` object can be passed directly (SQLAlchemy will handle it).
        *   If the target database column is `BIGINT` (for storing Unix epoch time), the UTC `datetime` object should be converted to an integer representing seconds since the epoch (e.g., `int(utc_datetime.timestamp())`).
        *   For CSV output or other sinks, the timestamp should also be consistently represented in UTC, preferably in ISO 8601 format (e.g., `YYYY-MM-DDTHH:MM:SSZ`).
    *   **Rationale:** Standardizing on UTC at the scraper level prevents timezone ambiguities, ensures data consistency in the central database, and simplifies time-based queries and partitioning in TimescaleDB, regardless of the original data source's timezone or format.

## 2. Database Schema Management via Alembic

*   **Rule:** Individual scraper services **MUST NOT** define or attempt to create/modify database schemas (e.g., tables, indexes) directly.
*   **Details:**
    *   **Centralized Schema Control:** All database schema definitions, initial creation, and subsequent migrations (e.g., adding tables for new scrapers, adding columns, creating indexes) **MUST** be managed centrally using **Alembic**.
    *   **Migration Scripts:** Developers adding a new scraper that requires a new table or modifications to an existing table must create or update Alembic migration scripts. These scripts will contain the necessary SQL DDL (Data Definition Language) commands.
        *   This includes `CREATE TABLE` statements for new scrapers' data, and importantly, the `SELECT create_hypertable(...)` command for any new time-series tables intended for TimescaleDB.
    *   **Scraper Assumption:** Scraper services should assume that the required database schema (tables, columns, types) already exists and is correctly configured when the scraper service starts. Their role is to interact with the data (CRUD operations), not manage the schema structure.
    *   **SQLAlchemy Models:** Scrapers can (and should) use SQLAlchemy models for ORM interaction, but these models are for data mapping and should reflect the Alembic-managed schema, not drive its creation (i.e., no `metadata.create_all()` calls for schema setup within scraper code).
    *   **Deployment:** Database migrations using Alembic **MUST** be run as a separate step in the deployment process *before* scraper services that depend on the schema are started.
    *   **Rationale:** This decouples schema management from individual scraper application logic, prevents schema conflicts, ensures version-controlled schema changes, simplifies scraper development, and makes the overall database architecture more robust and maintainable.

## 3. Standardized Configuration and Secrets Management

*   **Rule:** All scraper services **MUST** manage their configurations and sensitive data (e.g., API keys) in a consistent and secure manner.
*   **Details:**
    *   **Configuration Files:** Use a structured configuration file (e.g., `config.yaml` or `settings.toml`) for non-sensitive operational parameters such as target keywords, polling intervals, feature flags, or source-specific settings.
    *   **Secrets Management:** API keys, database credentials, and other secrets **MUST** be loaded from environment variables. These can be populated via a `.env` file (e.g., `scraper_name.env`) specific to the scraper, which **MUST** be included in the project's `.gitignore` file.
    *   **Consistency:** Strive for a common structure in configuration files for similar types of scrapers to enhance understandability and maintainability.
*   **Rationale:** Ensures that scraper configurations are easy to manage, deploy, and secure, separating sensitive information from the codebase and promoting consistent operational practices.

## 4. Mandatory Data Validation (Input and Output)

*   **Rule:** All scraper services **MUST** validate incoming data from external sources and outgoing data destined for storage sinks.
*   **Details:**
    *   **Input Validation:** Use `pydantic` models to define the expected structure and data types of raw data received from external APIs or sources. This helps catch unexpected data formats or missing fields early.
    *   **Output Validation:** Use `pydantic` models to define the data structure being passed to storage sinks (e.g., the `SubmissionRecord` for `PostgresSink` or `CsvSink`). This ensures that the data conforms to the expected schema (managed by Alembic) before attempting to store it.
*   **Rationale:** Proactive data validation improves data quality, prevents malformed data from entering the system, provides clear data contracts between components, and aids in debugging by identifying data issues at their source or before storage.

## 5. Robust Error Handling and Retry Mechanisms

*   **Rule:** All scraper services **MUST** implement robust error handling and appropriate retry mechanisms for interactions with external services.
*   **Details:**
    *   **Categorize Errors:** Distinguish between transient errors (e.g., temporary network issues, rate limits) and permanent errors (e.g., invalid API key, non-existent endpoint).
    *   **Retry Strategy:** For transient errors, implement retry mechanisms such as exponential backoff with jitter. Libraries like `tenacity` can be used for this. Define a reasonable maximum number of retries.
    *   **Failure Action:** Upon final failure after retries, or for permanent errors, the scraper must take a defined action: log the detailed error, skip the problematic item/batch, send an alert, or (in critical cases) halt the scraper gracefully.
    *   **Data Integrity:** Ensure that error handling does not lead to partial data writes or inconsistent states.
*   **Rationale:** Scrapers rely on external systems that can be unreliable. Robust error handling and retries increase the resilience and reliability of data collection, minimizing data loss due to temporary issues.

## 6. Consistent Logging Practices

*   **Rule:** All scraper services **MUST** adhere to consistent logging practices for operational transparency and debugging.
*   **Details:**
    *   **Standard Library:** Utilize Python's standard `logging` module.
    *   **Log Levels:** Employ standard log levels appropriately: `DEBUG` for detailed diagnostic information, `INFO` for routine operational messages (e.g., scraper started, batch processed), `WARNING` for recoverable issues or potential problems (e.g., retrying an API call), `ERROR` for significant failures that prevent normal operation for a specific item/task, and `CRITICAL` for issues that might require the scraper to stop.
    *   **Contextual Information:** Log messages **MUST** include relevant context, such as the scraper's name or type, timestamp, function/module name, and specific identifiers related to the data being processed (e.g., submission ID, search query) where applicable.
    *   **Structured Logging (Optional but Recommended):** Consider using structured logging (e.g., outputting logs in JSON format) if logs are intended for ingestion and analysis by centralized log management systems (e.g., ELK stack, Splunk).
*   **Rationale:** Comprehensive and consistent logging is essential for monitoring the health and behavior of scrapers, diagnosing problems, and understanding the data flow through the pipeline.

## 7. Ensuring Idempotent Data Ingestion

*   **Rule:** Scraper services **MUST** ensure that their data ingestion processes are idempotent, especially when writing to persistent storage like TimescaleDB.
*   **Details:**
    *   **Unique Identifiers:** Identify a unique natural key for each data item from its source (e.g., Reddit submission ID, Tweet ID, article URL).
    *   **Database Handling:** When writing to TimescaleDB (or other relational databases), use database mechanisms to handle conflicts based on this unique key. For PostgreSQL, this typically involves `INSERT ... ON CONFLICT DO NOTHING` (if new data for an existing ID should be ignored) or `INSERT ... ON CONFLICT DO UPDATE ...` (if existing records should be updated with new data).
    *   **Application-Level Checks (for other sinks):** For sinks like CSV files where database-level conflict resolution isn't available, the scraper might need to implement application-level checks if duplicates are to be avoided (e.g., maintaining a set of seen IDs for the current run, though this has limitations for long-running or restarted processes).
*   **Rationale:** Idempotency prevents the creation of duplicate records if a scraper processes the same data multiple times (e.g., due to retries, restarts, or overlapping queries). This is crucial for maintaining data integrity in the pipeline.

## 8. Graceful Shutdown Handling

*   **Rule:** Scraper services **MUST** be designed to handle shutdown signals gracefully.
*   **Details:**
    *   **Signal Handling:** Implement handlers for `SIGINT` (Ctrl+C) and `SIGTERM` (sent by Docker on stop) signals.
    *   **Cleanup Actions:** Upon receiving a shutdown signal, the scraper should attempt to:
        *   Stop accepting new tasks or initiating new API calls.
        *   Complete any in-progress data processing or API requests if feasible within a short, predefined timeout.
        *   Flush any buffered data to all configured sinks.
        *   Close database connections, network sessions, and other critical resources cleanly.
*   **Rationale:** Graceful shutdown ensures that the scraper can terminate cleanly, minimizing data loss or corruption, and releasing system resources properly. This is particularly important in containerized environments like Docker.

## 9. Adherence to a Common Data Output Contract

*   **Rule:** All scraper services **MUST** strive to map their collected data to a common core data model before sending it to storage sinks, supplemented by source-specific metadata.
*   **Details:**
    *   **Core Data Model:** Define a core `pydantic` model (e.g., `GenericPipelineItem`) that represents the essential, common fields expected from any data source. This model **MUST** include fields such as:
        *   `item_id_from_source` (type: `str`, unique ID from the source platform)
        *   `text_content` (type: `str`, primary textual content for analysis)
        *   `author_id_from_source` (type: `Optional[str]`, unique ID of the author on the source platform)
        *   `created_utc` (type: `datetime`, standardized UTC timestamp as per Rule 1)
        *   `source_platform` (type: `str`, e.g., "reddit", "twitter", "news_api_vX")
        *   `item_type` (type: `str`, e.g., "submission", "comment", "article", "tweet")
    *   **Source-Specific Data:** Fields that are unique to a specific data source and do not fit into the core model should be stored in a flexible `metadata` field within the core model (e.g., a `dict` or a `pydantic` model, which can be stored as JSON/JSONB in PostgreSQL).
    *   **Schema Alignment:** The structure of this common data model (and its representation in the database) will be defined and managed via Alembic migrations.
*   **Rationale:** A common data contract simplifies downstream processing, such as sentiment analysis and visualization, by providing a consistent data structure. It allows analytical tools to work with data from multiple sources with minimal adaptation, while still preserving rich source-specific details.

## 10. Standardized Dual Storage Output (TimescaleDB and CSV)

*   **Rule:** All scraper services **MUST** write their collected data to both TimescaleDB (as the primary analytical data store) and a local CSV file (for operational backup, quick inspection, or alternative local access).
*   **Details:**
    *   **TimescaleDB Sink:** This is the primary destination. Data written **MUST** adhere to the Alembic-managed schema (Rule #2) and the Common Data Output Contract (Rule #9).
    *   **CSV Sink:**
        *   **Mandatory Output:** CSV output is a required secondary sink.
        *   **Directory Structure:** CSV files **MUST** be saved within a dedicated subdirectory inside the project's root `/data/` folder. This subdirectory should be named after the `source_platform` as defined in the Common Data Output Contract (Rule #9), e.g., `/data/reddit/`, `/data/twitter/`, `/data/news_api_vX/`.
        *   **File Naming:** Within its directory, a scraper can choose a consistent naming strategy (e.g., `YYYY-MM-DD_data.csv`, or a single continuously appended `scraped_data.csv`).
        *   **Content:** The CSV data should reflect the fields defined in the Common Data Output Contract (Rule #9) and include a header row.
        *   **Configuration:** The enabling and specific path for the CSV sink should be configurable (as per Rule #3), defaulting to the standardized location.
    *   **Operational Consideration:** Errors writing to one sink (e.g., CSV disk full) should be logged but ideally should not prevent writing to the other (e.g., TimescaleDB), unless the failure is critical to the scraper's core function.
*   **Rationale:** Enforcing TimescaleDB as the primary sink ensures data is available for robust, time-series analysis. Requiring a standardized CSV output provides a simple, accessible backup, facilitates quick data checks, and allows for easy use by tools or processes that readily consume CSV. Standardizing the output location keeps the project organized and predictable.

---
*These rules are subject to updates as the project evolves. Always refer to the latest version of this document.*
