"""CSV storage implementation for Reddit submission records."""

import csv
import logging
import os
from pathlib import Path
from typing import List, Set, Optional

from reddit_scraper.storage.data_sink import DataSink

import pandas as pd

from reddit_scraper.models.submission import SubmissionRecord

logger = logging.getLogger(__name__)





class CsvSink(DataSink):
    """CSV file implementation of the DataSink interface."""
    
    # Column order matching the PRD specification
    COLUMNS = [
        "id", "created_utc", "subreddit", "title", "selftext", 
        "author", "score", "upvote_ratio", "num_comments", 
        "url", "flair_text", "over_18"
    ]
    
    def __init__(self, csv_path: str):
        """
        Initialize the CSV sink with a file path.
        
        Args:
            csv_path: Path to the CSV file
        """
        self.csv_path = csv_path
        self._ensure_directory()
    
    def _ensure_directory(self) -> None:
        """Ensure the directory for the CSV file exists."""
        directory = os.path.dirname(self.csv_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
    
    def _file_exists(self) -> bool:
        """Check if the CSV file already exists."""
        return os.path.exists(self.csv_path) and os.path.getsize(self.csv_path) > 0
    
    def append(self, records: List[SubmissionRecord]) -> int:
        """
        Append records to the CSV file.
        
        Args:
            records: List of submission records to append
            
        Returns:
            Number of records successfully appended
        """
        if not records:
            return 0
            
        try:
            # Convert records to DataFrame
            df = pd.DataFrame(records)
            
            # Ensure columns are in the correct order
            df = df.reindex(columns=self.COLUMNS)
            
            # If file exists, read existing data to merge and sort
            file_exists = self._file_exists()
            if file_exists:
                # Read existing CSV
                existing_df = pd.read_csv(self.csv_path, encoding="utf-8")
                
                # Combine with new records
                df = pd.concat([existing_df, df], ignore_index=True)
                
                # Remove any duplicates based on ID
                df = df.drop_duplicates(subset=["id"], keep="first")
            
            # Normalize created_utc column to handle mixed data types (float timestamps vs datetime strings)
            # Convert all created_utc values to pandas datetime for consistent sorting
            try:
                # First, try to convert to datetime, handling both Unix timestamps and datetime strings
                df['created_utc'] = pd.to_datetime(df['created_utc'], errors='coerce', unit='s')
                # If that fails for string datetimes, try parsing as datetime strings
                mask = df['created_utc'].isna()
                if mask.any():
                    df.loc[mask, 'created_utc'] = pd.to_datetime(df.loc[mask, 'created_utc'], errors='coerce')
            except Exception as e:
                logger.warning(f"Could not normalize created_utc column: {e}. Skipping sort.")
                # If normalization fails, don't sort to avoid the comparison error
                df = df.copy()
            else:
                # Sort by created_utc timestamp (chronological order) only if normalization succeeded
                df = df.sort_values(by="created_utc", ascending=True)
            
            # Write to CSV (overwrite mode since we're rewriting the entire file)
            df.to_csv(
                self.csv_path,
                mode="w",  # Overwrite mode
                index=False,
                header=True,
                quoting=csv.QUOTE_MINIMAL,
                encoding="utf-8"
            )
            
            count = len(records)
            logger.info(f"Appended {count} records to {self.csv_path} (sorted chronologically)")
            return count
            
        except Exception as e:
            logger.error(f"Failed to append records to CSV: {str(e)}")
            return 0
    
    def load_ids(self) -> Set[str]:
        """
        Load existing submission IDs from the CSV file.
        
        Returns:
            Set of submission IDs already in the CSV
        """
        if not self._file_exists():
            return set()
            
        try:
            # Read only the ID column for efficiency
            ids = pd.read_csv(self.csv_path, usecols=["id"])["id"].unique()
            id_set = set(ids)
            
            logger.info(f"Loaded {len(id_set)} existing submission IDs from {self.csv_path}")
            return id_set
            
        except Exception as e:
            logger.error(f"Failed to load IDs from CSV: {str(e)}")
            return set()


class ParquetSink(DataSink):
    """
    Placeholder for future Parquet storage implementation.
    
    This class follows the same interface as CsvSink to allow easy switching.
    """
    
    def __init__(self, parquet_path: str):
        """
        Initialize the Parquet sink with a file path.
        
        Args:
            parquet_path: Path to the Parquet file
        """
        self.parquet_path = parquet_path
        # Implementation to be added in phase 2
        
    def append(self, records: List[SubmissionRecord]) -> int:
        """
        Append records to the Parquet file.
        
        Args:
            records: List of submission records to append
            
        Returns:
            Number of records successfully appended
        """
        # Placeholder for future implementation
        raise NotImplementedError("ParquetSink is not yet implemented")
    
    def load_ids(self) -> Set[str]:
        """
        Load existing submission IDs from the Parquet file.
        
        Returns:
            Set of submission IDs already in the Parquet file
        """
        # Placeholder for future implementation
        raise NotImplementedError("ParquetSink is not yet implemented")
