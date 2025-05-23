"""
SQLAlchemy-based PostgreSQL storage backend for Reddit submission records.

This module provides a PostgreSQL sink implementation using SQLAlchemy ORM
and connection pooling for efficient database access.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Set, Optional, Dict, Any, Generator

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.postgresql import insert

from reddit_scraper.models.submission import SubmissionRecord
from reddit_scraper.storage.database import get_db, RawEvent, init_db

logger = logging.getLogger(__name__)

class SQLAlchemyPostgresSink:
    """PostgreSQL sink for storing submission records using SQLAlchemy ORM."""
    
    def __init__(self):
        """
        Initialize SQLAlchemy PostgreSQL sink.
        
        Sets up connection to PostgreSQL and ensures schema exists.
        """
        # Log initialization with high visibility
        logger.warning("========== SQLALCHEMY POSTGRES SINK INITIALIZATION START ==========")
        
        # Verify database connection and schema
        if not init_db():
            logger.error("POSTGRES ERROR: Failed to initialize SQLAlchemy database connection")
            logger.warning("========== SQLALCHEMY POSTGRES SINK INITIALIZATION FAILED ==========")
            raise RuntimeError("Failed to initialize SQLAlchemy database connection")
        
        logger.warning("POSTGRES: Database connection and schema verification successful")
        logger.warning("========== SQLALCHEMY POSTGRES SINK INITIALIZATION COMPLETE ==========")
    
    def append(self, records: List[SubmissionRecord]) -> int:
        """
        Append records to the PostgreSQL database using SQLAlchemy ORM.
        
        Args:
            records: List of submission records to append
            
        Returns:
            Number of records successfully appended
        """
        if not records:
            logger.warning("POSTGRES: No records to append")
            return 0
            
        count = 0
        
        try:
            # Log record details for debugging
            for i, record in enumerate(records[:3]):  # Log first 3 records
                record_id = record['id'] if isinstance(record, dict) else record.id
                logger.warning(f"POSTGRES DEBUG: Record {i+1} ID: {record_id}")
                
                # Get more details about the record
                if isinstance(record, dict):
                    logger.warning(f"POSTGRES DEBUG: Record {i+1} is a dictionary with keys: {list(record.keys())}")
                else:
                    logger.warning(f"POSTGRES DEBUG: Record {i+1} is a {type(record).__name__} object with attributes: {dir(record)[:10]}...")
            
            # Get database session using the context manager
            logger.warning("POSTGRES: Getting database session")
            db = next(get_db())
            logger.warning("POSTGRES: Successfully got database session")
            
            # Process records in batches for better performance
            batch_size = 100
            batches = [records[i:i + batch_size] for i in range(0, len(records), batch_size)]
            
            logger.warning(f"POSTGRES: Processing {len(records)} records in {len(batches)} batches")
            
            for batch_idx, batch in enumerate(batches):
                try:
                    logger.warning(f"POSTGRES: Processing batch {batch_idx+1}/{len(batches)} with {len(batch)} records")
                    
                    # Prepare data for insertion
                    db_records = []
                    for record_idx, record in enumerate(batch):
                        try:
                            # Get record ID - format it as a UUID-like string for market_postgres compatibility
                            raw_id = record['id'] if isinstance(record, dict) else record.id
                            # Create a unique ID with a prefix to avoid collisions with existing records
                            record_id = f"reddit-scraper-{raw_id}"
                            
                            # Get timestamp
                            created_utc = record['created_utc'] if isinstance(record, dict) else record.created_utc
                            occurred_at = datetime.fromtimestamp(created_utc, tz=timezone.utc)
                            
                            # Convert record to JSON
                            if isinstance(record, dict):
                                payload = record
                            else:
                                # Use to_dict() method if available
                                payload = record.to_dict() if hasattr(record, 'to_dict') else vars(record)
                            
                            # Log record details for debugging (only first few records)
                            if record_idx < 3:
                                logger.warning(f"POSTGRES DEBUG: Batch {batch_idx+1}, Record {record_idx+1}")
                                logger.warning(f"  Source ID: reddit-scraper-{raw_id}")
                                logger.warning(f"  Occurred at: {occurred_at}")
                                logger.warning(f"  Payload keys: {list(payload.keys())[:5]}...")
                            
                            # Create SQLAlchemy model instance
                            db_record = RawEvent(
                                source="reddit",
                                source_id=record_id,
                                occurred_at=occurred_at,
                                payload=payload
                            )
                            
                            db_records.append(db_record)
                        except Exception as e:
                            logger.error(f"POSTGRES ERROR: Error preparing record for PostgreSQL: {str(e)}")
                            logger.error("POSTGRES ERROR details:", exc_info=True)
                    
                    if db_records:
                        logger.warning(f"POSTGRES: Adding {len(db_records)} records to session for batch {batch_idx+1}/{len(batches)}")
                        
                        # Add all records to the session
                        db.add_all(db_records)
                        logger.warning(f"POSTGRES: Successfully added records to session for batch {batch_idx+1}/{len(batches)}")
                        
                        # Commit the batch
                        logger.warning(f"POSTGRES: Committing batch {batch_idx+1}/{len(batches)}")
                        db.commit()
                        logger.warning(f"POSTGRES: Successfully committed batch {batch_idx+1}/{len(batches)}")
                        
                        # Update count
                        count += len(db_records)
                        logger.warning(f"POSTGRES SUCCESS: Inserted batch {batch_idx+1}/{len(batches)} with {len(db_records)} records")
                        
                        # Log the IDs of the first few inserted records
                        for i, record in enumerate(db_records[:3]):
                            logger.warning(f"POSTGRES DEBUG: Inserted record {i+1} with ID: {record.id}, Source ID: {record.source_id}")
                    else:
                        logger.warning(f"POSTGRES: No records to insert for batch {batch_idx+1}/{len(batches)}")
                    
                except SQLAlchemyError as e:
                    # Roll back the transaction if there's an error
                    db.rollback()
                    logger.error(f"POSTGRES ERROR: Failed to insert batch {batch_idx+1}: {str(e)}")
                    logger.error("POSTGRES ERROR details:", exc_info=True)
            
            logger.warning(f"POSTGRES SUCCESS: Inserted {count} records into PostgreSQL")
            
        except Exception as e:
            logger.error(f"POSTGRES ERROR: Failed appending records: {str(e)}")
            logger.error("POSTGRES ERROR details:", exc_info=True)
        
        logger.warning(f"===== POSTGRES: Append operation completed, {count} records inserted =====")
        return count
    
    def load_ids(self) -> Set[str]:
        """
        Load existing submission IDs from PostgreSQL storage.
        
        Returns:
            Set of existing submission IDs
        """
        logger.warning("POSTGRES: Loading submission IDs from PostgreSQL")
        
        ids = set()
        
        try:
            # Get database session using the context manager
            db = next(get_db())
            
            # Query for all Reddit submission IDs
            query = db.query(RawEvent.source_id).filter(RawEvent.source == 'reddit')
            
            # Process results in chunks to avoid memory issues
            chunk_size = 10000
            for chunk in self._query_in_chunks(query, chunk_size):
                for row in chunk:
                    # Extract the original ID from our prefixed format
                    source_id = row[0]
                    if source_id.startswith('reddit-scraper-'):
                        original_id = source_id[len('reddit-scraper-'):]
                        ids.add(original_id)
                    else:
                        # For records that don't have our prefix
                        ids.add(source_id)
            
            logger.warning(f"POSTGRES: Loaded {len(ids)} submission IDs from PostgreSQL")
                
            # Sample some IDs for verification
            if ids:
                sample_ids = list(ids)[:5] if len(ids) > 5 else list(ids)
                logger.warning(f"POSTGRES: Sample IDs: {', '.join(sample_ids)}")
                
        except Exception as e:
            logger.error(f"POSTGRES ERROR: Failed to load submission IDs: {str(e)}")
            logger.error("POSTGRES ERROR details:", exc_info=True)
                
        # Return the collected IDs
        return ids
    
    def _query_in_chunks(self, query, chunk_size: int) -> Generator[List[Any], None, None]:
        """
        Execute a query and yield results in chunks to avoid memory issues.
        
        Args:
            query: SQLAlchemy query object
            chunk_size: Number of records to fetch in each chunk
            
        Yields:
            List of query results
        """
        offset = 0
        while True:
            chunk = query.limit(chunk_size).offset(offset).all()
            if not chunk:
                break
            yield chunk
            offset += chunk_size
