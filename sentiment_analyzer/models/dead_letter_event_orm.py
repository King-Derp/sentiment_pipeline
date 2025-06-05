"""
SQLAlchemy ORM model for the 'dead_letter_events' table.
"""

from sqlalchemy import Column, Index, Integer, String, Text, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import TIMESTAMP
from sqlalchemy.sql import func

from .base import Base


class DeadLetterEventORM(Base):
    """
    SQLAlchemy ORM model representing an event that failed processing.

    Attributes:
        id (int): Primary key, auto-incrementing.
        event_id (str): The unique identifier of the original event.
        occurred_at (datetime): Timestamp when the original event occurred.
        source (str): The origin of the original event (e.g., "reddit").
        source_id (str): A secondary identifier from the original event's source.
        event_payload (dict, optional): The full payload of the original event that failed.
        processing_component (str, optional): The component/stage where processing failed.
        error_msg (str, optional): The error message or reason for failure.
        failed_at (datetime): Timestamp when the event was recorded as a dead letter (defaults to NOW()).
    """
    __tablename__ = "dead_letter_events"

    id = Column(Integer, autoincrement=True, comment="Part of composite PK, auto-incrementing.") # primary_key=True removed, will be part of composite PK
    event_id = Column(Text, nullable=False, comment="Identifier of the original event.")
    occurred_at = Column(TIMESTAMP(timezone=True), nullable=False, comment="Timestamp of the original event.")
    source = Column(Text, nullable=False, comment="Source of the original event.")
    source_id = Column(Text, nullable=False, comment="Source-specific ID of the original event.")
    event_payload = Column(JSONB, nullable=True, comment="Payload of the original event.")
    processing_component = Column(Text, nullable=True, comment="Component where processing failed.")
    error_msg = Column(Text, nullable=True, comment="Error message detailing the failure.")
    failed_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), comment="Timestamp of failure.")

    __table_args__ = (
        Index("idx_dle_event_id_occurred_at", "event_id", "occurred_at"),
        Index("idx_dle_failed_at", "failed_at"),
        PrimaryKeyConstraint('id', 'failed_at', name='pk_dead_letter_event'),
        # TimescaleDB hypertable conversion ('failed_at') is handled by Alembic migrations
    )

    def __repr__(self) -> str:
        return (
            f"<DeadLetterEventORM(id={self.id}, event_id='{self.event_id}', "
            f"failed_at='{self.failed_at}', error='{self.error_msg[:50]}...')>"
        )
