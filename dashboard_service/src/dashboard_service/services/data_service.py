"""
Data service module for dashboard service.

This module provides centralized data fetching and processing services
for the dashboard, with caching and error handling.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from loguru import logger

from dashboard_service.api import SentimentAPIClient
from dashboard_service.config import get_settings


class DataService:
    """
    Centralized data service for dashboard operations.
    
    Provides cached data fetching, processing, and aggregation
    for sentiment analysis data.
    """
    
    def __init__(self, api_client: SentimentAPIClient):
        """
        Initialize data service.
        
        Args:
            api_client: Sentiment API client instance
        """
        self.api_client = api_client
        self.settings = get_settings()
    
    @st.cache_data(ttl=300)  # Cache for 5 minutes
    def fetch_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        source: Optional[str] = None,
        sentiment_label: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Fetch sentiment events with caching.
        
        Args:
            start_time: Filter events after this timestamp
            end_time: Filter events before this timestamp
            source: Filter by source
            sentiment_label: Filter by sentiment label
            limit: Maximum number of events to fetch
            
        Returns:
            List of event dictionaries
        """
        try:
            events = self.api_client.get_events(
                start_time=start_time,
                end_time=end_time,
                source=source,
                sentiment_label=sentiment_label,
                limit=limit
            )
            
            # Convert to dict format for easier processing
            events_data = []
            for event in events:
                events_data.append({
                    'id': event.id,
                    'occurred_at': event.occurred_at,
                    'processed_at': event.processed_at,
                    'source': event.source,
                    'source_id': event.source_id,
                    'sentiment_label': event.sentiment_label,
                    'sentiment_score': event.sentiment_score,
                    'confidence': event.confidence,
                    'raw_text': event.raw_text
                })
            
            logger.info(f"Fetched {len(events_data)} events from API")
            return events_data
            
        except Exception as e:
            logger.error(f"Error fetching events: {str(e)}")
            return []
    
    @st.cache_data(ttl=300)  # Cache for 5 minutes
    def fetch_metrics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        source: Optional[str] = None,
        sentiment_label: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Fetch sentiment metrics with caching.
        
        Args:
            start_time: Filter metrics after this timestamp
            end_time: Filter metrics before this timestamp
            source: Filter by source
            sentiment_label: Filter by sentiment label
            limit: Maximum number of metrics to fetch
            
        Returns:
            List of metric dictionaries
        """
        try:
            metrics = self.api_client.get_metrics(
                start_time=start_time,
                end_time=end_time,
                source=source,
                sentiment_label=sentiment_label,
                limit=limit
            )
            
            # Convert to dict format for easier processing
            metrics_data = []
            for metric in metrics:
                metrics_data.append({
                    'id': metric.id,
                    'metric_timestamp': metric.metric_timestamp,
                    'source': metric.source,
                    'source_id': metric.source_id,
                    'sentiment_label': metric.sentiment_label,
                    'event_count': metric.event_count,
                    'avg_sentiment_score': metric.avg_sentiment_score,
                    'min_sentiment_score': metric.min_sentiment_score,
                    'max_sentiment_score': metric.max_sentiment_score,
                    'std_sentiment_score': metric.std_sentiment_score
                })
            
            logger.info(f"Fetched {len(metrics_data)} metrics from API")
            return metrics_data
            
        except Exception as e:
            logger.error(f"Error fetching metrics: {str(e)}")
            return []
    
    def calculate_overview_stats(self, events_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate overview statistics from events data.
        
        Args:
            events_data: List of event dictionaries
            
        Returns:
            Dictionary containing overview statistics
        """
        if not events_data:
            return {
                "total_events": 0,
                "avg_sentiment": 0.0,
                "sentiment_distribution": {},
                "sources": [],
                "confidence_avg": 0.0
            }
        
        df = pd.DataFrame(events_data)
        
        # Basic statistics
        total_events = len(df)
        avg_sentiment = df['sentiment_score'].mean()
        
        # Sentiment distribution
        sentiment_counts = df['sentiment_label'].value_counts().to_dict()
        
        # Unique sources
        sources = df['source'].unique().tolist()
        
        # Average confidence (if available)
        confidence_avg = 0.0
        if 'confidence' in df.columns and not df['confidence'].isna().all():
            confidence_avg = df['confidence'].mean()
        
        return {
            "total_events": total_events,
            "avg_sentiment": avg_sentiment,
            "sentiment_distribution": sentiment_counts,
            "sources": sources,
            "confidence_avg": confidence_avg
        }
    
    def prepare_time_series_data(self, events_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Prepare data for time series visualization.
        
        Args:
            events_data: List of event dictionaries
            
        Returns:
            DataFrame with time series data
        """
        if not events_data:
            return pd.DataFrame()
        
        df = pd.DataFrame(events_data)
        df['occurred_at'] = pd.to_datetime(df['occurred_at'])
        
        # Group by hour and sentiment label
        df['hour'] = df['occurred_at'].dt.floor('H')
        
        hourly_data = df.groupby(['hour', 'sentiment_label']).agg({
            'sentiment_score': ['mean', 'count', 'std'],
            'confidence': 'mean'
        }).reset_index()
        
        # Flatten column names
        hourly_data.columns = [
            'hour', 'sentiment_label', 'avg_score', 'count', 'std_score', 'avg_confidence'
        ]
        
        return hourly_data
    
    def get_source_analysis(self, events_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Analyze events by source.
        
        Args:
            events_data: List of event dictionaries
            
        Returns:
            DataFrame with source analysis
        """
        if not events_data:
            return pd.DataFrame()
        
        df = pd.DataFrame(events_data)
        
        # Group by source and sentiment
        source_analysis = df.groupby(['source', 'sentiment_label']).agg({
            'sentiment_score': ['count', 'mean', 'std'],
            'confidence': 'mean'
        }).reset_index()
        
        # Flatten column names
        source_analysis.columns = [
            'source', 'sentiment_label', 'event_count', 'avg_sentiment', 
            'std_sentiment', 'avg_confidence'
        ]
        
        return source_analysis
    
    def get_recent_events_for_display(
        self, 
        events_data: List[Dict[str, Any]], 
        limit: int = 50
    ) -> List[Dict[str, str]]:
        """
        Prepare recent events for display in table format.
        
        Args:
            events_data: List of event dictionaries
            limit: Maximum number of events to return
            
        Returns:
            List of formatted event dictionaries for display
        """
        if not events_data:
            return []
        
        # Sort by occurred_at descending and limit
        df = pd.DataFrame(events_data)
        df['occurred_at'] = pd.to_datetime(df['occurred_at'])
        df_sorted = df.sort_values('occurred_at', ascending=False).head(limit)
        
        # Format for display
        display_data = []
        for _, event in df_sorted.iterrows():
            display_data.append({
                "Time": event['occurred_at'].strftime("%Y-%m-%d %H:%M"),
                "Source": event['source'],
                "Source ID": str(event['source_id']),
                "Sentiment": event['sentiment_label'].title(),
                "Score": f"{event['sentiment_score']:.3f}",
                "Confidence": f"{event['confidence']:.3f}" if pd.notna(event['confidence']) else "N/A",
                "Text Preview": (
                    event['raw_text'][:100] + "..." 
                    if event['raw_text'] and len(str(event['raw_text'])) > 100 
                    else str(event['raw_text']) if event['raw_text'] else "N/A"
                )
            })
        
        return display_data
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on data service.
        
        Returns:
            Health check results
        """
        try:
            # Test API connectivity
            health = self.api_client.health_check()
            
            return {
                "status": "healthy",
                "api_status": health,
                "cache_enabled": True,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Data service health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
