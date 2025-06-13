from sqlalchemy import Column, Integer, Text, DateTime, String, Boolean, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class RawEventORM(Base):
    __tablename__ = 'raw_events'

    id = Column(Integer, primary_key=True) # Internal integer PK
    event_id = Column(String(255), nullable=True) # External string ID, mimics main ORM but is directly settable here
    source = Column(String(255), nullable=False)
    source_id = Column(String(255), nullable=True)
    content = Column(JSONB, nullable=False)
    payload = Column(JSONB, nullable=False, default={})
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed = Column(Boolean, default=False, nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    sentiment_processed_at = Column(DateTime(timezone=True), nullable=True)

    # Add a basic server_default for occurred_at for simplicity in tests
    __table_args__ = (
        {'comment': 'Stub table for raw events to satisfy FK constraints in tests.'},
    )
