# To-Do List: TimescaleDB Implementation for Sentiment Pipeline

**Version:** 1.0
**Date:** 2025-05-22

This document outlines the step-by-step tasks required to implement TimescaleDB as the primary data storage for the Sentiment Pipeline project, with a focus on an **Alembic-driven schema management** approach. Refer to `prd.md` for detailed requirements.

## Phase 1: Project Setup & Alembic Initialization

-   [x] **1.1. Finalize Docker Compose for TimescaleDB Service**
    -   [x] Ensure `docker-compose.yml` correctly defines the `timescaledb` service.
    -   [x] Mount a named volume for data persistence (e.g., `timescaledb_data:/var/lib/postgresql/data`).
    -   [x] Expose port `5432`.
    -   [x] Configure necessary environment variables (from `.env`) for `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`.
-   [x] **1.2. Setup Project-Level `.env` File**
    -   [x] Define `PG_HOST`, `PG_PORT`, `PG_USER`, `PG_PASSWORD`, `PG_DB` for use by services and Alembic.
    -   [ ] Ensure `.env.example` is up-to-date.
-   [x] **1.3. Initialize Alembic for Database Migrations**
    -   [x] Install Alembic (`pip install alembic sqlalchemy psycopg2-binary`).
    -   [x] Run `alembic init alembic` in the project root to create the `alembic` directory and `alembic.ini`.
-   [x] **1.4. Configure Alembic (`alembic.ini` and `alembic/env.py`)**
    -   [x] In `alembic.ini`, set `sqlalchemy.url` to read from environment variables (e.g., `postgresql://${PG_USER}:${PG_PASSWORD}@${PG_HOST}:${PG_PORT}/${PG_DB}`).
    -   [x] In `alembic/env.py`:
        -   [x] Import necessary SQLAlchemy models (e.g., from `reddit_scraper.src.models` or a central models location if created).
        -   [x] Set `target_metadata` to your SQLAlchemy `MetaData` object (e.g., `target_metadata = Base.metadata`).
        -   [x] Ensure `env.py` can construct the database URL from environment variables for the context.
-   [x] **1.5. Define SQLAlchemy Models (if not already complete)**
    -   [x] Ensure `SubmissionORM` (and any other relevant models) are correctly defined with SQLAlchemy, including appropriate data types and table names (e.g., `raw_submissions`). These models will be used by Alembic to autogenerate migration scripts.

## Phase 2: Initial Schema Migration with Alembic

-   [x] **2.1. Create First Alembic Migration Script (Autogenerate)**
    -   [x] With Alembic configured and models defined, generate the initial migration script: `alembic revision -m "create_initial_schema_and_hypertable" --autogenerate`.
    -   [x] Review the generated script in `alembic/versions/`.
-   [x] **2.2. Edit Migration Script for TimescaleDB Specifics**
    -   [x] In the generated migration script, add commands for:
        -   [x] Enabling the TimescaleDB extension: `op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")` (in the `upgrade` function).
        -   [x] Creating the hypertable: `op.execute("SELECT create_hypertable('raw_submissions', 'created_utc', chunk_time_interval => 604800, if_not_exists => TRUE);")` (after table creation in `upgrade`).  *Note: Implemented with 7-day interval (604800s).*
        -   [x] Add corresponding `DROP TABLE` and potentially `DROP EXTENSION` (if appropriate) in the `downgrade` function.
    -   [x] Ensure necessary indexes (e.g., on `created_utc`, `id`, `subreddit`) are also created via `op.create_index()`.
-   [x] **2.3. Apply the Initial Migration**
    -   [x] Ensure the TimescaleDB service is running (`docker-compose up -d timescaledb`).
    -   [x] Run the migration: `alembic upgrade head`.
-   [x] **2.4. Verify Schema and Hypertable in DB**
    -   [x] Connect to TimescaleDB (e.g., via `docker exec timescaledb_service psql ...`).
    -   [x] Verify table `raw_submissions` exists (`\dt`).
    -   [x] Verify TimescaleDB extension is active (`\dx`).
    -   [x] Verify `raw_submissions` is a hypertable (`SELECT * FROM timescaledb_information.hypertables;`).

## Phase 3: Scraper Integration with Alembic-Managed Schema

-   [x] **3.1. Update Scraper DB Connection Logic**
    -   [x] Ensure scraper(s) use the environment variables (`PG_HOST`, etc.) via a centralized `PostgresConfig` object to connect to TimescaleDB, as detailed in `timescaledb_integration_guide.md`.
        -   *Note (2025-05-23): Refactored `storage/db.py`, `storage/postgres_sink.py`, and `cli.py` to achieve this. `PostgresSink` now takes `PostgresConfig`, uses correct table `raw_submissions`, and aligns with Alembic-managed schema.* 
    -   [x] **Crucially**: Remove any `metadata.create_all()` calls from scraper code related to the TimescaleDB sink. Scrapers should assume tables exist. *(Achieved by refactoring `PostgresSink` not to manage schema)*
-   [x] **3.2. Test Scraper Data Ingestion**
    -   [x] Run the scraper service.
    -   [x] Verify data is being written to `raw_submissions` in TimescaleDB.
    -   [x] Check for any connection or ORM errors related to schema mismatches (should not occur if models align with Alembic migrations).
-   [x] **3.3. Implement Idempotent Writes (if not already robust)**
    -   [x] Ensure scraper write operations to TimescaleDB are idempotent (e.g., using `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_nothing()`).

## Phase 4: Documentation, Testing & Refinement

-   [x] **4.1. Update Project `README.md`**
    -   [x] Document the Alembic migration process for initial DB setup (done).
    -   [x] Update project structure to include `alembic/` directory and `alembic.ini` (done).
-   [x] **4.2. Update `reddit_scraper/README.md`**
    -   [x] Clarify that schema is managed by Alembic (done).
    -   [x] Reference `timescaledb_integration_guide.md` for connection details (done).
-   [x] **4.3. Update `timescaledb/prd.md`**
    -   [x] Reflect Alembic as the tool for schema and hypertable management (done).
-   [x] **4.4. Update this `timescaledb/todo.md` and `timescaledb/todo_details.md`**
    -   `[-]` This update is currently in progress for `todo.md`.
    -   `[ ]` Align `todo_details.md` with this new Alembic-focused task list.
-   [ ] **4.5. Write Unit/Integration Tests for DB Interaction**
    -   `[ ]` (Future) Tests for scraper writing to a test DB instance.
-   [ ] **4.6. Review Connection Pooling**
    -   `[ ]` Confirm SQLAlchemy's default pooling is adequate for initial needs.
    -   `[ ]` Document PgBouncer as a future scaling option if necessary.

## Phase 5: Future Enhancements (Post-MVP)

-   [ ] **5.1. Implement PgBouncer (if needed)**
-   [ ] **5.2. Advanced TimescaleDB Features (Continuous Aggregates, Compression)**
-   [ ] **5.3. Monitoring and Alerting for DB Performance**

---
*Self-review: Ensure all manual `psql` steps for schema/hypertable creation in old docs are replaced by Alembic procedures.*
