"""
Unit tests for API endpoints.

Tests the FastAPI endpoints for sentiment analysis functionality.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

from fastapi.testclient import TestClient
from httpx import AsyncClient
import pytest_asyncio

from sentiment_analyzer.api.main import app
from sentiment_analyzer.models.dtos import (
    AnalyzeTextRequest,
    AnalyzeTextsBulkRequest,
    AnalyzeTextRequestItem,
    SentimentAnalysisOutput,
    SentimentResultDTO,
    SentimentMetricDTO,
    PreprocessedText,
)
from sentiment_analyzer.models.sentiment_result_orm import SentimentResultORM
from sentiment_analyzer.models.sentiment_metric_orm import SentimentMetricORM


class TestAnalyzeEndpoint:
    """Test cases for the /analyze endpoint."""
    
    @pytest_asyncio.async_test
    async def test_analyze_text_success(self):
        """Test successful text analysis."""
        # Mock dependencies
        mock_preprocessor = AsyncMock()
        mock_analyzer = AsyncMock()
        
        # Setup mock responses
        mock_preprocessed = PreprocessedText(
            original_text="This is great news!",
            cleaned_text="This is great news!",
            detected_language_code="en",
            is_target_language=True
        )
        mock_preprocessor.preprocess_text.return_value = mock_preprocessed
        
        mock_result = SentimentAnalysisOutput(
            label="positive",
            confidence=0.85,
            scores={"positive": 0.85, "negative": 0.10, "neutral": 0.05},
            model_version="finbert-v1.0"
        )
        mock_analyzer.analyze_sentiment.return_value = mock_result
        
        # Test the endpoint
        async with AsyncClient(app=app, base_url="http://test") as client:
            with patch("sentiment_analyzer.api.endpoints.sentiment.get_preprocessor", return_value=mock_preprocessor):
                with patch("sentiment_analyzer.api.endpoints.sentiment.get_sentiment_analyzer", return_value=mock_analyzer):
                    response = await client.post(
                        "/api/v1/sentiment/analyze",
                        json={"text": "This is great news!"}
                    )
        
        assert response.status_code == 200
        result = response.json()
        assert result["label"] == "positive"
        assert result["confidence"] == 0.85
        assert result["model_version"] == "finbert-v1.0"
        
        # Verify mocks were called
        mock_preprocessor.preprocess_text.assert_called_once_with("This is great news!")
        mock_analyzer.analyze_sentiment.assert_called_once_with("This is great news!")
    
    @pytest_asyncio.async_test
    async def test_analyze_text_non_target_language(self):
        """Test analysis with non-target language text."""
        mock_preprocessor = AsyncMock()
        mock_analyzer = AsyncMock()
        
        # Setup mock responses for non-English text
        mock_preprocessed = PreprocessedText(
            original_text="Esto es una gran noticia!",
            cleaned_text="Esto es una gran noticia!",
            detected_language_code="es",
            is_target_language=False
        )
        mock_preprocessor.preprocess_text.return_value = mock_preprocessed
        
        mock_result = SentimentAnalysisOutput(
            label="positive",
            confidence=0.65,
            model_version="finbert-v1.0"
        )
        mock_analyzer.analyze_sentiment.return_value = mock_result
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            with patch("sentiment_analyzer.api.endpoints.sentiment.get_preprocessor", return_value=mock_preprocessor):
                with patch("sentiment_analyzer.api.endpoints.sentiment.get_sentiment_analyzer", return_value=mock_analyzer):
                    response = await client.post(
                        "/api/v1/sentiment/analyze",
                        json={"text": "Esto es una gran noticia!"}
                    )
        
        assert response.status_code == 200
        result = response.json()
        assert result["label"] == "positive"
        # Should still proceed with analysis despite non-target language
    
    @pytest_asyncio.async_test
    async def test_analyze_text_error(self):
        """Test error handling in text analysis."""
        mock_preprocessor = AsyncMock()
        mock_preprocessor.preprocess_text.side_effect = Exception("Preprocessing failed")
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            with patch("sentiment_analyzer.api.endpoints.sentiment.get_preprocessor", return_value=mock_preprocessor):
                response = await client.post(
                    "/api/v1/sentiment/analyze",
                    json={"text": "This should fail"}
                )
        
        assert response.status_code == 500
        assert "Analysis failed" in response.json()["detail"]


class TestBulkAnalyzeEndpoint:
    """Test cases for the /analyze/bulk endpoint."""
    
    @pytest_asyncio.async_test
    async def test_analyze_bulk_success(self):
        """Test successful bulk text analysis."""
        mock_preprocessor = AsyncMock()
        mock_analyzer = AsyncMock()
        
        # Setup mock responses
        mock_preprocessed = PreprocessedText(
            cleaned_text="cleaned text",
            is_target_language=True
        )
        mock_preprocessor.preprocess_text.return_value = mock_preprocessed
        
        mock_result = SentimentAnalysisOutput(
            label="positive",
            confidence=0.8,
            model_version="finbert-v1.0"
        )
        mock_analyzer.analyze_sentiment.return_value = mock_result
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            with patch("sentiment_analyzer.api.endpoints.sentiment.get_preprocessor", return_value=mock_preprocessor):
                with patch("sentiment_analyzer.api.endpoints.sentiment.get_sentiment_analyzer", return_value=mock_analyzer):
                    response = await client.post(
                        "/api/v1/sentiment/analyze/bulk",
                        json={
                            "texts": [
                                {"text": "Great news!"},
                                {"text": "Bad news!"}
                            ]
                        }
                    )
        
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 2
        assert all(result["label"] == "positive" for result in results)
    
    @pytest_asyncio.async_test
    async def test_analyze_bulk_partial_failure(self):
        """Test bulk analysis with some failures."""
        mock_preprocessor = AsyncMock()
        mock_analyzer = AsyncMock()
        
        # First call succeeds, second fails
        mock_preprocessor.preprocess_text.side_effect = [
            PreprocessedText(cleaned_text="cleaned", is_target_language=True),
            Exception("Preprocessing failed")
        ]
        
        mock_result = SentimentAnalysisOutput(
            label="positive",
            confidence=0.8,
            model_version="finbert-v1.0"
        )
        mock_analyzer.analyze_sentiment.return_value = mock_result
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            with patch("sentiment_analyzer.api.endpoints.sentiment.get_preprocessor", return_value=mock_preprocessor):
                with patch("sentiment_analyzer.api.endpoints.sentiment.get_sentiment_analyzer", return_value=mock_analyzer):
                    response = await client.post(
                        "/api/v1/sentiment/analyze/bulk",
                        json={
                            "texts": [
                                {"text": "Great news!"},
                                {"text": "This will fail"}
                            ]
                        }
                    )
        
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 2
        assert results[0]["label"] == "positive"
        assert results[1]["label"] == "error"


class TestEventsEndpoint:
    """Test cases for the /events endpoint."""
    
    @pytest_asyncio.async_test
    async def test_get_events_success(self):
        """Test successful retrieval of sentiment events."""
        # Mock database session and query results
        mock_session = AsyncMock()
        mock_result = MagicMock()
        
        # Create mock sentiment result ORM objects
        mock_event = SentimentResultORM(
            id=1,
            event_id=123,
            occurred_at=datetime(2025, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
            source="reddit",
            source_id="test_subreddit",
            sentiment_score=0.8,
            sentiment_label="positive",
            confidence=0.85,
            processed_at=datetime(2025, 6, 29, 12, 5, 0, tzinfo=timezone.utc),
            model_version="finbert-v1.0",
            cleaned_text="This is great news!"
        )
        
        mock_result.scalars.return_value.all.return_value = [mock_event]
        mock_session.execute.return_value = mock_result
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            with patch("sentiment_analyzer.api.endpoints.sentiment.get_db_session", return_value=mock_session):
                response = await client.get("/api/v1/sentiment/events")
        
        assert response.status_code == 200
        events = response.json()
        assert len(events) == 1
        assert events[0]["sentiment_label"] == "positive"
        assert events[0]["source"] == "reddit"
    
    @pytest_asyncio.async_test
    async def test_get_events_with_filters(self):
        """Test event retrieval with query filters."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            with patch("sentiment_analyzer.api.endpoints.sentiment.get_db_session", return_value=mock_session):
                response = await client.get(
                    "/api/v1/sentiment/events",
                    params={
                        "source": "reddit",
                        "sentiment_label": "positive",
                        "limit": 50
                    }
                )
        
        assert response.status_code == 200
        # Verify the query was called (mock_session.execute was called)
        mock_session.execute.assert_called_once()


class TestMetricsEndpoint:
    """Test cases for the /metrics endpoint."""
    
    @pytest_asyncio.async_test
    async def test_get_metrics_success(self):
        """Test successful retrieval of sentiment metrics."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        
        # Create mock sentiment metric ORM objects
        mock_metric = SentimentMetricORM(
            id=1,
            metric_timestamp=datetime(2025, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
            raw_event_source="reddit",
            raw_event_source_id="test_subreddit",
            sentiment_label="positive",
            model_version="finbert-v1.0",
            metric_name="event_count",
            metric_value=10.0
        )
        
        mock_result.scalars.return_value.all.return_value = [mock_metric]
        mock_session.execute.return_value = mock_result
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            with patch("sentiment_analyzer.api.endpoints.sentiment.get_db_session", return_value=mock_session):
                response = await client.get("/api/v1/sentiment/metrics")
        
        assert response.status_code == 200
        metrics = response.json()
        assert len(metrics) == 1
        assert metrics[0]["label"] == "positive"
        assert metrics[0]["source"] == "reddit"


class TestCursorPagination:
    """Test cases for cursor-based pagination utilities."""
    
    def test_encode_decode_cursor(self):
        """Test cursor encoding and decoding."""
        from sentiment_analyzer.api.endpoints.sentiment import encode_cursor, decode_cursor
        
        # Test data
        timestamp = datetime(2025, 6, 29, 12, 0, 0, tzinfo=timezone.utc)
        id_value = 123
        
        # Encode cursor
        cursor = encode_cursor(timestamp, id_value)
        assert isinstance(cursor, str)
        assert len(cursor) > 0
        
        # Decode cursor
        decoded_timestamp, decoded_id = decode_cursor(cursor)
        assert decoded_timestamp == timestamp
        assert decoded_id == id_value
    
    def test_decode_invalid_cursor(self):
        """Test decoding invalid cursor raises HTTPException."""
        from sentiment_analyzer.api.endpoints.sentiment import decode_cursor
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            decode_cursor("invalid_cursor")
        
        assert exc_info.value.status_code == 400
        assert "Invalid cursor" in str(exc_info.value.detail)
