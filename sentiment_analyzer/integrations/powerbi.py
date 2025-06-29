"""
Power BI integration client for streaming sentiment analysis results.

This module provides an async client for pushing sentiment analysis results
to Power BI streaming datasets in real-time.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
import json

import httpx
from pydantic import BaseModel

from sentiment_analyzer.models.dtos import SentimentResultDTO

logger = logging.getLogger(__name__)


class PowerBIRowData(BaseModel):
    """
    Data model for a single row to be pushed to Power BI.
    
    This model defines the structure of data that will be sent to the
    Power BI streaming dataset.
    """
    event_id: str
    occurred_at: datetime
    processed_at: datetime
    source: str
    source_id: str
    sentiment_score: float
    sentiment_label: str
    confidence: Optional[float] = None
    model_version: str
    
    def model_dump_json_compatible(self) -> Dict[str, Any]:
        """
        Convert model to JSON-compatible dictionary.
        
        Returns:
            Dict[str, Any]: JSON-compatible representation
        """
        data = self.model_dump()
        # Convert datetime objects to ISO format strings
        data["occurred_at"] = self.occurred_at.isoformat()
        data["processed_at"] = self.processed_at.isoformat()
        return data


class PowerBIClient:
    """
    Async client for pushing data to Power BI streaming datasets.
    
    Handles authentication, retry logic, and batching for efficient
    data transmission to Power BI.
    """
    
    def __init__(
        self,
        push_url: str,
        api_key: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        batch_size: int = 100,
        timeout: float = 30.0
    ):
        """
        Initialize PowerBI client.
        
        Args:
            push_url: Power BI streaming dataset push URL
            api_key: Optional API key for authentication
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            batch_size: Maximum number of rows to send in a single request
            timeout: Request timeout in seconds
        """
        self.push_url = push_url
        self.api_key = api_key
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.batch_size = batch_size
        self.timeout = timeout
        
        # Initialize HTTP client
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            
        self.client = httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(timeout)
        )
        
        # Batch processing
        self._batch_queue: List[PowerBIRowData] = []
        self._batch_lock = asyncio.Lock()
        
        logger.info(f"PowerBI client initialized with push URL: {push_url[:50]}...")
    
    async def close(self) -> None:
        """
        Close the HTTP client and flush any remaining batched data.
        """
        # Flush any remaining data
        await self.flush_batch()
        
        # Close HTTP client
        await self.client.aclose()
        logger.info("PowerBI client closed")
    
    async def push_row(self, sentiment_result: SentimentResultDTO) -> bool:
        """
        Push a single sentiment result row to Power BI.
        
        Args:
            sentiment_result: Sentiment analysis result to push
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Convert to PowerBI row format
            row_data = PowerBIRowData(
                event_id=sentiment_result.event_id,
                occurred_at=sentiment_result.occurred_at,
                processed_at=sentiment_result.processed_at,
                source=sentiment_result.source,
                source_id=sentiment_result.source_id,
                sentiment_score=sentiment_result.sentiment_score,
                sentiment_label=sentiment_result.sentiment_label,
                confidence=sentiment_result.confidence,
                model_version=sentiment_result.model_version
            )
            
            # Add to batch queue
            async with self._batch_lock:
                self._batch_queue.append(row_data)
                
                # If batch is full, flush it
                if len(self._batch_queue) >= self.batch_size:
                    await self._flush_batch_internal()
            
            return True
            
        except Exception as e:
            logger.error(f"Error preparing row for Power BI: {str(e)}")
            return False
    
    async def push_rows(self, sentiment_results: List[SentimentResultDTO]) -> bool:
        """
        Push multiple sentiment result rows to Power BI.
        
        Args:
            sentiment_results: List of sentiment analysis results to push
            
        Returns:
            bool: True if all successful, False otherwise
        """
        try:
            # Convert all to PowerBI row format
            row_data_list = []
            for result in sentiment_results:
                row_data = PowerBIRowData(
                    event_id=result.event_id,
                    occurred_at=result.occurred_at,
                    processed_at=result.processed_at,
                    source=result.source,
                    source_id=result.source_id,
                    sentiment_score=result.sentiment_score,
                    sentiment_label=result.sentiment_label,
                    confidence=result.confidence,
                    model_version=result.model_version
                )
                row_data_list.append(row_data)
            
            # Send in batches
            success = True
            for i in range(0, len(row_data_list), self.batch_size):
                batch = row_data_list[i:i + self.batch_size]
                batch_success = await self._send_batch(batch)
                if not batch_success:
                    success = False
            
            return success
            
        except Exception as e:
            logger.error(f"Error pushing multiple rows to Power BI: {str(e)}")
            return False
    
    async def flush_batch(self) -> bool:
        """
        Flush any remaining batched data to Power BI.
        
        Returns:
            bool: True if successful, False otherwise
        """
        async with self._batch_lock:
            return await self._flush_batch_internal()
    
    async def _flush_batch_internal(self) -> bool:
        """
        Internal method to flush batch queue (assumes lock is held).
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self._batch_queue:
            return True
        
        batch = self._batch_queue.copy()
        self._batch_queue.clear()
        
        return await self._send_batch(batch)
    
    async def _send_batch(self, batch: List[PowerBIRowData]) -> bool:
        """
        Send a batch of rows to Power BI with retry logic.
        
        Args:
            batch: List of PowerBI row data to send
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not batch:
            return True
        
        # Convert to JSON format expected by Power BI
        payload = {
            "rows": [row.model_dump_json_compatible() for row in batch]
        }
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(f"Sending batch of {len(batch)} rows to Power BI (attempt {attempt + 1})")
                
                response = await self.client.post(
                    self.push_url,
                    json=payload
                )
                
                if response.status_code == 200:
                    logger.info(f"Successfully pushed {len(batch)} rows to Power BI")
                    return True
                elif response.status_code == 429:
                    # Rate limited - wait longer before retry
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Rate limited by Power BI, waiting {wait_time}s before retry")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Power BI API error: {response.status_code} - {response.text}")
                    if attempt < self.max_retries:
                        await asyncio.sleep(self.retry_delay)
                        continue
                    else:
                        return False
                        
            except httpx.TimeoutException:
                logger.error(f"Timeout pushing to Power BI (attempt {attempt + 1})")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay)
                    continue
                else:
                    return False
                    
            except Exception as e:
                logger.error(f"Error pushing to Power BI (attempt {attempt + 1}): {str(e)}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay)
                    continue
                else:
                    return False
        
        return False
    
    async def test_connection(self) -> bool:
        """
        Test the connection to Power BI by sending an empty batch.
        
        Returns:
            bool: True if connection is working, False otherwise
        """
        try:
            payload = {"rows": []}
            response = await self.client.post(self.push_url, json=payload)
            
            if response.status_code == 200:
                logger.info("Power BI connection test successful")
                return True
            else:
                logger.error(f"Power BI connection test failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Power BI connection test error: {str(e)}")
            return False
