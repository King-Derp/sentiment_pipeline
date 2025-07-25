"""Data loading utilities for reconciliation process."""

import pandas as pd
import asyncio
import logging
from typing import Set, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

logger = logging.getLogger(__name__)

class CSVDataLoader:
    """Loads and processes data from reddit_finance.csv."""
    
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.data: Optional[pd.DataFrame] = None
    
    async def load_data(self) -> pd.DataFrame:
        """Load CSV data with proper data types."""
        logger.info(f"Loading CSV data from {self.csv_path}")
        
        # Define data types for efficient loading
        dtypes = {
            'id': 'string',
            'created_utc': 'int64',
            'subreddit': 'string',
            'title': 'string',
            'selftext': 'string',
            'author': 'string',
            'score': 'int32',
            'upvote_ratio': 'float32',
            'num_comments': 'int32',
            'url': 'string',
            'flair_text': 'string',
            'over_18': 'bool'
        }
        
        # Load in chunks to manage memory
        chunk_size = 10000
        chunks = []
        
        for chunk in pd.read_csv(self.csv_path, dtype=dtypes, chunksize=chunk_size):
            chunks.append(chunk)
            logger.info(f"Loaded chunk with {len(chunk)} records")
        
        self.data = pd.concat(chunks, ignore_index=True)
        logger.info(f"Total CSV records loaded: {len(self.data)}")
        
        return self.data
    
    def get_ids(self) -> Set[str]:
        """Get set of all Reddit IDs from CSV."""
        if self.data is None:
            raise ValueError("Data not loaded. Call load_data() first.")
        return set(self.data['id'].astype(str))
    
    def get_records_by_ids(self, ids: Set[str]) -> pd.DataFrame:
        """Get records matching specific IDs."""
        if self.data is None:
            raise ValueError("Data not loaded. Call load_data() first.")
        return self.data[self.data['id'].isin(ids)]

class TimescaleDBLoader:
    """Loads and processes data from TimescaleDB raw_events table."""
    
    def __init__(self):
        self.engine = self._create_engine()
        self.Session = sessionmaker(bind=self.engine)
    
    def _create_engine(self):
        """Create SQLAlchemy engine from environment variables."""
        # Use local connection parameters for reconciliation script
        db_host = os.environ.get("PG_HOST_LOCAL")
        db_port = os.environ.get("PG_PORT_HOST")
        db_name = os.environ.get("PG_DB")
        db_user = os.environ.get("PG_USER")
        db_password = os.environ.get("PG_PASSWORD")
        
        # Validate required environment variables
        required_vars = {
            "PG_HOST_LOCAL": db_host,
            "PG_PORT_HOST": db_port,
            "PG_DB": db_name,
            "PG_USER": db_user,
            "PG_PASSWORD": db_password
        }
        
        missing_vars = [var for var, value in required_vars.items() if not value]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        logger.info(f"Connecting to database: {db_user}@{db_host}:{db_port}/{db_name}")
        return create_engine(database_url, pool_pre_ping=True)
    
    async def load_reddit_data(self) -> pd.DataFrame:
        """Load all Reddit data from raw_events table."""
        logger.info("Loading Reddit data from TimescaleDB")
        
        query = text("""
            SELECT 
                id,
                source_id,
                occurred_at,
                payload,
                ingested_at,
                processed
            FROM raw_events 
            WHERE source = 'reddit'
            ORDER BY occurred_at
        """)
        
        with self.Session() as session:
            result = session.execute(query)
            rows = result.fetchall()
            
            data = []
            for row in rows:
                # Extract Reddit ID (remove prefix if present)
                reddit_id = row.source_id
                if reddit_id.startswith('reddit-scraper-'):
                    reddit_id = reddit_id[len('reddit-scraper-'):]
                
                data.append({
                    'db_id': row.id,
                    'reddit_id': reddit_id,
                    'occurred_at': row.occurred_at,
                    'payload': row.payload,
                    'ingested_at': row.ingested_at,
                    'processed': row.processed
                })
            
            df = pd.DataFrame(data)
            logger.info(f"Loaded {len(df)} Reddit records from TimescaleDB")
            return df
    
    def get_reddit_ids(self) -> Set[str]:
        """Get set of all Reddit IDs from database."""
        query = text("""
            SELECT DISTINCT source_id 
            FROM raw_events 
            WHERE source = 'reddit'
        """)
        
        with self.Session() as session:
            result = session.execute(query)
            ids = set()
            for row in result:
                reddit_id = row.source_id
                if reddit_id.startswith('reddit-scraper-'):
                    reddit_id = reddit_id[len('reddit-scraper-'):]
                ids.add(reddit_id)
            
            logger.info(f"Found {len(ids)} unique Reddit IDs in database")
            return ids
