FROM python:3.11.8-alpine3.19

# Set working directory
WORKDIR /app

# Create non-root user
RUN addgroup -S scraper && adduser -S -G scraper scraper

# Install build dependencies and Poetry
RUN apk add --no-cache gcc musl-dev python3-dev libffi-dev openssl-dev cargo && \
    pip install --no-cache-dir poetry==1.6.1

# Copy project files
COPY pyproject.toml README.md ./

# Configure Poetry to not use a virtual environment in the container
RUN poetry config virtualenvs.create false

# Copy application code (must be done before installing dependencies)
COPY reddit_scraper/ ./reddit_scraper/

# Install dependencies
RUN poetry install --only main --no-interaction --no-ansi

# Create data and logs directories and set permissions
RUN mkdir -p data logs && \
    chown -R scraper:scraper /app

# Switch to non-root user
USER scraper

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Command to run the application
# Using the --daemon flag to ensure continuous operation
# The maintenance_interval_sec in config.yaml controls how frequently it checks for new posts (61 seconds)
ENTRYPOINT ["python", "-m", "reddit_scraper.cli"]
CMD ["scrape", "--daemon", "--config", "config.yaml", "--loglevel", "INFO"]
