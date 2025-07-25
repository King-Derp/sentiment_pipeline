"""Validation utilities for reconciliation results."""

import pandas as pd
import logging
from typing import Dict, List, Tuple
from .data_loaders import CSVDataLoader, TimescaleDBLoader

logger = logging.getLogger(__name__)

class ReconciliationValidator:
    """Validates reconciliation results."""
    
    def __init__(self, csv_path: str):
        self.csv_loader = CSVDataLoader(csv_path)
        self.db_loader = TimescaleDBLoader()
    
    async def validate_reconciliation(self) -> Dict[str, bool]:
        """Run comprehensive validation checks."""
        logger.info("Starting bi-directional reconciliation validation")
        
        results = {}
        
        # Load data
        csv_data = await self.csv_loader.load_data()
        db_data = await self.db_loader.load_reddit_data()
        
        # Validation checks
        results['id_uniqueness'] = await self._validate_id_uniqueness(db_data)
        results['timestamp_consistency'] = await self._validate_timestamps(csv_data, db_data)
        results['data_completeness'] = await self._validate_completeness(csv_data, db_data)
        results['payload_integrity'] = await self._validate_payload_integrity(db_data)
        results['bidirectional_sync'] = await self._validate_bidirectional_sync(csv_data, db_data)
        
        # Overall validation result
        results['overall_success'] = all(results.values())
        
        logger.info(f"Bi-directional validation complete. Overall success: {results['overall_success']}")
        return results
    
    async def _validate_id_uniqueness(self, db_data: pd.DataFrame) -> bool:
        """Validate that all Reddit IDs are unique in database."""
        unique_ids = db_data['reddit_id'].nunique()
        total_ids = len(db_data)
        
        is_valid = unique_ids == total_ids
        logger.info(f"ID uniqueness: {unique_ids}/{total_ids} unique ({'PASS' if is_valid else 'FAIL'})")
        return is_valid
    
    async def _validate_timestamps(self, csv_data: pd.DataFrame, db_data: pd.DataFrame) -> bool:
        """Validate timestamp consistency between sources."""
        # Sample validation on common records
        common_ids = set(csv_data['id']) & set(db_data['reddit_id'])
        sample_size = min(100, len(common_ids))
        sample_ids = list(common_ids)[:sample_size]
        
        mismatches = 0
        for reddit_id in sample_ids:
            csv_timestamp = csv_data[csv_data['id'] == reddit_id]['created_utc'].iloc[0]
            db_record = db_data[db_data['reddit_id'] == reddit_id].iloc[0]
            db_timestamp = int(db_record['occurred_at'].timestamp())
            
            if abs(csv_timestamp - db_timestamp) > 1:  # Allow 1 second tolerance
                mismatches += 1
        
        is_valid = mismatches == 0
        logger.info(f"Timestamp consistency: {sample_size - mismatches}/{sample_size} consistent ({'PASS' if is_valid else 'FAIL'})")
        return is_valid
    
    async def _validate_completeness(self, csv_data: pd.DataFrame, db_data: pd.DataFrame) -> bool:
        """Validate data completeness after reconciliation."""
        csv_ids = set(csv_data['id'])
        db_ids = set(db_data['reddit_id'])
        
        # Check if all CSV records are now in database
        missing_in_db = csv_ids - db_ids
        coverage = (len(csv_ids) - len(missing_in_db)) / len(csv_ids) * 100
        
        is_valid = len(missing_in_db) == 0
        logger.info(f"Data completeness: {coverage:.2f}% coverage ({'PASS' if is_valid else 'FAIL'})")
        return is_valid
    
    async def _validate_payload_integrity(self, db_data: pd.DataFrame) -> bool:
        """Validate JSON payload structure integrity."""
        required_fields = ['id', 'created_utc', 'subreddit', 'title', 'author']
        invalid_payloads = 0
        
        for _, row in db_data.head(100).iterrows():  # Sample validation
            payload = row['payload']
            if not all(field in payload for field in required_fields):
                invalid_payloads += 1
        
        is_valid = invalid_payloads == 0
        logger.info(f"Payload integrity: {100 - invalid_payloads}% valid payloads ({'PASS' if is_valid else 'FAIL'})")
        return is_valid
    
    async def _validate_bidirectional_sync(self, csv_data: pd.DataFrame, db_data: pd.DataFrame) -> bool:
        """Validate that both sources are synchronized (bi-directional)."""
        csv_ids = set(csv_data['id'])
        db_ids = set(db_data['reddit_id'])
        
        # For bi-directional sync, both sources should have the same IDs
        csv_only = csv_ids - db_ids
        db_only = db_ids - csv_ids
        
        is_synchronized = len(csv_only) == 0 and len(db_only) == 0
        
        if not is_synchronized:
            logger.warning(f"Bi-directional sync incomplete: {len(csv_only)} CSV-only, {len(db_only)} DB-only records")
        else:
            logger.info(f"Bi-directional sync: PASS - {len(csv_ids)} records in both sources")
        
        return is_synchronized
