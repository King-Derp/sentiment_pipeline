# Gap Detection and Filling Implementation Plan

This document outlines the step-by-step plan to implement a systematic process for detecting and filling data gaps in the `reddit_scraper` service. The goal is to ensure data completeness by leveraging the existing `PushshiftHistoricalScraper` and the TimescaleDB database.

---

## Phase 1: Implement the Gap Detection Command

**Objective:** Create a robust CLI command to identify all time gaps greater than 10 minutes directly from the TimescaleDB `submissions` table.

**Tasks:**

1.  **Modify `reddit_scraper/reddit_scraper/cli_db.py`:**
    *   Add a new Typer command named `find-gaps`.
    *   This command will establish a connection to the PostgreSQL database using the existing `get_connection` utility.
    *   It will execute the following SQL query to find gaps, partitioned by subreddit:

        ```sql
        WITH posts_with_previous AS (
            SELECT
                subreddit,
                created_utc,
                LAG(created_utc, 1) OVER (PARTITION BY subreddit ORDER BY created_utc) AS prev_created_utc
            FROM
                submissions
        )
        SELECT
            subreddit,
            prev_created_utc AS gap_start,
            created_utc AS gap_end,
            EXTRACT(EPOCH FROM (created_utc - prev_created_utc)) AS gap_duration_seconds
        FROM
            posts_with_previous
        WHERE
            EXTRACT(EPOCH FROM (created_utc - prev_created_utc)) > 600 -- 10 minutes
        ORDER BY
            gap_duration_seconds DESC;
        ```

    *   The command should accept an optional `--output-file` argument to save the results as a JSON file. If not provided, it should print the JSON to the console.
    *   The output format will be a list of JSON objects, where each object represents a single gap:
        ```json
        [
          {
            "subreddit": "wallstreetbets",
            "gap_start": "2023-01-15T10:00:00Z",
            "gap_end": "2023-01-15T10:45:00Z",
            "gap_duration_seconds": 2700
          }
        ]
        ```

---

## Phase 2: Adapt `PushshiftHistoricalScraper` for Targeted Fills

**Objective:** Refactor the `PushshiftHistoricalScraper` to allow it to be invoked for a specific, ad-hoc time window, making its core logic reusable.

**Tasks:**

1.  **Modify `reddit_scraper/reddit_scraper/scrapers/pushshift_historical_scraper.py`:**
    *   Create a new public method: `async def run_for_window(self, subreddit: str, start_date: datetime, end_date: datetime) -> int:`.
    *   This method will serve as a dedicated entry point for filling a single gap. It will orchestrate the scraper's lifecycle:
        1.  Call `await self.initialize()` to set up the `aiohttp` session and data sinks.
        2.  Invoke `await self.scrape_time_period(subreddit, start_date, end_date)` to perform the actual scraping.
        3.  Call `await self.cleanup()` to properly close the session and any other resources.
    *   This approach encapsulates the logic for a single run without altering the scraper's primary `run` method, which is used for broad historical backfills.

---

## Phase 3: Create the `fill-gaps` Orchestrator Command

**Objective:** Build a master CLI command that automates the end-to-end process of finding all gaps and then systematically filling them.

**Tasks:**

1.  **Modify `reddit_scraper/reddit_scraper/cli.py`:**
    *   Add a new Typer command named `fill-gaps`.

2.  **Implement the Orchestration Logic:**
    *   The `fill-gaps` command will first invoke the `find-gaps` logic (from `cli_db.py`) to retrieve the full list of data gaps, sorted from largest to smallest.
    *   It will then iterate through this list of gaps.
    *   For each gap, it will:
        1.  Instantiate the `PushshiftHistoricalScraper`.
        2.  Call the new `run_for_window` method, passing in the `subreddit`, `gap_start`, and `gap_end` from the current gap object.
        3.  Include clear logging to monitor progress, e.g., `"INFO: Now filling gap for r/stocks from [start_time] to [end_time] (Duration: X seconds)..."`
        4.  After a successful run, log the number of posts collected for that gap.

This three-phase approach ensures a modular, testable, and robust implementation for maintaining data integrity.
