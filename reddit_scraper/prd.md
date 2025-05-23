# Reddit Finance-Subreddits Scraper

## Product Requirements Document

### 1. Purpose

Build a Python 3.10+ tool that continuously harvests submission data (including self‐text) from key finance-oriented subreddits, stores it in a single CSV, and keeps the dataset current with minimal manual intervention. The dataset underpins downstream sentiment analysis and market-behaviour research.

### 2. Goals & Success Criteria

| Goal | Measurable Success |
|------|-------------------|
| Complete historical back-fill | 100% of available submissions retrieved for each target subreddit |
| Near-real-time updates | New posts captured within 10 minutes of Reddit appearance |
| Data integrity | < 0.1% duplicate rows; 0 missing mandatory fields |
| Reliability | < 0.5% runs aborted by unhandled exceptions over a rolling month |

### 3. Stakeholders

| Role | Interest |
|------|----------|
| Data Engineering (owner) | Implementation, maintenance |
| Quant/ML Analysts | Consume dataset for sentiment features |
| DevOps | Container deployment, monitoring |

### 4. In-Scope vs Out-of-Scope

| In-Scope | Out-of-Scope |
|----------|-------------|
| Reddit submissions (posts) | Comments (phase 2) |
| Seven finance subreddits | Any others unless added to config |
| TimescaleDB storage (primary) | Direct DB/Parquet sinks (future) |
| CSV storage (append-only, secondary) |  |

### 5. Target Subreddits

wallstreetbets, stocks, investing, StockMarket, options, finance, UKInvesting

### 6. Functional Requirements

#### 6.1 Configuration

- `.env` for OAuth creds
- `config.yaml` keys:
  ```yaml
  subreddits:
    - wallstreetbets
    ...
  window_days: 30      # historic search window
  timescaledb_uri: "postgresql://user:password@host:port/dbname"
  csv_path: data/reddit_finance.csv
  initial_backfill: true
  failure_threshold: 5
  maintenance_interval_sec: 600
  ```

#### 6.2 Authentication

- OAuth2 via asyncpraw
- Custom user_agent string: `finance_scraper/0.1 by <organisation>`

#### 6.3 Collection Logic

- Latest pass – `subreddit.new(limit=None)` until no unseen IDs returned.
- Historic loop – decrement time window (`window_days`) and query with CloudSearch syntax:
  `timestamp:{start}..{end} sort:new limit:1000`.
- Termination criteria – consecutive empty windows across all subreddits.
- Maintenance mode – every 10 min poll `.new()` only.

#### 6.4 Rate Limiting

- Parse `X-Ratelimit-Remaining` header.
- If remaining < 5 calls, `asyncio.sleep(reset + 2 s)`.
- Absolute ceiling: 100 requests min⁻¹.

#### 6.5 Error Handling

| Type | Action |
|------|--------|
| 5xx (<= failure_threshold) | Exponential back-off (1 → 32 s) and retry |
| 5xx (> threshold) | Abort run, log CRITICAL |
| 429 | Honour Retry-After, then resume |
| Others | Log WARNING, skip item |

#### 6.6 Data Model

| Column | Type | Notes |
|--------|------|-------|
| id | str | Reddit base36 ID |
| created_utc | int | Unix epoch |
| subreddit | str | lowercase |
| title | str | UTF-8 |
| selftext | str | May be empty |
| author | str | [deleted] allowed |
| score | int | Up-votes minus down-votes |
| upvote_ratio | float | 0–1 |
| num_comments | int | Snapshot at fetch |
| url | str | Submission URL |
| flair_text | str | Nullable |
| over_18 | bool | NSFW flag |

Primary key: (id).

#### 6.7 Storage

The scraper will implement a dual storage strategy:

1.  **Primary Storage: TimescaleDB Database**
    *   All successfully scraped and validated Reddit submissions (conforming to the `Submission` model) will be written to the project's TimescaleDB instance.
    *   This serves as the primary, authoritative data store for analysis and long-term retention.
    *   Database interactions will use SQLAlchemy, with connection parameters sourced from environment variables.
    *   Data ingestion must be idempotent (e.g., using `ON CONFLICT DO UPDATE` or `ON CONFLICT DO NOTHING` strategies) to prevent duplicates upon re-runs or overlaps.
    *   The scraper relies on an externally managed schema (via Alembic). It will not attempt to create or alter database tables.

2.  **Secondary Storage: CSV Files**
    *   In addition to TimescaleDB, all scraped data will also be appended to local CSV files.
    *   **Path**: `../data/raw/reddit_scraper/<subreddit_name>/<YYYY-MM-DD>.csv`
    *   **Format**: Standard CSV, with headers matching the `Submission` model fields.
    *   **Mode**: Append-only (`a+`).
    *   **Purpose**: Provides a local backup, facilitates quick data inspection, and ensures data capture resilience if the database is temporarily unavailable.
    *   The scraper will manage CSV file creation (including subdirectories if they don't exist) and appending data.
    *   On start-up, for CSV-specific deduplication (if any, beyond database idempotency), the scraper might load the first column (e.g., `id`) of existing CSVs for the current day into a `seen_ids` set to avoid re-writing identical records to the CSV. However, the primary mechanism for deduplication resides with the TimescaleDB ingestion logic.

#### 6.8 CLI / UX

```
python scrape.py --config config.yaml            # one-shot
python scrape.py --daemon --loglevel INFO        # loop forever
```

Flags: `--reset-backfill`, `--verbose`, `--since YYYY-MM-DD`.

### 7. Non-Functional Requirements

| Aspect | Requirement |
|--------|-------------|
| Performance | Initial back-fill < 72 h on 1 vCPU / 2 GB RAM |
| Reliability | Automatic restart via systemd/Docker health-check |
| Security | Never log tokens; .env excluded in .gitignore |
| Observability | Rotating scraper.log (10 MB × 5) + optional Prometheus endpoint |
| Maintainability | Black & Ruff formatting, typed with MyPy strict |

### 8. Deployment

- Dockerfile: slim Python base, non-root user.
- CI pipeline: lint, unit-tests, build image, push to registry.
- Runtime options:
  - Local cron
  - Kubernetes CronJob
  - systemd service (for `--daemon`)

### 9. Monitoring & Alerts

| Metric | Alert when |
|--------|------------|
| "consecutive_5xx" counter | ≥ failure_threshold |
| latest_fetch_age | > 20 min |
| disk_usage(csv) | > 90% quota |

### 10. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Reddit changes API limits | Scraper blocked | Abstract requester; make rate limit configurable |
| CSV size grows > 1 TB | Storage cost, slow analytics | Plan migration to Parquet + S3/Postgres |
| Pushshift becomes available again | Duplicate effort | Keep historic branch modular; swap data source easily |

### 11. Timeline (indicative)

| Week | Milestone |
|------|-----------|
| 1 | Code-base scaffold, config loader, env auth |
| 2 | Latest-post collector, CSV sink, dedupe |
| 3 | Historic window search, rate-limit handler |
| 4 | Docker & CI; manual back-fill dry-run |
| 5 | Maintenance loop, logging, Prometheus |
| 6 | Documentation, hand-off, production deploy |

### 12. Acceptance Tests

- End-to-end back-fill on test subreddit returns ≥ 99% of Pushshift-verified IDs.
- Rate-limit compliance: no minute with > 100 calls in logs.
- Recovery: kill network mid-run; scraper resumes without data loss.
- Dataset schema exactly matches Section 6.6 header order.
