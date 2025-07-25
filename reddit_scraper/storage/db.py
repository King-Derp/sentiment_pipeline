"""PostgreSQL database connection utilities."""

import os
import logging
from typing import Optional
import psycopg2
from psycopg2.extensions import connection

logger = logging.getLogger(__name__)

def get_connection() -> Optional[connection]:
    """
    Create and return a PostgreSQL connection from environment variables.
    Returns:
        Optional[connection]: A psycopg2 connection object or None if the connection fails.
    """
    try:
        # Get connection parameters from environment variables
        # Support both PG_* and POSTGRES_* variables for flexibility
        host = os.environ.get('PG_HOST') or os.environ.get('POSTGRES_HOST', 'localhost')
        port = os.environ.get('PG_PORT') or os.environ.get('POSTGRES_PORT', '5432')
        dbname = os.environ.get('PG_DB') or os.environ.get('POSTGRES_DB', 'postgres')
        user = os.environ.get('PG_USER') or os.environ.get('POSTGRES_USER', 'postgres')
        password = os.environ.get('PG_PASSWORD') or os.environ.get('POSTGRES_PASSWORD', '')
        
        # Log connection details (masking password)
        logger.warning(f"Attempting PostgreSQL connection with:")
        logger.warning(f"  - host: {host}")
        logger.warning(f"  - port: {port}")
        logger.warning(f"  - dbname: {dbname}")
        logger.warning(f"  - user: {user}")
        
        # Check that we have all required parameters
        if not all([host, port, dbname, user, password]):
            missing = []
            if not host: missing.append("host")
            if not port: missing.append("port")
            if not dbname: missing.append("dbname")
            if not user: missing.append("user")
            if not password: missing.append("password")
            logger.error(f"Missing PostgreSQL connection parameters: {', '.join(missing)}")
            return None
            
        # Attempt connection with detailed logging
        logger.warning(f"Connecting to PostgreSQL at {host}:{port}/{dbname}...")
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password
        )
        conn.autocommit = True
        logger.warning(f"Successfully connected to PostgreSQL at {host}:{port}/{dbname}")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {str(e)}")
        logger.error(f"Connection error details:", exc_info=True)
        return None
        
def ensure_schema(conn: connection) -> bool:
    """
    Verify compatibility with the existing schema in market_postgres.
    
    This function checks if the raw_events table exists and has the required columns,
    but does not attempt to modify the schema as we're using an existing database.
    
    Args:
        conn: PostgreSQL connection object
        
    Returns:
        True if schema is compatible, False otherwise
    """
    try:
        with conn.cursor() as cur:
            # Check if the raw_events table exists
            cur.execute("""
            SELECT EXISTS (
                SELECT FROM pg_tables 
                WHERE schemaname = 'public' AND tablename = 'raw_events'
            );
            """)
            table_exists = cur.fetchone()[0]
            
            if not table_exists:
                logger.error("raw_events table does not exist in the market_postgres database!")
                logger.error("This is unexpected. The table should be created by the market_postgres container.")
                return False
            
            # Check the table structure to ensure compatibility
            cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'raw_events' AND table_schema = 'public'
            ORDER BY ordinal_position;
            """)
            columns = cur.fetchall()
            column_names = [col[0] for col in columns]
            logger.info(f"Found columns in raw_events: {', '.join(column_names)}")
            
            # Check for required columns
            required_columns = ['id', 'source', 'source_id', 'occurred_at', 'payload']
            missing_columns = [col for col in required_columns if col not in column_names]
            
            if missing_columns:
                logger.error(f"raw_events table is missing required columns: {missing_columns}")
                return False
            
            # Check if the table is partitioned (for informational purposes only)
            cur.execute("""
            SELECT EXISTS (
                SELECT FROM pg_partitioned_table pt
                JOIN pg_class c ON c.oid = pt.partrelid
                WHERE c.relname = 'raw_events'
            );
            """)
            is_partitioned = cur.fetchone()[0]
            
            if is_partitioned:
                logger.info("raw_events table is partitioned")
            else:
                logger.info("raw_events table is not partitioned - this is expected for market_postgres")
            
            # Check for ingested_at vs created_at column
            if 'ingested_at' in column_names and not 'created_at' in column_names:
                logger.info("Using 'ingested_at' column instead of 'created_at'")
            elif 'created_at' in column_names:
                logger.info("Using 'created_at' column")
            
            logger.info("Existing raw_events table structure is compatible")
            return True
    except Exception as e:
        logger.error(f"Failed to verify PostgreSQL schema: {str(e)}")
        logger.error("Schema verification error details:", exc_info=True)
        return False

def ensure_partition(conn: connection, day_str: str) -> bool:
    """
    Check if partitioning is needed for the specified day.
    
    For the market_postgres database with a non-partitioned table,
    this function just logs the situation and returns True without
    attempting to create partitions.
    
    Args:
        conn: PostgreSQL connection object
        day_str: Day string in 'YYYY_MM_DD' format
        
    Returns:
        True if partition exists or was created, False otherwise
    """
    try:
        # Check if the table is partitioned
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
                # This is a partitioned table, so we should check for the partition
                partition_name = f"raw_events_{day_str}"
                cur.execute("""
                SELECT EXISTS (
                    SELECT FROM pg_tables 
                    WHERE schemaname = 'public' AND tablename = %s
                );
                """, (partition_name,))
                partition_exists = cur.fetchone()[0]
                
                if partition_exists:
                    logger.info(f"Partition {partition_name} already exists")
                    return True
                    
                # Check for partition creation function
                cur.execute("""
                SELECT EXISTS (
                    SELECT FROM pg_proc p
                    JOIN pg_namespace n ON p.pronamespace = n.oid
                    WHERE n.nspname = 'public' AND p.proname = 'create_partition_for_date'
                );
                """)
                has_partition_function = cur.fetchone()[0]
                
                if has_partition_function:
                    # Use the existing function to create the partition
                    logger.info(f"Using existing create_partition_for_date function for {day_str}")
                    sql_date = day_str.replace('_', '-')
                    try:
                        cur.execute(f"SELECT create_partition_for_date('{sql_date}'::date);")
                        logger.info(f"Created partition {partition_name} using existing function")
                        return True
                    except Exception as func_error:
                        logger.error(f"Error using existing partition function: {str(func_error)}")
                        return False
                else:
                    # Manual partition creation
                    sql_date = day_str.replace('_', '-')
                    next_day = f"'{sql_date}'::date + interval '1 day'"
                    
                    logger.info(f"Creating partition {partition_name} manually")
                    cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {partition_name}
                    PARTITION OF raw_events
                    FOR VALUES FROM ('{sql_date}') TO ({next_day});
                    """)
                    
                    logger.info(f"Created partition {partition_name} manually")
                    return True
            else:
                # This is a non-partitioned table (market_postgres case)
                logger.info(f"Table raw_events is not partitioned - no need to create partition for {day_str}")
                return True
    except Exception as e:
        logger.error(f"Failed to check/create partition for {day_str}: {str(e)}")
        logger.error("Partition check error details:", exc_info=True)
        return False
