# TimescaleDB Integration Guide for Scrapers

**Version:** 1.0
**Date:** 2025-05-23

This document provides guidelines and best practices for connecting scraper services to the TimescaleDB instance within the Sentiment Pipeline project.

## 1. Overview

All scraper services, as per `scraper_implementation_rule.md`, are required to use TimescaleDB as their primary data sink. This guide details how to establish and manage the database connection from a typical Python-based scraper service using SQLAlchemy.

## 2. Configuration and Connection Parameters

Connection to TimescaleDB **MUST** be configured using environment variables for sensitive information, aligning with **Rule #3 (Standardized Configuration and Secrets Management)** in `scraper_implementation_rule.md`.

Key environment variables required by a scraper to connect to TimescaleDB are:

*   `PG_HOST`: The hostname or IP address of the TimescaleDB server. When running within the project's Docker Compose setup, this will typically be the service name of the TimescaleDB container (e.g., `timescaledb`).
*   `PG_PORT`: The port number on which TimescaleDB is listening (default is `5432`).
*   `PG_USER`: The PostgreSQL username for connecting to the database.
*   `PG_PASSWORD`: The password for the `PG_USER`.
*   `PG_DB`: The name of the PostgreSQL database to connect to.

These variables should be defined in the scraper's specific `.env` file (e.g., `reddit_scraper/.env`) and loaded by the scraper application at runtime.

## 3. Constructing the SQLAlchemy Connection String

Scrapers should use SQLAlchemy to interact with TimescaleDB. The connection string (URL) for SQLAlchemy typically follows this format for PostgreSQL:

```
postgresql+psycopg2://<USER>:<PASSWORD>@<HOST>:<PORT>/<DATABASE_NAME>
```

Or, for asynchronous operations with `asyncpg` (recommended for `asyncpraw`-based scrapers):

```
postgresql+asyncpg://<USER>:<PASSWORD>@<HOST>:<PORT>/<DATABASE_NAME>
```

**Example (Python code snippet for a scraper's database module):**

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

# Load environment variables (e.g., using python-dotenv)
# from dotenv import load_dotenv
# load_dotenv()

PG_HOST = os.getenv("PG_HOST", "timescaledb")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_USER = os.getenv("PG_USER")
PG_PASSWORD = os.getenv("PG_PASSWORD")
PG_DB = os.getenv("PG_DB")

if not all([PG_USER, PG_PASSWORD, PG_DB]):
    raise ValueError("Missing one or more PostgreSQL connection environment variables (PG_USER, PG_PASSWORD, PG_DB)")

# For synchronous operations
DATABASE_URL_SYNC = f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"
# engine_sync = create_engine(DATABASE_URL_SYNC)

# For asynchronous operations (preferred for async scrapers)
DATABASE_URL_ASYNC = f"postgresql+asyncpg://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"
# engine_async = create_async_engine(DATABASE_URL_ASYNC)

# It's recommended to use the async engine if your scraper uses asyncio
# For example, in your PostgresSink:
# self.engine = create_async_engine(DATABASE_URL_ASYNC)
```

## 4. Database Interaction

*   **SQLAlchemy Models:** Define SQLAlchemy models that reflect the table structures. These models should align with the schema defined and managed by **Alembic** (as per Rule #2 in `scraper_implementation_rule.md`). Scrapers **DO NOT** create tables using `metadata.create_all()`.
*   **Data Sink Logic:** Implement a `PostgresSink` class (or similar) that uses the SQLAlchemy engine to perform database operations (e.g., inserting new records).
*   **Connection Pooling:** SQLAlchemy engines manage connection pooling by default, which is generally sufficient for most scraper workloads.

## 5. Docker Compose Considerations

When running services via `docker-compose.yml`:

*   Ensure the scraper service is on the same Docker network as the `timescaledb` service.
*   Use the TimescaleDB service name (e.g., `timescaledb`) as the `PG_HOST` in the scraper's environment configuration.
*   Use `depends_on` in the `docker-compose.yml` to ensure the `timescaledb` service is healthy before the scraper service starts, and that database migrations (via Alembic) have completed.

## 6. Schema Management Reminder

As a reminder, all database schema (tables, hypertables, indexes, etc.) are managed via **Alembic** (Rule #2). Scrapers assume the necessary schema exists. If a new scraper requires a new table or modifications to an existing one, an Alembic migration script must be created.

---
*This guide should be updated if connection mechanisms or best practices evolve.*
