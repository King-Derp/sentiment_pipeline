"""
Integration tests for the complete API workflow.

Tests the full end-to-end functionality of the sentiment analyzer API,
including database interactions and component integration.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import json

from fastapi.testclient import TestClient
from httpx import AsyncClient
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from sentiment_analyzer.api.main import app
from sentiment_analyzer.models.dtos import (
    AnalyzeTextRequest,
    SentimentAnalysisOutput,
    PreprocessedText,
)
from sentiment_analyzer.models.sentiment_result_orm import SentimentResultORM
from sentiment_analyzer.models.sentiment_metric_orm import SentimentMetricORM


class TestAPIIntegration:
    """Integration tests for the complete API workflow."""
    
    @pytest_asyncio.async_test
    async def test_complete_analysis_workflow(self):
        """Test the complete sentiment analysis workflow from API to database."""
        # Mock all dependencies
        mock_session = AsyncMock(spec=AsyncSession)
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
        
        # Test the complete workflow
        async with AsyncClient(app=app, base_url="http://test") as client:
            with patch("sentiment_analyzer.api.endpoints.sentiment.get_preprocessor", return_value=mock_preprocessor):
                with patch("sentiment_analyzer.api.endpoints.sentiment.get_sentiment_analyzer", return_value=mock_analyzer):
                    response = await client.post(
                        "/api/v1/sentiment/analyze",
                        json={"text": "This is great news!"}
                    )
        
        # Verify response
        assert response.status_code == 200
        result = response.json()
        assert result["label"] == "positive"
        assert result["confidence"] == 0.85
        assert result["model_version"] == "finbert-v1.0"
        assert "scores" in result
        
        # Verify component interactions
        mock_preprocessor.preprocess_text.assert_called_once_with("This is great news!")
        mock_analyzer.analyze_sentiment.assert_called_once_with("This is great news!")
    
    @pytest_asyncio.async_test
    async def test_bulk_analysis_workflow(self):
        """Test bulk analysis with multiple texts."""
        mock_preprocessor = AsyncMock()
        mock_analyzer = AsyncMock()
        
        # Setup mock responses for multiple texts
        mock_preprocessed = PreprocessedText(
            cleaned_text="cleaned text",
            is_target_language=True
        )
        mock_preprocessor.preprocess_text.return_value = mock_preprocessed
        
        mock_results = [
            SentimentAnalysisOutput(
                label="positive",
                confidence=0.8,
                model_version="finbert-v1.0"
            ),
            SentimentAnalysisOutput(
                label="negative", 
                confidence=0.7,
                model_version="finbert-v1.0"
            )
        ]
        mock_analyzer.analyze_sentiment.side_effect = mock_results
        
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
        assert results[0]["label"] == "positive"
        assert results[1]["label"] == "negative"
        
        # Verify both texts were processed
        assert mock_preprocessor.preprocess_text.call_count == 2
        assert mock_analyzer.analyze_sentiment.call_count == 2
    
    @pytest_asyncio.async_test
    async def test_events_endpoint_with_database(self):
        """Test events endpoint with database interaction."""
        # Mock database session and results
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        
        # Create mock sentiment result ORM objects
        mock_events = [
            SentimentResultORM(
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
            ),
            SentimentResultORM(
                id=2,
                event_id=124,
                occurred_at=datetime(2025, 6, 29, 13, 0, 0, tzinfo=timezone.utc),
                source="twitter",
                source_id="test_user",
                sentiment_score=-0.6,
                sentiment_label="negative",
                confidence=0.75,
                processed_at=datetime(2025, 6, 29, 13, 5, 0, tzinfo=timezone.utc),
                model_version="finbert-v1.0",
                cleaned_text="This is bad news!"
            )
        ]
        
        mock_result.scalars.return_value.all.return_value = mock_events
        mock_session.execute.return_value = mock_result
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            with patch("sentiment_analyzer.api.endpoints.sentiment.get_db_session", return_value=mock_session):
                response = await client.get("/api/v1/sentiment/events")
        
        assert response.status_code == 200
        events = response.json()
        assert len(events) == 2
        
        # Verify first event
        assert events[0]["sentiment_label"] == "positive"
        assert events[0]["source"] == "reddit"
        assert events[0]["confidence"] == 0.85
        
        # Verify second event
        assert events[1]["sentiment_label"] == "negative"
        assert events[1]["source"] == "twitter"
        assert events[1]["confidence"] == 0.75
        
        # Verify database query was executed
        mock_session.execute.assert_called_once()
    
    @pytest_asyncio.async_test
    async def test_events_endpoint_with_filters(self):
        """Test events endpoint with query filters applied."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        
        # Mock filtered results (only positive sentiment from reddit)
        mock_filtered_events = [
            SentimentResultORM(
                id=1,
                event_id=123,
                occurred_at=datetime(2025, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
                source="reddit",
                source_id="test_subreddit",
                sentiment_score=0.8,
                sentiment_label="positive",
                confidence=0.85,
                processed_at=datetime(2025, 6, 29, 12, 5, 0, tzinfo=timezone.utc),
                model_version="finbert-v1.0"
            )
        ]
        
        mock_result.scalars.return_value.all.return_value = mock_filtered_events
        mock_session.execute.return_value = mock_result
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            with patch("sentiment_analyzer.api.endpoints.sentiment.get_db_session", return_value=mock_session):
                response = await client.get(
                    "/api/v1/sentiment/events",
                    params={
                        "source": "reddit",
                        "sentiment_label": "positive",
                        "limit": 10
                    }
                )
        
        assert response.status_code == 200
        events = response.json()
        assert len(events) == 1
        assert events[0]["source"] == "reddit"
        assert events[0]["sentiment_label"] == "positive"
        
        # Verify database query was executed with filters
        mock_session.execute.assert_called_once()
    
    @pytest_asyncio.async_test
    async def test_metrics_endpoint_with_database(self):
        """Test metrics endpoint with database interaction."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        
        # Create mock sentiment metric ORM objects
        mock_metrics = [
            SentimentMetricORM(
                id=1,
                metric_timestamp=datetime(2025, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
                raw_event_source="reddit",
                raw_event_source_id="test_subreddit",
                sentiment_label="positive",
                model_version="finbert-v1.0",
                metric_name="event_count",
                metric_value=15.0
            ),
            SentimentMetricORM(
                id=2,
                metric_timestamp=datetime(2025, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
                raw_event_source="reddit",
                raw_event_source_id="test_subreddit",
                sentiment_label="negative",
                model_version="finbert-v1.0",
                metric_name="event_count",
                metric_value=5.0
            )
        ]
        
        mock_result.scalars.return_value.all.return_value = mock_metrics
        mock_session.execute.return_value = mock_result
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            with patch("sentiment_analyzer.api.endpoints.sentiment.get_db_session", return_value=mock_session):
                response = await client.get("/api/v1/sentiment/metrics")
        
        assert response.status_code == 200
        metrics = response.json()
        assert len(metrics) == 2
        
        # Verify metrics data
        assert metrics[0]["label"] == "positive"
        assert metrics[0]["source"] == "reddit"
        assert metrics[1]["label"] == "negative"
        assert metrics[1]["source"] == "reddit"
        
        # Verify database query was executed
        mock_session.execute.assert_called_once()
    
    @pytest_asyncio.async_test
    async def test_health_check_endpoint(self):
        """Test the health check endpoint."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/health")
        
        assert response.status_code == 200
        health_data = response.json()
        assert health_data["status"] == "healthy"
        assert health_data["service"] == "sentiment-analyzer"
        assert "timestamp" in health_data
        assert "version" in health_data
    
    @pytest_asyncio.async_test
    async def test_api_error_handling(self):
        """Test API error handling for various failure scenarios."""
        # Test invalid JSON input
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/sentiment/analyze",
                json={"invalid_field": "test"}  # Missing required 'text' field
            )
        
        assert response.status_code == 422  # Validation error
        error_data = response.json()
        assert "detail" in error_data
    
    @pytest_asyncio.async_test
    async def test_preprocessing_failure_handling(self):
        """Test handling of preprocessing failures."""
        mock_preprocessor = AsyncMock()
        mock_preprocessor.preprocess_text.side_effect = Exception("Preprocessing failed")
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            with patch("sentiment_analyzer.api.endpoints.sentiment.get_preprocessor", return_value=mock_preprocessor):
                response = await client.post(
                    "/api/v1/sentiment/analyze",
                    json={"text": "This should fail"}
                )
        
        assert response.status_code == 500
        error_data = response.json()
        assert "Analysis failed" in error_data["detail"]
    
    @pytest_asyncio.async_test
    async def test_sentiment_analysis_failure_handling(self):
        """Test handling of sentiment analysis failures."""
        mock_preprocessor = AsyncMock()
        mock_analyzer = AsyncMock()
        
        mock_preprocessed = PreprocessedText(
            cleaned_text="test text",
            is_target_language=True
        )
        mock_preprocessor.preprocess_text.return_value = mock_preprocessed
        mock_analyzer.analyze_sentiment.side_effect = Exception("Analysis failed")
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            with patch("sentiment_analyzer.api.endpoints.sentiment.get_preprocessor", return_value=mock_preprocessor):
                with patch("sentiment_analyzer.api.endpoints.sentiment.get_sentiment_analyzer", return_value=mock_analyzer):
                    response = await client.post(
                        "/api/v1/sentiment/analyze",
                        json={"text": "This should fail"}
                    )
        
        assert response.status_code == 500
        error_data = response.json()
        assert "Analysis failed" in error_data["detail"]
    
    @pytest_asyncio.async_test
    async def test_database_failure_handling(self):
        """Test handling of database failures in query endpoints."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.side_effect = Exception("Database connection failed")
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            with patch("sentiment_analyzer.api.endpoints.sentiment.get_db_session", return_value=mock_session):
                response = await client.get("/api/v1/sentiment/events")
        
        assert response.status_code == 500
        error_data = response.json()
        assert "Database error" in error_data["detail"]


class TestCursorPaginationIntegration:
    """Integration tests for cursor-based pagination."""
    
    @pytest_asyncio.async_test
    async def test_pagination_with_cursor(self):
        """Test pagination using cursor parameter."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        
        # Mock paginated results
        mock_events = [
            SentimentResultORM(
                id=3,
                event_id=125,
                occurred_at=datetime(2025, 6, 29, 14, 0, 0, tzinfo=timezone.utc),
                source="reddit",
                source_id="test_subreddit",
                sentiment_score=0.9,
                sentiment_label="positive",
                confidence=0.95,
                processed_at=datetime(2025, 6, 29, 14, 5, 0, tzinfo=timezone.utc),
                model_version="finbert-v1.0"
            )
        ]
        
        mock_result.scalars.return_value.all.return_value = mock_events
        mock_session.execute.return_value = mock_result
        
        # Create a valid cursor (base64 encoded JSON)
        import base64
        cursor_data = {
            "timestamp": "2025-06-29T13:00:00+00:00",
            "id": 2
        }
        cursor = base64.b64encode(json.dumps(cursor_data).encode()).decode()
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            with patch("sentiment_analyzer.api.endpoints.sentiment.get_db_session", return_value=mock_session):
                response = await client.get(
                    "/api/v1/sentiment/events",
                    params={"cursor": cursor, "limit": 10}
                )
        
        assert response.status_code == 200
        events = response.json()
        assert len(events) == 1
        
        # Verify database query was executed with cursor constraints
        mock_session.execute.assert_called_once()
    
    @pytest_asyncio.async_test
    async def test_invalid_cursor_handling(self):
        """Test handling of invalid cursor values."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/sentiment/events",
                params={"cursor": "invalid_cursor_value"}
            )
        
        assert response.status_code == 400
        error_data = response.json()
        assert "Invalid cursor" in error_data["detail"]
