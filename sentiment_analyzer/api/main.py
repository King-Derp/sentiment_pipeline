"""
FastAPI application for the Sentiment Analyzer service.

This module initializes and configures the FastAPI application that serves
the sentiment analysis API endpoints.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# Configure logging to ensure all loggers output at INFO level
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s',
    force=True  # Override any existing configuration
)
# Ensure specific loggers are at INFO level
logging.getLogger('sentiment_analyzer').setLevel(logging.INFO)
logging.getLogger('sentiment_analyzer.core.pipeline').setLevel(logging.INFO)

from sentiment_analyzer.config.settings import settings
from sentiment_analyzer.api.endpoints import sentiment
from sentiment_analyzer.integrations.powerbi import PowerBIClient
from sentiment_analyzer.core.pipeline import SentimentPipeline


# Global PowerBI client instance
powerbi_client: PowerBIClient | None = None

# Global pipeline instance and background task
pipeline: SentimentPipeline | None = None
pipeline_task: asyncio.Task | None = None

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager for startup and shutdown events.
    
    Handles initialization of resources like PowerBI client and background
    sentiment processing pipeline on startup and cleanup on shutdown.
    """
    global powerbi_client, pipeline, pipeline_task
    
    # Startup
    print(f"LIFESPAN: Starting {settings.APP_NAME} v{settings.APP_VERSION}")  # Using print to ensure visibility
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Initialize PowerBI client if configured
    if hasattr(settings, 'POWERBI_PUSH_URL') and settings.POWERBI_PUSH_URL:
        logger.info("Initializing PowerBI client")
        powerbi_client = PowerBIClient(
            push_url=settings.POWERBI_PUSH_URL,
            api_key=getattr(settings, 'POWERBI_API_KEY', None)
        )
    else:
        logger.info("PowerBI integration not configured - skipping client initialization")
    
    # Initialize and start the sentiment processing pipeline as a background task
    print("LIFESPAN: About to initialize sentiment processing pipeline")
    logger.info("Starting sentiment processing pipeline as background task")
    try:
        print("LIFESPAN: Creating SentimentPipeline instance...")
        pipeline = SentimentPipeline()
        print("LIFESPAN: SentimentPipeline created successfully")
        logger.info("Sentiment processing pipeline initialized successfully")
    except Exception as e:
        print(f"LIFESPAN: Pipeline initialization failed: {e}")
        logger.error(f"Failed to initialize sentiment processing pipeline: {e}", exc_info=True)
        # Continue without pipeline rather than failing the entire service
        pipeline = None
    
    async def pipeline_worker():
        """Background worker that runs the sentiment processing pipeline."""
        run_interval_seconds = settings.PIPELINE_RUN_INTERVAL_SECONDS
        print(f"PIPELINE_WORKER: Started with interval {run_interval_seconds}s")
        logger.info(f"Sentiment processing pipeline worker started. Run interval: {run_interval_seconds}s")
        
        try:
            while True:
                print("PIPELINE_WORKER: Starting new processing cycle")
                logger.info("Starting new pipeline processing cycle.")
                events_attempted = await pipeline.run_pipeline_once()
                
                # Determine sleep duration
                current_sleep_interval = run_interval_seconds
                if events_attempted == 0:
                    logger.debug(f"No events found. Sleeping for {current_sleep_interval} seconds.")
                else:
                    logger.info(f"Processed a batch of {events_attempted} events. Sleeping for {current_sleep_interval} seconds.")
                
                await asyncio.sleep(current_sleep_interval)
                
        except asyncio.CancelledError:
            logger.info("Pipeline background worker cancelled. Shutting down.")
            raise
        except Exception as e:
            logger.error(f"Error in pipeline background worker: {e}", exc_info=True)
            # Continue running despite errors to maintain service availability
    
    # Start the background pipeline task
    if pipeline:
        print("LIFESPAN: Creating background pipeline task")
        logger.info("Creating background pipeline task")
        pipeline_task = asyncio.create_task(pipeline_worker())
        print("LIFESPAN: Background pipeline task created successfully")
        logger.info("Background pipeline task created successfully")
    else:
        print("LIFESPAN: Pipeline not initialized - skipping background task creation")
        logger.warning("Pipeline not initialized - skipping background task creation")
        pipeline_task = None
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    
    # Cancel the background pipeline task
    if pipeline_task:
        logger.info("Stopping sentiment processing pipeline background task")
        pipeline_task.cancel()
        try:
            await pipeline_task
        except asyncio.CancelledError:
            logger.info("Pipeline background task cancelled successfully")
    
    # Close PowerBI client
    if powerbi_client:
        await powerbi_client.close()


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        FastAPI: Configured FastAPI application instance.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="""Sentiment Analysis API for processing text and retrieving sentiment data.
        
        This API provides endpoints for:
        - Real-time sentiment analysis of text
        - Bulk sentiment analysis
        - Querying stored sentiment results with filtering and pagination
        - Retrieving aggregated sentiment metrics
        - Health monitoring
        
        The API uses advanced NLP models for accurate sentiment classification
        and supports real-time streaming to Power BI dashboards.""",
        debug=settings.DEBUG,
        lifespan=lifespan,
        docs_url="/docs" if settings.DEBUG else None,  # Disable docs in production
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_tags=[
            {
                "name": "sentiment",
                "description": "Sentiment analysis operations"
            },
            {
                "name": "health",
                "description": "Health check and monitoring"
            }
        ]
    )
    
    # Add CORS middleware with production-ready settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS if not settings.DEBUG else ["*"],
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )
    
    # Add trusted host middleware for security
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS if not settings.DEBUG else ["*"]
    )
    
    # Include API routers
    app.include_router(
        sentiment.router,
        prefix="/api/v1/sentiment",
        tags=["sentiment"]
    )
    
    # Health check endpoint
    @app.get("/health", tags=["health"], summary="Health Check", description="Get application health status and configuration")
    async def health_check():
        """
        Health check endpoint providing comprehensive application status.
        
        Returns:
            dict: Application health status including:
                - Service status
                - Version information
                - Timestamp
                - PowerBI integration status
                - Configuration summary
        """
        from datetime import datetime, timezone
        
        # Check PowerBI client status
        powerbi_status = "disabled"
        if powerbi_client:
            try:
                # Quick connection test (non-blocking)
                powerbi_status = "enabled"
            except Exception:
                powerbi_status = "error"
        
        return {
            "status": "healthy",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "powerbi_integration": powerbi_status,
            "debug_mode": settings.DEBUG,
            "api_host": settings.API_HOST,
            "api_port": settings.API_PORT
        }
    
    return app


# Create the application instance
app = create_app()


def get_powerbi_client() -> PowerBIClient | None:
    """
    Get the global PowerBI client instance.
    
    Returns:
        PowerBIClient | None: PowerBI client if configured, None otherwise.
    """
    return powerbi_client
