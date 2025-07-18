FROM python:3.11.8-alpine3.19

# Set working directory
WORKDIR /app

# Create non-root user
RUN addgroup -S scraper && adduser -S -G scraper scraper

# Install build dependencies and Poetry
RUN apk add --no-cache gcc musl-dev python3-dev libffi-dev openssl-dev cargo && \
    pip install --no-cache-dir poetry==1.6.1

# Copy project files
COPY pyproject.toml poetry.lock* README.md ./

# Configure Poetry to not use a virtual environment in the container
RUN poetry config virtualenvs.create false

# Copy application code (must be done before installing dependencies)
# Copy inner package directly to /app/reddit_scraper to avoid double nesting
# Copy full project directory so nested package structure is preserved
COPY reddit_scraper/ /app/reddit_scraper/
COPY reddit_scraper/run_gap_filler.py /app/

# Install dependencies
RUN poetry install --only main --no-interaction --no-ansi

# Create data and logs directories and set permissions
RUN mkdir -p data logs && \
    chown -R scraper:scraper /app

# Switch to non-root user
USER scraper

# Set environment variables
ENV PYTHONUNBUFFERED=1
# Ensure root path is on PYTHONPATH so `import reddit_scraper.cli` resolves correctly
ENV PYTHONPATH="/app${PYTHONPATH:+:$PYTHONPATH}"

# Command to run the application
ENTRYPOINT ["python", "-m", "reddit_scraper.reddit_scraper.cli"]

# CMD to run the scraper with specified config and loglevel
# The 'scrape' command should come before its options.
CMD ["scrape", "--daemon", "--config", "/app/config.yaml", "--loglevel", "INFO"]

# Temporary diagnostic ENTRYPOINT (commented out)
# ENTRYPOINT ["python", "-c", "import os, sys; print('--- Contents of /app ---'); print(sorted(os.listdir('/app'))); print('--- Contents of /app/reddit_scraper ---'); print(sorted(os.listdir('/app/reddit_scraper'))); print('--- sys.path ---'); print(sys.path); print('--- Attempting import ---'); import reddit_scraper.cli; print('--- Import successful: reddit_scraper.cli found ---')"]
# CMD []
