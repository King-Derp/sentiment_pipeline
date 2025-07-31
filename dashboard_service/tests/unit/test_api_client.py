"""
Unit tests for the SentimentAPIClient.

Tests the API client functionality including error handling,
retry logic, and response parsing.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from dashboard_service.api.client import SentimentAPIClient, APIError


class TestSentimentAPIClient:
    """Test cases for SentimentAPIClient."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = SentimentAPIClient(
            base_url="http://test-api.com",
            timeout=10
        )
    
    def test_init_default_settings(self):
        """Test client initialization with default settings."""
        with patch('dashboard_service.api.client.get_settings') as mock_settings:
            mock_settings.return_value.sentiment_api_base_url = "http://default.com"
            mock_settings.return_value.sentiment_api_timeout = 30
            
            client = SentimentAPIClient()
            assert client.base_url == "http://default.com/"
            assert client.timeout == 30
    
    def test_init_custom_settings(self):
        """Test client initialization with custom settings."""
        client = SentimentAPIClient(
            base_url="http://custom.com",
            timeout=60
        )
        assert client.base_url == "http://custom.com/"
        assert client.timeout == 60
    
    @patch('dashboard_service.api.client.requests.request')
    def test_make_request_success(self, mock_request):
        """Test successful API request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"test": "data"}
        mock_request.return_value = mock_response
        
        response = self.client._make_request("GET", "test-endpoint")
        
        assert response == mock_response
        mock_request.assert_called_once()
    
    @patch('dashboard_service.api.client.requests.request')
    def test_make_request_retry_on_failure(self, mock_request):
        """Test request retry logic on failure."""
        mock_request.side_effect = [
            Exception("Connection error"),
            Exception("Connection error"),
            Mock(status_code=200)
        ]
        
        with patch('dashboard_service.api.client.asyncio.sleep'):
            response = self.client._make_request("GET", "test-endpoint", retries=2)
            
        assert mock_request.call_count == 3
    
    @patch('dashboard_service.api.client.requests.request')
    def test_make_request_api_error(self, mock_request):
        """Test API error handling."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_request.return_value = mock_response
        
        with pytest.raises(APIError) as exc_info:
            self.client._make_request("GET", "test-endpoint")
        
        assert "HTTP 500" in str(exc_info.value)
        assert exc_info.value.status_code == 500
    
    @patch('dashboard_service.api.client.requests.request')
    def test_get_events_success(self, mock_request):
        """Test successful events retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": 1,
                "event_id": 123,
                "occurred_at": "2023-01-01T12:00:00Z",
                "source": "reddit",
                "source_id": "test_post",
                "sentiment_score": 0.8,
                "sentiment_label": "positive",
                "processed_at": "2023-01-01T12:01:00Z",
                "model_version": "v1.0"
            }
        ]
        mock_request.return_value = mock_response
        
        events = self.client.get_events(limit=10)
        
        assert len(events) == 1
        assert events[0].sentiment_score == 0.8
        assert events[0].sentiment_label == "positive"
    
    @patch('dashboard_service.api.client.requests.request')
    def test_get_events_with_filters(self, mock_request):
        """Test events retrieval with filters."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_request.return_value = mock_response
        
        start_time = datetime(2023, 1, 1, 12, 0, 0)
        end_time = datetime(2023, 1, 2, 12, 0, 0)
        
        self.client.get_events(
            start_time=start_time,
            end_time=end_time,
            source="reddit",
            sentiment_label="positive",
            limit=50
        )
        
        # Verify request was made with correct parameters
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        params = call_args[1]['params']
        
        assert params['start_time'] == start_time.isoformat()
        assert params['end_time'] == end_time.isoformat()
        assert params['source'] == "reddit"
        assert params['sentiment_label'] == "positive"
        assert params['limit'] == 50
    
    @patch('dashboard_service.api.client.requests.request')
    def test_analyze_text_success(self, mock_request):
        """Test successful text analysis."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "sentiment_score": 0.7,
            "sentiment_label": "positive",
            "confidence": 0.85,
            "model_version": "v1.0",
            "sentiment_scores": {
                "positive": 0.7,
                "negative": 0.2,
                "neutral": 0.1
            }
        }
        mock_request.return_value = mock_response
        
        result = self.client.analyze_text("This is a great day!")
        
        assert result.sentiment_score == 0.7
        assert result.sentiment_label == "positive"
        assert result.confidence == 0.85
        assert result.sentiment_scores["positive"] == 0.7
    
    @patch('dashboard_service.api.client.requests.request')
    def test_health_check_success(self, mock_request):
        """Test successful health check."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": "2023-01-01T12:00:00Z"
        }
        mock_request.return_value = mock_response
        
        health = self.client.health_check()
        
        assert health["status"] == "healthy"
        assert health["version"] == "1.0.0"
