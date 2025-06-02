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

## Docker Test Environment for Integration Tests

### Overview
A dedicated Docker environment for TimescaleDB integration tests ensures consistent, reproducible test results across development environments while maintaining isolation from production databases.

### Docker Test Environment Architecture

#### Components
1. **Test TimescaleDB Container**:
   - Based on the same `timescale/timescaledb:latest-pg15-oss` image used in production
   - Configured with a dedicated test database
   - Ephemeral storage (data is not persisted between test runs)
   - Exposed on a different port to avoid conflicts with development instances

2. **Test Network**:
   - Isolated Docker network for test containers
   - Prevents interference with other running containers

3. **Test Runner**:
   - Python test environment with pytest
   - Connects to the test TimescaleDB instance
   - Executes Alembic migrations before tests
   - Cleans up after tests complete

### Docker Compose Configuration for Tests

```yaml
# docker-compose.test.yml
services:
  timescaledb_test:
    image: timescale/timescaledb:latest-pg15-oss
    container_name: timescaledb_test_service
    ports:
      - "${TEST_PG_PORT_HOST:-5434}:5432"
    environment:
      POSTGRES_USER: ${TEST_PG_USER:-test_user}
      POSTGRES_PASSWORD: ${TEST_PG_PASSWORD:-test_password}
      POSTGRES_DB: ${TEST_PG_DB:-sentiment_pipeline_test_db}
    tmpfs:
      - /var/lib/postgresql/data  # Use tmpfs for ephemeral storage
    networks:
      - test_net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${TEST_PG_USER:-test_user} -d ${TEST_PG_DB:-sentiment_pipeline_test_db} -h localhost -p 5432"]
      interval: 5s
      timeout: 3s
      retries: 5
      start_period: 5s

networks:
  test_net:
    driver: bridge
```

### Test Environment Variables

Create a dedicated `.env.test` file with test-specific configuration:

```
# Test database configuration
TEST_PG_USER=test_user
TEST_PG_PASSWORD=test_password
TEST_PG_DB=sentiment_pipeline_test_db
TEST_PG_PORT_HOST=5434
TEST_PG_PORT_CONTAINER=5432
TEST_DATABASE_URL=postgresql://test_user:test_password@localhost:5434/sentiment_pipeline_test_db
```

### Test Execution Workflow

Two PowerShell scripts have been implemented to automate the test execution workflow:

#### Option 1: Full Lifecycle Management (Recommended for CI/CD)

Use `run_docker_tests.ps1` to handle the complete test lifecycle:

```powershell
# Run all tests in the current directory
.\run_docker_tests.ps1

# Run specific tests
.\run_docker_tests.ps1 test_specific_file.py
```

This script:
1. Loads environment variables from `.env.test`
2. Starts the Docker test environment using `docker-compose.test.yml`
3. Waits for the database to be healthy using the container's healthcheck
4. Runs Alembic migrations to set up the schema
5. Executes pytest with the specified test target
6. Shuts down the Docker environment after tests complete

#### Option 2: Development Workflow (For Rapid Iteration)

Use `run_tests.ps1` when you want to run tests against an already running environment:

```powershell
# Run all tests in the current directory
.\run_tests.ps1

# Run specific tests
.\run_tests.ps1 test_specific_file.py

# Run tests and shut down the environment after completion
.\run_tests.ps1 -ShutdownAfter
```

This script:
1. Checks if the TimescaleDB test container is running
2. If not running, it calls `run_docker_tests.ps1` to start the environment
3. If running, it loads environment variables and runs the tests
4. With the `-ShutdownAfter` flag, it will shut down the test environment after tests complete

Both scripts ensure proper environment variable configuration and test execution.

### Integration with CI/CD

For continuous integration, use the `run_docker_tests.ps1` script which handles the complete test lifecycle:

```powershell
# In CI/CD pipeline
.\run_docker_tests.ps1
```

This script is designed to be self-contained and will:

1. Start a clean test environment
2. Run all tests
3. Properly clean up resources
4. Return appropriate exit codes for CI/CD pipeline status

The script can be integrated into any CI/CD system that supports PowerShell execution.

### Implemented Test Helper Scripts

The following PowerShell scripts have been implemented to simplify test execution:

1. **`run_docker_tests.ps1`**:
   ```powershell
   # Run all tests with full lifecycle management
   .\run_docker_tests.ps1
   
   # Run specific test file
   .\run_docker_tests.ps1 test_specific_file.py
   ```
   - Handles the complete test lifecycle (start → test → shutdown)
   - Ideal for CI/CD or one-off test runs
   - Loads environment variables from `.env.test`
   - Starts the Docker test environment
   - Waits for the database to become healthy
   - Runs Alembic migrations
   - Executes pytest with the specified test target
   - Shuts down the Docker environment after tests complete
   - Returns the pytest exit code for proper CI/CD integration

2. **`run_tests.ps1`**:
   ```powershell
   # Run all tests against an existing environment
   .\run_tests.ps1
   
   # Run specific test file
   .\run_tests.ps1 test_specific_file.py
   
   # Run tests and shut down the environment after completion
   .\run_tests.ps1 -ShutdownAfter
   ```
   - Designed for development workflow when iterating quickly
   - Checks if TimescaleDB test container is running
   - If container is not running, calls `run_docker_tests.ps1`
   - If container is running, runs tests against it
   - With `-ShutdownAfter` flag, shuts down the environment after tests
   - Loads environment variables from `.env.test`
   - Returns the pytest exit code

### Common Test Fixtures

Update `/common/tests/conftest.py` to support the Docker test environment:

```python
@pytest.fixture(scope="session")
def docker_test_db_url():
    """Returns the database URL for the Docker test environment."""
    return os.environ.get(
        "TEST_DATABASE_URL", 
        "postgresql://test_user:test_password@localhost:5434/sentiment_pipeline_test_db"
    )

@pytest.fixture(scope="session")
def docker_db_engine(docker_test_db_url):
    """Creates a SQLAlchemy engine connected to the Docker test database."""
    engine = create_engine(docker_test_db_url)
    yield engine
    engine.dispose()
```

## Implementation Order

1. **Setup Docker Test Environment**:
   - Create `docker-compose.test.yml`
   - Create `.env.test` file
   - Implement test helper scripts

2. **Setup Common Test Infrastructure**:
   - Create `/common/tests/conftest.py` with Docker-aware fixtures
   - Implement database setup utilities

3. **Implement High Priority Unit Tests**:
   - Data mapping tests
   - Batch processing tests
   - Error handling tests

4. **Implement High Priority Integration Tests**:
   - Single record write test
   - Idempotency test

5. **Implement Medium Priority Tests**:
   - Schema validation tests
   - Constraint tests

6. **Document Test Coverage**:
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

This consolidated test strategy provides a balanced approach to testing TimescaleDB integration. It prioritizes critical functionality while reducing redundancy and maintaining a clear path for future expansion to additional data sources. The Docker test environment ensures tests are reproducible across development environments and CI/CD pipelines, providing consistent and reliable test results while maintaining isolation from development and production databases.
