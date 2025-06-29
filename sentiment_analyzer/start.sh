#!/usr/bin/env bash
# Startup script for Sentiment Analyzer API container
# 1. Run database migrations
# 2. Launch the FastAPI service

set -e

echo "Starting Sentiment Analyzer API Service..."

# Wait for database to be ready
echo "Waiting for database connection..."
for i in {1..30}; do
  echo "Database connection attempt $i/30..."
  if python -c "from sentiment_analyzer.utils.db_health import test_db_connection; import asyncio; asyncio.run(test_db_connection())" 2>/dev/null; then
    echo "Database connection successful!"
    break
  fi
  if [ $i -eq 30 ]; then
    echo "Failed to connect to database after 30 attempts. Exiting."
    exit 1
  fi
  sleep 2
done

# Run database migrations
echo "Running Alembic migrations..."
for i in {1..5}; do
  echo "Migration attempt $i/5..."
  if alembic upgrade head; then
    echo "Migrations applied successfully."
    break
  fi
  if [ $i -eq 5 ]; then
    echo "Failed to apply migrations after 5 attempts. Exiting."
    exit 1
  fi
  echo "Migration failed. Retrying in 3 seconds..."
  sleep 3
done

# Set default values for environment variables
export HOST=${HOST:-0.0.0.0}
export PORT=${PORT:-8001}
export WORKERS=${WORKERS:-1}
export LOG_LEVEL=${LOG_LEVEL:-info}

echo "Starting FastAPI server on $HOST:$PORT with $WORKERS workers..."
echo "Log level: $LOG_LEVEL"

# Launch the FastAPI application with Uvicorn
exec uvicorn sentiment_analyzer.api.main:app \
  --host "$HOST" \
  --port "$PORT" \
  --workers "$WORKERS" \
  --log-level "$LOG_LEVEL" \
  --access-log \
  --loop uvloop
