#!/usr/bin/env bash
# Startup script for Sentiment Analyzer container
# 1. Run database migrations
# 2. Launch the sentiment analysis pipeline as a long-running process

set -e

# Attempt to run Alembic migrations until success (DB might not be ready yet)
for i in {1..10}; do
  echo "Running Alembic migrations (attempt $i)..."
  if alembic upgrade head; then
    echo "Migrations applied successfully."
    break
  fi
  echo "Migrations failed; database might not be ready. Sleeping before retry..."
  sleep 5
done

# Launch the sentiment analysis pipeline (will block)
exec python -m sentiment_analyzer.core.pipeline
