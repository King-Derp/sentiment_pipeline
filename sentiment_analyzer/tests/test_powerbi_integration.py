"""
Unit tests for PowerBI integration.

Tests the PowerBI client for streaming sentiment analysis results.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import json

import httpx
import pytest_asyncio
from httpx import Response

from sentiment_analyzer.integrations.powerbi import PowerBIClient, PowerBIRowData
from sentiment_analyzer.models.dtos import SentimentResultDTO


class TestPowerBIRowData:
    """Test cases for PowerBIRowData model."""
    
    def test_model_dump_json_compatible(self):
        """Test JSON-compatible model dumping."""
        row_data = PowerBIRowData(
            event_id="test_123",
            occurred_at=datetime(2025, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
            processed_at=datetime(2025, 6, 29, 12, 5, 0, tzinfo=timezone.utc),
            source="reddit",
            source_id="test_subreddit",
            sentiment_score=0.8,
            sentiment_label="positive",
            confidence=0.85,
            model_version="finbert-v1.0"
        )
        
        json_data = row_data.model_dump_json_compatible()
        
        assert json_data["event_id"] == "test_123"
        assert json_data["source"] == "reddit"
        assert json_data["sentiment_score"] == 0.8
        assert json_data["sentiment_label"] == "positive"
        assert json_data["confidence"] == 0.85
        assert json_data["model_version"] == "finbert-v1.0"
        
        # Check datetime conversion
        assert json_data["occurred_at"] == "2025-06-29T12:00:00+00:00"
        assert json_data["processed_at"] == "2025-06-29T12:05:00+00:00"


class TestPowerBIClient:
    """Test cases for PowerBIClient."""
    
    @pytest_asyncio.async_test
    async def test_client_initialization(self):
        """Test PowerBI client initialization."""
        client = PowerBIClient(
            push_url="https://api.powerbi.com/beta/test/datasets/123/rows",
            api_key="test_key",
            max_retries=2,
            batch_size=50
        )
        
        assert client.push_url == "https://api.powerbi.com/beta/test/datasets/123/rows"
        assert client.api_key == "test_key"
        assert client.max_retries == 2
        assert client.batch_size == 50
        assert len(client._batch_queue) == 0
        
        await client.close()
    
    @pytest_asyncio.async_test
    async def test_push_row_success(self):
        """Test successful single row push."""
        # Create mock HTTP client
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        
        mock_http_client = AsyncMock()
        mock_http_client.post.return_value = mock_response
        
        client = PowerBIClient(
            push_url="https://api.powerbi.com/test",
            batch_size=1  # Force immediate flush
        )
        client.client = mock_http_client
        
        # Create test sentiment result
        sentiment_result = SentimentResultDTO(
            id=1,
            event_id="test_123",
            occurred_at=datetime(2025, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
            processed_at=datetime(2025, 6, 29, 12, 5, 0, tzinfo=timezone.utc),
            source="reddit",
            source_id="test_subreddit",
            sentiment_score=0.8,
            sentiment_label="positive",
            confidence=0.85,
            model_version="finbert-v1.0"
        )
        
        # Test push_row
        result = await client.push_row(sentiment_result)
        
        assert result is True
        mock_http_client.post.assert_called_once()
        
        # Verify the payload structure
        call_args = mock_http_client.post.call_args
        assert call_args[0][0] == "https://api.powerbi.com/test"
        payload = call_args[1]["json"]
        assert "rows" in payload
        assert len(payload["rows"]) == 1
        assert payload["rows"][0]["event_id"] == "test_123"
        
        await client.close()
    
    @pytest_asyncio.async_test
    async def test_push_row_batching(self):
        """Test row batching functionality."""
        mock_http_client = AsyncMock()
        
        client = PowerBIClient(
            push_url="https://api.powerbi.com/test",
            batch_size=3  # Batch size of 3
        )
        client.client = mock_http_client
        
        # Create test sentiment results
        sentiment_results = []
        for i in range(2):  # Add 2 rows (less than batch size)
            result = SentimentResultDTO(
                id=i,
                event_id=f"test_{i}",
                occurred_at=datetime(2025, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
                processed_at=datetime(2025, 6, 29, 12, 5, 0, tzinfo=timezone.utc),
                source="reddit",
                source_id="test_subreddit",
                sentiment_score=0.8,
                sentiment_label="positive",
                model_version="finbert-v1.0"
            )
            sentiment_results.append(result)
        
        # Push 2 rows - should not trigger HTTP call yet
        for result in sentiment_results:
            await client.push_row(result)
        
        # No HTTP calls should have been made yet
        mock_http_client.post.assert_not_called()
        assert len(client._batch_queue) == 2
        
        await client.close()
    
    @pytest_asyncio.async_test
    async def test_push_rows_bulk(self):
        """Test bulk row pushing."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        
        mock_http_client = AsyncMock()
        mock_http_client.post.return_value = mock_response
        
        client = PowerBIClient(
            push_url="https://api.powerbi.com/test",
            batch_size=2
        )
        client.client = mock_http_client
        
        # Create test sentiment results
        sentiment_results = []
        for i in range(3):
            result = SentimentResultDTO(
                id=i,
                event_id=f"test_{i}",
                occurred_at=datetime(2025, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
                processed_at=datetime(2025, 6, 29, 12, 5, 0, tzinfo=timezone.utc),
                source="reddit",
                source_id="test_subreddit",
                sentiment_score=0.8,
                sentiment_label="positive",
                model_version="finbert-v1.0"
            )
            sentiment_results.append(result)
        
        # Test push_rows
        result = await client.push_rows(sentiment_results)
        
        assert result is True
        # Should make 2 HTTP calls (batch size 2: first 2 rows, then 1 row)
        assert mock_http_client.post.call_count == 2
        
        await client.close()
    
    @pytest_asyncio.async_test
    async def test_retry_on_rate_limit(self):
        """Test retry logic on rate limiting (429 status)."""
        # First call returns 429, second call succeeds
        mock_responses = [
            MagicMock(spec=Response, status_code=429),
            MagicMock(spec=Response, status_code=200)
        ]
        
        mock_http_client = AsyncMock()
        mock_http_client.post.side_effect = mock_responses
        
        client = PowerBIClient(
            push_url="https://api.powerbi.com/test",
            max_retries=2,
            retry_delay=0.1  # Short delay for testing
        )
        client.client = mock_http_client
        
        # Create test data
        test_batch = [
            PowerBIRowData(
                event_id="test_123",
                occurred_at=datetime(2025, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
                processed_at=datetime(2025, 6, 29, 12, 5, 0, tzinfo=timezone.utc),
                source="reddit",
                source_id="test_subreddit",
                sentiment_score=0.8,
                sentiment_label="positive",
                model_version="finbert-v1.0"
            )
        ]
        
        # Test retry logic
        result = await client._send_batch(test_batch)
        
        assert result is True
        assert mock_http_client.post.call_count == 2
        
        await client.close()
    
    @pytest_asyncio.async_test
    async def test_max_retries_exceeded(self):
        """Test behavior when max retries are exceeded."""
        # All calls return 500 error
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        
        mock_http_client = AsyncMock()
        mock_http_client.post.return_value = mock_response
        
        client = PowerBIClient(
            push_url="https://api.powerbi.com/test",
            max_retries=1,
            retry_delay=0.1
        )
        client.client = mock_http_client
        
        # Create test data
        test_batch = [
            PowerBIRowData(
                event_id="test_123",
                occurred_at=datetime(2025, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
                processed_at=datetime(2025, 6, 29, 12, 5, 0, tzinfo=timezone.utc),
                source="reddit",
                source_id="test_subreddit",
                sentiment_score=0.8,
                sentiment_label="positive",
                model_version="finbert-v1.0"
            )
        ]
        
        # Test max retries
        result = await client._send_batch(test_batch)
        
        assert result is False
        assert mock_http_client.post.call_count == 2  # Initial + 1 retry
        
        await client.close()
    
    @pytest_asyncio.async_test
    async def test_timeout_handling(self):
        """Test timeout handling."""
        mock_http_client = AsyncMock()
        mock_http_client.post.side_effect = httpx.TimeoutException("Request timeout")
        
        client = PowerBIClient(
            push_url="https://api.powerbi.com/test",
            max_retries=1,
            retry_delay=0.1
        )
        client.client = mock_http_client
        
        # Create test data
        test_batch = [
            PowerBIRowData(
                event_id="test_123",
                occurred_at=datetime(2025, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
                processed_at=datetime(2025, 6, 29, 12, 5, 0, tzinfo=timezone.utc),
                source="reddit",
                source_id="test_subreddit",
                sentiment_score=0.8,
                sentiment_label="positive",
                model_version="finbert-v1.0"
            )
        ]
        
        # Test timeout handling
        result = await client._send_batch(test_batch)
        
        assert result is False
        assert mock_http_client.post.call_count == 2  # Initial + 1 retry
        
        await client.close()
    
    @pytest_asyncio.async_test
    async def test_test_connection_success(self):
        """Test successful connection test."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        
        mock_http_client = AsyncMock()
        mock_http_client.post.return_value = mock_response
        
        client = PowerBIClient(push_url="https://api.powerbi.com/test")
        client.client = mock_http_client
        
        result = await client.test_connection()
        
        assert result is True
        mock_http_client.post.assert_called_once_with(
            "https://api.powerbi.com/test",
            json={"rows": []}
        )
        
        await client.close()
    
    @pytest_asyncio.async_test
    async def test_test_connection_failure(self):
        """Test connection test failure."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 401
        
        mock_http_client = AsyncMock()
        mock_http_client.post.return_value = mock_response
        
        client = PowerBIClient(push_url="https://api.powerbi.com/test")
        client.client = mock_http_client
        
        result = await client.test_connection()
        
        assert result is False
        
        await client.close()
    
    @pytest_asyncio.async_test
    async def test_flush_batch(self):
        """Test manual batch flushing."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        
        mock_http_client = AsyncMock()
        mock_http_client.post.return_value = mock_response
        
        client = PowerBIClient(
            push_url="https://api.powerbi.com/test",
            batch_size=10  # Large batch size to prevent auto-flush
        )
        client.client = mock_http_client
        
        # Add some data to the batch queue
        sentiment_result = SentimentResultDTO(
            id=1,
            event_id="test_123",
            occurred_at=datetime(2025, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
            processed_at=datetime(2025, 6, 29, 12, 5, 0, tzinfo=timezone.utc),
            source="reddit",
            source_id="test_subreddit",
            sentiment_score=0.8,
            sentiment_label="positive",
            model_version="finbert-v1.0"
        )
        
        await client.push_row(sentiment_result)
        
        # Verify no HTTP call yet
        mock_http_client.post.assert_not_called()
        
        # Manually flush
        result = await client.flush_batch()
        
        assert result is True
        mock_http_client.post.assert_called_once()
        assert len(client._batch_queue) == 0
        
        await client.close()
