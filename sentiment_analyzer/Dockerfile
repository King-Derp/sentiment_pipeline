# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Install poetry
RUN pip install poetry

# Copy the project files into the container
# Copy only the pyproject.toml to force dependency resolution
# Copy the service-specific dependency files
COPY ./sentiment_analyzer/pyproject.toml ./sentiment_analyzer/poetry.lock* /app/

# Install project dependencies
RUN poetry config virtualenvs.create false && \
    poetry install --no-root --only main --no-interaction --no-ansi

# Install heavy ML deps (CPU wheels)
RUN pip install --no-cache-dir \
    torch==2.2.1+cu118 torchvision==0.17.1+cu118 torchaudio==2.2.1+cu118 \
    -f https://download.pytorch.org/whl/cu118/torch_stable.html \
    transformers==4.38.2 spacy==3.7.2 \
 && pip install --no-cache-dir \
    https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.7.0/en_core_web_lg-3.7.0-py3-none-any.whl
# Copy the rest of the application code
COPY ./sentiment_analyzer /app/sentiment_analyzer

# Copy reddit_scraper package (inner) for Alembic imports
COPY ./reddit_scraper/reddit_scraper /app/reddit_scraper

# Copy Alembic config and migrations
COPY ./alembic.ini /app/alembic.ini
COPY ./alembic /app/alembic

# Copy startup script
COPY ./sentiment_analyzer/start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Ensure package import paths
ENV PYTHONPATH="/app${PYTHONPATH:+:$PYTHONPATH}"

# Entry point
CMD ["/app/start.sh"]
