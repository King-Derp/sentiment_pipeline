"""PostgreSQL database connection utilities."""

import logging
from typing import Optional
import psycopg2
from psycopg2.extensions import connection

from reddit_scraper.config import PostgresConfig

logger = logging.getLogger(__name__)

def get_connection(db_config: PostgresConfig) -> Optional[connection]:
    """
    Create and return a PostgreSQL connection using provided configuration.

    Args:
        db_config: A PostgresConfig object containing connection parameters.

    Returns:
        Optional[connection]: A psycopg2 connection object or None if the connection fails.
    """
    try:
        # Log connection details (masking password)
        logger.warning(f"Attempting PostgreSQL connection with:")
        logger.warning(f"  - host: {db_config.host}")
        logger.warning(f"  - port: {db_config.port}")
        logger.warning(f"  - dbname: {db_config.database}")
        logger.warning(f"  - user: {db_config.user}")
        
        # Check that we have all required parameters
        if not all([db_config.host, db_config.port, db_config.database, db_config.user, db_config.password is not None]): 
            missing = []
            if not db_config.host: missing.append("host")
            if not db_config.port: missing.append("port")
            if not db_config.database: missing.append("database")
            if not db_config.user: missing.append("user")
            if db_config.password is None: missing.append("password") 
            logger.error(f"Missing PostgreSQL connection parameters: {', '.join(missing)}")
            return None
            
        # Attempt connection with detailed logging
        logger.warning(f"Connecting to PostgreSQL at {db_config.host}:{db_config.port}/{db_config.database}...")
        conn = psycopg2.connect(
            host=db_config.host,
            port=db_config.port,
            dbname=db_config.database,
            user=db_config.user,
            password=db_config.password
        )
        conn.autocommit = True 
        logger.warning(f"Successfully connected to PostgreSQL at {db_config.host}:{db_config.port}/{db_config.database}")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {str(e)}")
        logger.error(f"Connection error details:", exc_info=True)
        return None
        
def ensure_schema(conn: connection) -> bool:
    """
    Verify that the 'raw_submissions' table exists.

    Alembic is responsible for creating and managing the schema. This function
    only performs a basic check to ensure the main table is present.
    
    Args:
        conn: PostgreSQL connection object
        
    Returns:
        True if 'raw_submissions' table exists, False otherwise
    """
    try:
        with conn.cursor() as cur:
            # Check if the raw_submissions table exists
            cur.execute("""
            SELECT EXISTS (
                SELECT FROM pg_tables 
                WHERE schemaname = 'public' AND tablename = 'raw_submissions'
            );
            """)
            table_exists = cur.fetchone()[0]
            
            if not table_exists:
                logger.error("'raw_submissions' table does not exist in the database!")
                logger.error("Ensure migrations have been run correctly using Alembic.")
                return False
            
            logger.info("'raw_submissions' table exists. Schema check passed.")
            return True
    except Exception as e:
        logger.error(f"Failed to verify PostgreSQL schema: {str(e)}")
        logger.error("Schema verification error details:", exc_info=True)
        return False
