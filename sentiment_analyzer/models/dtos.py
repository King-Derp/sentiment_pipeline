"""
Pydantic Data Transfer Objects (DTOs) for the Sentiment Analyzer service.

These models are used for API request/response validation and internal data transfer.
"""

from datetime import datetime
from typing import List, Optional, Dict # Added Dict

from pydantic import BaseModel, Field, Json
from typing import Any # Added for RawEventDTO payload


class RawEventDTO(BaseModel):
    """
    DTO for raw event data, typically sourced from scrapers.

    Mirrors RawEventORM and is used for data transfer, especially for the Data Fetcher.
    """
    id: int
    event_id: str
    occurred_at: datetime
    source: str
    source_id: Optional[str] = None
    payload: Dict[str, Any]
    ingested_at: datetime
    processed: bool = False
    processed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SentimentResultDTO(BaseModel):
    """
    DTO for sentiment analysis results.

    Mirrors SentimentResultORM but is used for API responses and internal data transfer.
    """
    id: int
    event_id: str
    occurred_at: datetime
    source: str
    source_id: str
    sentiment_score: float
    sentiment_label: str
    confidence: Optional[float] = None
    processed_at: datetime
    model_version: str
    raw_text: Optional[str] = None

    model_config = {"from_attributes": True}


class SentimentMetricDTO(BaseModel):
    """
    DTO for aggregated sentiment metrics.

    Mirrors SentimentMetricORM and is used for API responses.
    """
    time_bucket: datetime
    source: str
    source_id: str
    label: str
    count: int
    avg_score: float

    model_config = {"from_attributes": True}


class AnalyzeTextRequestItem(BaseModel):
    """
    Individual item for a bulk text analysis request.
    """
    text: str = Field(..., min_length=1, description="The text content to analyze.")
    event_id: Optional[str] = Field(None, description="Optional unique identifier for the event/text.")
    source: Optional[str] = Field(None, description="Optional source of the text (e.g., 'user_input', 'reddit').")
    source_id: Optional[str] = Field(None, description="Optional identifier within the source (e.g., 'user_id_123', 'subreddit_name').")
    occurred_at: Optional[datetime] = Field(None, description="Optional timestamp of when the original event/text occurred.")


class AnalyzeTextRequest(AnalyzeTextRequestItem):
    """
    Request model for analyzing a single piece of text.
    Inherits fields from AnalyzeTextRequestItem.
    """
    pass


class PreprocessedText(BaseModel):
    """
    DTO for the output of the text preprocessing step.
    """
    original_text: str
    cleaned_text: str
    detected_language_code: str  # e.g., 'en', 'es'
    detected_language_confidence: Optional[float] = None
    is_target_language: bool

    model_config = {"from_attributes": True}


class SentimentAnalysisOutput(BaseModel):
    """
    DTO for the output of the sentiment analysis step.
    """
    label: str  # e.g., 'positive', 'negative', 'neutral'
    confidence: float  # Probability of the predicted label
    scores: Dict[str, float]  # Probabilities for all labels, e.g., {"positive": 0.7, "negative": 0.1, "neutral": 0.2}
    model_version: str

    model_config = {"from_attributes": True}


class AnalyzeTextsBulkRequest(BaseModel):
    """
    Request model for analyzing a batch of texts.
    """
    texts: List[AnalyzeTextRequestItem] = Field(..., min_items=1, description="A list of text items to analyze.")

