# Test Implementation Plan: Scraper Database Interaction

**Objective:** Ensure the reliability, correctness, and idempotency of the `SQLAlchemyPostgresSink` when writing Reddit data to the `raw_events` table in TimescaleDB.

**Testing Framework:** Pytest

## 1. Test Environment & Setup

### 1.1. Directory Structure
-   Tests will reside in `reddit_scraper/tests/`.
-   Database interaction tests for sinks: `reddit_scraper/tests/storage/`.
    -   Unit tests: `reddit_scraper/tests/storage/test_sqlalchemy_postgres_sink_unit.py`
    -   Integration tests: `reddit_scraper/tests/storage/test_sqlalchemy_postgres_sink_integration.py`
-   Fixtures: `reddit_scraper/tests/storage/conftest.py` (preferred for storage-specific fixtures) or `reddit_scraper/tests/conftest.py` (for general fixtures).

### 1.2. Test Database (Integration Tests)
-   **Technology:** Dockerized TimescaleDB (leveraging existing `docker-compose.yml` setup, possibly with a dedicated test service or by managing test database creation/deletion within the existing service).
-   **Isolation:** Each test session/module should ideally use a clean, uniquely named database or schema. Alternatively, ensure thorough data cleanup between tests if using a shared test database.
-   **Schema Management:** Alembic will be used to apply migrations (`alembic -c alembic.ini upgrade head`) to the test database before tests run. The `alembic.ini` might need a separate section or dynamic configuration for the test database URL.

### 1.3. `conftest.py` Fixtures (Integration Tests)
-   `test_db_url`: Fixture providing the connection URL for the temporary test database.
-   `db_engine`: SQLAlchemy engine connected to the test TimescaleDB (scoped appropriately, e.g., session or module).
-   `db_session_factory`: A factory to create SQLAlchemy sessions for tests, bound to the `db_engine`.
-   `db_session`: A function-scoped fixture providing a clean test DB session that rolls back changes after each test.
-   `initialize_test_db`: Session-scoped fixture that:
    1.  Creates the test database (if not handled by Docker service config).
    2.  Runs Alembic migrations to set up the schema.
    3.  Yields.
    4.  Drops the test database after the test session.
-   `sqlalchemy_postgres_sink`: Fixture providing an initialized `SQLAlchemyPostgresSink` instance configured for the test DB.

## 2. Critical Prerequisite: Clarify `SubmissionRecord['created_utc']` Type

-   **Issue:** `SQLAlchemyPostgresSink` uses `datetime.fromtimestamp(record['created_utc'], tz=timezone.utc)`, implying `created_utc` in the input `actual_record_data` (derived from `SubmissionRecord`) is a numeric timestamp. However, the `SubmissionRecord` TypedDict defines `created_utc: datetime`.
-   **Action (First Implementation Step):**
    1.  Investigate the actual data type of `created_utc` being passed to the sink. This involves tracing how `SubmissionRecord` instances are created from PRAW objects.
    2.  If `PRAW.Submission.created_utc` (which is a float timestamp) is directly assigned or converted to `SubmissionRecord['created_utc']` as a float: The sink's current logic is fine, but the `SubmissionRecord` TypedDict `created_utc: datetime` is misleading and should be `created_utc: float`.
    3.  If `PRAW.Submission.created_utc` is converted to a `datetime` object *before* or *during* `SubmissionRecord` instantiation: The `SubmissionRecord` TypedDict is correct, but the sink's `datetime.fromtimestamp()` call is wrong and should be adjusted to handle a `datetime` object (e.g., ensure it's UTC-aware).
    4.  **Goal:** Ensure consistency. The `SubmissionRecord` type hint and the sink's expectation for `created_utc` must align.
-   **Tests will be written assuming this is resolved, with `RawEventORM.occurred_at` being correctly populated.**

## 3. Unit Tests (`test_sqlalchemy_postgres_sink_unit.py`)

**Goal:** Test `SQLAlchemyPostgresSink` logic in isolation, mocking database interactions.

### 3.1. Mocking Strategy
-   Mock `reddit_scraper.storage.sqlalchemy_postgres_sink.get_db` to return a mock session object (`unittest.mock.MagicMock`).
-   The mock session will allow asserting calls like `execute()`, `commit()`, `rollback()`.

### 3.2. Test Cases
1.  **Test Data Mapping (`SubmissionRecord` to `RawEventORM`):**
    -   Input: Sample `SubmissionRecord` (TypedDict), ensuring `created_utc` type matches the resolution from Section 2.
    -   Action: Call `sink.append()` with the sample.
    -   Assert:
        -   The mock session's `execute()` method was called with an `sqlalchemy.dialects.postgresql.insert` statement.
        -   The values within the insert statement correctly map:
            -   `source` = "reddit"
            -   `source_id` = `record['id']`
            -   `occurred_at` = correctly converted from `record['created_utc']` (must be a timezone-aware UTC `datetime` object).
            -   `payload` = the original `record` dictionary.
2.  **Test Handling of Malformed `SubmissionRecord` (KeyError):**
    -   Input: `SubmissionRecord` missing a required key (e.g., 'id').
    -   Action: Call `sink.append()`.
    -   Assert: Error is logged; malformed record is skipped; other valid records in a batch are processed.
3.  **Test Handling of Empty Record List:**
    -   Input: Empty list `[]`.
    -   Action: Call `sink.append()`.
    -   Assert: No database operations attempted; returns 0.
4.  **Test Batching Logic:**
    -   Input: List of records > `batch_size` (e.g., 105 if `batch_size` is 100).
    -   Action: Call `sink.append()`.
    -   Assert: Mock session's `execute()` and `commit()` are called appropriately for each batch (e.g., twice: once for 100, once for 5).
5.  **Test Database Error During Insert (Simulated):**
    -   Setup: Mock session's `execute()` to raise `sqlalchemy.exc.SQLAlchemyError`.
    -   Action: Call `sink.append()` with valid records.
    -   Assert: `db.rollback()` is called; error is logged; sink returns 0 or appropriate error indicator.

## 4. Integration Tests (`test_sqlalchemy_postgres_sink_integration.py`)

**Goal:** Test `SQLAlchemyPostgresSink` interaction with a live (test) TimescaleDB.
**Prerequisite:** All tests use fixtures that ensure a clean, migrated database schema.

### 4.1. Test Cases
1.  **Test Successful Single Record Write:**
    -   Input: One valid `SubmissionRecord`.
    -   Action: Call `sink.append()`.
    -   Assert: Record exists in `raw_events` with correct data; `ingested_at` populated; `processed` is `false`; `id` (auto-incrementing PK) populated.
2.  **Test Successful Batch Record Write:**
    -   Input: Multiple valid `SubmissionRecord`s.
    -   Action: Call `sink.append()`.
    -   Assert: All records exist in `raw_events` with correct data.
3.  **Test Idempotency (Unique Constraint: `source`, `source_id`, `occurred_at`):**
    -   Action: Write a record. Write the exact same record again. Write a record with same unique fields but different payload.
    -   Assert: Only one instance (based on unique fields) exists. `ON CONFLICT DO NOTHING` prevents duplicates/errors.
4.  **Test NOT NULL Constraints:**
    -   Input: `SubmissionRecord` that would make `RawEventORM.source_id` (or other non-nullable fields like `payload`, `source`) `None`.
    -   Action: Call `sink.append()`.
    -   Assert: Database (or SQLAlchemy) raises `IntegrityError`; transaction rolled back.
5.  **Test Timestamp and Timezone Handling (`occurred_at`):**
    -   Input: `SubmissionRecord`s with `created_utc` values (type resolved from Section 2).
    -   Action: Call `sink.append()`.
    -   Assert: `occurred_at` stored and retrieved correctly as timezone-aware UTC `datetime`.
6.  **Test `load_ids()` Method:**
    -   Setup: Insert records with `source='reddit'` and `source='other_source'`.
    -   Action: Call `sink.load_ids()`.
    -   Assert: Returns set of `source_id`s only for `source='reddit'`.

## 5. Implementation Order (Initial Steps)

1.  **Create `tests_implementation_plan.md` (This document).** (Completed)
2.  **Resolve `SubmissionRecord['created_utc']` Type Ambiguity (as per Section 2).** This is the **first coding task**.
3.  **Setup Test Directory Structure and Basic `conftest.py`:**
    -   Create `reddit_scraper/tests/storage/`.
    -   Create `reddit_scraper/tests/storage/conftest.py`.
    -   Implement basic Dockerized DB setup fixture and Alembic integration in `conftest.py`.
4.  **Implement First Unit Test:** Start with data mapping (Section 3.2.1), particularly focusing on the `created_utc` conversion.
5.  **Implement First Integration Test:** Start with successful single record write (Section 4.1.1), ensuring Alembic schema setup works reliably in fixtures.

## 6. Out of Scope for this Plan

-   Tests for the legacy `PostgresSink` (direct `psycopg2`), unless it's decided to update and maintain it.
-   UI or end-to-end tests for the scraper application.
