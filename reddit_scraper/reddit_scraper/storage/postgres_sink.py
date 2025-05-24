import json
import logging
from datetime import datetime, timezone
from typing import List, Set, Optional

import psycopg2
from psycopg2.extras import execute_values
from psycopg2.extensions import connection

from reddit_scraper.models.submission import SubmissionRecord
from reddit_scraper.storage.db import get_connection, ensure_schema
from reddit_scraper.config import PostgresConfig

logger = logging.getLogger(__name__)


class PostgresSink:
    """PostgreSQL sink for storing submission records."""
    
    def __init__(self, db_config: PostgresConfig):
        """
        Initialize PostgreSQL sink.
        
        Args:
            db_config: PostgreSQL connection configuration.
        """
        logger.info("Initializing PostgresSink with provided configuration.")
        self.db_config = db_config
        conn = get_connection(self.db_config)
        if not conn:
            logger.error("POSTGRES ERROR: Failed to connect to database during initialization")
            raise RuntimeError("Could not connect to PostgreSQL database")
        
        try:
            schema_valid = ensure_schema(conn)
            if not schema_valid:
                logger.error("POSTGRES ERROR: Database schema is not compatible or 'raw_submissions' table is missing.")
                raise RuntimeError("PostgreSQL schema is not compatible or 'raw_submissions' table is missing.")
            logger.info("PostgreSQL schema validation successful for 'raw_submissions'.")
        finally:
            if conn:
                conn.close()

    def append(self, records: List[SubmissionRecord]) -> int:
        """Append records to the PostgreSQL database into 'raw_submissions' table.
        
        Args:
            records: List of submission records to append
            
        Returns:
            Number of records successfully appended
        """
        if not records:
            return 0

        conn = None
        count = 0
        try:
            conn = get_connection(self.db_config)
            if not conn:
                logger.error("POSTGRES ERROR: Failed to connect to database for appending records")
                return 0

            with conn.cursor() as cur:
                # Prepare data for insertion
                # Ensure all fields from SubmissionRecord are included in the correct order
                sql = """
                INSERT INTO raw_submissions (
                    id, created_utc, retrieved_utc, subreddit, title, author, 
                    body, url, score, upvote_ratio, num_comments, 
                    flair_text, over_18
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id, created_utc) DO NOTHING
                """
                insert_data = [
                    (
                        r['id'],
                        r['created_utc'],
                        datetime.now(timezone.utc),  # retrieved_utc
                        r['subreddit'],
                        r['title'],
                        r['author'],
                        r.get('selftext', None),  # body (maps to selftext in record)
                        r['url'],
                        r['score'],
                        r['upvote_ratio'],
                        r['num_comments'],
                        r.get('flair_text', None),  # flair_text
                        r['over_18']
                    )
                    for r in records
                ]

                if not insert_data:
                    return 0

                execute_values(cur, sql, insert_data, page_size=100)
                conn.commit() # Commit after execute_values
                count = cur.rowcount if cur.rowcount is not None else 0 # Handle potential None from rowcount
                logger.info(f"Successfully appended/updated {count} records in 'raw_submissions'.")

        except psycopg2.Error as e:
            logger.error(f"POSTGRES DB ERROR during append: {e}")
            if conn: # Rollback in case of error if a transaction was started implicitly or explicitly
                conn.rollback()
        except Exception as e:
            logger.error(f"POSTGRES UNEXPECTED ERROR during append: {str(e)}", exc_info=True)
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
        
        return count
    
    def load_ids(self) -> Set[str]:
        """
        Load existing submission IDs from 'raw_submissions' table.
        
        Returns:
            Set of existing submission IDs (Reddit base36 IDs)
        """
        logger.info("Loading existing submission IDs from 'raw_submissions'.")
        ids = set()
        conn = None
        try:
            conn = get_connection(self.db_config)
            if not conn:
                logger.error("POSTGRES ERROR: Failed to connect for loading IDs")
                return ids

            with conn.cursor() as cur:
                cur.execute("SELECT id FROM raw_submissions;")
                for row in cur:
                    ids.add(row[0])
                logger.info(f"Loaded {len(ids)} submission IDs from 'raw_submissions'.")
        except Exception as e:
            logger.error(f"POSTGRES ERROR: Failed to load submission IDs: {str(e)}", exc_info=True)
        finally:
            if conn:
                conn.close()
        return ids
