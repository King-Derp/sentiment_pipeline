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

## Current / Next Tasks

- **Verify no writes to `raw_submissions` and update downstream consumers** (Added: YYYY-MM-DD)
  - Confirm no active code paths attempt to write to the (now dropped) `raw_submissions` table.
  - Identify and update any downstream processes or queries that previously read from `raw_submissions` to use `raw_events`.
  - Plan for removal of any remaining `SubmissionORM` definitions or related old code if no longer needed.
