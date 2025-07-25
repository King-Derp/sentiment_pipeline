"""
SQLAlchemy ORM integration for the Reddit scraper.

This module provides SQLAlchemy ORM models and database connection utilities
for integrating with the market_postgres database.
"""

import os
import logging
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session

logger = logging.getLogger(__name__)

# Get database connection parameters from environment variables
DB_HOST = os.environ.get("PG_HOST", "localhost")
DB_PORT = os.environ.get("PG_PORT", "5432")
DB_NAME = os.environ.get("PG_DB", "marketdb")
DB_USER = os.environ.get("PG_USER", "market_user")
# Use environment variable with a fallback to empty string to force explicit configuration
DB_PASSWORD = os.environ.get("PG_PASSWORD", "")

# Construct the database URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create the SQLAlchemy engine with connection pooling settings
engine = create_engine(
    DATABASE_URL,
    pool_size=10,           # Adjust based on application needs
    max_overflow=20,        # Allow creating additional connections when pool is full
    pool_timeout=30,        # Seconds to wait before giving up on getting a connection
    pool_recycle=1800,      # Recycle connections after 30 minutes
    pool_pre_ping=True,     # Verify connections before using them
)

# Create a scoped session factory
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

# Create base class for declarative models
Base = declarative_base()

# Define models matching the existing schema
class RawEvent(Base):
    """
    SQLAlchemy model for the raw_events table in the market_postgres database.
    
    This model matches the existing table structure with non-partitioned tables.
    """
    __tablename__ = "raw_events"
    
    id = Column(Integer, primary_key=True)
    source = Column(String, nullable=False)
    source_id = Column(String, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    payload = Column(JSONB, nullable=False)
    ingested_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processed = Column(Boolean, nullable=False, default=False)
    
    def __repr__(self):
        return f"<RawEvent(id={self.id}, source='{self.source}', source_id='{self.source_id}')>"

class SentimentScore(Base):
    """
    SQLAlchemy model for the sentiment_scores table in the market_postgres database.
    """
    __tablename__ = "sentiment_scores"
    
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, nullable=False)
    score = Column(Integer, nullable=False)
    confidence = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    def __repr__(self):
        return f"<SentimentScore(id={self.id}, event_id={self.event_id}, score={self.score})>"

# Database session context manager
def get_db():
    """
    Get a database session.
    
    This function provides a context manager for database sessions,
    ensuring that sessions are properly closed after use.
    
    Yields:
        SQLAlchemy session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    Initialize the database connection and verify the schema.
    
    This function is called during application startup to verify
    that the database connection is working and the schema is compatible.
    
    Returns:
        bool: True if initialization was successful, False otherwise
    """
    try:
        # Create a session to test the connection
        db = SessionLocal()
        
        # Check if the raw_events table exists
        result = db.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'raw_events');"))
        table_exists = result.scalar()
        
        if not table_exists:
            logger.error("raw_events table does not exist in the market_postgres database!")
            return False
        
        # Check the table structure to ensure compatibility
        result = db.execute(text("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'raw_events' AND table_schema = 'public'
        ORDER BY ordinal_position;
        """))
        columns = result.fetchall()
        column_names = [col[0] for col in columns]
        logger.info(f"Found columns in raw_events: {', '.join(column_names)}")
        
        # Check for required columns
        required_columns = ['id', 'source', 'source_id', 'occurred_at', 'payload']
        missing_columns = [col for col in required_columns if col not in column_names]
        
        if missing_columns:
            logger.error(f"raw_events table is missing required columns: {missing_columns}")
            return False
        
        logger.info("Database connection and schema verification successful")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        logger.error("Database initialization error details:", exc_info=True)
        return False
    finally:
        db.close()
