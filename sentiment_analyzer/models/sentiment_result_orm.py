"""
SQLAlchemy ORM model for the 'sentiment_results' table.
"""

from sqlalchemy import Column, Float, ForeignKeyConstraint, Index, Integer, BigInteger, String, UniqueConstraint
from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy import Text
from sqlalchemy import TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy.dialects.postgresql import JSONB  # Add import for JSONB type

from .base import Base


class SentimentResultORM(Base):
    """
    SQLAlchemy ORM model representing an individual sentiment analysis result.

    Attributes:
        id (int): Primary key, auto-incrementing.
        event_id (int): The unique identifier of the event from its source (e.g., Reddit's base36 ID).
                        Part of the foreign key to `raw_events`.
        occurred_at (datetime): The timestamp when the event originally occurred.
                                Part of the foreign key to `raw_events`.
        source (str): The origin of the data (e.g., "reddit").
        source_id (str): A secondary identifier from the source (e.g., subreddit name).
        sentiment_score (float): The calculated sentiment score (e.g., from -1.0 to 1.0).
        sentiment_label (str): The categorical sentiment label (e.g., "positive", "negative", "neutral").
        confidence (float, optional): The confidence level of the sentiment prediction, if available.
        processed_at (datetime): Timestamp when the sentiment analysis was performed (defaults to NOW()).
        model_version (str): Version of the sentiment analysis model used.
        raw_text (str, optional): The original text that was analyzed.
        sentiment_scores_json (JSON object, optional): JSON object of scores for all sentiment classes.
    """
    __tablename__ = "sentiment_results"

    id = Column(BigInteger, nullable=False, autoincrement=True, comment="Unique identifier for the sentiment result.")
    event_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Identifier of the original event. Logically references raw_events.id (BIGINT). Not an enforced FK due to TimescaleDB limitations.")
    occurred_at = Column(TIMESTAMP(timezone=True), nullable=False, comment="Timestamp when the event originally occurred.")
    source = Column(Text, nullable=False, comment="The origin of the data (e.g., 'reddit').")
    source_id = Column(Text, nullable=False, comment="A secondary identifier from the source (e.g., subreddit name).")
    sentiment_score = Column(Float, nullable=False, comment="The calculated sentiment score.")
    sentiment_label = Column(Text, nullable=False, comment="The categorical sentiment label.")
    confidence = Column(Float, nullable=True, comment="Confidence level of the sentiment prediction.")
    sentiment_scores_json = Column(JSONB, nullable=True, comment="JSON object of scores for all sentiment classes.")
    processed_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), comment="Timestamp of sentiment processing.")
    model_version = Column(Text, nullable=False, comment="Version of the sentiment analysis model used.")
    raw_text = Column(Text, nullable=True, comment="The original text that was analyzed.")

    __table_args__ = (
        PrimaryKeyConstraint("id", "processed_at", name="pk_sentiment_result"),
        UniqueConstraint("event_id", "occurred_at", "processed_at", name="uq_sentiment_result_event_occurred_processed_at"),
        Index("idx_sentiment_result_src_time", "source", "occurred_at"),
        Index("idx_sentiment_result_label_time", "sentiment_label", "occurred_at"),
        Index("idx_sentiment_result_event_id_occurred_at", "event_id", "occurred_at"), # For FK lookups and uniqueness
    )

    def __repr__(self) -> str:
        return (
            f"<SentimentResultORM(id={self.id}, event_id='{self.event_id}', "
            f"occurred_at='{self.occurred_at}', label='{self.sentiment_label}')>"
        )
