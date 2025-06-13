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
    Many fields are optional here so that lightweight unit tests can instantiate
    the object without specifying the full real schema.
    """
    id: int
    # The external/event‐source identifier (e.g. Reddit base36 id). Optional in tests.
    event_id: Optional[str] = None  # noqa: A003  # allow shadowing built-in names in pydantic models
    occurred_at: Optional[datetime] = None
    source: Optional[str] = None
    source_id: Optional[str] = None
    # Raw JSON payload from the source. Optional for unit tests that only need a `content` field.
    payload: Optional[Dict[str, Any]] = None
    # Convenience alias used in some legacy tests – treated as the raw text payload.
    # Changed to Optional[Any] to handle cases where ORM's JSONB content is a dict.
    content: Optional[Any] = None

    # Metadata columns – optional for unit tests.
    ingested_at: Optional[datetime] = None
    processed: bool = False
    processed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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

    All fields are optional/nullable so unit tests can create minimal instances.
    """
    original_text: Optional[str] = None
    cleaned_text: Optional[str] = None
    detected_language_code: Optional[str] = None  # e.g., 'en', 'es'
    detected_language_confidence: Optional[float] = None
    is_target_language: bool = True

    model_config = {"from_attributes": True}


class SentimentAnalysisOutput(BaseModel):
    """
    DTO for the output of the sentiment analysis step.
    """
    label: str  # e.g., 'positive', 'negative', 'neutral'
    confidence: float  # Probability of the predicted label
    scores: Optional[Dict[str, float]] = None  # May be omitted in simple tests
    model_version: Optional[str] = None

    model_config = {"from_attributes": True}


class AnalyzeTextsBulkRequest(BaseModel):
    """
    Request model for analyzing a batch of texts.
    """
    texts: List[AnalyzeTextRequestItem] = Field(..., min_items=1, description="A list of text items to analyze.")


class DeadLetterEventDTO(BaseModel):
    """
    DTO for events that failed processing and were moved to the dead-letter queue.

    Mirrors DeadLetterEventORM.
    """
    id: int
    raw_event_id: int
    error_message: str
    failed_stage: str
    failed_at: datetime
    raw_event_content: Optional[Dict[str, Any]] = None # Store original content if possible

    model_config = {"from_attributes": True}
