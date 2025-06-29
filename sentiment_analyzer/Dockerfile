# Multi-stage build for optimized production image
FROM python:3.10-slim AS builder

# Set build environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install poetry==1.7.1

# Set working directory
WORKDIR /app

# Copy dependency files
COPY ./sentiment_analyzer/pyproject.toml ./sentiment_analyzer/poetry.lock* /app/

# Configure poetry and install dependencies
RUN poetry config virtualenvs.create false && \
    poetry install --no-root --only main --no-interaction --no-ansi

# Install ML dependencies with GPU/CPU support based on build argument
ARG USE_GPU=false
RUN if [ "$USE_GPU" = "true" ] ; then \
        echo "Installing GPU-enabled PyTorch..." && \
        pip install --no-cache-dir \
            torch==2.2.1+cu118 torchvision==0.17.1+cu118 torchaudio==2.2.1+cu118 \
            -f https://download.pytorch.org/whl/cu118/torch_stable.html ; \
    else \
        echo "Installing CPU-only PyTorch..." && \
        pip install --no-cache-dir \
            torch==2.2.1+cpu torchvision==0.17.1+cpu torchaudio==2.2.1+cpu \
            -f https://download.pytorch.org/whl/cpu/torch_stable.html ; \
    fi && \
    pip install --no-cache-dir \
        transformers==4.38.2 \
        spacy==3.7.2 \
        https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.7.0/en_core_web_lg-3.7.0-py3-none-any.whl

# Production stage
ARG USE_GPU=false
FROM python:3.10-slim AS production

# Install system dependencies
RUN apt-get update && \
    apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# Set runtime environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app"
ENV PORT=8001

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
# Copy application code
COPY ./sentiment_analyzer /app/sentiment_analyzer

# Copy reddit_scraper package (inner) for Alembic imports
COPY ./reddit_scraper/reddit_scraper /app/reddit_scraper

# Copy Alembic config and migrations
COPY ./alembic.ini /app/alembic.ini
COPY ./alembic /app/alembic

# Copy startup script and make executable
COPY ./sentiment_analyzer/start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Create model cache directories with proper permissions
RUN mkdir -p /app/models/transformers_cache /app/models/spacy_cache && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Entry point
CMD ["/app/start.sh"]
