"""PostgreSQL storage backend for Reddit submission records."""

import json
import logging
from datetime import datetime, timezone
from typing import List, Set, Optional

import psycopg2
from psycopg2.extras import execute_values
from psycopg2.extensions import connection

from reddit_scraper.models.submission import SubmissionRecord
from reddit_scraper.storage.db import get_connection, ensure_schema, ensure_partition

logger = logging.getLogger(__name__)


class PostgresSink:
    """PostgreSQL sink for storing submission records."""
    
    def __init__(self):
        """
        Initialize PostgreSQL sink.
        
        Sets up connection to PostgreSQL and ensures schema exists.
        """
        # Log initialization with high visibility
        logger.warning("========== POSTGRES SINK INITIALIZATION START ==========")
        
        # Attempt to establish a connection and validate the schema
        logger.warning("POSTGRES: Establishing initial database connection to market_postgres...")
        conn = get_connection()
        if not conn:
            logger.error("POSTGRES ERROR: Failed to connect to market_postgres during initialization")
            logger.warning("========== POSTGRES SINK INITIALIZATION FAILED ==========")
            raise RuntimeError("Could not connect to market_postgres database")
        
        logger.warning("POSTGRES: Initial connection established successfully")
            
        # Validate schema compatibility (don't try to create/modify schema)
        logger.warning("POSTGRES: Validating database schema compatibility...")
        schema_valid = ensure_schema(conn)
        if not schema_valid:
            logger.error("POSTGRES ERROR: market_postgres schema is not compatible")
            conn.close()
            logger.warning("========== POSTGRES SINK INITIALIZATION FAILED ==========")
            raise RuntimeError("market_postgres schema is not compatible with Reddit scraper")
        
        logger.warning("POSTGRES: Schema validation successful")
            
        # Check if raw_events table exists and is properly partitioned
        try:
            logger.warning("POSTGRES: Verifying raw_events table structure...")
            cur = conn.cursor()
            
            # Check if table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'raw_events'
                );
            """)
            table_exists = cur.fetchone()[0]
            
            if not table_exists:
                logger.error("POSTGRES ERROR: raw_events table does not exist in market_postgres")
                conn.close()
                logger.warning("========== POSTGRES SINK INITIALIZATION FAILED ==========")
                raise RuntimeError("raw_events table not found in market_postgres")
            
            # Check if table is partitioned
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM pg_partitioned_table pt
                    JOIN pg_class c ON c.oid = pt.partrelid
                    WHERE c.relname = 'raw_events'
                );
            """)
            is_partitioned = cur.fetchone()[0]
            
            if not is_partitioned:
                logger.error("POSTGRES ERROR: raw_events table in market_postgres is not partitioned")
                conn.close()
                logger.warning("========== POSTGRES SINK INITIALIZATION FAILED ==========")
                raise RuntimeError("raw_events table in market_postgres is not partitioned")
            
            # Check for partitions
            logger.warning("POSTGRES: Checking for table partitions...")
            cur.execute("""
                SELECT count(*) FROM pg_inherits
                WHERE inhparent = 'raw_events'::regclass;
            """)
            partition_count = cur.fetchone()[0]
            logger.warning(f"POSTGRES: Found {partition_count} existing partitions")
            
            # Check table structure
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'raw_events' AND table_schema = 'public'
                ORDER BY ordinal_position;
            """)
            columns = cur.fetchall()
            column_names = [col[0] for col in columns]
            logger.warning(f"POSTGRES: raw_events columns: {', '.join(column_names)}")
            
            # Check for required columns
            required_columns = ['id', 'source', 'source_id', 'occurred_at', 'payload']
            missing_columns = [col for col in required_columns if col not in column_names]
            
            if missing_columns:
                logger.error(f"POSTGRES ERROR: raw_events table is missing required columns: {missing_columns}")
                conn.close()
                logger.warning("========== POSTGRES SINK INITIALIZATION FAILED ==========")
                raise RuntimeError(f"raw_events table missing columns: {missing_columns}")
            
            cur.close()
            logger.warning("POSTGRES: raw_events table exists and is compatible")
            
            # Close the initialization connection
            conn.close()
            logger.warning("POSTGRES: Initial connection closed")
                
        except Exception as e:
            logger.error(f"POSTGRES ERROR: Schema validation failed: {str(e)}")
            logger.error("POSTGRES ERROR details:", exc_info=True)
            if conn:
                conn.close()
            logger.warning("========== POSTGRES SINK INITIALIZATION FAILED ==========")
            raise RuntimeError(f"Error during PostgreSQL initialization: {str(e)}")
            
        logger.warning("========== POSTGRES SINK INITIALIZATION COMPLETE ==========")
    
    def _ensure_partitions_exist(self, conn: connection, records: List[SubmissionRecord]) -> None:
        """
        Check if partitioning is needed for the market_postgres database.
        
        This is a compatibility function that checks if the table is partitioned.
        For the market_postgres database, which uses a non-partitioned table,
        this function does nothing but logs the situation.
        
        Args:
            conn: PostgreSQL connection
            records: List of records to be inserted
        """
        logger.warning(f"POSTGRES: Checking partitioning status for {len(records)} records")
        
        # Check if the table is partitioned
        try:
            with conn.cursor() as cur:
                cur.execute("""
                SELECT EXISTS (
                    SELECT FROM pg_partitioned_table pt
                    JOIN pg_class c ON c.oid = pt.partrelid
                    WHERE c.relname = 'raw_events'
                );
                """)
                is_partitioned = cur.fetchone()[0]
                
                if is_partitioned:
                    logger.warning("POSTGRES: Table is partitioned, would normally create partitions")
                    # In this case, we would create partitions, but we'll skip it
                    # since we're using the existing market_postgres database
                else:
                    logger.warning("POSTGRES: Table is not partitioned, skipping partition creation")
                    # The market_postgres database uses a non-partitioned table, so we don't need to do anything
        except Exception as e:
            logger.error(f"POSTGRES ERROR: Failed to check partitioning status: {str(e)}")
            logger.error("POSTGRES ERROR details:", exc_info=True)
        
        logger.warning("POSTGRES: Using existing non-partitioned table structure in market_postgres")
    
    def append(self, records: List[SubmissionRecord]) -> int:
        """Append records to the PostgreSQL database.
        
        Args:
            records: List of submission records to append
            
        Returns:
            Number of records successfully appended
        """
        if not records:
            return 0
            
        count = 0
        conn = None
        
        try:
            # Get connection
            conn = get_connection()
            if not conn:
                logger.error("POSTGRES ERROR: Failed to connect to PostgreSQL for appending records")
                return 0
                
            logger.warning(f"POSTGRES: Connected successfully for appending {len(records)} records")
            
            # Check table structure (no need to create partitions for market_postgres)
            self._ensure_partitions_exist(conn, records)
            
            # Check column names in the table
            cur = conn.cursor()
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' AND table_name = 'raw_events'
                ORDER BY ordinal_position;
            """)
            columns = [col[0] for col in cur.fetchall()]
            logger.warning(f"POSTGRES: Found columns: {', '.join(columns)}")
            
            # Check if we have ingested_at instead of created_at
            has_ingested_at = 'ingested_at' in columns
            has_created_at = 'created_at' in columns
            
            # Prepare data for insertion
            insert_data = []
            for record in records:
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
                        payload = json.dumps(record)
                    else:
                        # Use to_dict() method if available
                        payload = json.dumps(record.to_dict() if hasattr(record, 'to_dict') else vars(record))
                    
                    # Prepare data tuple for market_postgres compatibility
                    data = (
                        "reddit",  # source
                        record_id,  # source_id - unique with our prefix
                        occurred_at,  # occurred_at
                        payload  # payload as JSON
                    )
                    
                    insert_data.append(data)
                except Exception as e:
                    logger.error(f"POSTGRES ERROR: Error preparing record for PostgreSQL: {str(e)}")
            
            # Insert records
            logger.warning(f"POSTGRES: Prepared {len(insert_data)} records for insertion")
            
            if insert_data:
                logger.warning("POSTGRES: Executing INSERT statement...")
                
                # The market_postgres database expects these exact columns
                # The ingested_at and processed columns have default values
                logger.warning("POSTGRES: Using market_postgres table structure")
                try:
                    execute_values(
                        cur,
                        """
                        INSERT INTO raw_events 
                        (source, source_id, occurred_at, payload)
                        VALUES %s
                        ON CONFLICT (source_id, occurred_at) DO NOTHING
                        RETURNING id
                        """,
                        insert_data
                    )
                    logger.warning("POSTGRES: INSERT statement executed successfully")
                except Exception as insert_error:
                    logger.error(f"POSTGRES ERROR: Failed to execute INSERT: {str(insert_error)}")
                    logger.error("POSTGRES ERROR details:", exc_info=True)
                    
                    # Try a more detailed error diagnosis
                    try:
                        # Check table constraints
                        cur.execute("""
                        SELECT conname, pg_get_constraintdef(oid) 
                        FROM pg_constraint 
                        WHERE conrelid = 'raw_events'::regclass;
                        """)
                        constraints = cur.fetchall()
                        logger.error(f"POSTGRES: Table constraints: {constraints}")
                        
                        # Try a simpler insert with one record for diagnosis
                        if insert_data:
                            sample_data = insert_data[0]
                            logger.warning(f"POSTGRES: Trying single record insert with: {sample_data}")
                            cur.execute("""
                            INSERT INTO raw_events (source, source_id, occurred_at, payload)
                            VALUES (%s, %s, %s, %s::jsonb)
                            ON CONFLICT (source_id, occurred_at) DO NOTHING
                            RETURNING id
                            """, sample_data)
                    except Exception as diag_error:
                        logger.error(f"POSTGRES ERROR: Diagnostic query failed: {str(diag_error)}")
                        logger.error("POSTGRES ERROR details:", exc_info=True)
                
                count = cur.rowcount
                logger.warning(f"POSTGRES SUCCESS: Inserted {count} records into PostgreSQL")
                
                # Log some sample IDs that were inserted
                if count > 0:
                    sample_ids = [str(row[0]) for row in cur.fetchmany(min(5, count))]
                    logger.warning(f"POSTGRES: Sample inserted IDs: {', '.join(sample_ids)}")
            
            # Close cursor
            cur.close()
            
        except Exception as e:
            logger.error(f"POSTGRES ERROR: Failed appending records: {str(e)}")
            logger.error("POSTGRES ERROR details:", exc_info=True)
        finally:
            if conn:
                conn.close()
                logger.warning("POSTGRES: Connection closed")
        
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
        conn = None
        
        try:
            # Get connection
            conn = get_connection()
            if not conn:
                logger.error("POSTGRES ERROR: Failed to connect to PostgreSQL for loading IDs")
                return ids
            
            logger.warning("POSTGRES: Connection established successfully for loading IDs")
            
            # Query for all submission IDs
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT source_id FROM raw_events
                    WHERE source = 'reddit'
                """)
                    
                for row in cur:
                    ids.add(row[0])
                    
                logger.warning(f"POSTGRES: Loaded {len(ids)} submission IDs from PostgreSQL")
                    
                # Sample some IDs for verification
                if ids:
                    sample_ids = list(ids)[:5] if len(ids) > 5 else list(ids)
                    logger.warning(f"POSTGRES: Sample IDs: {', '.join(sample_ids)}")
        except Exception as e:
            logger.error(f"POSTGRES ERROR: Failed to load submission IDs: {str(e)}")
            logger.error("POSTGRES ERROR details:", exc_info=True)
        finally:
            if conn:
                conn.close()
                logger.warning("POSTGRES: Connection closed after loading IDs")
                
        # Return the collected IDs
        return ids
