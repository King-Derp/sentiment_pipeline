# TODO: Sentiment Analysis Service Implementation

This document outlines the step-by-step tasks required to implement the Sentiment Analysis Service as per the `prd.md` and `design.md`.

**Legend:**
- `[ ]` Task to be done
- `[x]` Task completed
- `[-]` Task in progress
- `[!]` Task blocked

## Phase 1: Project Setup & Foundation (Sentiment Service Module) - COMPLETED

- `[x]` **1.1: Create Service Directory Structure:**
  - `[x]` Create `sentiment_analyzer` main directory (e.g., `f:/Coding/sentiment_pipeline/sentiment_analyzer/`).
  - `[x]` Inside `sentiment_analyzer`, create subdirectories: `core` (for main logic), `models` (for DTOs/ORMs), `api`, `config`, `tests`, `utils`.
  - `[x]` Add `__init__.py` files to make them Python packages.
- `[x]` **1.2: Initialize Dependency Management:**
  - `[x]` Create/update `requirements.txt` or `pyproject.toml` (if using Poetry/PDM) for the service, including:
    - `fastapi`, `uvicorn`, `pydantic`
    - `sqlalchemy`, `asyncpg` (for TimescaleDB)
    - `alembic` (for migrations specific to sentiment tables)
    - `spacy` (and download `en_core_web_lg` model)
    - `transformers`, `torch` (for FinBERT, ensure CUDA version compatibility if using GPU)
    - `langdetect` or `fasttext`
    - `python-dotenv`, `pyyaml` (for configuration)
    - `pytest`, `httpx` (for testing)
- `[x]` **1.3: Basic Configuration Setup:**
  - `[x]` Create `sentiment_analyzer/config/config.yaml` (with placeholders for DB, model paths, etc.).
  - `[x]` Implement a utility to load configuration from YAML and environment variables (e.g., in `sentiment_analyzer/config/loader.py`).
- `[x]` **1.4: Logging Setup:**
  - `[x]` Implement a centralized logging configuration (e.g., in `sentiment_analyzer/utils/logging_setup.py`) for structured JSON logging.

## Phase 2: Database Integration & Models - COMPLETED

- `[x]` **2.1: Define ORM Models & Pydantic DTOs:** (in `sentiment_analyzer/models/`)
  - `[x]` Create `SentimentResultORM` (SQLAlchemy model for `sentiment_results` table).
  - `[x]` Create `SentimentMetricORM` (SQLAlchemy model for `sentiment_metrics` table).
  - `[x]` Create `SentimentResultDTO` (Pydantic model for API and internal data transfer).
  - `[x]` Create `SentimentMetricDTO` (Pydantic model for API).
  - `[x]` Create Pydantic models for API request bodies (e.g., `AnalyzeTextRequest`).
- `[x]` **2.2: Alembic Setup for Sentiment Tables:**
  - `[x]` Initialize Alembic within the `sentiment_analyzer` module if it's to manage its own migrations (or integrate with a project-wide Alembic setup).
  - `[x]` Create initial Alembic migration script to create `sentiment_results` and `sentiment_metrics` hypertables (as defined in `design.md`).
  - `[x]` Create Alembic migration script for `dead_letter_events` table.
- `[x]` **2.3: Database Connection Utility:**
  - `[x]` Create a utility (e.g., `sentiment_analyzer/utils/db_session.py`) to manage asynchronous database sessions using SQLAlchemy and `asyncpg`.

## Phase 3: Core Components Implementation (in `sentiment_analyzer/core/`)

- `[x]` **3.1: Data Fetcher (`data_fetcher.py`):**
  - `[x]` Implement logic to connect to TimescaleDB.
  - `[x]` Implement function to fetch a batch of unprocessed events from `raw_events` (check for a `processed` flag).
  - `[x]` Implement logic to claim events (e.g., set `processed = TRUE`, `processed_at = NOW()`).
- `[x]` **3.2: Preprocessor (`preprocessor.py`):**
  - `[x]` Implement text cleaning using `spaCy` (`en_core_web_lg`):
    - `[x]` Lowercasing, URL removal, emoji removal/conversion.
    - `[x]` Lemmatization, stop-word removal.
  - `[x]` Implement language detection (e.g., using `langdetect`). Initially, filter for English.
- `[x]` **3.3: Sentiment Analyzer (`sentiment_analyzer_component.py`):**
  - `[x]` Implement loading of the FinBERT model (from Hugging Face Transformers or local path).
    - `[x]` Ensure GPU support is correctly configured if available (PyTorch CUDA).
  - `[x]` Implement function to perform sentiment analysis on preprocessed text, returning score, label, confidence.
  - `[x]` Include model version in the output.
- `[x]` **3.4: Result Processor (`result_processor.py`):**
  - `[x]` Implement logic to save individual `SentimentResultDTO` objects to the `sentiment_results` table using `SentimentResultORM`.
  - `[x]` Implement logic to update/insert aggregated data into the `sentiment_metrics` table (using `SentimentMetricORM`) based on new results.
- `[x]` **3.5: Main Pipeline Orchestrator (`pipeline.py`):**
  - `[x]` Create a main loop/function that orchestrates the flow: Data Fetcher -> Preprocessor -> Sentiment Analyzer -> Result Processor.
  - `[x]` Implement batch processing logic.
  - `[x]` Integrate error handling and logging for each step.

## Phase 4: API Development (in `sentiment_analyzer/api/`)

- `[ ]` **4.1: Setup FastAPI Application (`main.py` or `app.py`):**
  - `[ ]` Initialize FastAPI app.
  - `[ ]` Include routers, middleware (e.g., for logging, error handling).
- `[ ]` **4.2: Implement API Endpoints (`endpoints/sentiment.py`):**
  - `[ ]` **`POST /api/v1/sentiment/analyze`:**
    - `[ ]` Accept text input (validated by Pydantic model).
    - `[ ]` Perform preprocessing and sentiment analysis (on-the-fly).
    - `[ ]` Return sentiment score, label, confidence, model version.
  - `[ ]` **`GET /api/v1/sentiment/events`:**
    - `[ ]` Implement query parameters for filtering (time range, source, source_id, label).
    - `[ ]` Fetch data from `sentiment_results` table.
    - `[ ]` Return list of `SentimentResultDTO`.
    - `[ ]` Implement cursor-based pagination.
  - `[ ]` **`GET /api/v1/sentiment/metrics`:**
    - `[ ]` Implement query parameters for filtering (time range, bucket, source, source_id, label).
    - `[ ]` Fetch data from `sentiment_metrics` table.
    - `[ ]` Return list of `SentimentMetricDTO`.
    - `[ ]` Implement cursor-based pagination.
  - `[ ]` Create helper utilities for cursor-based pagination (encoding/decoding).
- `[ ]` **4.3: API Input Validation:**
  - `[ ]` Ensure all API inputs are strictly validated using Pydantic models.

## Phase 5: Dockerization & Deployment Configuration

- `[ ]` **5.1: Create `Dockerfile` for the Sentiment Service:**
  - `[ ]` Include steps to install dependencies (Python, system libraries if any).
  - `[ ]` Copy application code.
  - `[ ]` Set up entry point (e.g., to run Uvicorn for API, or a script for the batch processor).
  - `[ ]` Ensure spaCy and Hugging Face models are handled correctly (download during build or mount if large).
- `[ ]` **5.2: Update `docker-compose.yml` (Project Root):**
  - `[ ]` Add a service definition for `sentiment-analyzer`.
  - `[ ]` Configure build context to the `sentiment_analyzer` directory.
  - `[ ]` Set up environment variables (DB connection, model paths, API port).
  - `[ ]` Define dependencies (e.g., `depends_on: timescaledb`).
  - `[ ]` Configure volume mounts if needed (e.g., for models, config files if not baked into image).
  - `[ ]` Add health checks.
- `[ ]` **5.3: Environment Variables (`.env.example` file):**
  - `[ ]` Ensure all necessary sentiment-service-specific environment variables are documented with examples in the project's `.env.example` file.

## Phase 6: Testing

- `[ ]` **6.1: Unit Tests (in `sentiment_analyzer/tests/unit/`):**
  - `[ ]` Write unit tests for Preprocessor functions (mocking `spaCy` if needed, or testing with small inputs).
  - `[ ]` Write unit tests for Sentiment Analyzer component (mocking model inference or using a tiny dummy model).
  - `[ ]` Write unit tests for Data Fetcher logic (mocking DB interactions).
  - `[ ]` Write unit tests for Result Processor logic (mocking DB interactions).
  - `[ ]` Write unit tests for API endpoint logic (mocking service calls).
  - `[ ]` Write unit tests for configuration loading and utility functions.
- `[ ]` **6.2: Integration Tests (in `sentiment_analyzer/tests/integration/`):**
  - `[ ]` Test the full pipeline flow: `raw_events` -> Data Fetcher -> ... -> `sentiment_results`/`sentiment_metrics` (requires a test TimescaleDB instance).
  - `[ ]` Test API endpoints against a live (test) service and database.
  - `[ ]` Test database interactions (CRUD operations for ORMs).
  - `[ ]` Reference and reuse common test fixtures from `common/tests/timescaledb_test_strategy.md` where applicable.
- `[ ]` **6.3: Test Coverage:**
  - `[ ]` Aim for a high test coverage percentage.

## Phase 7: Documentation & Finalization

- `[ ]` **7.1: Update/Create `README.md` for Sentiment Service:**
  - `[ ]` Add specific setup instructions for the sentiment service.
  - `[ ]` Document API endpoints in detail.
  - `[ ]` Explain configuration options.
  - `[ ]` Provide instructions on how to run the service (batch processor, API server).
- `[ ]` **7.2: Code Review & Refinement:**
  - `[ ]` Perform a thorough code review.
  - `[ ]` Ensure all code adheres to PEP8 and project styling guidelines.
  - `[ ]` Add/improve comments and docstrings.
- `[ ]` **7.3: Performance Profiling & Optimization (if needed):**
  - `[ ]` Profile key components (preprocessor, sentiment model inference, DB writes) under load.
  - `[ ]` Optimize bottlenecks if performance targets from `prd.md` are not met.
- `[ ]` **7.4: Final Check against `prd.md` and `design.md`:**
  - `[ ]` Ensure all requirements and design specifications have been met.

## Discovered During Work (New Tasks)

- `[ ]` Define schema and implement Alembic migration for `dead_letter_events` table.
- `[ ]` (Post-MVP) Design and implement a background job/mechanism to retry events from `dead_letter_events`.
- `[ ]` ... (Add any new tasks that arise during development)
