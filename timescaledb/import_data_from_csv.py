import sys
import os
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import csv
import json
from datetime import datetime, timezone
from typing import List, Dict, Any
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert

# Import your models and config
from reddit_scraper.reddit_scraper.models.submission import RawEventORM
from reddit_scraper.reddit_scraper.config import PostgresConfig

def create_db_connection(config: PostgresConfig):
    """Create a database connection using SQLAlchemy."""
    db_url = f"postgresql://{config.user}:{config.password}@{config.host}:{config.port}/{config.database}"
    engine = create_engine(db_url)
    return sessionmaker(bind=engine)()

def csv_row_to_record(row: Dict[str, str]) -> Dict[str, Any]:
    """
    Convert a CSV row (from reddit_finance_test.csv format) to a dictionary 
    matching RawEventORM fields.
    """
    try:
        # Construct payload from all CSV fields
        payload_dict = {k: v for k, v in row.items()}

        # Convert 'created_utc' (epoch string) to datetime object
        occurred_at_datetime = datetime.fromtimestamp(int(row["created_utc"]), timezone.utc)

        return {
            "source": "reddit",  # Hardcode source as "reddit"
            "source_id": row["id"],  # Use CSV 'id' as 'source_id'
            "occurred_at": occurred_at_datetime,
            "payload": payload_dict # Store the entire original row as JSON payload
        }
    except (KeyError, ValueError, TypeError) as e: # Added TypeError for int() conversion
        # Raise a more informative error, including the problematic row content
        raise ValueError(f"Error processing CSV row {row}: {str(e)}")

def import_csv_to_timescale(
    csv_path: str,
    config: PostgresConfig,
    batch_size: int = 1000
) -> None:
    """
    Import data from a CSV file to TimescaleDB using SQLAlchemy.
    
    Args:
        csv_path: Path to the CSV file
        config: PostgreSQL configuration
        batch_size: Number of records to process in a single batch
    """
    session = create_db_connection(config)
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            batch = []
            
            for i, row in enumerate(reader, 1):
                try:
                    record = csv_row_to_record(row)
                    batch.append(record)
                    
                    # Process in batches
                    if len(batch) >= batch_size:
                        _process_batch(session, batch)
                        batch = []
                        
                    if i % 1000 == 0:
                        print(f"Processed {i} records...")
                        
                except Exception as e:
                    print(f"Error processing row {i}: {str(e)}")
                    continue
            
            # Process any remaining records
            if batch:
                _process_batch(session, batch)
                
    except Exception as e:
        print(f"Error during import: {str(e)}")
        raise
    finally:
        session.close()

def _process_batch(session, batch: List[Dict[str, Any]]) -> None:
    """Process a batch of records with idempotent insert."""
    if not batch:
        return
        
    stmt = insert(RawEventORM).values(batch)
    # Use the existing unique constraint for conflict resolution
    stmt = stmt.on_conflict_do_nothing(
        index_elements=['source', 'source_id', 'occurred_at'] 
    )
    
    try:
        session.execute(stmt)
        session.commit()
        print(f"Inserted/updated {len(batch)} records")
    except Exception as e:
        session.rollback()
        print(f"Error in batch: {str(e)}")
        raise

if __name__ == "__main__":
    # Configure with your database credentials
    config = PostgresConfig(
        host="localhost",
        port=5433,  # Default TimescaleDB port
        database="sentiment_pipeline_db_test",  
        user="test_user",
        password="test_password"
    )
    
    # Path to your CSV file
    csv_path = "F:\\Coding\\sentiment_pipeline\\data\\reddit_finance_test.csv"  
    
    # Run the import
    import_csv_to_timescale(csv_path, config)