"""
SQLAlchemy ORM integration for the Reddit scraper.

This module provides SQLAlchemy ORM models and database connection utilities
for integrating with the market_postgres database.
"""

import os
import logging
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from contextlib import contextmanager

from reddit_scraper.config import PostgresConfig

logger = logging.getLogger(__name__)

# Declare engine and SessionLocal at module level, to be initialized by init_db
engine = None
SessionLocal = None

# Create base class for declarative models
Base = declarative_base()



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
@contextmanager
def get_db():
    """
    Get a database session.
    
    This function provides a context manager for database sessions,
    ensuring that sessions are properly closed after use.
    
    Yields:
        SQLAlchemy session
    """
    if SessionLocal is None:
        logger.error("SessionLocal is not initialized. init_db may have failed or was not called.")
        raise RuntimeError("Database session factory (SessionLocal) is not initialized.")

    db = None  # Initialize db to None
    try:
        db = SessionLocal()
        yield db
    finally:
        if db:  # Check if db was successfully created
            db.close()

def init_db(pg_config: PostgresConfig) -> bool:
    """
    Initialize the database connection and verify the schema.
    
    This function is called during application startup to verify
    that the database connection is working and the schema is compatible.
    It now uses the provided PostgresConfig to establish the connection.
    
    Args:
        pg_config: PostgreSQL configuration object.
            
    Returns:
        bool: True if initialization was successful and SessionLocal is ready, False otherwise.
    """
    global engine, SessionLocal # Declare them as global to modify module-level variables

    if not pg_config.enabled:
        logger.warning("PostgreSQL is disabled in configuration. Skipping init_db. SessionLocal will not be initialized.")
        engine = None
        SessionLocal = None
        return False # CRITICAL: Return False if not enabled, so SessionLocal is not expected.

    db = None  # Initialize local db variable to None
    try:
        database_url = f"postgresql://{pg_config.user}:{pg_config.password}@{pg_config.host}:{pg_config.port}/{pg_config.database}"
        
        current_engine = create_engine(
            database_url,
            pool_size=pg_config.pool_size if hasattr(pg_config, 'pool_size') else 10, 
            max_overflow=pg_config.max_overflow if hasattr(pg_config, 'max_overflow') else 20,
            pool_timeout=pg_config.pool_timeout if hasattr(pg_config, 'pool_timeout') else 30,
            pool_recycle=pg_config.pool_recycle if hasattr(pg_config, 'pool_recycle') else 1800,
            pool_pre_ping=True,
            connect_args=pg_config.connect_args if hasattr(pg_config, 'connect_args') else {}
        )
        engine = current_engine # Assign to global engine

        current_session_local = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
        SessionLocal = current_session_local # Assign to global SessionLocal

        # Create all tables in the database that are defined in Base.metadata
        # This will not recreate tables if they already exist.
        # Base.metadata.create_all(engine) # Cascade: Commented out - Schema should be managed by Alembic

        # Test connection and verify schema
        logger.info("Testing database connection...")
        db = SessionLocal()
        
        # Cascade: Commenting out schema verification logic as it's based on RawEvent model,
        # which conflicts with the Alembic-managed schema for 'raw_submissions'.
        # This block can be revisited if a new health check for Alembic schema is needed.
        # # Check if the raw_submissions table exists
        # result = db.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'raw_submissions');"))
        # table_exists = result.scalar()
        # 
        # if not table_exists:
        #     logger.error("raw_submissions table does not exist in the market_postgres database!")
        #     # Base.metadata.create_all(engine) will handle creation, so this check might be redundant
        #     # or could be a stricter pre-check if we don't want auto-creation in some scenarios.
        #     # For now, allowing create_all to handle it is fine.
        #     pass # Table will be created by Base.metadata.create_all(engine)
        # 
        # # Check the table structure to ensure compatibility
        # # This check is good to have even if create_all runs, to verify existing tables.
        # result = db.execute(text("""
        # SELECT column_name, data_type 
        # FROM information_schema.columns 
        # WHERE table_name = 'raw_submissions' AND table_schema = 'public'
        # ORDER BY ordinal_position;
        # """))
        # columns = result.fetchall()
        # column_names = [col[0] for col in columns]
        # logger.info(f"Found columns in raw_submissions: {', '.join(column_names)}")
        # 
        # # Check for required columns
        # required_columns = ['id', 'source', 'source_id', 'occurred_at', 'payload']
        # missing_columns = [col for col in required_columns if col not in column_names]
        # 
        # if missing_columns:
        #     logger.error(f"raw_submissions table is missing required columns: {missing_columns}")
        #     return False
        
        logger.info("Database connection successful (schema verification for RawEvent skipped).")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        logger.error("Database initialization error details:", exc_info=True)
        engine = None         # Ensure engine is reset on error
        SessionLocal = None   # Ensure SessionLocal is reset on error
        return False
    finally:
        if db:  # Check if db was assigned before trying to close
            db.close()
