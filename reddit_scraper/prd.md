# Reddit Finance-Subreddits Scraper

## Product Requirements Document

### 1. Purpose

Build a Python 3.10+ tool that continuously harvests submission data (including self‐text) from key finance-oriented subreddits. The data is ingested as `RawEventDTO` objects and stored primarily in a TimescaleDB `raw_events` table (using `RawEventORM`) and secondarily in local CSV files. This dataset underpins downstream sentiment analysis and market-behaviour research.

### 2. Goals & Success Criteria

| Goal | Measurable Success |
|------|-------------------|
| Complete historical back-fill | 100% of available submissions (as `raw_events`) retrieved for each target subreddit |
| Near-real-time updates | New posts captured as `raw_events` within 10 minutes of Reddit appearance |
| Data integrity | < 0.1% duplicate `raw_events` in TimescaleDB; 0 missing mandatory `RawEventORM` fields |
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
| Reddit submissions (posts) ingested as `raw_events` with `event_type = "reddit_submission"` | Comments (can be added as a new `event_type` using the same `raw_events` infrastructure, but not part of initial Reddit scraper scope) |
| Seven finance subreddits | Any others unless added to config |
| TimescaleDB storage for `raw_events` (primary) | Direct DB/Parquet sinks for other raw data (future) |
| CSV storage of `RawEventDTOs` (append-only, secondary) |  |

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
  # window_days: 30      # historic search window (managed by CLI --since/--until or default lookback)
  csv_path_root: data/raw/reddit_scraper # Root directory for CSVs, actual files are <subreddit_name>/<YYYY-MM-DD>.csv
  initial_backfill: true
  failure_threshold: 5
  maintenance_interval_sec: 600
  # TimescaleDB connection details are sourced from environment variables (PG_HOST, PG_USER, etc.)
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

The primary data model for storage in TimescaleDB is `RawEventORM`, as defined in `ARCHITECTURE.md`. For Reddit submissions, the `data` field of `RawEventORM` will contain the original submission details.

| `RawEventORM` Field | Type         | Notes                                                                 |
|---------------------|--------------|-----------------------------------------------------------------------|
| `event_id`          | `UUID`       | Primary Key, auto-generated.                                            |
| `event_type`        | `String`     | E.g., "reddit_submission".                                              |
| `source`            | `String`     | E.g., "reddit".                                                       |
| `source_event_id`   | `String`     | Original Reddit submission ID (e.g., base36 ID like "t3_xxxxxx").       |
| `occurred_at`       | `DateTime`   | Timestamp of the event (submission creation time). Partitioning key.    |
| `recorded_at`       | `DateTime`   | Timestamp when the event was recorded by the system. Auto-set.          |
| `data`              | `JSONB`      | Original Reddit submission data (title, selftext, author, score, etc.). |
| `metadata`          | `JSONB`      | Additional metadata (e.g., scraper version, processing notes). Nullable.|

**Unique Constraint:** `(source, source_event_id, event_type)` ensures idempotency.

**Original Submission Fields (within `data` JSONB):**

| Original Field | Type    | Notes                   |
|----------------|---------|-------------------------|
| id             | str     | Reddit base36 ID        |
| created_utc    | int     | Unix epoch              |
| subreddit      | str     | lowercase               |
| title          | str     | UTF-8                   |
| selftext       | str     | May be empty            |
| author         | str     | `[deleted]` allowed     |
| score          | int     | Up-votes minus down-votes |
| upvote_ratio   | float   | 0–1                     |
| num_comments   | int     | Snapshot at fetch       |
| url            | str     | Submission URL          |
| flair_text     | str     | Nullable                |
| over_18        | bool    | NSFW flag               |

#### 6.7 Storage

The scraper will implement a dual storage strategy as outlined in `ARCHITECTURE.md` and `scraper_implementation_rule.md`:

1.  **Primary Storage: TimescaleDB Database (`raw_events` table)**
    *   All successfully scraped Reddit submissions are transformed into `RawEventDTO` objects and then persisted as `RawEventORM` records in the `raw_events` table.
    *   This serves as the primary, authoritative data store for analysis and long-term retention.
    *   Database interactions use SQLAlchemy with the `SQLAlchemyPostgresSink`.
    *   Connection parameters are sourced from environment variables (e.g., `PG_HOST`, `PG_USER`, `PG_DB`, `PG_PASSWORD`, `PG_PORT`).
    *   Data ingestion is idempotent due to the unique constraint on `(source, source_event_id, event_type)` in the `raw_events` table.
    *   The scraper relies on an externally managed schema (via Alembic). It will not attempt to create or alter database tables.

2.  **Secondary Storage: CSV Files**
    *   In addition to TimescaleDB, all scraped `RawEventDTOs` will also be appended to local CSV files.
    *   **Path**: `data/raw/reddit_scraper/<subreddit_name>/<YYYY-MM-DD>.csv` (relative to project root, configurable via `csv_path_root` in `config.yaml`).
    *   **Format**: Standard CSV. Each row represents a `RawEventDTO`. The `data` field of the DTO (containing the original submission) will be stored as a JSON string within a CSV column. Other `RawEventDTO` fields (`event_id`, `event_type`, `source`, `source_event_id`, `occurred_at`, `metadata`) will be distinct columns.
    *   **Mode**: Append-only (`a+`).
    *   **Purpose**: Provides a local backup, facilitates quick data inspection, and ensures data capture resilience if the database is temporarily unavailable.
    *   The scraper will manage CSV file creation (including subdirectories if they don't exist) and appending data.
    *   Primary deduplication is handled at the database level. CSVs are a raw log of DTOs processed.

#### 6.8 CLI / UX

```bash
python -m reddit_scraper.cli scrape --config config.yaml            # one-shot backfill based on config or default lookback
python -m reddit_scraper.cli scrape --config config.yaml --daemon --loglevel INFO # continuous monitoring
```

Flags (examples, refer to `reddit_scraper/README.md` for full list): `--since YYYY-MM-DD`, `--until YYYY-MM-DD`.

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
| CSV size grows > 1 TB | Storage cost, slow analytics | Implement log rotation/archival for CSVs; primary store is TimescaleDB. Consider Parquet for long-term cold CSV storage if needed. |
| ~~Pushshift becomes available again~~ | ~~Duplicate effort~~ | ~~Keep historic branch modular; swap data source easily~~ (Pushshift is no longer a primary consideration for real-time/recent data) |

### 11. Timeline (indicative)

*(This timeline is historical and for reference only. Current tasks are tracked in `TASK.md`.)*

| Week | Milestone |
|------|-----------|
| 1 | Code-base scaffold, config loader, env auth |
| 2 | Latest-post collector, CSV sink, dedupe |
| 3 | Historic window search, rate-limit handler |
| 4 | Docker & CI; manual back-fill dry-run |
| 5 | Maintenance loop, logging, Prometheus |
| 6 | Documentation, hand-off, production deploy |

### 12. Acceptance Tests

- End-to-end back-fill on test subreddit populates `raw_events` table with expected submissions.
- Rate-limit compliance: no minute with > 100 calls in logs (or as configured).
- Recovery: kill network mid-run; scraper resumes without data loss in `raw_events` (due to idempotency) and continues CSV logging.
- `raw_events` table schema in TimescaleDB matches `RawEventORM` structure defined in `ARCHITECTURE.md`.
- CSV files contain `RawEventDTO` data, with the `data` payload as a JSON string.
