"""
Sentiment analysis API endpoints.

This module implements the RESTful API endpoints for sentiment analysis functionality,
including on-the-fly text analysis and data retrieval from stored results.
"""

import logging
from datetime import datetime
from typing import List, Optional
from urllib.parse import unquote
import base64
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, asc
from sqlalchemy.orm import selectinload

from sentiment_analyzer.models.dtos import (
    AnalyzeTextRequest,
    AnalyzeTextsBulkRequest,
    SentimentResultDTO,
    SentimentMetricDTO,
    SentimentAnalysisOutput,
    PreprocessedText,
)
from sentiment_analyzer.models.sentiment_result_orm import SentimentResultORM
from sentiment_analyzer.models.sentiment_metric_orm import SentimentMetricORM
from sentiment_analyzer.core.preprocessor import Preprocessor
from sentiment_analyzer.core.sentiment_analyzer_component import SentimentAnalyzerComponent
from sentiment_analyzer.utils.db_session import get_db_session
from sentiment_analyzer.config.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)


# Dependency to get preprocessor instance
async def get_preprocessor() -> Preprocessor:
    """Get preprocessor instance."""
    return Preprocessor()


# Dependency to get sentiment analyzer instance
async def get_sentiment_analyzer() -> SentimentAnalyzerComponent:
    """Get sentiment analyzer instance."""
    return SentimentAnalyzerComponent()


def encode_cursor(timestamp: datetime, id_value: int) -> str:
    """
    Encode cursor for pagination.
    
    Args:
        timestamp: Timestamp value for ordering
        id_value: ID value for tie-breaking
        
    Returns:
        str: Base64 encoded cursor
    """
    cursor_data = {
        "timestamp": timestamp.isoformat(),
        "id": id_value
    }
    cursor_json = json.dumps(cursor_data)
    return base64.b64encode(cursor_json.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    """
    Decode cursor for pagination.
    
    Args:
        cursor: Base64 encoded cursor
        
    Returns:
        tuple: (timestamp, id) values
        
    Raises:
        HTTPException: If cursor is invalid
    """
    try:
        cursor_json = base64.b64decode(cursor.encode()).decode()
        cursor_data = json.loads(cursor_json)
        timestamp = datetime.fromisoformat(cursor_data["timestamp"])
        id_value = cursor_data["id"]
        return timestamp, id_value
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid cursor: {str(e)}")


@router.post("/analyze", response_model=SentimentAnalysisOutput)
async def analyze_text(
    request: AnalyzeTextRequest,
    preprocessor: Preprocessor = Depends(get_preprocessor),
    analyzer: SentimentAnalyzerComponent = Depends(get_sentiment_analyzer)
) -> SentimentAnalysisOutput:
    """
    Analyze sentiment of a single text input.
    
    Performs on-the-fly preprocessing and sentiment analysis of the input text.
    
    Args:
        request: Text analysis request containing the text to analyze
        preprocessor: Text preprocessor instance
        analyzer: Sentiment analyzer instance
        
    Returns:
        SentimentAnalysisOutput: Sentiment analysis results including score, label, and confidence
        
    Raises:
        HTTPException: If analysis fails
    """
    try:
        logger.info(f"Analyzing text: {request.text[:100]}...")
        
        # Preprocess the text
        preprocessed = await preprocessor.preprocess_text(request.text)
        
        # Check if text is in target language
        if not preprocessed.is_target_language:
            logger.warning(f"Text not in target language: {preprocessed.detected_language_code}")
            # Still proceed with analysis but log the warning
        
        # Perform sentiment analysis
        result = await analyzer.analyze_sentiment(preprocessed.cleaned_text or request.text)
        
        logger.info(f"Analysis complete: {result.label} (confidence: {result.confidence})")
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing text: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/analyze/bulk", response_model=List[SentimentAnalysisOutput])
async def analyze_texts_bulk(
    request: AnalyzeTextsBulkRequest,
    preprocessor: Preprocessor = Depends(get_preprocessor),
    analyzer: SentimentAnalyzerComponent = Depends(get_sentiment_analyzer)
) -> List[SentimentAnalysisOutput]:
    """
    Analyze sentiment of multiple texts in a single request.
    
    Args:
        request: Bulk text analysis request
        preprocessor: Text preprocessor instance
        analyzer: Sentiment analyzer instance
        
    Returns:
        List[SentimentAnalysisOutput]: List of sentiment analysis results
        
    Raises:
        HTTPException: If bulk analysis fails
    """
    try:
        logger.info(f"Analyzing {len(request.texts)} texts in bulk")
        
        results = []
        for i, text_item in enumerate(request.texts):
            try:
                # Preprocess the text
                preprocessed = await preprocessor.preprocess_text(text_item.text)
                
                # Perform sentiment analysis
                result = await analyzer.analyze_sentiment(preprocessed.cleaned_text or text_item.text)
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error analyzing text {i}: {str(e)}")
                # Continue with other texts, but include error result
                results.append(SentimentAnalysisOutput(
                    label="error",
                    confidence=0.0,
                    model_version="error",
                    scores={"error": 1.0}
                ))
        
        logger.info(f"Bulk analysis complete: {len(results)} results")
        return results
        
    except Exception as e:
        logger.error(f"Error in bulk analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Bulk analysis failed: {str(e)}")


@router.get("/events", response_model=List[SentimentResultDTO])
async def get_sentiment_events(
    session: AsyncSession = Depends(get_db_session),
    start_time: Optional[datetime] = Query(None, description="Filter events after this timestamp"),
    end_time: Optional[datetime] = Query(None, description="Filter events before this timestamp"),
    source: Optional[str] = Query(None, description="Filter by event source"),
    source_id: Optional[str] = Query(None, description="Filter by source ID"),
    sentiment_label: Optional[str] = Query(None, description="Filter by sentiment label"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    cursor: Optional[str] = Query(None, description="Pagination cursor")
) -> List[SentimentResultDTO]:
    """
    Retrieve sentiment analysis results with filtering and pagination.
    
    Args:
        session: Database session
        start_time: Filter events after this timestamp
        end_time: Filter events before this timestamp
        source: Filter by event source
        source_id: Filter by source ID
        sentiment_label: Filter by sentiment label
        limit: Maximum number of results
        cursor: Pagination cursor
        
    Returns:
        List[SentimentResultDTO]: List of sentiment results
        
    Raises:
        HTTPException: If query fails
    """
    try:
        # Build query
        query = select(SentimentResultORM)
        
        # Apply filters
        conditions = []
        
        if start_time:
            conditions.append(SentimentResultORM.processed_at >= start_time)
        
        if end_time:
            conditions.append(SentimentResultORM.processed_at <= end_time)
            
        if source:
            conditions.append(SentimentResultORM.source == source)
            
        if source_id:
            conditions.append(SentimentResultORM.source_id == source_id)
            
        if sentiment_label:
            conditions.append(SentimentResultORM.sentiment_label == sentiment_label)
        
        # Handle cursor-based pagination
        if cursor:
            cursor_time, cursor_id = decode_cursor(cursor)
            conditions.append(
                (SentimentResultORM.processed_at < cursor_time) |
                (
                    (SentimentResultORM.processed_at == cursor_time) &
                    (SentimentResultORM.id < cursor_id)
                )
            )
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Order by processed_at DESC, id DESC for consistent pagination
        query = query.order_by(desc(SentimentResultORM.processed_at), desc(SentimentResultORM.id))
        
        # Apply limit
        query = query.limit(limit)
        
        # Execute query
        result = await session.execute(query)
        events = result.scalars().all()
        
        # Convert to DTOs
        event_dtos = [
            SentimentResultDTO(
                id=event.id,
                event_id=str(event.event_id),  # Convert to string for API
                occurred_at=event.occurred_at,
                source=event.source,
                source_id=event.source_id,
                sentiment_score=event.sentiment_score,
                sentiment_label=event.sentiment_label,
                confidence=event.confidence,
                processed_at=event.processed_at,
                model_version=event.model_version,
                raw_text=event.raw_text  # Use raw_text from ORM model
            )
            for event in events
        ]
        
        logger.info(f"Retrieved {len(event_dtos)} sentiment events")
        return event_dtos
        
    except Exception as e:
        logger.error(f"Error retrieving sentiment events: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve events: {str(e)}")


@router.get("/metrics", response_model=List[SentimentMetricDTO])
async def get_sentiment_metrics(
    session: AsyncSession = Depends(get_db_session),
    start_time: Optional[datetime] = Query(None, description="Filter metrics after this timestamp"),
    end_time: Optional[datetime] = Query(None, description="Filter metrics before this timestamp"),
    time_bucket_size: Optional[str] = Query("hour", description="Time bucket size (hour, day, week)"),
    source: Optional[str] = Query(None, description="Filter by event source"),
    source_id: Optional[str] = Query(None, description="Filter by source ID"),
    sentiment_label: Optional[str] = Query(None, description="Filter by sentiment label"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    cursor: Optional[str] = Query(None, description="Pagination cursor")
) -> List[SentimentMetricDTO]:
    """
    Retrieve aggregated sentiment metrics with filtering and pagination.
    
    Args:
        session: Database session
        start_time: Filter metrics after this timestamp
        end_time: Filter metrics before this timestamp
        time_bucket_size: Time bucket size for aggregation
        source: Filter by event source
        source_id: Filter by source ID
        sentiment_label: Filter by sentiment label
        limit: Maximum number of results
        cursor: Pagination cursor
        
    Returns:
        List[SentimentMetricDTO]: List of sentiment metrics
        
    Raises:
        HTTPException: If query fails
    """
    try:
        # Build query
        query = select(SentimentMetricORM)
        
        # Apply filters
        conditions = []
        
        if start_time:
            conditions.append(SentimentMetricORM.metric_timestamp >= start_time)
        
        if end_time:
            conditions.append(SentimentMetricORM.metric_timestamp <= end_time)
            
        if source:
            conditions.append(SentimentMetricORM.raw_event_source == source)
            
        if source_id:
            conditions.append(SentimentMetricORM.raw_event_source_id == source_id)
            
        if sentiment_label:
            conditions.append(SentimentMetricORM.sentiment_label == sentiment_label)
        
        # Handle cursor-based pagination
        if cursor:
            cursor_time, cursor_id = decode_cursor(cursor)
            conditions.append(
                (SentimentMetricORM.metric_timestamp < cursor_time) |
                (
                    (SentimentMetricORM.metric_timestamp == cursor_time) &
                    (SentimentMetricORM.id < cursor_id)
                )
            )
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Order by metric_timestamp DESC, id DESC for consistent pagination
        query = query.order_by(desc(SentimentMetricORM.metric_timestamp), desc(SentimentMetricORM.id))
        
        # Apply limit
        query = query.limit(limit)
        
        # Execute query
        result = await session.execute(query)
        metrics = result.scalars().all()
        
        # Convert to DTOs - need to aggregate by time bucket, source, source_id, label
        # For now, return raw metrics and let client handle aggregation
        # TODO: Implement proper time-bucket aggregation in the query
        metric_dtos = [
            SentimentMetricDTO(
                time_bucket=metric.metric_timestamp,
                source=metric.raw_event_source,
                source_id=metric.raw_event_source_id or "",
                label=metric.sentiment_label,
                count=int(metric.metric_value) if metric.metric_name == "event_count" else 1,
                avg_score=metric.metric_value if metric.metric_name == "confidence_sum" else 0.0
            )
            for metric in metrics
        ]
        
        logger.info(f"Retrieved {len(metric_dtos)} sentiment metrics")
        return metric_dtos
        
    except Exception as e:
        logger.error(f"Error retrieving sentiment metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve metrics: {str(e)}")
