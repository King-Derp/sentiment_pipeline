"""Data models for generic raw events from various sources."""

from typing import TypedDict, Optional, Dict, Any
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, BigInteger, Text, func, Index, PrimaryKeyConstraint, Identity, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import expression
from sqlalchemy.sql.sqltypes import TIMESTAMP
from datetime import datetime


class Base(DeclarativeBase):
    pass


class RawEventORM(Base):
    """
    SQLAlchemy ORM model for generic raw events from various sources.
    This table will store raw event data before processing.
    Schema (as defined by Alembic migration 2dde641de514):
      id            BIGINT,  -- Part of composite PK
      source        TEXT NOT NULL,
      source_id     TEXT NOT NULL,
      occurred_at   TIMESTAMPTZ NOT NULL, -- Part of composite PK & unique constraint
      payload       JSONB NOT NULL,
      ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
      processed     BOOLEAN NOT NULL DEFAULT false
    Primary Key: (id, occurred_at)
    Unique Constraint: (source, source_id, occurred_at)
    """
    __tablename__ = "raw_events"

    # Columns
    id: Mapped[int] = mapped_column(BigInteger, Identity(start=1, cycle=False), primary_key=True, comment="Auto-incrementing ID, part of composite PK")
    source: Mapped[str] = mapped_column(Text, nullable=False, comment="Source system of the event (e.g., 'reddit', 'twitter')")
    source_id: Mapped[str] = mapped_column(Text, nullable=False, comment="Unique identifier of the event within the source system") # Removed unique=True
    occurred_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), primary_key=True, nullable=False, comment="Timestamp when the event originally occurred, part of composite PK")
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, comment="Full event payload as JSON")
    ingested_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), comment="Timestamp when the event was ingested into the system")

    # Fields for sentiment analysis processing state
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=expression.false(), index=True, comment="Flag indicating if sentiment analysis has been performed on this event")
    processed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True, comment="Timestamp when sentiment analysis was completed for this event")

    __table_args__ = (
        # PrimaryKeyConstraint('id', 'occurred_at'), # SQLAlchemy infers composite PK from multiple primary_key=True columns
        UniqueConstraint('source', 'source_id', 'occurred_at', name='uq_raw_events_source_source_id_occurred_at'),
        Index('ix_raw_events_occurred_at', 'occurred_at'),
        # Optional: Index for common queries if source and source_id are often queried together without occurred_at
        # Index('ix_raw_events_source_source_id', 'source', 'source_id'), 
        Index('ix_raw_events_processed_occurred_at', 'processed', 'occurred_at', postgresql_where=(expression.column('processed') == False)), # Index for sentiment analysis fetcher
        {'comment': 'Stores raw event data from various sources. Partitioned by occurred_at.'}
    )

    def __repr__(self) -> str:
        return f"<RawEventORM(id={self.id}, source='{self.source}', source_id='{self.source_id}', occurred_at='{self.occurred_at}')>"


class SubmissionRecord(TypedDict):
    """
    TypedDict for a Reddit submission record structure.
    Ensures consistent data structure for processing and storage.
    Corresponds to the data expected by various sinks.
    """
    id: str  # Reddit's base36 ID, e.g., "t3_q4jbfq" or just "q4jbfq"
    created_utc: float  # Submission creation time (UTC) as a Unix timestamp (float)
    subreddit: str  # Subreddit name, e.g., "wallstreetbets"
    title: str  # Submission title
    selftext: Optional[str]  # Submission self-text (None if not a self-post or empty)
    author: Optional[str]  # Submission author's username (None if deleted)
    score: int  # Submission score (upvotes - downvotes)
    upvote_ratio: Optional[float]  # Ratio of upvotes to total votes (None if not available)
    num_comments: int  # Number of comments on the submission
    url: str  # Full URL to the submission on Reddit
    flair_text: Optional[str]  # Flair text (None if no flair)
    over_18: bool  # NSFW (Not Safe For Work) flag
    # Additional fields that might be present in raw data but not core to SubmissionRecord
    domain: Optional[str] = None
    permalink: Optional[str] = None
    gilded: Optional[int] = None
    is_video: Optional[bool] = None
    is_original_content: Optional[bool] = None
    # The 'payload' field from PRAW Submission object can be stored here if needed
    # For example, if we want to keep the entire raw PRAW object for later re-processing
    payload_praw: Optional[Dict[str, Any]] = None  # Example if PRAW object itself is needed
