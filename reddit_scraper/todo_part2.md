# Reddit Scraper - Phase 2 Tasks

This document outlines the next set of tasks following the initial development and testing.

## 1. Implement Pagination for Targeted Scraper Searches

**Goal:** Enhance the `TargetedHistoricalScraper` to retrieve more than the default 100 posts per search query, up to the Reddit API's search limit (~1000).

**Steps:**

-   [ ] **Modify Search Utilities (`scraper_utils.py`):**
    -   [ ] Update `search_by_term` and `search_by_date_range` functions (or the underlying `collector._search_submissions` method they call).
    -   [ ] Implement a loop to handle pagination using PRAW's `after` parameter.
    -   [ ] Continue fetching batches (`limit=100`) as long as the previous batch returned 100 results.
    -   [ ] Stop the loop when a batch returns < 100 results or if a maximum number of pages/results (e.g., ~10 pages / 1000 results) is reached to respect Reddit's likely search cap.
    -   [ ] Accumulate results from all pages for a single search query before returning.
-   [ ] **Rate Limiting:**
    -   [ ] Add appropriate `asyncio.sleep()` delays between paginated API calls within the loop to avoid hitting rate limits.
-   [ ] **Testing:**
    -   [ ] Test with specific subreddits and search terms known to have > 100 results.
    -   [ ] Verify that more than 100 results are collected when available.
    -   [ ] Observe behavior when the ~1000 result limit is likely hit.
-   [ ] **Documentation:**
    -   [ ] Add comments explaining the pagination logic.
    -   [ ] Document the ~1000 result limitation imposed by the Reddit search API in the code or README.

## 2. Implement PostgreSQL Database Sink

**Goal:** Replace the `CsvSink` with a `PostgresSink` to store scraped data in a PostgreSQL database for better scalability, querying, and data management.

**Steps:**

-   [ ] **Dependency:**
    -   [ ] Choose a suitable PostgreSQL library (e.g., `asyncpg` for asyncio compatibility).
    -   [ ] Add the chosen library to `requirements.txt`.
-   [ ] **Database Schema:**
    -   [ ] Design a SQL schema for a `submissions` table (columns should match `SubmissionRecord` fields).
    -   [ ] Define appropriate data types, constraints (e.g., `submission_id` as primary key or unique constraint).
    -   [ ] Create an SQL script (`schema.sql`?) to initialize the table.
-   [ ] **Create `PostgresSink`:**
    -   [ ] Create `reddit_scraper/storage/postgres_sink.py`.
    -   [ ] Implement a `PostgresSink` class with an `async def store(self, records: List[SubmissionRecord])` method.
    -   [ ] Implement connection handling (connection pool recommended).
    -   [ ] Implement logic to insert records into the `submissions` table (e.g., using `INSERT ... ON CONFLICT DO NOTHING` based on `submission_id` to handle duplicates).
-   [ ] **Configuration:**
    -   [ ] Add PostgreSQL connection details (host, port, user, password, database name) to `config.yaml` or `.env`. Ensure `.env` is gitignored.
    -   [ ] Update `BaseScraper` or `cli.py` to conditionally instantiate `PostgresSink` based on configuration (e.g., a `storage_type: postgres` setting in `config.yaml`).
-   [ ] **Integration:**
    -   [ ] Modify `BaseScraper` to use the configured sink instance.
-   [ ] **Data Migration (Optional):**
    -   [ ] Create a one-time script (`migrate_csv_to_postgres.py`?) to load data from the existing `data/reddit_finance.csv` into the PostgreSQL database.
-   [ ] **Documentation:**
    -   [ ] Update `README.md` with instructions for setting up PostgreSQL, configuring the connection, and initializing the schema.

## 3. Create Docker Image

**Goal:** Containerize the Reddit Scraper application for consistent deployment and dependency management.

**Steps:**

-   [ ] **Create `Dockerfile`:**
    -   [ ] Choose an appropriate Python base image (e.g., `python:3.10-slim`).
    -   [ ] Set the working directory (e.g., `/app`).
    -   [ ] Copy `requirements.txt`.
    -   [ ] Install dependencies using `pip install --no-cache-dir -r requirements.txt`.
    -   [ ] Copy the application code (`reddit_scraper` directory, `cli.py`, etc.).
    -   [ ] Define the `ENTRYPOINT` or `CMD` to run the scraper via `python -m reddit_scraper.cli scraper ...`. Consider parameterizing the scraper type/config path.
-   [ ] **Create `.dockerignore`:**
    -   [ ] Add entries to exclude `.git`, `.vscode`, `__pycache__`, `*.pyc`, `logs/`, `data/`, `.env`, `venv/`, etc. to keep the image small and clean.
-   [ ] **Build & Test:**
    -   [ ] Build the image using `docker build -t reddit-scraper:latest .`.
    -   [ ] Test running the scraper within a container.
    -   [ ] Verify logs and data output (if applicable during testing).
-   [ ] **Configuration/Secrets Handling:**
    -   [ ] Determine the strategy for providing `config.yaml` and `.env` to the container (e.g., volume mounts, Docker secrets, environment variables passed at runtime). Update `docker-compose.yml` if used.
-   [ ] **Documentation:**
    -   [ ] Update `README.md` with instructions on how to build the Docker image and run the scraper using Docker (including configuration handling).
