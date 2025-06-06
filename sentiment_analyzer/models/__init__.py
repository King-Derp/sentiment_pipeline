"""
Models package for the Sentiment Analyzer service.

This package contains SQLAlchemy ORM models and Pydantic DTOs.
"""

from .base import Base
from .sentiment_result_orm import SentimentResultORM
from .sentiment_metric_orm import SentimentMetricORM
from reddit_scraper.models.submission import RawEventORM # Updated import
from .dtos import (
    RawEventDTO, # Added RawEventDTO
    SentimentResultDTO,
    SentimentMetricDTO,
    AnalyzeTextRequestItem,
    AnalyzeTextRequest,
    AnalyzeTextsBulkRequest,
)
from .dead_letter_event_orm import DeadLetterEventORM

__all__ = [
    "Base",
    "SentimentResultORM",
    "SentimentMetricORM",
    "SentimentResultDTO",
    "SentimentMetricDTO",
    "AnalyzeTextRequestItem",
    "AnalyzeTextRequest",
    "AnalyzeTextsBulkRequest",
    "DeadLetterEventORM",
]
