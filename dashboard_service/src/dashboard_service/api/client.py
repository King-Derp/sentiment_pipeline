"""
HTTP client for sentiment analyzer API integration.

This module provides a client for interacting with the existing sentiment_analyzer
API endpoints, including error handling, retry logic, and response caching.
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

import httpx
import requests
from loguru import logger
from pydantic import BaseModel

from ..config import get_settings


class SentimentResultResponse(BaseModel):
    """Response model for sentiment analysis results."""
    id: int
    event_id: int
    occurred_at: datetime
    source: str
    source_id: str
    sentiment_score: float
    sentiment_label: str
    sentiment_scores_json: Optional[Dict[str, float]] = None
    confidence: Optional[float] = None
    processed_at: datetime
    model_version: str
    raw_text: Optional[str] = None


class SentimentMetricResponse(BaseModel):
    """Response model for sentiment metrics."""
    time_bucket: datetime
    source: str
    source_id: str
    label: str
    count: int
    avg_score: float


class AnalyzeTextRequest(BaseModel):
    """Request model for text analysis."""
    text: str


class AnalyzeTextResponse(BaseModel):
    """Response model for text analysis."""
    sentiment_score: float
    sentiment_label: str
    confidence: float
    model_version: str
    sentiment_scores: Dict[str, float]


class APIError(Exception):
    """Custom exception for API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class SentimentAPIClient:
    """
    HTTP client for sentiment analyzer API.
    
    Provides methods to interact with all available sentiment analyzer endpoints
    with proper error handling, retry logic, and response validation.
    """
    
    def __init__(self, base_url: Optional[str] = None, timeout: Optional[int] = None):
        """
        Initialize the API client.
        
        Args:
            base_url: Base URL for the sentiment analyzer API
            timeout: Request timeout in seconds
        """
        settings = get_settings()
        self.base_url = base_url or settings.sentiment_api_base_url
        self.timeout = timeout or settings.sentiment_api_timeout
        
        # Ensure base URL ends with /
        if not self.base_url.endswith('/'):
            self.base_url += '/'
            
        logger.info(f"Initialized SentimentAPIClient with base_url: {self.base_url}")
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        retries: int = 3
    ) -> requests.Response:
        """
        Make HTTP request with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            json_data: JSON request body
            retries: Number of retry attempts
            
        Returns:
            requests.Response: HTTP response
            
        Raises:
            APIError: If request fails after all retries
        """
        url = urljoin(self.base_url, endpoint)
        
        for attempt in range(retries + 1):
            try:
                logger.debug(f"Making {method} request to {url} (attempt {attempt + 1})")
                
                response = requests.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    logger.debug(f"Request successful: {method} {url}")
                    return response
                elif response.status_code == 429:  # Rate limit
                    if attempt < retries:
                        wait_time = 2 ** attempt  # Exponential backoff
                        logger.warning(f"Rate limited, waiting {wait_time}s before retry")
                        asyncio.sleep(wait_time)
                        continue
                    else:
                        raise APIError(f"Rate limited: {response.text}", response.status_code)
                else:
                    raise APIError(f"HTTP {response.status_code}: {response.text}", response.status_code)
                    
            except requests.exceptions.RequestException as e:
                if attempt < retries:
                    wait_time = 2 ** attempt
                    logger.warning(f"Request failed, retrying in {wait_time}s: {str(e)}")
                    asyncio.sleep(wait_time)
                    continue
                else:
                    raise APIError(f"Request failed after {retries} retries: {str(e)}")
        
        raise APIError(f"Request failed after {retries} retries")
    
    def get_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        source: Optional[str] = None,
        source_id: Optional[str] = None,
        sentiment_label: Optional[str] = None,
        limit: int = 100,
        cursor: Optional[str] = None
    ) -> List[SentimentResultResponse]:
        """
        Retrieve sentiment analysis results with filtering and pagination.
        
        Args:
            start_time: Filter events after this timestamp
            end_time: Filter events before this timestamp  
            source: Filter by event source
            source_id: Filter by source ID
            sentiment_label: Filter by sentiment label
            limit: Maximum number of results (1-1000)
            cursor: Pagination cursor
            
        Returns:
            List[SentimentResultResponse]: List of sentiment results
            
        Raises:
            APIError: If request fails
        """
        params = {"limit": limit}
        
        if start_time:
            params["start_time"] = start_time.isoformat()
        if end_time:
            params["end_time"] = end_time.isoformat()
        if source:
            params["source"] = source
        if source_id:
            params["source_id"] = source_id
        if sentiment_label:
            params["sentiment_label"] = sentiment_label
        if cursor:
            params["cursor"] = cursor
            
        response = self._make_request("GET", "api/v1/sentiment/events", params=params)
        
        try:
            data = response.json()
            return [SentimentResultResponse(**item) for item in data]
        except Exception as e:
            raise APIError(f"Failed to parse events response: {str(e)}")
    
    def get_metrics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        time_bucket_size: str = "hour",
        source: Optional[str] = None,
        source_id: Optional[str] = None,
        sentiment_label: Optional[str] = None,
        limit: int = 100,
        cursor: Optional[str] = None
    ) -> List[SentimentMetricResponse]:
        """
        Retrieve aggregated sentiment metrics with filtering and pagination.
        
        Args:
            start_time: Filter metrics after this timestamp
            end_time: Filter metrics before this timestamp
            time_bucket_size: Time bucket size (hour, day, week)
            source: Filter by event source
            source_id: Filter by source ID
            sentiment_label: Filter by sentiment label
            limit: Maximum number of results (1-1000)
            cursor: Pagination cursor
            
        Returns:
            List[SentimentMetricResponse]: List of sentiment metrics
            
        Raises:
            APIError: If request fails
        """
        params = {
            "limit": min(limit, 1000),
            "time_bucket_size": time_bucket_size
        }
        
        if start_time:
            params["start_time"] = start_time.isoformat()
        if end_time:
            params["end_time"] = end_time.isoformat()
        if source:
            params["source"] = source
        if source_id:
            params["source_id"] = source_id
        if sentiment_label:
            params["sentiment_label"] = sentiment_label
        if cursor:
            params["cursor"] = cursor
            
        response = self._make_request("GET", "api/v1/sentiment/metrics", params=params)
        
        try:
            data = response.json()
            return [SentimentMetricResponse(**item) for item in data]
        except Exception as e:
            raise APIError(f"Failed to parse metrics response: {str(e)}")
    
    def analyze_text(self, text: str) -> AnalyzeTextResponse:
        """
        Analyze sentiment of a single text input.
        
        Args:
            text: Text to analyze
            
        Returns:
            AnalyzeTextResponse: Sentiment analysis results
            
        Raises:
            APIError: If request fails
        """
        request_data = AnalyzeTextRequest(text=text)
        response = self._make_request("POST", "api/v1/sentiment/analyze", json_data=request_data.dict())
        
        try:
            data = response.json()
            return AnalyzeTextResponse(**data)
        except Exception as e:
            raise APIError(f"Failed to parse analyze response: {str(e)}")
    
    def analyze_texts_bulk(self, texts: List[str]) -> List[AnalyzeTextResponse]:
        """
        Analyze sentiment of multiple texts in a single request.
        
        Args:
            texts: List of texts to analyze
            
        Returns:
            List[AnalyzeTextResponse]: List of sentiment analysis results
            
        Raises:
            APIError: If request fails
        """
        request_data = {"texts": [{"text": text} for text in texts]}
        response = self._make_request("POST", "api/v1/sentiment/analyze/bulk", json_data=request_data)
        
        try:
            data = response.json()
            return [AnalyzeTextResponse(**item) for item in data]
        except Exception as e:
            raise APIError(f"Failed to parse bulk analyze response: {str(e)}")
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check API health status.
        
        Returns:
            Dict[str, Any]: Health status information
            
        Raises:
            APIError: If request fails
        """
        try:
            response = self._make_request("GET", "health", retries=1)
            return response.json()
        except Exception as e:
            raise APIError(f"Health check failed: {str(e)}")
