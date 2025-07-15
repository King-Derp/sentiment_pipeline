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

from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy import text

from reddit_scraper.models.submission import SubmissionRecord, RawEventORM
from reddit_scraper.storage.database import get_db
from reddit_scraper.config import PostgresConfig

logger = logging.getLogger(__name__)

class SQLAlchemyPostgresSink:
    """PostgreSQL sink for storing submission records using SQLAlchemy ORM."""
    
    def __init__(self, pg_config: PostgresConfig):
        """
        Initialize SQLAlchemy PostgreSQL sink.
        
        Relies on the database being initialized elsewhere (e.g., application startup)
        and the schema being managed by Alembic.
        
        Args:
            pg_config: PostgreSQL configuration object.
        """
        # Log initialization with high visibility
        logger.warning("========== SQLALCHEMY POSTGRES SINK INITIALIZATION START ==========")
        logger.info(f"Initializing SQLAlchemyPostgresSink with host: {pg_config.host}, db: {pg_config.database}")
        
        # The database (engine, SessionLocal) should be initialized by the main application calling init_db.
        # The sink itself should not be responsible for schema creation or direct DB init.
        # We assume get_db() will work if init_db() has been called successfully at app startup.
        try:
            with get_db() as db:
                db.execute(text("SELECT 1")) # Test connection
            logger.info("SQLAlchemyPostgresSink: Database connection test successful.")
        except Exception as e:
            logger.error(f"POSTGRES ERROR: Database connection test failed for SQLAlchemyPostgresSink: {str(e)}")
            logger.warning("========== SQLALCHEMY POSTGRES SINK INITIALIZATION FAILED ==========")
            raise RuntimeError(f"Database connection failed for SQLAlchemyPostgresSink: {str(e)}")
        
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
                record_id = record.get('id') if isinstance(record, dict) else getattr(record, 'id', None)
                logger.warning(f"POSTGRES DEBUG: Record {i+1} ID: {record_id}")
                
                # Get more details about the record
                if isinstance(record, dict):
                    logger.warning(f"POSTGRES DEBUG: Record {i+1} is a dictionary with keys: {list(record.keys())}")
                else:
                    logger.warning(f"POSTGRES DEBUG: Record {i+1} is a {type(record).__name__} object with attributes: {dir(record)[:10]}...")
            
            # Get database session using the context manager
            logger.warning("POSTGRES: Getting database session")
            with get_db() as db:
                logger.warning("POSTGRES: Successfully got database session")
                
                # Process records in batches for better performance
                batch_size = 100
                batches = [records[i:i + batch_size] for i in range(0, len(records), batch_size)]
                
                logger.warning(f"POSTGRES: Processing {len(records)} records in {len(batches)} batches")
                
                for batch_idx, batch_records in enumerate(batches):
                    orm_instances_to_insert = []
                    for record_dict in batch_records: # Assuming records are List[SubmissionRecord] which are TypedDicts
                        try:
                            # Map SubmissionRecord to RawEventORM
                            # Ensure record_dict is a dict, as SubmissionRecord is a TypedDict
                            if not isinstance(record_dict, dict):
                                # If it's an object with attributes, convert to dict if possible
                                # This case should ideally not happen if input is consistently SubmissionRecord
                                if hasattr(record_dict, '__dict__'):
                                    actual_record_data = record_dict.__dict__
                                elif hasattr(record_dict, '_asdict'): # for namedtuples
                                    actual_record_data = record_dict._asdict()
                                else:
                                    # Attempt to access items like a dict as a fallback for SubmissionRecord
                                    actual_record_data = {k: record_dict[k] for k in SubmissionRecord.__annotations__ if k in record_dict}
                            else:
                                actual_record_data = record_dict

                            # Convert created_utc (Unix timestamp) to datetime object
                            created_utc_dt = datetime.fromtimestamp(actual_record_data['created_utc'], tz=timezone.utc)

                            orm_instance = RawEventORM(
                                source="reddit",
                                source_id=actual_record_data['id'], # Reddit submission ID
                                occurred_at=created_utc_dt, # Use datetime object
                                payload=actual_record_data # Store the whole SubmissionRecord as payload
                                # ingested_at and processed have server defaults
                            )
                            orm_instances_to_insert.append(orm_instance)
                        except KeyError as ke:
                            logger.error(f"POSTGRES MAPPING ERROR: Missing key {ke} in record: {actual_record_data.get('id', 'UNKNOWN_ID')}")
                            # Decide if to skip this record or raise error
                            continue # Skip malformed record
                        except Exception as e_map:
                            logger.error(f"POSTGRES MAPPING ERROR: Error mapping record {actual_record_data.get('id', 'UNKNOWN_ID')}: {str(e_map)}")
                            continue # Skip malformed record
                    
                    if not orm_instances_to_insert:
                        logger.warning(f"POSTGRES: Batch {batch_idx+1}/{len(batches)} resulted in no records to insert after mapping.")
                        continue

                    try:
                        # Prepare data for bulk insert, converting ORM instances to dicts
                        # The values for the insert statement should be a list of dictionaries.
                        # SQLAlchemy's insert().values() expects a list of dicts or a single dict.
                        # We use orm_instance.__dict__ but need to be careful about SQLAlchemy internal state attributes like '_sa_instance_state'.
                        # A safer way is to explicitly list columns or use a helper to convert ORM to dict for insert.
                        # For simplicity here, we'll assume direct dict conversion is okay for RawEventORM if it's simple.
                        # However, a more robust approach for complex ORMs would be to construct dicts field by field.
                        
                        # Let's construct dicts manually to be safe and clear
                        values_to_insert = []
                        for orm_instance in orm_instances_to_insert:
                            values_to_insert.append({
                                "source": orm_instance.source,
                                "source_id": orm_instance.source_id,
                                "occurred_at": orm_instance.occurred_at,
                                "payload": orm_instance.payload
                                # id, ingested_at, processed are handled by DB defaults/identity
                            })

                        # Upsert statement for RawEventORM
                        # Conflict on (source, source_id, occurred_at)
                        if db.bind.dialect.name == 'sqlite':
                            # HACK: This is a workaround for testing with SQLite, which does not support
                            # autoincrement on composite primary keys. We manually assign an ID.
                            # In production (PostgreSQL), the 'id' column is an IDENTITY column and
                            # is generated automatically.
                            for i, record in enumerate(values_to_insert, 1):
                                record['id'] = i
                            stmt = sqlite.insert(RawEventORM).values(values_to_insert)
                        else:
                            stmt = postgresql.insert(RawEventORM).values(values_to_insert)

                        stmt = stmt.on_conflict_do_nothing(
                            index_elements=["source", "source_id", "occurred_at"]
                        )
                        db.execute(stmt)
                        db.commit()
                        
                        count += len(orm_instances_to_insert)
                        logger.warning(f"POSTGRES SUCCESS: Inserted/Skipped batch {batch_idx+1}/{len(batches)} with {len(orm_instances_to_insert)} records into raw_events")

                        # Log the IDs of the first few inserted records for debugging
                        for i, record_orm_instance in enumerate(orm_instances_to_insert[:3]):
                            logger.warning(f"POSTGRES DEBUG: Processed event for source_id: {record_orm_instance.source_id}, occurred_at: {record_orm_instance.occurred_at}")
                            
                    except Exception as e: # Catch any other unexpected errors
                        db.rollback()
                        logger.error(f"POSTGRES UNEXPECTED ERROR during batch {batch_idx+1} insert: {str(e)}")
                        logger.error("POSTGRES UNEXPECTED ERROR details:", exc_info=True)
                
                logger.warning(f"POSTGRES SUCCESS: Processed {count} records for insertion into PostgreSQL using RawEventORM")
            
        except Exception as e:
            logger.error(f"POSTGRES ERROR: Failed appending records: {str(e)}")
            logger.error("POSTGRES ERROR details:", exc_info=True)
        
        logger.warning(f"===== POSTGRES: Append operation completed, {count} records inserted =====")
        return count
    
    def load_ids(self) -> Set[str]:
        """
        Load existing submission IDs from PostgreSQL storage for 'reddit' source.
        
        Returns:
            Set of existing submission IDs (Reddit base36 IDs) for the 'reddit' source.
        """
        logger.warning("POSTGRES: Loading submission IDs from raw_events for source 'reddit'")
        
        ids = set()
        
        try:
            with get_db() as db:
                # Query for source_id from RawEventORM where source is 'reddit'
                query = db.query(RawEventORM.source_id).filter(RawEventORM.source == 'reddit')
                
                chunk_size = 10000
                for chunk_idx, chunk in enumerate(self._query_in_chunks(query, chunk_size)):
                    logger.debug(f"POSTGRES: Processing ID chunk {chunk_idx + 1} from raw_events")
                    for row in chunk:
                        ids.add(row[0]) # row[0] is RawEventORM.source_id
                
                logger.warning(f"POSTGRES: Loaded {len(ids)} submission IDs for source 'reddit' from raw_events")
                    
                # Sample some IDs for verification
                if ids:
                    sample_ids = list(ids)[:5] if len(ids) > 5 else list(ids)
                    logger.warning(f"POSTGRES: Sample IDs from raw_events: {', '.join(sample_ids)}")
                
        except Exception as e:
            logger.error(f"POSTGRES ERROR: Failed to load submission IDs from raw_events: {str(e)}")
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
