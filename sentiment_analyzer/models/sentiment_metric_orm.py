"""
SQLAlchemy ORM model for the 'sentiment_metrics' table.
"""

from sqlalchemy import Column, Float, Integer, PrimaryKeyConstraint, String
from sqlalchemy import Text
from sqlalchemy import TIMESTAMP

from .base import Base


class SentimentMetricORM(Base):
    """
    SQLAlchemy ORM model representing aggregated sentiment metrics over time buckets.

    Attributes:
        time_bucket (datetime): The start of the time bucket (e.g., hourly, daily).
                                Part of the composite primary key.
        source (str): The origin of the data (e.g., "reddit").
                      Part of the composite primary key.
        source_id (str): A secondary identifier from the source (e.g., subreddit name, 'unknown').
                         Part of the composite primary key.
        label (str): The categorical sentiment label (e.g., "positive", "negative").
                     Part of the composite primary key.
        count (int): The number of sentiment results falling into this bucket and category.
        avg_score (float): The average sentiment score for this bucket and category.
    """
    __tablename__ = "sentiment_metrics"

    time_bucket = Column(TIMESTAMP(timezone=True), nullable=False, comment="Start of the time bucket.")
    source = Column(Text, nullable=False, comment="Origin of the data.")
    source_id = Column(Text, nullable=False, comment="Secondary identifier from the source (use 'unknown' if none).")
    label = Column(Text, nullable=False, comment="Categorical sentiment label.")
    count = Column(Integer, nullable=False, comment="Number of sentiment results in this bucket/category.")
    avg_score = Column(Float, nullable=False, comment="Average sentiment score for this bucket/category.")

    __table_args__ = (
        PrimaryKeyConstraint("time_bucket", "source", "source_id", "label", name="pk_sentiment_metric"),
        # TimescaleDB hypertable conversion is handled by Alembic migrations
    )

    def __repr__(self) -> str:
        return (
            f"<SentimentMetricORM(time_bucket='{self.time_bucket}', source='{self.source}', "
            f"source_id='{self.source_id}', label='{self.label}', count={self.count})>"
        )
