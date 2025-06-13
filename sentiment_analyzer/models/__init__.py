"""
Models package for the Sentiment Analyzer service.

This package contains SQLAlchemy ORM models and Pydantic DTOs.
"""

# Ensure all ORM models are registered with the Base metadata when this package is imported.
from . import base
from . import dead_letter_event_orm
from . import sentiment_metric_orm
from . import sentiment_result_orm

# Import Base and ORM models for easy access
from .base import Base
from .dead_letter_event_orm import DeadLetterEventORM
from .sentiment_metric_orm import SentimentMetricORM
from .sentiment_result_orm import SentimentResultORM

# Import DTOs for easy access
from .dtos import (
    AnalyzeTextRequest,
    AnalyzeTextRequestItem,
    AnalyzeTextsBulkRequest,
    DeadLetterEventDTO,
    PreprocessedText,
    RawEventDTO,
    SentimentAnalysisOutput,
    SentimentMetricDTO,
    SentimentResultDTO,
)

# Define what is exported with 'from sentiment_analyzer.models import *'
__all__ = [
    # Base
    "Base",
    # ORMs
    "DeadLetterEventORM",
    "SentimentMetricORM",
    "SentimentResultORM",
    # DTOs
    "AnalyzeTextRequest",
    "AnalyzeTextRequestItem",
    "AnalyzeTextsBulkRequest",
    "DeadLetterEventDTO",
    "PreprocessedText",
    "RawEventDTO",
    "SentimentAnalysisOutput",
    "SentimentMetricDTO",
    "SentimentResultDTO",
]
