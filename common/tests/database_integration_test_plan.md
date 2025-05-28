# Database Integration Test Plan

## Overview
This document outlines the testing strategy for database integration across different data sources (Reddit, Twitter, etc.). The goal is to ensure consistent behavior and data quality while allowing for source-specific implementations.

## Key Principles
1. **Schema Management**: All schema changes must be done via Alembic migrations
2. **Idempotency**: Writes must be idempotent to handle retries safely
3. **Consistency**: Data must be consistently formatted in the `raw_events` table
4. **Isolation**: Tests must not affect production data

> 🔄 = Partially implemented  
> ✅ = Immediate implementation  
> ⏳ = Future implementation  

## ✅ Test Structure

### ✅ 1. Unit Tests (`test_sqlalchemy_postgres_sink_unit.py`)

#### 1.1. Test Data Transformation
- **Input**: Raw data from source API (Reddit, etc.)
- **Output**: `RawEventORM` instance
- **Test Cases**:
  -  Map source data to `RawEventORM` fields
  -  Handle missing optional fields
  -  Convert timestamps to timezone-aware UTC
  -  Handle special characters in text fields
  -  Validate required fields
  -  Handle edge cases (empty data, null values)

#### 1.2. Test Sink Operations
- ✅ Test batch operations
- ✅ Test idempotent writes
- ✅ Test error handling (database errors, timeouts)
- ✅ Test transaction management

### 🔄 2. Integration Tests (`test_sqlalchemy_postgres_sink_integration.py`)

#### 2.1. Database Operations
- ✅ Test insert single record
- ✅ Test batch insert
- ✅ Test duplicate handling (idempotency)
- ✅ Test transaction rollback on error
- ✅ Test with real database connection

#### 2.2. Schema Validation
- ✅ Verify table structure matches ORM
- ✅ Test constraints (NOT NULL, unique)
- ✅ Test indexes are used in queries
- ✅ Test time-based partitioning works

### ⏳ 3. End-to-End Tests (Future Phase)
- Test full scrape → transform → load pipeline
- Test error recovery and retries
- Test monitoring and alerting
- Test with production-like data volume

## 🔄 Test Data Management

### Test Data Factories
- ✅ Factory for `RawEventORM`
- ✅ Factory for source-specific data (Reddit, etc.)
- ✅ Edge case generators
- ⏳ Performance test data generation

### Test Database Setup
- ✅ In-memory SQLite for unit tests
- ✅ Dockerized TimescaleDB for integration tests
- ✅ Database reset between tests
- ⏳ Performance test database

## Source-Specific Tests

### ✅ Reddit Implementation
- Test PRAW data → `RawEventDTO` / `RawEventORM` conversion
- Test rate limit handling
- Test subreddit filtering
- Test comment tree traversal (as an example of source-specific event processing logic for comment events)

### ⏳ Future Sources
- Twitter API integration
- Other social media platforms
- Custom data sources

## ⏳ Performance Testing (Future Phase)
- Test write throughput
- Test query performance
- Test under load
- Monitor resource usage

## ⏳ Security Testing (Future Phase)
- Test API key rotation
- Test data encryption
- Test access controls
- Audit logging

## 🔄 Test Automation
- ✅ pytest framework
- ✅ GitHub Actions for CI
- ⏳ Test result reporting
- ⏳ Code coverage tracking

## Implementation Guidelines
1. **Fixtures**: Use `conftest.py` for shared fixtures
2. **Isolation**: Each test should be independent
3. **Idempotency**: Tests should be rerunnable
4. **Documentation**: Document test cases and assumptions
