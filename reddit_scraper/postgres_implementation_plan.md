**Postgres Implementation Plan**

This document outlines a step-by-step plan for integrating the scraper service with PostgreSQL while maintaining the existing CSV storage as a fallback.

---

## 1. Prerequisites

* **PostgreSQL instance** up and running (version >= 12).
* Network connectivity and credentials (host, port, database, user, password).
* Existing scraper service codebase (e.g. `scraper-service`).
* Library dependencies: `psycopg2` or `asyncpg` (for Python), or appropriate driver.
* Migration tool (e.g. Alembic, Flyway).

## 2. Define Database Schema

1. **Create `raw_events` table** with range partitioning on `occurred_at`:

   ```sql
   CREATE TABLE IF NOT EXISTS raw_events (
     id            BIGSERIAL     PRIMARY KEY,
     source        TEXT          NOT NULL,
     source_id     TEXT          NOT NULL UNIQUE,
     occurred_at   TIMESTAMPTZ   NOT NULL,
     payload       JSONB         NOT NULL,
     created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
     processed     BOOLEAN       NOT NULL DEFAULT FALSE
   ) PARTITION BY RANGE (occurred_at);
   ```

2. **Set up daily partitions** (one per calendar day):

   ```sql
   -- Example: partition for May 15, 2025
   CREATE TABLE IF NOT EXISTS raw_events_2025_05_15
     PARTITION OF raw_events
     FOR VALUES FROM ('2025-05-15') TO ('2025-05-16');
   ```

   * **Naming convention**: `raw_events_YYYY_MM_DD`
   * **Bounds**: start at midnight of the day, end at midnight of the next day.
   * **Automation**: schedule a daily job (e.g. at 00:05) to create the next day's partition.

3. **Indexes**:

   ```sql
   CREATE INDEX ON raw_events (source, occurred_at);
   CREATE INDEX ON raw_events USING GIN (payload);
   ```

4. **Migrations**: Add these DDL statements into versioned migration scripts (Alembic/Flyway).

5. **Initial cleanup** (optional): If you’re migrating over existing test data, clear out old tables before ingestion:

   ```sql
   TRUNCATE raw_events, sentiment_scores;
   ```

   Or, to drop and recreate from scratch:

   ```sql
   DROP TABLE IF EXISTS raw_events;
   DROP TABLE IF EXISTS sentiment_scores;
   -- then rerun migrations to recreate
   ```

## 3. Update Scraper Service

1. **Install DB driver** (e.g. in `requirements.txt`):

   ```text
   psycopg2-binary>=2.8
   ```
2. **Configuration**: Add new env vars:

   ```env
   PG_HOST=...      # e.g. marketdb.host
   PG_PORT=5432
   PG_DB=marketdb
   PG_USER=market_user
   PG_PASSWORD=...
   ```
3. **Connection utility** (`db.py`):

   ```python
   import os
   import psycopg2

   conn = psycopg2.connect(
     host=os.getenv("PG_HOST"),
     port=os.getenv("PG_PORT"),
     dbname=os.getenv("PG_DB"),
     user=os.getenv("PG_USER"),
     password=os.getenv("PG_PASSWORD")
   )
   conn.autocommit = True
   ```

## 4. Implement Dual Write Logic

1. **Abstract writer interface**:

   ```python
   class StorageWriter:
       def write(self, record: dict):
           raise NotImplementedError

   class CSVWriter(StorageWriter):
       def write(self, record):
           # existing CSV logic

   class PostgresWriter(StorageWriter):
       def write(self, record):
           with conn.cursor() as cur:
               cur.execute(
                   """
                   INSERT INTO raw_events (source, source_id, occurred_at, payload)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (source_id) DO NOTHING
                   """,
                   (
                     record['source'],
                     record['id'],
                     record['timestamp'],
                     json.dumps(record)
                   )
               )
   ```

2. **Compose writers** in main pipeline:

   ```python
   writers = [CSVWriter(), PostgresWriter()]
   for record in fetch_records():
       for w in writers:
           w.write(record)
   ```

## 5. Error Handling & Retries

* Wrap Postgres writes in try/except:

  ```python
  try:
      PostgresWriter().write(record)
  except Exception as e:
      logger.error(f"Postgres write failed: {e}")
      # continue to CSV; optionally enqueue for retry
  ```
* Optionally implement a retry queue (Redis/RabbitMQ) for failed DB writes.

## 6. Testing & Validation

1. **Unit tests**:

   * Mock DB connection to assert SQL executed.
   * Test CSVWriter unchanged behavior.
2. **Integration tests**:

   * Spin up a temporary Postgres container (e.g. via pytest-postgresql).
   * Run scraper against sample data; assert rows in `raw_events`.
3. **Data validation**:

   * Verify JSON schema in `payload`.
   * Spot-check timestamp consistency.

## 7. Deployment

1. **CI/CD pipeline**:

   * Include DB migration step before deployment.
   * Add liveness check: scrape → insert → confirm in DB.
2. **Rollout**:

   * Deploy to staging; run smoke tests.
   * Monitor for errors, then deploy to production.

## 8. Monitoring & Observability

* **Metrics**:

  * Count of records ingested per source (Prometheus gauge).
  * DB write failures.
* **Logs**:

  * Structured logs with `source` and `source_id`.
* **Alerts**:

  * Trigger if write-failure rate > 1% over 5 minutes.

---

By following this plan with daily partitions, you’ll get fine-grained retention and fast, low-volume queries for each day—while still automating partition management easily.
