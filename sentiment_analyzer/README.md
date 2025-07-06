# Sentiment Analyzer Service

A FastAPI micro-service that performs FinBERT-based sentiment analysis on raw text events (initially Reddit submissions) ingested by the Sentiment Pipeline.  Results are written to TimescaleDB hypertables and streamed to Power BI in real-time.

## Features

* Async FastAPI REST API with OpenAPI docs
* Batch pipeline that:
  1. Fetches unprocessed events from `raw_events`
  2. Cleans & language-filters text (spaCy)
  3. Runs FinBERT to produce polarity & confidence
  4. Persists results (`sentiment_results`) & aggregates (`sentiment_metrics`)
  5. Streams JSON rows to Power BI
* Production-ready Docker image with health-checks, non-root user & resource limits
* Extensive unit & integration tests

## Quick Start (Local Docker Compose)

```bash
# Repo root
cp .env.example .env               # configure DB creds & ports

# Build & run all services
docker-compose up -d

# Verify health
curl http://localhost:8001/health
```

## Running Locally (Poetry)

```bash
poetry install --with dev
poetry run uvicorn sentiment_analyzer.api.main:app --reload --port 8001
```

Batch processor entry-point:

```bash
poetry run python -m sentiment_analyzer.core.pipeline
```

## Architecture Overview

The service is split into two cooperating components:

1. **FastAPI Web Server** (`sentiment_analyzer.api`)
   * Exposes REST endpoints for ad-hoc text analysis and querying stored results/metrics.
   * Handles request validation, authentication (optional), and response serialization.
2. **Batch Pipeline** (`sentiment_analyzer.core.pipeline`)
   * Periodically fetches new events from the shared `raw_events` table using efficient, async SQLAlchemy queries.
   * Runs language filtering, text preprocessing (spaCy), then FinBERT inference.
   * Persists per-event polarity scores to `sentiment_results` and aggregated time-bucket metrics to `sentiment_metrics` (TimescaleDB hypertables).
   * Streams processed rows to a configurable Power BI streaming dataset for near-real-time dashboards.

Both components share common utilities (database session management, configuration, DTOs) and can be scaled independently via Docker Compose/Kubernetes.

A more detailed sequence and component diagram can be found in `sentiment_docs/design.md`.

---

## API Endpoints (v1)

| Method | Path | Description |
| --- | --- | --- |
| POST | /api/v1/sentiment/analyze | Analyze ad-hoc text payload |
| GET  | /api/v1/sentiment/events | Query stored sentiment results (filters + pagination) |
| GET  | /api/v1/sentiment/metrics | Query aggregated metrics |
| GET  | /health | Component liveness & Power BI status |

See `sentiment_docs/API_EXAMPLES.md` for full request / response examples.

## Configuration

Key env vars (see `.env.example`):

* `DATABASE_URL` – TimescaleDB async URL
* `POWERBI_PUSH_URL` – Streaming dataset endpoint (optional)
* `MODEL_NAME` / `MODEL_VERSION` – HuggingFace identifiers
* `BATCH_SIZE`, `PIPELINE_RUN_INTERVAL_SECONDS`

## Testing

```bash
poetry run pytest -q
```

Test suite spins up a disposable TimescaleDB instance via Docker and exercises API & pipeline end-to-end.

## Documentation Map

* High-level design – `sentiment_docs/design.md`
* Deployment guide – `sentiment_docs/DEPLOYMENT.md`
* Power BI integration – `sentiment_docs/POWERBI.md`

---
Released under the MIT License.
