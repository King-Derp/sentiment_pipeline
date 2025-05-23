# TimescaleDB Implementation: Detailed Task Breakdown

**Version:** 1.1 (Alembic Focused)
**Date:** 2025-05-23

This document provides a detailed breakdown of the tasks outlined in `timescaledb/todo.md` for integrating TimescaleDB using an **Alembic-driven schema management** strategy.

---

## Phase 1: Project Setup & Alembic Initialization

Details for tasks in `timescaledb/todo.md - Phase 1`.

### Task 1.1: Finalize Docker Compose for TimescaleDB Service

*   **Objective:** Ensure the `timescaledb` service in `docker-compose.yml` is correctly configured for persistence, networking, and environment variables.
*   **Details:**
    *   **Image:** Use `timescale/timescaledb:latest-pg<XX>` (e.g., `latest-pg14` or `latest-pg15`).
    *   **Volume:** `timescaledb_data:/var/lib/postgresql/data` for persistence.
    *   **Ports:** Map `"5433:5432"` (or similar, if local 5432 is in use, otherwise `"5432:5432"`) to access the DB locally.
    *   **Environment Variables:** Source `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` from the root `.env` file.
        ```yaml
        # In docker-compose.yml
        services:
          timescaledb:
            image: timescale/timescaledb:latest-pg15-oss # Or your preferred version
            container_name: timescaledb_service
            ports:
              - "${PG_PORT_HOST}:${PG_PORT_CONTAINER}" # e.g., 5433:5432 from .env
            environment:
              POSTGRES_USER: ${PG_USER}
              POSTGRES_PASSWORD: ${PG_PASSWORD}
              POSTGRES_DB: ${PG_DB}
            volumes:
              - timescaledb_data:/var/lib/postgresql/data
            networks:
              - sentiment_net
        # ... other services
        volumes:
          timescaledb_data:
        networks:
          sentiment_net:
            driver: bridge
        ```

### Task 1.2: Setup Project-Level `.env` File

*   **Objective:** Centralize database connection parameters for all services and Alembic.
*   **Details:** Create/update `.env` in the project root:
    ```env
    # .env (example)
    PG_HOST=timescaledb_service # Service name in docker-compose for other containers
    PG_HOST_LOCAL=localhost     # For local connections if accessing directly
    PG_PORT_HOST=5433           # Host port mapped in docker-compose
    PG_PORT_CONTAINER=5432      # Port inside the container
    PG_USER=youruser
    PG_PASSWORD=yourstrongpassword
    PG_DB=sentiment_db

    # For Alembic and SQLAlchemy URL construction (used by services connecting to DB)
    DATABASE_URL=postgresql://${PG_USER}:${PG_PASSWORD}@${PG_HOST}:${PG_PORT_CONTAINER}/${PG_DB}
    # For Alembic running locally, or from a script that needs to connect to the host-mapped port
    DATABASE_URL_LOCAL=postgresql://${PG_USER}:${PG_PASSWORD}@${PG_HOST_LOCAL}:${PG_PORT_HOST}/${PG_DB}
    ```
    *Ensure `.env.example` reflects these variables.* 

### Task 1.3: Initialize Alembic

*   **Objective:** Set up the Alembic environment for managing database schema migrations.
*   **Steps:**
    1.  Ensure you are in the project root directory (`f:/Coding/sentiment_pipeline`).
    2.  If not already installed in your Python environment (ideally a project virtual environment):
        ```bash
        pip install alembic sqlalchemy psycopg2-binary python-dotenv
        ```
    3.  Run the Alembic initialization command:
        ```bash
        alembic init alembic
        ```
        This creates an `alembic/` directory and an `alembic.ini` file.

### Task 1.4: Configure Alembic (`alembic.ini` and `alembic/env.py`)

*   **Objective:** Configure Alembic to connect to TimescaleDB and recognize project SQLAlchemy models.
*   **Details for `alembic.ini`:**
    *   Locate the `sqlalchemy.url` line.
    *   Modify it to use the environment variable for the database URL. You might need a small script or rely on `env.py` to load this if direct environment variable substitution isn't supported by your Alembic version or setup for `alembic.ini` itself. A common practice is to set it in `env.py`.
        ```ini
        # alembic.ini
        # ... other settings ...
        # sqlalchemy.url = driver://user:pass@host/dbname
        # Comment out the above line or set it if your env.py doesn't override it.
        # It's often better to fully configure in env.py for flexibility.
        ```
*   **Details for `alembic/env.py`:**
    1.  **Import `load_dotenv` and os:**
        ```python
        # At the top of alembic/env.py
        import os
        from dotenv import load_dotenv
        load_dotenv() # Loads variables from .env file in the project root
        ```
    2.  **Set `sqlalchemy.url`:** Ensure the script constructs the database URL dynamically using environment variables. This typically happens within the `run_migrations_online()` function or by setting a variable that `config.set_main_option('sqlalchemy.url', YOUR_CONSTRUCTED_URL)` uses.
        ```python
        # Inside alembic/env.py, usually before or at the start of run_migrations_online()
        # or as a global variable if appropriate.
        db_user = os.getenv('PG_USER')
        db_password = os.getenv('PG_PASSWORD')
        db_host = os.getenv('PG_HOST') # Use PG_HOST_LOCAL if running alembic outside Docker pointing to host port
        db_port = os.getenv('PG_PORT_CONTAINER') # Use PG_PORT_HOST if running alembic outside Docker
        db_name = os.getenv('PG_DB')
        SQLALCHEMY_URL = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        
        # ... later, in run_migrations_online() or where config is available:
        # config.set_main_option("sqlalchemy.url", SQLALCHEMY_URL)
        # Or, if file_config = config.get_section(config.config_file_name)
        # file_config['sqlalchemy.url'] = SQLALCHEMY_URL 
        # Ensure this is correctly passed to connectable = engine_from_config(...)
        ```
        *Correction*: The `config` object in `env.py` already has `config.get_main_option("sqlalchemy.url")`. If you set `sqlalchemy.url` in `alembic.ini` to a placeholder and then load it in `env.py` to configure the engine, that's a common pattern. Or, more directly:
        ```python
        # In env.py, within run_migrations_online before creating the engine:
        connectable = create_engine(SQLALCHEMY_URL) # Using the URL constructed above
        # ... with connectable.connect() as connection:
        # context.configure(connection=connection, target_metadata=target_metadata)
        ```

    3.  **Import and set `target_metadata`:**
        *   Ensure your SQLAlchemy models (e.g., `SubmissionORM` from `reddit_scraper.src.models.submission.SubmissionORM` and its `Base.metadata`) are accessible.
        *   You might need to adjust `sys.path` if Alembic can't find your modules or install your project as an editable package (`pip install -e .`).
        ```python
        # alembic/env.py
        # Add to imports:
        # from myapp.mymodel import Base # Adjust to your project structure
        # e.g.:
        # import sys
        # sys.path.append(os.path.join(sys.path[0], '..')) # If alembic is one level down from root
        from reddit_scraper.src.models.submission import Base # Assuming models are structured this way
        target_metadata = Base.metadata
        ```
        *Ensure this `target_metadata` is passed to `context.configure()` in `run_migrations_online()` and `run_migrations_offline()`.* 

### Task 1.5: Define SQLAlchemy Models
*   **Objective:** Ensure SQLAlchemy models accurately reflect the desired database schema for Alembic to use.
*   **Details:** Review `reddit_scraper.src.models.submission.SubmissionORM`. Confirm all columns, types, constraints (like `primary_key=True` on `id`) are correctly defined. Alembic's autogenerate feature compares these models against the database state.

---

## Phase 2: Initial Schema Migration with Alembic

Details for tasks in `timescaledb/todo.md - Phase 2`.

### Task 2.1: Create First Alembic Migration Script (Autogenerate)

*   **Objective:** Generate the initial Alembic migration script based on your SQLAlchemy models.
*   **Steps:**
    1.  Ensure the TimescaleDB Docker container is **NOT** running or that the database is empty/does not have the tables yet. Autogenerate works best by comparing models to an empty DB or a DB at a known migration state.
    2.  From the project root, run:
        ```bash
        alembic revision -m "create_initial_schema_and_hypertable" --autogenerate
        ```
    3.  A new migration script will be created in `alembic/versions/`. Inspect its contents.
        *   It should contain `op.create_table(...)` for `raw_submissions` and any other tables defined in your `target_metadata`.

### Task 2.2: Edit Migration Script for TimescaleDB Specifics

*   **Objective:** Add TimescaleDB-specific commands (enable extension, create hypertable) to the autogenerated script.
*   **Details:** Open the newly generated migration file (e.g., `alembic/versions/<hash>_create_initial_schema.py`).
    *   **`upgrade()` function:**
        *   After `op.create_table('raw_submissions', ...)`:
            ```python
            op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
            op.execute("SELECT create_hypertable('raw_submissions', 'created_utc', chunk_time_interval => 86400, if_not_exists => TRUE);") # 86400 seconds = 1 day
            ```
        *   Ensure any necessary indexes are also created, especially on `created_utc` and `id` if not automatically part of `create_table` from model definition:
            ```python
            # Example index, if not covered by primary_key or model definition
            # op.create_index(op.f('ix_raw_submissions_created_utc'), 'raw_submissions', ['created_utc'], unique=False)
            ```
    *   **`downgrade()` function:**
        *   Before `op.drop_table('raw_submissions')`:
            ```python
            # Optional: remove hypertable information if you want to be very thorough.
            # Usually, dropping the table itself is sufficient for downgrade.
            # op.execute("SELECT drop_chunks('raw_submissions');") # This might be too aggressive or complex for a simple downgrade.
            # No standard op to remove hypertable status before dropping table.
            ```
        *   Consider if `DROP EXTENSION timescaledb` is appropriate for your downgrade. Usually not, as other tables might use it. If it's the *only* user, then perhaps.

### Task 2.3: Apply the Initial Migration

*   **Objective:** Execute the migration script to create the schema in TimescaleDB.
*   **Steps:**
    1.  Start the TimescaleDB service: `docker-compose up -d timescaledb`.
    2.  Wait a few moments for it to initialize.
    3.  Execute Alembic upgrade from a container that has Alembic and your project code/models installed (e.g., `reddit_scraper` if it includes Alembic, or a dedicated service):
        ```bash
        docker-compose exec reddit_scraper alembic upgrade head
        ```
        Or, if running Alembic locally and configured to point to the Dockerized DB:
        ```bash
        alembic upgrade head
        ```

### Task 2.4: Verify Schema and Hypertable in DB

*   **Objective:** Confirm the database schema and hypertable were created correctly.
*   **Steps:**
    1.  Connect to TimescaleDB:
        ```bash
        docker-compose exec timescaledb_service psql -U ${PG_USER} -d ${PG_DB}
        ```
        (You might be prompted for the password, or it might connect directly if trust is configured or via `pg_hba.conf` implicitly by Docker setup).
    2.  In `psql`:
        *   List tables: `\dt` (should show `raw_submissions`).
        *   Describe table: `\d raw_submissions` (shows columns, types, indexes).
        *   Check extensions: `\dx` (should list `timescaledb`).
        *   Check hypertables: `SELECT * FROM timescaledb_information.hypertables;` (should list `raw_submissions`).
        *   Detailed hypertable info: `\d+ raw_submissions` (shows chunks if any data were added).

---

## Phase 3: Scraper Integration with Alembic-Managed Schema

Details for tasks in `timescaledb/todo.md - Phase 3`.

### Task 3.1: Update Scraper DB Connection Logic

*   **Objective:** Ensure scrapers connect to TimescaleDB using the defined environment variables and **do not** attempt to manage schema.
*   **Details:**
    *   In `reddit_scraper`'s database connection module (e.g., where `create_engine` is called for the TimescaleDB sink):
        *   Ensure it reads `DATABASE_URL` (or individual `PG_HOST`, `PG_USER`, etc.) from environment variables.
        *   **Crucially, remove any calls to `Base.metadata.create_all(engine)`** for the TimescaleDB connection. The schema is now managed by Alembic.

### Task 3.2: Test Scraper Data Ingestion

*   **Objective:** Verify the scraper can write data to the Alembic-created schema.
*   **Steps:**
    1.  Run `docker-compose up -d reddit_scraper` (ensure `timescaledb` is also up).
    2.  Monitor scraper logs: `docker-compose logs -f reddit_scraper`.
    3.  After some time, query the `raw_submissions` table in TimescaleDB to confirm data is being inserted.

### Task 3.3: Implement Idempotent Writes

*   **Objective:** Prevent duplicate data entries if the scraper reprocesses data.
*   **Details:**
    *   When inserting data with SQLAlchemy, use the `on_conflict_do_nothing` or `on_conflict_do_update` feature for PostgreSQL.
    *   Example for `on_conflict_do_nothing` (if `id` is the primary key or has a unique constraint):
        ```python
        from sqlalchemy.dialects.postgresql import insert

        # ... in your scraper's data saving function ...
        stmt = insert(SubmissionORM).values(data_dict_list) # data_dict_list is a list of dicts
        stmt = stmt.on_conflict_do_nothing(index_elements=['id'])
        session.execute(stmt)
        session.commit()
        ```

---

## Phase 4: Documentation, Testing & Refinement

Details for tasks in `timescaledb/todo.md - Phase 4`.

### Task 4.1 - 4.3: Update Documentation (READMEs, PRDs)
*   **Objective:** Ensure all project documentation reflects the Alembic-driven workflow.
*   **Status:** These were largely addressed in previous steps by editing the respective Markdown files.
    *   `README.md`: Updated for Alembic DB setup.
    *   `reddit_scraper/README.md`: Clarified schema management.
    *   `timescaledb/prd.md`: Updated for Alembic schema/hypertable management.

### Task 4.4: Update `timescaledb/todo.md` and `timescaledb/todo_details.md`
*   **Objective:** Align these To-Do list documents with the new Alembic workflow.
*   **Status:**
    *   `timescaledb/todo.md`: Updated in a previous step.
    *   `timescaledb/todo_details.md`: This current update addresses this task for this file.

### Task 4.5: Write Unit/Integration Tests (Future)
*   **Objective:** Develop tests for database interactions.
*   **Details:** This is a placeholder for future work. Would involve setting up a test database, running migrations, and testing scraper write/read operations.

### Task 4.6: Review Connection Pooling
*   **Objective:** Confirm default SQLAlchemy pooling is sufficient; note PgBouncer as future option.
*   **Details:** For now, SQLAlchemy's default `QueuePool` is likely sufficient. If connection limits become an issue with many scrapers or services, PgBouncer can be introduced. This is noted in `timescaledb_integration_guide.md` and `scraper_implementation_rule.md`.

---

## Phase 5: Future Enhancements

Details for tasks in `timescaledb/todo.md - Phase 5`.

*   These tasks (PgBouncer, TimescaleDB advanced features, monitoring) are for future consideration after the core Alembic-managed TimescaleDB integration is stable.

This detailed breakdown should guide the implementation of TimescaleDB with Alembic. Remember to commit changes frequently and test each significant step.
