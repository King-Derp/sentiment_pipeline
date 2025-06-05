# Sentiment Analysis Service Implementation: Detailed Task Breakdown

**Version:** 1.0
**Date:** 2025-06-04

This document provides a detailed breakdown of the tasks outlined in `sentiment_docs/TODO.md` for implementing the Sentiment Analysis Service.

---

## Phase 1: Project Setup & Foundation (Sentiment Service Module)

Details for tasks in `sentiment_docs/TODO.md - Phase 1`.

### Task 1.1: Create Service Directory Structure

*   **Objective:** Establish a clean, organized, and conventional directory layout for the sentiment analyzer service code, promoting modularity and maintainability.
*   **Details:**
    *   Create the main service directory: `f:/Coding/sentiment_pipeline/sentiment_analyzer/`.
        *   *Rationale:* This follows the project pattern (e.g., `reddit_scraper`), keeping services as top-level directories under the project root.
    *   Inside `sentiment_analyzer/`, create the following subdirectories:
        *   `core/`: For the main business logic components (data fetching, preprocessing, analysis, results processing, pipeline orchestration).
        *   `models/`: For Pydantic Data Transfer Objects (DTOs) and SQLAlchemy Object Relational Mapper (ORM) models.
        *   `api/`: For FastAPI application setup, API endpoint definitions, and related utilities.
        *   `config/`: For configuration files (e.g., `config.yaml`) and loading logic.
        *   `tests/`: For unit and integration tests, mirroring the application structure (e.g., `tests/core`, `tests/api`).
        *   `utils/`: For shared utility functions (e.g., logging setup, database session management).
    *   Add an empty `__init__.py` file to `sentiment_analyzer/` and each of its subdirectories to ensure they are treated as Python packages/modules, enabling proper imports.

### Task 1.2: Initialize Dependency Management

*   **Objective:** Define and manage all Python package dependencies required for the sentiment analysis service in a reproducible manner.
*   **Details:**
    *   Create or update a dependency file within the `sentiment_analyzer/` directory. A `requirements.txt` is suitable for direct pip installation, or `pyproject.toml` if using a modern build system like Poetry or PDM.
    *   Key dependencies to include (refer to `sentiment_docs/TODO.md` for a more comprehensive list):
        *   `fastapi`, `uvicorn[standard]`: For building and serving the REST API.
        *   `pydantic`: For data validation and settings management.
        *   `sqlalchemy`, `asyncpg`: For asynchronous database interaction with TimescaleDB/PostgreSQL.
        *   `alembic`: For managing database schema migrations for sentiment-specific tables.
        *   `spacy`: For advanced text preprocessing. Remember to also download the required model, e.g., `python -m spacy download en_core_web_lg`.
        *   `transformers`, `torch`: For using FinBERT or other Transformer-based models. Ensure PyTorch is installed with appropriate CUDA version if GPU acceleration is intended.
        *   `langdetect` or `fasttext`: For language detection.
        *   `python-dotenv`, `pyyaml`: For loading configuration from `.env` files and YAML files.
        *   `pytest`, `httpx`: For writing and running unit and integration tests.

### Task 1.3: Basic Configuration Setup & `.env.example`

*   **Objective:** Create a flexible and secure configuration system for the service, separating static configuration from environment-specific and sensitive data.
*   **Details:**
    *   Create `sentiment_analyzer/config/config.yaml`: This file will hold non-sensitive, static configuration parameters for the service, such as model names, default batch sizes, or preprocessor settings.
        ```yaml
        # sentiment_analyzer/config/config.yaml (Example)
        model:
          name: "ProsusAI/finbert"
          version: "1.0"
        preprocessor:
          language_target: "en"
          spacy_model: "en_core_web_lg"
        data_fetcher:
          batch_size: 100
        ```
    *   Implement `sentiment_analyzer/config/loader.py`: This utility will be responsible for loading settings from `config.yaml` and merging/overriding them with environment variables (loaded via `python-dotenv` from a root `.env` file). Pydantic's `BaseSettings` can be very useful here.
        ```python
        # Example snippet for config/loader.py
        from pydantic import BaseSettings
        from python_dotenv import load_dotenv
        import os

        load_dotenv()  # Load environment variables from .env

        class Settings(BaseSettings):
            # Static configuration from config.yaml
            model_name: str
            model_version: str
            preprocessor_language_target: str
            preprocessor_spacy_model: str
            data_fetcher_batch_size: int

            # Environment variables
            pg_host: str
            pg_user: str
            pg_password: str
            pg_db: str
            pg_port: int

            class Config:
                env_file = ".env"
                env_file_encoding = "utf-8"
        ```
    *   Create/update `.env.example` in the project root, ensuring it includes placeholders for all database connection parameters (`PG_HOST`, `PG_USER`, `PG_PASSWORD`, `PG_DB`, `PG_PORT`) and any other environment-specific settings the sentiment service might need. Examples for sentiment service:
        *   `SENTIMENT_API_PORT=8000`
        *   `SENTIMENT_LOG_LEVEL=INFO`
        *   `SENTIMENT_LOG_FORMAT=json` (or `console`)
        *   `FINBERT_MODEL_NAME="ProsusAI/finbert"`
        *   `SPACY_MODEL_NAME="en_core_web_lg"`
        *   `BATCH_PROCESSOR_INTERVAL_SECONDS=30`
        *   `RETRY_MAX_ATTEMPTS=3`

### Task 1.4: Logging Setup

*   **Objective:** Implement robust, structured, and configurable logging throughout the sentiment analysis service.
*   **Details:**
    *   Create `sentiment_analyzer/utils/logging_setup.py`: This module will configure the Python `logging` framework.
    *   Aim for structured logging, preferably in JSON format. This makes logs easier to parse, search, and analyze by log management systems (e.g., ELK stack, Splunk).
    *   Allow configuration of log levels (e.g., DEBUG, INFO, WARNING, ERROR) via environment variables or the `config.yaml`.
    *   Ensure logs include relevant context like timestamps, module names, function names, and potentially correlation IDs for tracing requests across components.
    *   Configure log format (e.g., JSON for production, human-readable/pretty-print for development) based on an environment variable (e.g., `SENTIMENT_LOG_FORMAT`).
        *   *Example Snippet Placeholder for `logging_setup.py`*:
            ```python
            # import logging
            # import os
            # from pythonjsonlogger import jsonlogger

            # def setup_logging():
            #     log_format_type = os.getenv('SENTIMENT_LOG_FORMAT', 'console').lower()
            #     logger = logging.getLogger()
            #     handler = logging.StreamHandler()

            #     if log_format_type == 'json':
            #         formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(module)s %(funcName)s %(lineno)d %(message)s')
            #     else: # console / pretty-print
            #         formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

            #     handler.setFormatter(formatter)
            #     if not logger.handlers:
            #         logger.addHandler(handler)
            #     logger.setLevel(os.getenv('SENTIMENT_LOG_LEVEL', 'INFO').upper())
            #     # ... further configuration ...
            ```

---

## Phase 2: Database Integration & Models

Details for tasks in `sentiment_docs/TODO.md - Phase 2`.

### Task 2.1: Define ORM Models & Pydantic DTOs

*   **Objective:** Create Python representations for database tables (ORM models) and data structures for API communication and internal data transfer (Pydantic DTOs), ensuring data consistency and validation.
*   **Details:** (To be placed in `sentiment_analyzer/models/`)
    *   **SQLAlchemy ORM Models:** Based on the schema in `sentiment_docs/design.md`.
        *   `SentimentResultORM`: Maps to the `sentiment_results` table. Includes columns like `event_id`, `text_hash`, `sentiment_score`, `sentiment_label`, `sentiment_confidence`, `model_version`, `processed_at`.
        *   `SentimentMetricORM`: Maps to the `sentiment_metrics` table. Includes columns for aggregated data like `time_bucket`, `source`, `label`, `total_score`, `event_count`, `last_event_at`.
        *   `DeadLetterEventORM`: Maps to the `dead_letter_events` table. Includes columns for storing events that failed processing, like `event_id`, `payload`, `error_message`, `timestamp`.
    *   **Pydantic DTOs:**
        *   `SentimentResultDTO`: For representing a single sentiment analysis result. Used internally and potentially in API responses.
        *   `SentimentMetricDTO`: For representing aggregated sentiment metrics, used in API responses.
        *   `DeadLetterEventDTO`: For representing events that failed processing.
        *   `AnalyzeTextRequest`: Pydantic model for validating the JSON body of the `POST /api/v1/sentiment/analyze` endpoint (e.g., containing `text_content: str`).
        *   Other DTOs as needed for API query parameters or complex response structures.

### Task 2.2: Alembic Setup for Sentiment Tables

*   **Objective:** Enable and manage database schema migrations for the tables specific to the sentiment analysis service using Alembic.
*   **Details:**
    *   **Integration Strategy:** Decide if Alembic will be managed per-service or project-wide. If project-wide Alembic (from `f:/Coding/sentiment_pipeline/alembic/`) is used, ensure it's configured to pick up models from the `sentiment_analyzer` service. If service-specific, initialize Alembic within `sentiment_analyzer/`.
    *   Create an initial Alembic migration script (e.g., `versions/xxxx_create_sentiment_tables.py`) that defines the `UPGRADE` and `DOWNGRADE` functions for creating/dropping the `sentiment_results` and `sentiment_metrics` tables. This should include hypertable creation commands as per `design.md`.
    *   Create a separate Alembic migration script for the `dead_letter_events` table.
    *   Ensure all DDL commands within migrations (especially `CREATE EXTENSION` and `create_hypertable`) use `IF NOT EXISTS` clauses to ensure idempotency.
    *   Consider adding a manual check or a simple test step after migrations to verify hypertable properties are correctly set.

### Task 2.3: Database Connection Utility

*   **Objective:** Provide a standardized, asynchronous way for the service to obtain and manage database sessions.
*   **Details:**
    *   Create `sentiment_analyzer/utils/db_session.py`.
    *   This module will configure the SQLAlchemy asynchronous engine (`create_async_engine`) using connection details from the configuration (ultimately from environment variables).
    *   Provide an asynchronous session factory (`async_sessionmaker`) and potentially a dependency injector for FastAPI to manage session lifecycles per request or task.
    *   Ensure it uses `asyncpg` as the DBAPI driver for PostgreSQL.

---

## Phase 3: Core Components Implementation

Details for tasks in `sentiment_docs/TODO.md - Phase 3`. (To be placed in `sentiment_analyzer/core/`)

### Task 3.1: Data Fetcher (`data_fetcher.py`)

*   **Objective:** Retrieve new, unprocessed event data from the `raw_events` table in TimescaleDB.
*   **Details:**
    *   Implement functions to establish a database connection using the `db_session.py` utility.
    *   Query the `raw_events` table for records that have not yet been processed by the sentiment service.
        *   This requires a mechanism to track processed events. Options:
            1.  A boolean flag (e.g., `sentiment_processed_v1`) in `raw_events`. This might require an Alembic migration for `raw_events` managed by the main project Alembic.
            2.  Checking for the existence of `event_id` in `sentiment_results` (less efficient for large datasets).
            3.  A separate tracking table (e.g., `processed_event_log_sentiment`).
    *   Fetch events in batches (batch size configurable via `config.yaml`).
    *   Implement logic to "claim" events to prevent reprocessing by other instances or runs (e.g., update the flag immediately after fetching or use a robust advisory lock mechanism if concurrent processors are planned).

### Task 3.2: Preprocessor (`preprocessor.py`)

*   **Objective:** Clean, normalize, and prepare raw text data for effective sentiment analysis.
*   **Details:**
    *   **Language Detection:** Use `langdetect` or `fastText` to identify the language of the input text. Initially, filter to process only English texts (configurable).
    *   **Text Cleaning (spaCy):** Utilize `spaCy` with a suitable model (e.g., `en_core_web_lg` as per `design.md`).
        *   Standard cleaning: Lowercasing, removal/normalization of URLs, emails, mentions, hashtags.
        *   Emoji handling: Convert emojis to text representation or remove them, based on strategy.
        *   Tokenization.
        *   Lemmatization: Reduce words to their base/dictionary form.
        *   Stop-word removal: Remove common words that don't carry significant sentiment.
        *   Optional: Basic Named Entity Recognition (NER) if aspects of it are useful for context, though full ABSA is a future consideration.

### Task 3.3: Sentiment Analyzer (`sentiment_analyzer_component.py`)

*   **Objective:** Perform sentiment analysis on the preprocessed text using the chosen machine learning model.
*   **Details:**
    *   **Model Loading:** Implement logic to load the FinBERT model (e.g., `ProsusAI/finbert` from Hugging Face Transformers) or any other model specified in the configuration.
        *   Handle model path configuration (local path or Hugging Face identifier).
        *   Ensure efficient model loading (e.g., load once on service startup).
    *   **GPU Configuration:** If NVIDIA GPUs are available (as per project context), ensure PyTorch can utilize them for model inference. Add checks and configurations for CUDA.
    *   **Inference Function:** Create a function that takes preprocessed text as input and returns:
        *   Sentiment score (e.g., a continuous value from -1 to 1, or probabilities for each class).
        *   Sentiment label (e.g., 'positive', 'negative', 'neutral').
        *   Confidence score for the prediction (if available from the model).
    *   **Model Versioning:** Include the version of the sentiment model used for the analysis in the output. This is crucial for traceability and reproducibility.

### Task 3.4: Result Processor (`result_processor.py`)

*   **Objective:** Store the sentiment analysis results in the database and update any aggregated metrics.
*   **Details:**
    *   **Save Individual Results:** Take the output from the Sentiment Analyzer (as `SentimentResultDTO`) and save it to the `sentiment_results` table using the `SentimentResultORM` and an async database session.
    *   **Update Aggregated Metrics:** Based on the new sentiment result, update relevant records in the `sentiment_metrics` table.
        *   This might involve incrementing counts, summing scores for specific time buckets, sources, or labels.
        *   Consider if this aggregation should be real-time with each result or batched periodically.
    *   If an event consistently fails processing (e.g., after multiple retries if implemented, or due to unrecoverable data issues), it should be moved to a `dead_letter_events` table for later inspection. (Note: Full retry mechanism is post-MVP, but initial DLQ logging/storage can be part of this task).

### Task 3.5: Main Pipeline Orchestrator (`pipeline.py`)

*   **Objective:** Coordinate the sequential execution of the data fetcher, preprocessor, sentiment analyzer, and result processor for batch processing of events. Consider how events that fail processing will be handled (e.g., logged to a dead-letter queue for post-MVP retry mechanism).
*   **Objective:** Coordinate the sequential execution of the data fetcher, preprocessor, sentiment analyzer, and result processor for batch processing of events.
*   **Details:**
    *   Implement a main loop or function that defines the workflow:
        1.  Fetch a batch of raw events using `Data Fetcher`.
        2.  For each event in the batch:
            a.  Preprocess text using `Preprocessor`.
            b.  Perform sentiment analysis using `Sentiment Analyzer`.
            c.  Save results and update metrics using `Result Processor`.
    *   Manage batch processing logic (e.g., loop until no more data or for a set duration).
    *   Integrate comprehensive error handling: What happens if a single event fails? Skip it and log? Retry? Dead-letter queue (DLQ) for persistent failures (as per `design.md` future considerations, but basic error logging is MVP).
    *   Ensure detailed logging at each stage of the pipeline for monitoring and debugging.

---

## Phase 4: API Development

Details for tasks in `sentiment_docs/TODO.md - Phase 4`. (To be placed in `sentiment_analyzer/api/`)

### Task 4.1: Setup FastAPI Application (`main.py` or `app.py`)

*   **Objective:** Initialize and configure the FastAPI application that will serve the sentiment analysis API.
*   **Details:**
    *   In `sentiment_analyzer/api/main.py` (or `app.py`):
        *   Create an instance of the `FastAPI` application.
        *   Include API routers (defined in separate files, e.g., `endpoints/sentiment.py`).
        *   Set up application-level middleware if needed (e.g., for request logging, custom error handling, CORS).
        *   Define startup and shutdown events if necessary (e.g., to load ML models on startup, close DB connections on shutdown).

### Task 4.2: Implement API Endpoints (`endpoints/sentiment.py`)

*   **Objective:** Expose the sentiment analysis functionality and data retrieval capabilities via well-defined RESTful API endpoints.
*   **Details:** Create a router in `sentiment_analyzer/api/endpoints/sentiment.py` and implement the following endpoints as per `sentiment_docs/design.md`:
    *   **`POST /api/v1/sentiment/analyze`:**
        *   **Input:** JSON body containing text to analyze (e.g., `{"text_content": "Some financial news..."}`). Validated by `AnalyzeTextRequest` Pydantic model.
        *   **Processing:** Performs on-the-fly preprocessing and sentiment analysis of the input text using the core components.
        *   **Output:** JSON response with sentiment score, label, confidence, and model version (e.g., `SentimentResultDTO`).
    *   **`GET /api/v1/sentiment/events`:**
        *   **Input:** Query parameters for filtering results (e.g., `start_time`, `end_time`, `source`, `source_id`, `sentiment_label`, `limit`, `offset`). Use Pydantic models for query parameter validation if complex.
        *   **Processing:** Fetches data from the `sentiment_results` table based on filters.
        *   **Output:** JSON array of `SentimentResultDTO` objects, with pagination metadata.
    *   **`GET /api/v1/sentiment/metrics`:**
        *   **Input:** Query parameters for filtering aggregated metrics (e.g., `time_bucket_size` (e.g., 'hour', 'day'), `start_time`, `end_time`, `source`, `sentiment_label`).
        *   **Processing:** Fetches data from the `sentiment_metrics` table based on filters.
        *   **Output:** JSON array of `SentimentMetricDTO` objects.

### Task 4.3: API Input Validation

*   **Objective:** Ensure the robustness, security, and correctness of API endpoints by strictly validating all incoming data.
*   **Details:**
    *   Leverage FastAPI's automatic request body validation using Pydantic models for all `POST`/`PUT` requests.
    *   For `GET` request query parameters, define them with type hints in endpoint function signatures. For more complex validation or groups of query parameters, Pydantic models can also be used with `Depends`.
    *   Ensure appropriate HTTP status codes are returned for validation errors (FastAPI handles this well with 422 Unprocessable Entity).

---

## Phase 5: Dockerization & Deployment Configuration

Details for tasks in `sentiment_docs/TODO.md - Phase 5`.

### Task 5.1: Create `Dockerfile` for the Sentiment Service

*   **Objective:** Package the sentiment analysis service, its dependencies, and necessary assets into a portable, reproducible Docker image.
*   **Details:** (Create `sentiment_analyzer/Dockerfile`)
    *   Start from an official Python base image (e.g., `python:3.9-slim`).
    *   Set up a working directory (e.g., `/app`).
    *   Copy dependency files (`requirements.txt` or `pyproject.toml`) and install dependencies.
        *   Consider multi-stage builds to keep the final image lean.
    *   Copy the application code (`sentiment_analyzer/` content) into the image.
    *   Handle ML models:
        *   If small, they can be downloaded during the Docker build (e.g., `spacy download en_core_web_lg`).
        *   If large, consider downloading them as a separate step or mounting them via volumes in deployment, or using a custom base image with models pre-loaded.
    *   Set the entry point/command to run the service (e.g., `uvicorn sentiment_analyzer.api.main:app --host 0.0.0.0 --port 80` for the API, or a script for the batch processor if it's a separate process).
    *   Expose the necessary port (e.g., `EXPOSE 80`).

### Task 5.2: Update `docker-compose.yml` (Project Root)

*   **Objective:** Integrate the new sentiment analyzer service into the project's overall Docker Compose orchestration.
*   **Details:** (Edit `f:/Coding/sentiment_pipeline/docker-compose.yml`)
    *   Add a new service definition for `sentiment-analyzer`:
        ```yaml
        services:
          # ... other services (e.g., timescaledb, reddit_scraper)
          sentiment-analyzer:
            build:
              context: ./sentiment_analyzer # Path to the Dockerfile directory
              dockerfile: Dockerfile
            container_name: sentiment_analyzer_service
            ports:
              - "8001:80" # Expose service on host port 8001, container port 80
            environment:
              - PG_HOST=timescaledb_service
              - PG_PORT=${PG_PORT_CONTAINER} # from .env
              - PG_USER=${PG_USER}
              - PG_PASSWORD=${PG_PASSWORD}
              - PG_DB=${PG_DB}
              - FINBERT_MODEL_PATH=/models/finbert # Example if mounting models
              # ... other necessary env vars
            volumes:
              # - ./models_volume:/models # Example for mounting large ML models
            depends_on:
              - timescaledb
            networks:
              - sentiment_net # Assuming a shared network
            # healthcheck: ... (Define a health check)
        ```
    *   Ensure correct build context, environment variable propagation (from `.env`), volume mounts (if any), network configuration, and dependencies (`depends_on`).
    *   Define a health check for the service.

### Task 5.3: Environment Variables (`.env` file)

*   **Objective:** Manage all externalized configuration parameters, especially sensitive ones and deployment-specific settings, in a central `.env` file.
*   **Details:**
    *   Ensure all environment variables required by the `sentiment-analyzer` service (as defined in its configuration loader and `docker-compose.yml`) are documented in the project's root `.env.example` file.
    *   This includes database connection strings/components, paths to models (if external), API keys for external services (if any), logging levels, etc.

---

## Phase 6: Testing

Details for tasks in `sentiment_docs/TODO.md - Phase 6`. (Tests to be placed in `sentiment_analyzer/tests/`)

### Task 6.1: Unit Tests

*   **Objective:** Verify that individual functions, methods, and classes (units) of the sentiment service work correctly in isolation.
*   **Details:** (In `sentiment_analyzer/tests/unit/`)
    *   **Preprocessor:** Test text cleaning functions with various inputs (URLs, emojis, mixed case, punctuation). Mock spaCy if its full processing is too slow for unit tests, or test with a small, controlled spaCy pipeline.
    *   **Sentiment Analyzer:** Test the sentiment analysis logic. Mock the actual ML model inference to avoid heavy computation and external dependencies; focus on the surrounding logic (data transformation, output formatting).
    *   **Data Fetcher/Result Processor:** Mock database interactions (e.g., using `unittest.mock.AsyncMock` for session methods) to test the logic of querying, data transformation, and constructing ORM objects without hitting a real database.
    *   **API Endpoint Logic:** Test the business logic within API endpoint functions. Mock service calls (e.g., to the core pipeline components) and database interactions. Use FastAPI's `TestClient` for some unit-level testing of request/response handling if not covered by integration tests.
    *   **Configuration Loading & Utilities:** Test any utility functions or configuration loading logic.

### Task 6.2: Integration Tests

*   **Objective:** Verify that different components of the sentiment service work together correctly and interact properly with external systems like the database.
*   **Details:** (In `sentiment_analyzer/tests/integration/`)
    *   **Full Pipeline Test:** Test the end-to-end batch processing pipeline: seeding `raw_events` in a test database, running the orchestrator, and verifying that `sentiment_results` and `sentiment_metrics` are correctly populated.
    *   **API Endpoint Tests:** Use FastAPI's `TestClient` (with `httpx` for async) to send HTTP requests to the API endpoints and assert responses. These tests should interact with a real (but test-scoped) database instance where migrations have been applied.
        *   Test `POST /analyze` with various inputs.
        *   Test `GET /events` and `GET /metrics` with different filter parameters, checking data integrity and pagination.
    *   **Database Interactions:** Test CRUD operations using the ORM models against a test database to ensure mappings and relationships are correct.
    *   **Test Fixture Reusability:** Explicitly reference `common/tests/timescaledb_test_strategy.md`. Adapt and reuse existing common test fixtures (e.g., for Dockerized TimescaleDB instances, database session fixtures) to avoid duplication and maintain consistency with the broader project's testing approach.

### Task 6.3: Test Coverage

*   **Objective:** Ensure a significant portion of the codebase is covered by automated tests to improve reliability and catch regressions.
*   **Details:**
    *   Use tools like `pytest-cov` to measure test coverage.
    *   Aim for a high coverage percentage (e.g., >80-90%) for critical components.
    *   Analyze coverage reports to identify untested code paths.

---

## Phase 7: Documentation & Finalization

Details for tasks in `sentiment_docs/TODO.md - Phase 7`.

### Task 7.1: Update/Create `README.md` for Sentiment Service

*   **Objective:** Provide comprehensive, user-friendly documentation for understanding, setting up, running, and developing the sentiment analysis service.
*   **Details:** (Create/update `sentiment_analyzer/README.md`)
    *   **Overview:** Briefly describe the service's purpose and architecture.
    *   **Setup Instructions:** How to set up the development environment, install dependencies, configure environment variables.
    *   **Running the Service:** Instructions for running the API server (e.g., `uvicorn ...`) and the batch processor (if it's a separate script/entry point).
    *   **API Endpoint Documentation:** Detailed descriptions of each API endpoint, including URL, HTTP method, request parameters/body, and example responses (can link to or summarize from `design.md`).
    *   **Configuration:** Explain key configuration options in `config.yaml` and relevant environment variables.
    *   **Testing:** How to run unit and integration tests.

### Task 7.2: Code Review & Refinement

*   **Objective:** Ensure the codebase is high-quality, maintainable, readable, and adheres to project standards before considering it complete.
*   **Details:**
    *   Perform a thorough peer review of the code if possible, or a self-review against a checklist.
    *   Ensure adherence to PEP 8 style guidelines. Use linters (e.g., Flake8) and formatters (e.g., Black).
    *   Add or improve comments and docstrings (e.g., Google style as per user rules) where logic is complex or non-obvious.
    *   Refactor any overly complex or duplicated code.

### Task 7.3: Performance Profiling & Optimization (if needed)

*   **Objective:** Ensure the sentiment analysis service meets the performance targets defined in `sentiment_docs/prd.md` (e.g., throughput, API latency).
*   **Details:**
    *   Identify potential bottlenecks: ML model inference, database queries, text preprocessing, API request handling.
    *   Use profiling tools (e.g., `cProfile`, `Pyinstrument`, or APM tools) to measure the performance of critical components under realistic load.
    *   If performance targets are not met, optimize the identified bottlenecks. This could involve code changes, query optimization, or infrastructure adjustments.

### Task 7.4: Final Check against `prd.md` and `design.md`

*   **Objective:** Confirm that the implemented service fulfills all specified requirements and aligns with the agreed-upon design.
*   **Details:**
    *   Systematically review each requirement in `sentiment_docs/prd.md` (functional, non-functional, data, etc.) and verify it has been met.
    *   Compare the final implementation against the architectural decisions and component designs in `sentiment_docs/design.md`.
    *   Document any deviations and their rationale.

---

This detailed breakdown should guide the implementation of the Sentiment Analysis Service. Remember to commit changes frequently and test each significant step.
