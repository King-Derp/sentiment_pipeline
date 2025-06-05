# Project Tasks

## Completed

- **Resolve Alembic migration issues and set up `raw_events` table** (Completed: YYYY-MM-DD)
  - Corrected `down_revision` in migration `2dde641de514`.
  - Fixed `sqlalchemy.url` in `alembic.ini`.
  - Ensured `PrimaryKeyConstraint` and `UniqueConstraint` on `raw_events` include the TimescaleDB partitioning column (`occurred_at`).
  - Successfully ran `alembic upgrade head` and verified `raw_events` hypertable.
- **Update data ingestion logic to use `RawEventORM`** (Completed: YYYY-MM-DD)
  - Modified `SQLAlchemyPostgresSink` in `reddit_scraper` to write to the `raw_events` table using `RawEventORM`.
  - Ensured correct mapping of `SubmissionRecord` fields to `RawEventORM`, including `datetime` conversion for `occurred_at`.
  - Verified successful data ingestion into `raw_events` via `docker-compose` and `psql`.
- **Create `ARCHITECTURE.md` to consolidate core architectural documentation.** (Completed: 2024-07-26)
  - Synthesized information from existing docs into a new `ARCHITECTURE.md`. Updated `README.md` to reference it.
- **Simplify `scraper_implementation_rule.md`** (Completed: 2024-07-26)
    - Removed redundant details now in `ARCHITECTURE.md`.
    - Updated terminology (e.g., `raw_event` to `raw_events`, `timestamp` to `occurred_at`).
- **Simplify `timescaledb_integration_guide.md`** (Completed: 2024-07-26)
    - Removed redundant details now in `ARCHITECTURE.md`.
    - Ensured consistency with `RawEventORM` and Alembic-managed schema.
- **Simplify `reddit_scraper/README.md`** (Completed: 2024-07-27)
    - Removed redundant architectural details and deprecated scraper information.
    - Focused on scraper-specific setup, usage, and configuration, pointing to `ARCHITECTURE.md` for broader concepts.
- **Archive `reddit_scraper/docs/default_scraper.md`** (Completed: 2024-07-27)
  - Moved to `archive/default_scraper_2024-07-27.md` as its content is largely superseded by `ARCHITECTURE.md` and the updated `reddit_scraper/README.md`.
- **Archive `reddit_scraper/docs/specialized_scrapers.md`** (Completed: 2024-07-27)
  - Moved to `archive/specialized_scrapers_2024-07-27.md`. This document is obsolete as specialized scraper classes are deprecated in favor of the main `scrape` command with date parameters, as noted in `reddit_scraper/README.md`.
- **Refactor `reddit_scraper/prd.md`** (Completed: 2024-07-27)
  - Updated to reflect current architecture (`RawEventORM`, `raw_events` table), storage strategy, configuration (env vars for DB), and removed outdated requirements. Aligned with `ARCHITECTURE.md`.
- **Archive `reddit_scraper/todo.md`** (Completed: 2024-07-27)
  - Relevant future tasks migrated to 'Discovered During Work' section. File content replaced with an archival notice and original content moved to `archive/reddit_scraper_todo_2024-07-27.md`.
- **Archive `reddit_scraper/postgres_implementation_plan.md`** (Completed: 2024-07-27)
  - Content superseded by `ARCHITECTURE.md`, Alembic-managed schema, and `SQLAlchemyPostgresSink`. File content replaced with an archival notice and original content moved to `archive/reddit_scraper_postgres_implementation_plan_2024-07-27.md`.
- **Update `common/tests/comment_scraper_test_plan.md`** (Completed: 2024-07-27)
  - Renamed to `common/tests/database_integration_test_plan.md` to better reflect its content.
  - Updated to align with current testing strategies (Pytest), `RawEventORM`, and the `raw_events` table. Ensured terminology for data objects (`RawEventDTO`, `RawEventORM`) is accurate.
- **Review and Update Root `README.md`** (Completed: 2024-07-27)
  - Ensured it provides a clear, high-level overview.
  - Updated references to `ARCHITECTURE.md`, `raw_events` table, and other key documents.
  - Verified and updated the "Project Structure" and "Project Documentation" sections.
- **Update `DOCUMENTATION.md`** (Completed: 2024-07-27)
  - Accurately lists current, relevant documentation files (added `ARCHITECTURE.md`, updated `database_integration_test_plan.md`).
  - Removed entries for archived documents (`TODO.md` (root), `reddit_scraper/todo.md`, `reddit_scraper/postgres_implementation_plan.md`, `reddit_scraper/docs/default_scraper.md`, `reddit_scraper/docs/specialized_scrapers.md`).
  - Noted files for further review (`reddit_scraper/todo_part2.md`, `reddit_scraper/test_env.txt`).
- **Verify Root `PLANNING.md` and `PRD.md`** (Completed: 2024-07-27)
  - Confirmed that root `PLANNING.md` and `PRD.md` do not exist. `README.md` updated accordingly.
- **Review `reddit_scraper/README.md`** (Completed: 2024-07-27)
    - Ensured consistency with `ARCHITECTURE.md` and `raw_events` table.
    - Documented `use_sqlalchemy` flag and dual sink implementations (`SQLAlchemyPostgresSink` and `PostgresSink`).
    - Verified primary key information points to `ARCHITECTURE.md`.
- **Review `timescaledb/prd.md`** (Completed: 2024-07-27)
    - Ensured consistency with `ARCHITECTURE.md` (updated table name to `raw_events` and model to `RawEventORM`).
    - Confirmed no changes needed regarding the dual sink mechanism as PRD focuses on DB requirements.
- **Review `timescaledb_integration_guide.md`** (Completed: 2024-07-27)
    - Verified that primary key and schema information correctly defers to `ARCHITECTURE.md`.
    - Confirmed general consistency with `ARCHITECTURE.md` (table name, ORM model, Alembic schema management).
- **Fix all tests in `timescaledb/tests`** (Completed: 2025-06-02)
  - Created PowerShell scripts to automate the test environment lifecycle:
    - `run_docker_tests.ps1`: Handles the complete test lifecycle (start → test → shutdown)
    - `run_tests.ps1`: For development workflow with option to keep environment running
  - Fixed environment variable loading from `.env.test`
  - Implemented proper test path resolution
  - Fixed database URL construction
  - Added Alembic migration execution
  - Added container health checking
  - Successfully ran all 32 integration tests with both scripts
- **Refactor reddit_scraper/pyproject.toml to root and update docs** (Completed: 2025-05-30)
  - Read DOCUMENTATION.md and all mentioned documents.
  - Moved reddit_scraper/pyproject.toml to the project root.
  - Updated all relevant files and documents (DOCUMENTATION.md, reddit_scraper/README.md, reddit_scraper/Dockerfile, docker-compose.yml) to reflect this change.
  - Ran `poetry lock` and `poetry install` successfully in the root directory.
- **Complete Phase 2 of Sentiment Analysis Service: Database Integration & Models** (Completed: 2025-06-05)

## Current / Next Tasks

- **Verify no writes to `raw_submissions` and update downstream consumers** (Added: YYYY-MM-DD) # Placeholder, to be addressed separately
  - Confirm no active code paths attempt to write to the (now dropped) `raw_submissions` table.
  - Identify and update any downstream processes or queries that previously read from `raw_submissions` to use `raw_events`.
  - Plan for removal of any remaining `SubmissionORM` definitions or related old code if no longer needed.

### Documentation Simplification & Refactoring (Ongoing)

*   **Review and Refactor/Archive Remaining Documentation (Updated: 2024-07-27)**
    *   [x] **`reddit_scraper/docs/specialized_scrapers.md`** (Archived: 2024-07-27)
        *   Moved to `archive/specialized_scrapers_2024-07-27.md`. This document is obsolete as specialized scraper classes are deprecated in favor of the main `scrape` command with date parameters, as noted in `reddit_scraper/README.md`.
    *   [x] **`reddit_scraper/prd.md`** (Refactored: 2024-07-27)
        *   Updated to reflect current architecture (`RawEventORM`, `raw_events` table), storage strategy, configuration (env vars for DB), and removed outdated requirements. Aligned with `ARCHITECTURE.md`.
    *   [x] **`reddit_scraper/todo.md`** (Archived: 2024-07-27)
        *   Relevant future tasks migrated to 'Discovered During Work' section. File content replaced with an archival notice and original content moved to `archive/reddit_scraper_todo_2024-07-27.md`.
    *   [x] **`reddit_scraper/postgres_implementation_plan.md`** (Archived: 2024-07-27)
        *   Content superseded by `ARCHITECTURE.md`, Alembic-managed schema, and `SQLAlchemyPostgresSink`. File content replaced with an archival notice and original content moved to `archive/reddit_scraper_postgres_implementation_plan_2024-07-27.md`.
    *   [x] **`common/tests/database_integration_test_plan.md`** (Renamed & Updated: 2024-07-27)
        *   Renamed from `common/tests/comment_scraper_test_plan.md` to better reflect its content.
        *   Updated to align with current testing strategies (Pytest), `RawEventORM`, and the `raw_events` table. Ensured terminology for data objects (`RawEventDTO`, `RawEventORM`) is accurate.
    *   [x] **Root `README.md`** (Reviewed & Updated: 2024-07-27)
        *   Ensured it provides a clear, high-level overview.
        *   Updated references to `ARCHITECTURE.md`, `raw_events` table, and other key documents.
        *   Verified and updated the "Project Structure" and "Project Documentation" sections.
    *   [x] **`DOCUMENTATION.md`** (Reviewed & Updated: 2024-07-27)
        *   Accurately lists current, relevant documentation files (added `ARCHITECTURE.md`, updated `database_integration_test_plan.md`).
        *   Removed entries for archived documents (`TODO.md` (root), `reddit_scraper/todo.md`, `reddit_scraper/postgres_implementation_plan.md`, `reddit_scraper/docs/default_scraper.md`, `reddit_scraper/docs/specialized_scrapers.md`).
        *   Noted files for further review (`reddit_scraper/todo_part2.md`, `reddit_scraper/test_env.txt`).
    *   [x] **Verify Root `PLANNING.md` and `PRD.md`** (Completed: 2024-07-27)
        *   Confirmed that root `PLANNING.md` and `PRD.md` do not exist. `README.md` updated accordingly.
    *   [x] **Review `reddit_scraper/README.md`** (Completed: 2024-07-27)
        *   Ensured consistency with `ARCHITECTURE.md` and `raw_events` table.
        *   Documented `use_sqlalchemy` flag and dual sink implementations (`SQLAlchemyPostgresSink` and `PostgresSink`).
        *   Verified primary key information points to `ARCHITECTURE.md`.
    *   [x] **Review `timescaledb/prd.md`** (Completed: 2024-07-27)
        *   Ensured consistency with `ARCHITECTURE.md` (updated table name to `raw_events` and model to `RawEventORM`).
        *   Confirmed no changes needed regarding the dual sink mechanism as PRD focuses on DB requirements.
    *   [x] **Review `timescaledb_integration_guide.md`** (Completed: 2024-07-27)
        *   Verified that primary key and schema information correctly defers to `ARCHITECTURE.md`.
        *   Confirmed general consistency with `ARCHITECTURE.md` (table name, ORM model, Alembic schema management).


### Sentiment Analysis Service Implementation (Phase 1)
- **[x] Implement Phase 1: Project Setup & Foundation** (Added: 2025-06-05)
  - `[x]` Task 1.1: Create Service Directory Structure
  - `[x]` Task 1.2: Initialize Dependency Management
  - `[x]` Task 1.3: Basic Configuration Setup
  - `[x]` Task 1.4: Logging Setup

### Sentiment Analysis Service Implementation (Phase 2)
- **[x] Implement Phase 2: Database Integration & Models** (Added: 2025-06-05)
  - `[x]` Task 2.1: Define ORM Models & Pydantic DTOs (Verified complete based on existing models and memories)
  - `[x]` Task 2.2: Alembic Setup for Sentiment Tables (Verified complete based on existing migration and memories)
  - `[x]` Task 2.3: Database Connection Utility (Created `utils/db_session.py`)

### Discovered During Work

*   **Reddit Scraper Observability (from `reddit_scraper/todo.md` - Added: 2024-07-27):**
    *   Implement basic metrics (e.g., latest fetch age, error counters).
    *   Configure alerts based on these metrics (e.g., error thresholds, disk usage for CSVs).
*   **Reddit Scraper Future Features (from `reddit_scraper/todo.md` - Added: 2024-07-27):**
    *   Plan/Implement comment harvesting (as a new `event_type` for `raw_events`).
    *   Investigate Parquet migration for long-term cold storage of CSVs.
    *   Evaluate cloud storage (S3/GCS) for CSVs if local storage becomes a bottleneck.
*   **Review `reddit_scraper/todo_part2.md`**: Evaluate if its content should be merged into the main `TASK.md`, the `reddit_scraper/README.md`, `reddit_scraper/prd.md`, or archived if obsolete.
*   **Review `reddit_scraper/test_env.txt`**: Determine if this file should be kept as is, moved to an `.env.example` for the scraper, or if its contents are better suited for inclusion in `reddit_scraper/README.md` or testing documentation.

## Completed Tasks (Summary)
{{ ... }}
