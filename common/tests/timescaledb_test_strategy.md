# TimescaleDB Test Strategy

## Overview
This document provides a consolidated test strategy for TimescaleDB integration in the sentiment pipeline. It combines the approaches from the original TimescaleDB test implementation plan and the database integration test plan to create a comprehensive, non-redundant testing approach.

## Key Principles
1. **Schema Management**: All schema changes must be done via Alembic migrations
2. **Idempotency**: Writes must be idempotent to handle retries safely
3. **Consistency**: Data must be consistently formatted in the `raw_events` table
4. **Isolation**: Tests must not affect production data
5. **Efficiency**: Minimize redundancy while maintaining comprehensive coverage

> 🔄 = Partially implemented  
> ✅ = Immediate implementation  
> ⏳ = Future implementation  

## Test Structure and Organization

### Directory Structure
- **Common Test Components**:
  - Common fixtures: `/common/tests/conftest.py`
  - Database utilities: `/common/tests/db_utils.py`
  - Test data factories: `/common/tests/factories/`

- **Source-Specific Tests**:
  - Reddit tests: `/reddit_scraper/tests/storage/`
    - Unit tests: `/reddit_scraper/tests/storage/test_sqlalchemy_postgres_sink_unit.py`
    - Integration tests: `/reddit_scraper/tests/storage/test_sqlalchemy_postgres_sink_integration.py`
  - Future sources: In their respective directories

### Test Database Configuration (Integration Tests)
- **Technology**: Dockerized TimescaleDB (leveraging existing `docker-compose.yml` setup)
- **Isolation**: Each test session/module should use a clean, uniquely named database or schema
- **Schema Management**: Alembic for migrations to the test database

## Test Types and Priority

### ✅ 1. Unit Tests (`test_sqlalchemy_postgres_sink_unit.py`)

#### 1.1. High Priority: Data Transformation
- **Test Data Mapping** (`SubmissionRecord` to `RawEventORM`):
  - Verify correct mapping of fields (particularly `source_id`, `source`, `payload`)
  - Validate timestamp conversion (`created_utc` to `occurred_at`)
  - Ensure timezone-aware UTC datetime objects

#### 1.2. High Priority: Sink Operations
- **Test Batch Processing Logic**:
  - Verify batching works with various batch sizes
  - Ensure proper handling of empty record lists
- **Test Error Handling**:
  - Verify malformed records are skipped but don't break the batch
  - Ensure database errors trigger rollback

### ✅ 2. Integration Tests (`test_sqlalchemy_postgres_sink_integration.py`)

#### 2.1. High Priority: Database Operations
- **Test Single Record Write**:
  - Verify record exists with correct data
  - Validate auto-populated fields (`ingested_at`, `id`)
- **Test Idempotency**:
  - Verify duplicate records are handled correctly
  - Test `ON CONFLICT DO NOTHING` behavior
- **Test `load_ids()` Method**:
  - Verify correct retrieval of source IDs for 'reddit' source
  - Test chunked query behavior with large result sets
  - Verify only returns IDs where source is 'reddit'
  - Validate proper error handling for database issues

#### 2.2. Medium Priority: Schema Validation
- **Test Constraints**:
  - Verify NOT NULL constraints
  - Test unique constraints
- **Test Time-Based Partitioning**:
  - Verify records are stored in appropriate partitions

### ⏳ 3. Future Tests

#### 3.1. Performance Testing
- Test write throughput
- Test query performance
- Test under load conditions

#### 3.2. End-to-End Tests
- Test full scrape → transform → load pipeline
- Test error recovery and retries

## Test Fixtures (`conftest.py`)

### Essential Fixtures
- `test_db_url`: Connection URL for test database
- `db_engine`: SQLAlchemy engine connected to test TimescaleDB
- `db_session_factory`: Factory for SQLAlchemy sessions
- `db_session`: Clean test DB session with rollback after each test
- `initialize_test_db`: Setup fixture that:
  1. Creates test database
  2. Runs Alembic migrations
  3. Drops database after test session
- `sqlalchemy_postgres_sink`: Initialized sink instance for test DB

## Test Data Management

### Test Data Factories
- Factory for `RawEventORM`
- Source-specific data factories (Reddit, etc.)
- Edge case generators

## Implementation Order

1. **Setup Common Test Infrastructure**:
   - Create `/common/tests/conftest.py` with basic fixtures
   - Implement database setup utilities

2. **Implement High Priority Unit Tests**:
   - Data mapping tests
   - Batch processing tests
   - Error handling tests

3. **Implement High Priority Integration Tests**:
   - Single record write test
   - Idempotency test

4. **Implement Medium Priority Tests**:
   - Schema validation tests
   - Constraint tests

5. **Document Test Coverage**:
   - Update this document with test coverage decisions
   - Add notes to original test plans pointing to this consolidated strategy

## Reduced Test Set Rationale

This strategy reduces the number of tests from the original plans by:

1. **Eliminating Redundancy**:
   - Focusing unit tests on logic and integration tests on database interactions
   - Avoiding duplicate test cases between test types

2. **Prioritizing by Risk**:
   - Emphasizing tests for core functionality (data integrity, idempotency)
   - Deprioritizing edge cases with low probability

3. **Consolidating Similar Tests**:
   - Combining related test cases where appropriate
   - Using parameterized tests for similar scenarios

## Source-Specific Considerations

### Reddit Implementation
- Test PRAW data → `RawEventDTO` / `RawEventORM` conversion
- Test subreddit filtering
- Test comment tree traversal

### Future Sources
- Each new source should implement its own specific tests following this strategy
- Common test fixtures should be reused across sources

## Conclusion

This consolidated test strategy provides a balanced approach to testing TimescaleDB integration. It prioritizes critical functionality while reducing redundancy and maintaining a clear path for future expansion to additional data sources.
