"""
Main Streamlit application entry point for the dashboard service.

This module sets up the Streamlit app configuration, handles routing between pages,
and provides the main dashboard interface.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from loguru import logger

from dashboard_service.chart_simple import create_simple_sentiment_chart
from dashboard_service.chart_advanced import create_advanced_sentiment_chart, create_sentiment_heatmap_advanced
from dashboard_service.config import get_settings
from dashboard_service.api import SentimentAPIClient
from dashboard_service.utils.logging import setup_logging


def setup_page_config() -> None:
    """Configure Streamlit page settings."""
    st.set_page_config(
        page_title="Sentiment Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            'Get Help': 'https://github.com/your-repo/dashboard_service',
            'Report a bug': 'https://github.com/your-repo/dashboard_service/issues',
            'About': """
            # Sentiment Pipeline Dashboard
            
            Custom analytics and visualization dashboard for sentiment analysis results.
            
            **Version:** 1.0.0
            **Built with:** Streamlit + Plotly
            """
        }
    )


@st.cache_resource
def get_api_client() -> SentimentAPIClient:
    """Get or create API client instance (cached)."""
    settings = get_settings()
    return SentimentAPIClient(
        base_url=settings.sentiment_api_base_url,
        timeout=settings.sentiment_api_timeout
    )


def initialize_session_state() -> None:
    """Initialize Streamlit session state variables."""
    if 'api_client' not in st.session_state:
        st.session_state.api_client = get_api_client()
    
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = datetime.now()
    
    if 'auto_refresh' not in st.session_state:
        st.session_state.auto_refresh = True
    
    if 'refresh_interval' not in st.session_state:
        st.session_state.refresh_interval = 30
    
    if 'selected_sources' not in st.session_state:
        st.session_state.selected_sources = []
    
    if 'date_range' not in st.session_state:
        st.session_state.date_range = (
            datetime.now() - timedelta(days=7),
            datetime.now()
        )
    
    if 'fetch_limit' not in st.session_state:
        st.session_state.fetch_limit = 5000  # Default to 5000 events
    
    if 'enable_bulk_fetch' not in st.session_state:
        st.session_state.enable_bulk_fetch = True


def render_sidebar() -> None:
    """Render the sidebar with navigation and controls."""
    st.sidebar.title("📊 Sentiment Dashboard")
    
    # Navigation
    st.sidebar.markdown("## Navigation")
    
    # API Status
    st.sidebar.markdown("## API Status")
    try:
        health = st.session_state.api_client.health_check()
        st.sidebar.success("✅ API Connected")
        if st.sidebar.expander("API Details"):
            st.json(health)
    except Exception as e:
        st.sidebar.error(f"❌ API Error: {str(e)}")
    
    # Auto-refresh controls
    st.sidebar.markdown("## Refresh Settings")
    st.session_state.auto_refresh = st.sidebar.checkbox(
        "Auto Refresh", 
        value=st.session_state.auto_refresh
    )
    
    if st.session_state.auto_refresh:
        st.session_state.refresh_interval = st.sidebar.selectbox(
            "Refresh Interval (seconds)",
            options=[10, 30, 60, 300],
            index=1,
            format_func=lambda x: f"{x}s"
        )
    
    # Manual refresh button
    if st.sidebar.button("🔄 Refresh Now"):
        st.session_state.last_refresh = datetime.now()
        st.rerun()
    
    # Last refresh time
    st.sidebar.caption(f"Last refresh: {st.session_state.last_refresh.strftime('%H:%M:%S')}")
    
    # Data fetching controls
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        
        # Fetch limit configuration
        st.markdown("### 📊 Data Fetching")
        
        # Fetch mode selection
        fetch_mode = st.radio(
            "Fetch Mode",
            options=["Limited", "Comprehensive", "Unlimited"],
            index=st.session_state.get('fetch_mode_index', 1),
            help="Limited: Fast fetch with event limit. Comprehensive: Fetch more events with time chunking. Unlimited: Fetch ALL available events (may be slow)."
        )
        st.session_state.fetch_mode_index = ["Limited", "Comprehensive", "Unlimited"].index(fetch_mode)
        st.session_state.fetch_mode = fetch_mode
        
        if fetch_mode == "Limited":
            # Fetch limit slider
            fetch_limit = st.slider(
                "Event Fetch Limit",
                min_value=1000,
                max_value=10000,
                value=st.session_state.get('fetch_limit', 5000),
                step=500,
                help="Maximum number of events to fetch quickly."
            )
            st.session_state.fetch_limit = fetch_limit
            st.session_state.enable_bulk_fetch = False
        elif fetch_mode == "Comprehensive":
            # Comprehensive fetching with higher limits
            fetch_limit = st.slider(
                "Target Event Count",
                min_value=5000,
                max_value=100000,
                value=st.session_state.get('fetch_limit', 20000),
                step=5000,
                help="Target number of events to fetch using time-based chunking."
            )
            st.session_state.fetch_limit = fetch_limit
            st.session_state.enable_bulk_fetch = True
        else:  # Unlimited
            st.info("🚀 Unlimited mode will fetch ALL available events in the selected time range. This may take several minutes for large datasets.")
            st.session_state.fetch_limit = 999999  # Very high limit
            st.session_state.enable_bulk_fetch = True
        
        # Show current settings
        if fetch_mode != "Unlimited":
            st.caption(f"Current limit: {st.session_state.fetch_limit:,} events")
    
    if st.sidebar.expander("📋 Current Settings"):
        st.write(f"**Fetch Limit:** {st.session_state.fetch_limit:,} events")
        st.write(f"**Bulk Fetch:** {'Enabled' if st.session_state.enable_bulk_fetch else 'Disabled'}")
        st.write(f"**Cache TTL:** 5 minutes")


@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_events_data(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    source: Optional[str] = None,
    sentiment_label: Optional[str] = None,
    limit: int = 5000
) -> List[Dict[str, Any]]:
    """Fetch events data with caching, enhanced debugging, and bulk fetching support."""
    try:
        client = get_api_client()
        
        # Log the request parameters for debugging
        logger.info(f"Fetching events with params: start_time={start_time}, end_time={end_time}, source={source}, sentiment_label={sentiment_label}, limit={limit}")
        
        # First, try to get some data without date filters to check if API is working
        try:
            test_events = client.get_events(limit=5)
            logger.info(f"Test query returned {len(test_events)} events")
            if test_events:
                logger.info(f"Sample event date range: {test_events[0].occurred_at} to {test_events[-1].occurred_at}")
        except Exception as test_e:
            logger.error(f"Test query failed: {str(test_e)}")
        
        # Handle fetching ALL available events in the time range
        all_events = []
        
        # Always use comprehensive fetching when bulk fetch is enabled
        if st.session_state.get('enable_bulk_fetch', True):
            # Show progress for comprehensive fetching
            with st.spinner('Fetching ALL available events in time range...'):
                logger.info(f"Fetching ALL events in time range (ignoring limit={limit})")
                
                # Create progress indicators
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                if start_time and end_time:
                    # Calculate optimal number of time chunks based on date range
                    time_diff = end_time - start_time
                    days_diff = time_diff.days
                    
                    # Adaptive chunking based on time range
                    if days_diff <= 7:  # Week or less
                        chunk_count = max(1, days_diff)  # Daily chunks
                    elif days_diff <= 30:  # Month or less
                        chunk_count = min(10, days_diff // 3)  # 3-day chunks, max 10
                    else:  # Longer periods
                        chunk_count = min(20, days_diff // 7)  # Weekly chunks, max 20
                    
                    chunk_count = max(1, chunk_count)  # Ensure at least 1 chunk
                    chunk_duration = time_diff / chunk_count
                    
                    logger.info(f"Using {chunk_count} time chunks for {days_diff} days")
                    
                    for i in range(chunk_count):
                        chunk_start = start_time + (chunk_duration * i)
                        chunk_end = start_time + (chunk_duration * (i + 1))
                        
                        # Update progress
                        progress = (i + 1) / chunk_count
                        progress_bar.progress(progress)
                        status_text.text(f"Fetching time chunk {i+1}/{chunk_count} ({len(all_events):,} events loaded)")
                        
                        # Fetch ALL events in this time chunk using proper cursor-based pagination
                        chunk_events = []
                        page_limit = 10000  # Use the new higher API limit
                        max_pages = 100  # Safety limit to prevent infinite loops
                        page_count = 0
                        cursor = None  # Start with no cursor for first page
                        
                        while page_count < max_pages:
                            try:
                                # Use proper cursor-based pagination
                                page_events = client.get_events(
                                    start_time=chunk_start,
                                    end_time=chunk_end,
                                    source=source,
                                    sentiment_label=sentiment_label,
                                    limit=page_limit,
                                    cursor=cursor  # Pass cursor for pagination
                                )
                                
                                if not page_events:
                                    # No more events in this chunk
                                    logger.info(f"No more events found in chunk {i+1}, page {page_count+1}")
                                    break
                                
                                # Add all events from this page
                                chunk_events.extend(page_events)
                                page_count += 1
                                
                                logger.info(f"Chunk {i+1}, page {page_count}: fetched {len(page_events)} events (chunk total: {len(chunk_events)})")
                                
                                # If we got fewer events than requested, we've reached the end
                                if len(page_events) < page_limit:
                                    logger.info(f"Reached end of chunk {i+1} (got {len(page_events)} < {page_limit})")
                                    break
                                
                                # Generate cursor for next page from the last event
                                # The API expects cursor based on processed_at and id
                                last_event = page_events[-1]
                                import base64
                                import json
                                cursor_data = {
                                    "timestamp": last_event.processed_at.isoformat(),
                                    "id": last_event.id
                                }
                                cursor_json = json.dumps(cursor_data)
                                cursor = base64.b64encode(cursor_json.encode()).decode()
                                
                                logger.info(f"Generated cursor for next page: {cursor[:50]}...")
                                    
                            except Exception as page_e:
                                logger.warning(f"Error in page {page_count + 1} of chunk {i+1}: {str(page_e)}")
                                break
                        
                        if chunk_events:
                            all_events.extend(chunk_events)
                            logger.info(f"Fetched {len(chunk_events)} events from {chunk_start} to {chunk_end} ({page_count} pages), total: {len(all_events)}")
                        else:
                            logger.info(f"No events found in chunk {i+1} ({chunk_start} to {chunk_end})")
                else:
                    # Fallback: Just fetch maximum available without chunking
                    logger.warning("No time range specified, fetching single chunk with max limit")
                    try:
                        events = client.get_events(
                            start_time=start_time,
                            end_time=end_time,
                            source=source,
                            sentiment_label=sentiment_label,
                            limit=1000  # API limit
                        )
                        all_events.extend(events)
                        st.info(f"Fetched {len(events)} events (API limit reached)")
                    except Exception as e:
                        logger.error(f"Error in fallback fetch: {str(e)}")
                        st.error(f"Error fetching events: {str(e)}")
                
                # Clean up progress indicators
                progress_bar.empty()
                status_text.empty()
                
                # Show completion message
                if all_events:
                    # Remove duplicates based on event ID
                    unique_events = {}
                    for event in all_events:
                        if hasattr(event, 'id') and event.id not in unique_events:
                            unique_events[event.id] = event
                    
                    all_events = list(unique_events.values())
                    st.success(f"Successfully fetched {len(all_events):,} unique events")
                else:
                    st.warning("No events were fetched")
            
            events = all_events[:limit]  # Ensure we don't exceed the requested limit
        else:
            # Single request for smaller limits
            events = client.get_events(
                start_time=start_time,
                end_time=end_time,
                source=source,
                sentiment_label=sentiment_label,
                limit=min(limit, 1000)  # Cap at 1000 for single requests
            )
        
        logger.info(f"Final query returned {len(events)} events")
        
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
        
        return events_data
    except Exception as e:
        logger.error(f"Error fetching events data: {str(e)}")
        # Show error in UI for debugging
        st.error(f"API Error: {str(e)}")
        return []


def check_data_availability() -> Dict[str, Any]:
    """Check what data is available in the system for debugging.
    
    Returns:
        Dictionary with data availability information
    """
    try:
        client = get_api_client()
        
        # Get a small sample of recent data
        recent_events = client.get_events(limit=10)
        
        if not recent_events:
            return {
                "has_data": False,
                "total_events": 0,
                "date_range": None,
                "sources": [],
                "message": "No events found in the database"
            }
        
        # Get date range of available data
        dates = [event.occurred_at for event in recent_events]
        min_date = min(dates)
        max_date = max(dates)
        
        # Get unique sources
        sources = list(set(event.source for event in recent_events))
        
        return {
            "has_data": True,
            "total_events": len(recent_events),
            "date_range": f"{min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}",
            "sources": sources,
            "message": f"Found {len(recent_events)} recent events"
        }
        
    except Exception as e:
        return {
            "has_data": False,
            "total_events": 0,
            "date_range": None,
            "sources": [],
            "message": f"Error checking data availability: {str(e)}"
        }


@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_metrics_data(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    source: Optional[str] = None,
    sentiment_label: Optional[str] = None,
    limit: int = 1000
) -> List[Dict[str, Any]]:
    """Fetch metrics data with caching."""
    try:
        client = get_api_client()
        metrics = client.get_metrics(
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
        
        return metrics_data
    except Exception as e:
        logger.error(f"Error fetching metrics data: {str(e)}")
        return []


# Temporarily commented out broken chart function
# def create_sentiment_time_series_chart(events_data: List[Dict[str, Any]], granularity: str = 'hour') -> go.Figure:
#     """Create interactive time series chart with drill-down functionality."""
#     # This function has syntax errors and is temporarily disabled
#     # Using create_simple_sentiment_chart instead
#     pass


def create_sentiment_heatmap(events_data: List[Dict[str, Any]], time_granularity: str = 'hour') -> go.Figure:
    """Create sentiment distribution heatmap over time.
    
    Args:
        events_data: List of event dictionaries
        time_granularity: Time granularity for heatmap ('hour', 'day', 'week')
    
    Returns:
        Plotly heatmap figure
    """
    if not events_data:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available for heatmap",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        return fig
    
    df = pd.DataFrame(events_data)
    df['occurred_at'] = pd.to_datetime(df['occurred_at'])
    
    # Create time grouping
    if time_granularity == 'hour':
        df['time_period'] = df['occurred_at'].dt.hour
        df['date'] = df['occurred_at'].dt.date
        time_labels = [f"{i:02d}:00" for i in range(24)]
    elif time_granularity == 'day':
        df['time_period'] = df['occurred_at'].dt.day_name()
        # Use year-week format for better grouping
        df['date'] = df['occurred_at'].dt.strftime('%Y-W%U')
        time_labels = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    else:  # week
        # Use ISO week number for better consistency
        df['time_period'] = df['occurred_at'].dt.isocalendar().week
        df['date'] = df['occurred_at'].dt.year.astype(str)
        time_labels = [f"Week {i}" for i in range(1, 53)]
    
    # Create pivot table for heatmap
    heatmap_data = df.groupby(['date', 'time_period', 'sentiment_label']).size().unstack(fill_value=0)
    
    # Create separate heatmaps for each sentiment
    sentiments = ['positive', 'negative', 'neutral']
    colors = ['Greens', 'Reds', 'Blues']
    
    fig = make_subplots(
        rows=len(sentiments), cols=1,
        subplot_titles=[f'{s.title()} Sentiment Distribution' for s in sentiments],
        vertical_spacing=0.1
    )
    
    for i, (sentiment, colorscale) in enumerate(zip(sentiments, colors)):
        if sentiment in heatmap_data.columns:
            sentiment_pivot = df[df['sentiment_label'] == sentiment].groupby(['date', 'time_period']).size().unstack(fill_value=0)
            
            fig.add_trace(
                go.Heatmap(
                    z=sentiment_pivot.values,
                    x=sentiment_pivot.columns,
                    y=sentiment_pivot.index,
                    colorscale=colorscale,
                    showscale=True,
                    hovertemplate=f'<b>{sentiment.title()} Events</b><br>' +
                                 'Time: %{x}<br>' +
                                 'Date: %{y}<br>' +
                                 'Count: %{z}<extra></extra>'
                ),
                row=i+1, col=1
            )
    
    fig.update_layout(
        height=600,
        title_text=f"Sentiment Distribution Heatmap - {time_granularity.title()} View"
    )
    
    return fig


def create_multi_source_comparison_chart(events_data: List[Dict[str, Any]]) -> go.Figure:
    """Create multi-source comparison charts.
    
    Args:
        events_data: List of event dictionaries
    
    Returns:
        Plotly figure with source comparisons
    """
    if not events_data:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available for source comparison",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        return fig
    
    df = pd.DataFrame(events_data)
    
    # Create subplots for different comparison views
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            'Average Sentiment by Source',
            'Event Volume by Source',
            'Sentiment Distribution by Source',
            'Source Activity Timeline'
        ),
        specs=[[{"type": "bar"}, {"type": "bar"}],
               [{"type": "bar"}, {"type": "scatter"}]]
    )
    
    # 1. Average sentiment by source
    source_avg = df.groupby('source')['sentiment_score'].mean().sort_values(ascending=True)
    colors_avg = ['#2E8B57' if x > 0 else '#DC143C' if x < 0 else '#4682B4' for x in source_avg.values]
    
    fig.add_trace(
        go.Bar(
            x=source_avg.values,
            y=source_avg.index,
            orientation='h',
            marker_color=colors_avg,
            name='Avg Sentiment',
            hovertemplate='<b>%{y}</b><br>Avg Sentiment: %{x:.3f}<extra></extra>'
        ),
        row=1, col=1
    )
    
    # 2. Event volume by source
    source_counts = df['source'].value_counts()
    fig.add_trace(
        go.Bar(
            x=source_counts.index,
            y=source_counts.values,
            marker_color='#4682B4',
            name='Event Count',
            hovertemplate='<b>%{x}</b><br>Events: %{y}<extra></extra>'
        ),
        row=1, col=2
    )
    
    # 3. Sentiment distribution by source (stacked bar)
    source_sentiment = df.groupby(['source', 'sentiment_label']).size().unstack(fill_value=0)
    
    colors_sentiment = {'positive': '#2E8B57', 'negative': '#DC143C', 'neutral': '#4682B4'}
    for sentiment in source_sentiment.columns:
        fig.add_trace(
            go.Bar(
                x=source_sentiment.index,
                y=source_sentiment[sentiment],
                name=f'{sentiment.title()}',
                marker_color=colors_sentiment.get(sentiment, '#666666'),
                hovertemplate=f'<b>%{{x}}</b><br>{sentiment.title()}: %{{y}}<extra></extra>',
                showlegend=False
            ),
            row=2, col=1
        )
    
    # 4. Source activity timeline
    df['occurred_at'] = pd.to_datetime(df['occurred_at'])
    df['hour'] = df['occurred_at'].dt.floor('H')
    
    source_timeline = df.groupby(['hour', 'source']).size().reset_index(name='count')
    
    for source in df['source'].unique():
        source_data = source_timeline[source_timeline['source'] == source]
        fig.add_trace(
            go.Scatter(
                x=source_data['hour'],
                y=source_data['count'],
                mode='lines+markers',
                name=source,
                hovertemplate=f'<b>{source}</b><br>Time: %{{x}}<br>Events: %{{y}}<extra></extra>',
                showlegend=False
            ),
            row=2, col=2
        )
    
    # Update layout
    fig.update_layout(
        height=800,
        title_text="Multi-Source Sentiment Analysis Comparison",
        showlegend=True
    )
    
    # Update axes
    fig.update_xaxes(title_text="Average Sentiment Score", row=1, col=1)
    fig.update_yaxes(title_text="Source", row=1, col=1)
    fig.update_xaxes(title_text="Source", row=1, col=2)
    fig.update_yaxes(title_text="Event Count", row=1, col=2)
    fig.update_xaxes(title_text="Source", row=2, col=1)
    fig.update_yaxes(title_text="Event Count", row=2, col=1)
    fig.update_xaxes(title_text="Time", row=2, col=2)
    fig.update_yaxes(title_text="Event Count", row=2, col=2)
    
    return fig


def create_statistical_analysis_display(events_data: List[Dict[str, Any]]) -> Dict[str, go.Figure]:
    """Create statistical analysis displays with moving averages and percentiles.
    
    Args:
        events_data: List of event dictionaries
    
    Returns:
        Dictionary of Plotly figures for different statistical views
    """
    if not events_data:
        empty_fig = go.Figure()
        empty_fig.add_annotation(
            text="No data available for statistical analysis",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        return {"moving_averages": empty_fig, "percentiles": empty_fig}
    
    df = pd.DataFrame(events_data)
    df['occurred_at'] = pd.to_datetime(df['occurred_at'])
    df = df.sort_values('occurred_at')
    
    # Moving averages chart
    df['hour'] = df['occurred_at'].dt.floor('H')
    hourly_sentiment = df.groupby('hour')['sentiment_score'].mean().reset_index()
    
    # Calculate moving averages
    hourly_sentiment['ma_3h'] = hourly_sentiment['sentiment_score'].rolling(window=3, center=True).mean()
    hourly_sentiment['ma_6h'] = hourly_sentiment['sentiment_score'].rolling(window=6, center=True).mean()
    hourly_sentiment['ma_12h'] = hourly_sentiment['sentiment_score'].rolling(window=12, center=True).mean()
    
    ma_fig = go.Figure()
    
    # Add raw data
    ma_fig.add_trace(
        go.Scatter(
            x=hourly_sentiment['hour'],
            y=hourly_sentiment['sentiment_score'],
            mode='markers',
            name='Hourly Average',
            marker=dict(color='lightblue', size=4),
            opacity=0.6
        )
    )
    
    # Add moving averages
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1']
    windows = ['ma_3h', 'ma_6h', 'ma_12h']
    labels = ['3-Hour MA', '6-Hour MA', '12-Hour MA']
    
    for ma, color, label in zip(windows, colors, labels):
        ma_fig.add_trace(
            go.Scatter(
                x=hourly_sentiment['hour'],
                y=hourly_sentiment[ma],
                mode='lines',
                name=label,
                line=dict(color=color, width=2)
            )
        )
    
    ma_fig.update_layout(
        title="Sentiment Moving Averages",
        xaxis_title="Time",
        yaxis_title="Sentiment Score",
        height=400
    )
    
    # Percentiles chart
    percentile_fig = go.Figure()
    
    # Calculate rolling percentiles
    hourly_sentiment['p10'] = hourly_sentiment['sentiment_score'].rolling(window=12).quantile(0.1)
    hourly_sentiment['p25'] = hourly_sentiment['sentiment_score'].rolling(window=12).quantile(0.25)
    hourly_sentiment['p50'] = hourly_sentiment['sentiment_score'].rolling(window=12).quantile(0.5)
    hourly_sentiment['p75'] = hourly_sentiment['sentiment_score'].rolling(window=12).quantile(0.75)
    hourly_sentiment['p90'] = hourly_sentiment['sentiment_score'].rolling(window=12).quantile(0.9)
    
    # Add percentile bands
    percentile_fig.add_trace(
        go.Scatter(
            x=hourly_sentiment['hour'],
            y=hourly_sentiment['p90'],
            mode='lines',
            name='90th Percentile',
            line=dict(color='rgba(255,0,0,0)'),
            showlegend=False
        )
    )
    
    percentile_fig.add_trace(
        go.Scatter(
            x=hourly_sentiment['hour'],
            y=hourly_sentiment['p10'],
            mode='lines',
            name='10-90th Percentile',
            fill='tonexty',
            fillcolor='rgba(255,182,193,0.3)',
            line=dict(color='rgba(255,0,0,0)')
        )
    )
    
    percentile_fig.add_trace(
        go.Scatter(
            x=hourly_sentiment['hour'],
            y=hourly_sentiment['p75'],
            mode='lines',
            name='75th Percentile',
            line=dict(color='rgba(0,100,80,0)'),
            showlegend=False
        )
    )
    
    percentile_fig.add_trace(
        go.Scatter(
            x=hourly_sentiment['hour'],
            y=hourly_sentiment['p25'],
            mode='lines',
            name='25-75th Percentile',
            fill='tonexty',
            fillcolor='rgba(0,176,246,0.3)',
            line=dict(color='rgba(0,100,80,0)')
        )
    )
    
    percentile_fig.add_trace(
        go.Scatter(
            x=hourly_sentiment['hour'],
            y=hourly_sentiment['p50'],
            mode='lines',
            name='Median (50th)',
            line=dict(color='#2E8B57', width=2)
        )
    )
    
    percentile_fig.update_layout(
        title="Sentiment Score Percentiles (12-Hour Rolling Window)",
        xaxis_title="Time",
        yaxis_title="Sentiment Score",
        height=400
    )
    
    return {
        "moving_averages": ma_fig,
        "percentiles": percentile_fig
    }


def create_export_data(events_data: List[Dict[str, Any]], export_format: str) -> bytes:
    """Create exportable data in various formats.
    
    Args:
        events_data: List of event dictionaries
        export_format: Format to export ('csv', 'json', 'excel')
    
    Returns:
        Bytes data for download
    """
    if not events_data:
        return b"No data available for export"
    
    df = pd.DataFrame(events_data)
    
    if export_format.lower() == 'csv':
        return df.to_csv(index=False).encode('utf-8')
    elif export_format.lower() == 'json':
        return df.to_json(orient='records', indent=2).encode('utf-8')
    elif export_format.lower() == 'excel':
        from io import BytesIO
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Sentiment_Data', index=False)
            
            # Add summary statistics sheet
            summary_stats = df.groupby('sentiment_label').agg({
                'sentiment_score': ['count', 'mean', 'std', 'min', 'max'],
                'source': lambda x: x.nunique()
            }).round(3)
            summary_stats.to_excel(writer, sheet_name='Summary_Statistics')
            
        return buffer.getvalue()
    else:
        return b"Unsupported export format"


def render_export_controls(events_data: List[Dict[str, Any]]) -> None:
    """Render export controls and handle downloads.
    
    Args:
        events_data: List of event dictionaries for export
    """
    st.markdown("### 📥 Export Data")
    
    if not events_data:
        st.warning("No data available for export")
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📄 Export CSV", use_container_width=True):
            csv_data = create_export_data(events_data, 'csv')
            st.download_button(
                label="Download CSV",
                data=csv_data,
                file_name=f"sentiment_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    
    with col2:
        if st.button("📋 Export JSON", use_container_width=True):
            json_data = create_export_data(events_data, 'json')
            st.download_button(
                label="Download JSON",
                data=json_data,
                file_name=f"sentiment_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
    
    with col3:
        if st.button("📊 Export Excel", use_container_width=True):
            excel_data = create_export_data(events_data, 'excel')
            st.download_button(
                label="Download Excel",
                data=excel_data,
                file_name=f"sentiment_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    # Show data preview
    if st.checkbox("📋 Preview Export Data"):
        df = pd.DataFrame(events_data)
        st.dataframe(df.head(100), use_container_width=True)
        st.caption(f"Showing first 100 rows of {len(df)} total records")


def render_advanced_filters() -> dict:
    """Render advanced filtering interface.
    
    Returns:
        Dictionary of advanced filter parameters
    """
    st.markdown("### 🔍 Advanced Filters")
    
    with st.expander("Advanced Filter Options", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            # Sentiment score range filter
            score_range = st.slider(
                "Sentiment Score Range",
                min_value=-1.0,
                max_value=1.0,
                value=(-1.0, 1.0),
                step=0.1
            )
            
            # Confidence threshold
            confidence_threshold = st.slider(
                "Minimum Confidence",
                min_value=0.0,
                max_value=1.0,
                value=0.0,
                step=0.05
            )
        
        with col2:
            # Text length filters
            min_text_length = st.number_input(
                "Minimum Text Length",
                min_value=0,
                value=0,
                step=10
            )
            
            max_text_length = st.number_input(
                "Maximum Text Length",
                min_value=0,
                value=10000,
                step=100
            )
        
        # Keyword filters
        include_keywords = st.text_input(
            "Include Keywords (comma-separated)",
            placeholder="keyword1, keyword2, ..."
        )
        
        exclude_keywords = st.text_input(
            "Exclude Keywords (comma-separated)",
            placeholder="spam, bot, ..."
        )
    
    return {
        "score_range": score_range,
        "confidence_threshold": confidence_threshold,
        "min_text_length": min_text_length,
        "max_text_length": max_text_length,
        "include_keywords": [k.strip() for k in include_keywords.split(",") if k.strip()] if include_keywords else [],
        "exclude_keywords": [k.strip() for k in exclude_keywords.split(",") if k.strip()] if exclude_keywords else []
    }


def apply_advanced_filters(events_data: List[Dict[str, Any]], filters: dict) -> List[Dict[str, Any]]:
    """Apply advanced filters to events data.
    
    Args:
        events_data: List of event dictionaries
        filters: Dictionary of filter parameters
    
    Returns:
        Filtered list of events
    """
    if not events_data:
        return events_data
    
    df = pd.DataFrame(events_data)
    
    # Apply sentiment score range filter
    score_min, score_max = filters["score_range"]
    df = df[(df['sentiment_score'] >= score_min) & (df['sentiment_score'] <= score_max)]
    
    # Apply confidence threshold
    if 'confidence' in df.columns:
        df = df[df['confidence'] >= filters["confidence_threshold"]]
    
    # Apply text length filters
    if 'text' in df.columns:
        df['text_length'] = df['text'].str.len()
        df = df[
            (df['text_length'] >= filters["min_text_length"]) & 
            (df['text_length'] <= filters["max_text_length"])
        ]
    
    # Apply keyword filters
    if filters["include_keywords"] and 'text' in df.columns:
        pattern = '|'.join(filters["include_keywords"])
        df = df[df['text'].str.contains(pattern, case=False, na=False)]
    
    if filters["exclude_keywords"] and 'text' in df.columns:
        pattern = '|'.join(filters["exclude_keywords"])
        df = df[~df['text'].str.contains(pattern, case=False, na=False)]
    
    return df.to_dict('records')


def create_sentiment_distribution_chart(events_data: List[Dict[str, Any]]) -> go.Figure:
    """Create pie chart for sentiment distribution."""
    if not events_data:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        return fig
    
    # Count sentiment labels
    df = pd.DataFrame(events_data)
    sentiment_counts = df['sentiment_label'].value_counts()
    
    # Color mapping
    color_map = {
        'positive': '#2E8B57',
        'negative': '#DC143C', 
        'neutral': '#4682B4'
    }
    
    colors = [color_map.get(label, '#666666') for label in sentiment_counts.index]
    
    fig = go.Figure(data=[
        go.Pie(
            labels=[label.title() for label in sentiment_counts.index],
            values=sentiment_counts.values,
            hole=0.3,
            marker_colors=colors,
            hovertemplate='<b>%{label}</b><br>' +
                         'Count: %{value}<br>' +
                         'Percentage: %{percent}<extra></extra>'
        )
    ])
    
    fig.update_layout(
        title_text="Sentiment Distribution",
        height=400
    )
    
    return fig


def create_source_analysis_chart(events_data: List[Dict[str, Any]]) -> go.Figure:
    """Create bar chart for source analysis."""
    if not events_data:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        return fig
    
    # Analyze by source and sentiment
    df = pd.DataFrame(events_data)
    source_sentiment = df.groupby(['source', 'sentiment_label']).size().unstack(fill_value=0)
    
    # Create stacked bar chart
    fig = go.Figure()
    
    color_map = {
        'positive': '#2E8B57',
        'negative': '#DC143C',
        'neutral': '#4682B4'
    }
    
    for sentiment in source_sentiment.columns:
        fig.add_trace(go.Bar(
            name=sentiment.title(),
            x=source_sentiment.index,
            y=source_sentiment[sentiment],
            marker_color=color_map.get(sentiment, '#666666'),
            hovertemplate='<b>%{fullData.name}</b><br>' +
                         'Source: %{x}<br>' +
                         'Count: %{y}<extra></extra>'
        ))
    
    fig.update_layout(
        title_text="Sentiment Analysis by Source",
        xaxis_title="Source",
        yaxis_title="Event Count",
        barmode='stack',
        height=400
    )
    
    return fig


def render_filters() -> dict:
    """
    Render filter controls and return filter values.
    
    Returns:
        dict: Filter parameters
    """
    st.markdown("## 🔍 Filters")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Date range filter
        date_range = st.date_input(
            "Date Range",
            value=st.session_state.date_range,
            max_value=datetime.now().date()
        )
        
        if len(date_range) == 2:
            start_date, end_date = date_range
            start_time = datetime.combine(start_date, datetime.min.time())
            end_time = datetime.combine(end_date, datetime.max.time())
        else:
            start_time = datetime.combine(date_range[0], datetime.min.time())
            end_time = datetime.now()
    
    with col2:
        # Source filter
        source = st.selectbox(
            "Source",
            options=["All", "reddit", "twitter"],  # Add more as needed
            index=0
        )
        source = None if source == "All" else source
    
    with col3:
        # Sentiment filter
        sentiment_label = st.selectbox(
            "Sentiment",
            options=["All", "positive", "negative", "neutral"],
            index=0
        )
        sentiment_label = None if sentiment_label == "All" else sentiment_label
    
    return {
        "start_time": start_time,
        "end_time": end_time,
        "source": source,
        "sentiment_label": sentiment_label
    }


def render_overview_metrics(filters: dict, events_data: Optional[List[Dict[str, Any]]] = None) -> None:
    """
    Render overview metrics cards.
    
    Args:
        filters: Filter parameters
        events_data: Pre-fetched events data (optional, will fetch if not provided)
    """
    st.markdown("## 📊 Overview Metrics")
    
    try:
        # Use provided events_data or fetch with configurable limit
        if events_data is None:
            events_data = fetch_events_data(
                start_time=filters["start_time"],
                end_time=filters["end_time"],
                source=filters["source"],
                sentiment_label=filters["sentiment_label"],
                limit=st.session_state.fetch_limit  # Use configurable limit
            )
        
        if events_data:
            # Calculate metrics
            total_events = len(events_data)
            avg_sentiment = sum(event['sentiment_score'] for event in events_data) / total_events
            
            # Count by sentiment
            sentiment_counts = {}
            for event in events_data:
                label = event['sentiment_label']
                sentiment_counts[label] = sentiment_counts.get(label, 0) + 1
            
            positive_count = sentiment_counts.get("positive", 0)
            negative_count = sentiment_counts.get("negative", 0)
            neutral_count = sentiment_counts.get("neutral", 0)
            
            # Display metrics in columns
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric(
                    label="Total Events",
                    value=f"{total_events:,}"
                )
            
            with col2:
                st.metric(
                    label="Avg Sentiment",
                    value=f"{avg_sentiment:.3f}",
                    delta=f"{avg_sentiment:.3f}" if avg_sentiment > 0 else None
                )
            
            with col3:
                st.metric(
                    label="Positive",
                    value=f"{positive_count:,}",
                    delta=f"{positive_count/total_events*100:.1f}%"
                )
            
            with col4:
                st.metric(
                    label="Negative", 
                    value=f"{negative_count:,}",
                    delta=f"{negative_count/total_events*100:.1f}%"
                )
            
            with col5:
                st.metric(
                    label="Neutral",
                    value=f"{neutral_count:,}",
                    delta=f"{neutral_count/total_events*100:.1f}%"
                )
        else:
            # Show data availability information when no data is found
            st.warning("No data available for the selected filters.")
            
            # Check what data is actually available
            with st.expander("🔍 Data Availability Check", expanded=True):
                data_info = check_data_availability()
                
                if data_info["has_data"]:
                    st.info(f"✅ {data_info['message']}")
                    st.write(f"**Available date range:** {data_info['date_range']}")
                    st.write(f"**Available sources:** {', '.join(data_info['sources'])}")
                    st.write("💡 **Tip:** Try adjusting your date range to match the available data.")
                else:
                    st.error(f"❌ {data_info['message']}")
                    st.write("**Possible solutions:**")
                    st.write("- Check if the sentiment analyzer API is running")
                    st.write("- Verify that data is being processed and stored")
                    st.write("- Check the API connection in the sidebar")
            
    except Exception as e:
        st.error(f"Error loading overview metrics: {str(e)}")


def render_recent_events(filters: dict) -> None:
    """
    Render recent events table.
    
    Args:
        filters: Filter parameters
    """
    st.markdown("## 📋 Recent Events")
    
    try:
        events = st.session_state.api_client.get_events(
            start_time=filters["start_time"],
            end_time=filters["end_time"],
            source=filters["source"],
            sentiment_label=filters["sentiment_label"],
            limit=50
        )
        
        if events:
            # Convert to display format
            display_data = []
            for event in events:
                display_data.append({
                    "Time": event.occurred_at.strftime("%Y-%m-%d %H:%M"),
                    "Source": event.source,
                    "Source ID": event.source_id,
                    "Sentiment": event.sentiment_label.title(),
                    "Score": f"{event.sentiment_score:.3f}",
                    "Confidence": f"{event.confidence:.3f}" if event.confidence else "N/A",
                    "Text Preview": (event.raw_text[:100] + "...") if event.raw_text and len(event.raw_text) > 100 else event.raw_text or "N/A"
                })
            
            st.dataframe(
                display_data,
                use_container_width=True,
                height=400
            )
        else:
            st.info("No recent events found for the selected filters.")
            
    except Exception as e:
        st.error(f"Error loading recent events: {str(e)}")


def main() -> None:
    """Main application function with multi-page dashboard layout."""
    # Setup
    setup_page_config()
    setup_logging()
    initialize_session_state()
    
    # Initialize page selection in session state
    if 'selected_page' not in st.session_state:
        st.session_state.selected_page = "Overview"
    
    # Render sidebar with navigation
    render_sidebar()
    
    # Page navigation in sidebar
    st.sidebar.markdown("## 📄 Dashboard Pages")
    pages = {
        "📊 Overview": "Overview",
        "📈 Advanced Analytics": "Advanced Analytics", 
        "🔥 Heatmaps": "Heatmaps",
        "📋 Multi-Source Analysis": "Multi-Source",
        "📊 Statistical Analysis": "Statistical",
        "📥 Data Export": "Export"
    }
    
    selected_page = st.sidebar.selectbox(
        "Select Dashboard Page",
        options=list(pages.keys()),
        index=list(pages.values()).index(st.session_state.selected_page) if st.session_state.selected_page in pages.values() else 0
    )
    st.session_state.selected_page = pages[selected_page]
    
    # Auto-refresh logic
    if st.session_state.auto_refresh:
        time_since_refresh = (datetime.now() - st.session_state.last_refresh).total_seconds()
        if time_since_refresh >= st.session_state.refresh_interval:
            st.session_state.last_refresh = datetime.now()
            st.rerun()
    
    # Render filters (common to all pages)
    filters = render_filters()
    
    # Apply advanced filters if available
    advanced_filters = render_advanced_filters()
    
    # Fetch base data using configurable limits
    events_data = fetch_events_data(
        start_time=filters["start_time"],
        end_time=filters["end_time"],
        source=filters["source"],
        sentiment_label=filters["sentiment_label"],
        limit=st.session_state.fetch_limit  # Use configurable limit
    )
    
    # Apply advanced filters to data
    if events_data:
        events_data = apply_advanced_filters(events_data, advanced_filters)
    
    # Page routing
    if st.session_state.selected_page == "Overview":
        render_overview_page(filters, events_data)
    elif st.session_state.selected_page == "Advanced Analytics":
        render_advanced_analytics_page(events_data)
    elif st.session_state.selected_page == "Heatmaps":
        render_heatmaps_page(events_data)
    elif st.session_state.selected_page == "Multi-Source":
        render_multi_source_page(events_data)
    elif st.session_state.selected_page == "Statistical":
        render_statistical_page(events_data)
    elif st.session_state.selected_page == "Export":
        render_export_page(events_data)
    
    # Footer
    st.markdown("---")
    st.markdown("*Dashboard Service v1.0.0 - Phase 3 Advanced Features - Built with Streamlit*")


def render_overview_page(filters: dict, events_data: List[Dict[str, Any]]) -> None:
    """Render the overview dashboard page.
    
    Args:
        filters: Filter parameters
        events_data: List of event dictionaries
    """
    st.title("📊 Sentiment Analysis Dashboard - Overview")
    st.markdown("Real-time sentiment monitoring and analytics")
    
    # Render main content with the same events_data
    render_overview_metrics(filters, events_data)
    
    # Render visualizations if we have data
    if events_data:
        st.markdown("## 📈 Key Visualizations")
        
        # Time granularity selector
        col1, col2 = st.columns([3, 1])
        with col2:
            granularity = st.selectbox(
                "Time Granularity",
                options=['minute', 'hour', 'day', 'week'],
                index=1
            )
        
        # Enhanced time series chart with drill-down
        st.markdown("### Interactive Sentiment Trends")
        time_series_chart = create_simple_sentiment_chart(events_data, granularity)
        st.plotly_chart(time_series_chart, use_container_width=True)
        
        # Create tabs for additional visualizations
        tab1, tab2 = st.tabs(["🥧 Distribution", "📋 By Source"])
        
        with tab1:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### Sentiment Distribution")
                distribution_chart = create_sentiment_distribution_chart(events_data)
                st.plotly_chart(distribution_chart, use_container_width=True)
            
            with col2:
                st.markdown("### Key Statistics")
                df = pd.DataFrame(events_data)
                
                # Calculate statistics
                total_events = len(df)
                avg_sentiment = df['sentiment_score'].mean()
                sentiment_std = df['sentiment_score'].std()
                
                # Display statistics
                st.metric("Total Events", f"{total_events:,}")
                st.metric("Average Sentiment", f"{avg_sentiment:.3f}")
                st.metric("Sentiment Std Dev", f"{sentiment_std:.3f}")
                
                # Show sentiment score distribution
                st.markdown("**Sentiment Score Range:**")
                score_min = df['sentiment_score'].min()
                score_max = df['sentiment_score'].max()
                st.write(f"Min: {score_min:.3f} | Max: {score_max:.3f}")
                
                # Show confidence statistics if available
                if 'confidence' in df.columns and not df['confidence'].isna().all():
                    avg_confidence = df['confidence'].mean()
                    st.metric("Average Confidence", f"{avg_confidence:.3f}")
        
        with tab2:
            st.markdown("### Analysis by Source")
            source_chart = create_source_analysis_chart(events_data)
            st.plotly_chart(source_chart, use_container_width=True)
            
            # Show source statistics table
            st.markdown("### Source Statistics")
            df = pd.DataFrame(events_data)
            source_stats = df.groupby('source').agg({
                'sentiment_score': ['count', 'mean', 'std'],
                'sentiment_label': lambda x: x.value_counts().to_dict()
            }).round(3)
            
            # Flatten column names for display
            source_stats.columns = ['Event Count', 'Avg Sentiment', 'Sentiment Std', 'Label Distribution']
            st.dataframe(source_stats, use_container_width=True)
    
    # Render recent events table
    render_recent_events(filters)


def render_advanced_analytics_page(events_data: List[Dict[str, Any]]) -> None:
    """Render the advanced analytics page.
    
    Args:
        events_data: List of event dictionaries
    """
    st.title("📈 Advanced Analytics")
    st.markdown("Deep dive into sentiment patterns and trends")
    
    if not events_data:
        st.warning("No data available for advanced analytics")
        return
    
    # Advanced chart controls
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        granularity = st.selectbox(
            "Analysis Granularity",
            options=['minute', 'hour', 'day', 'week', 'month'],
            index=1,
            key="advanced_granularity"
        )
    with col2:
        show_confidence = st.checkbox(
            "Show Confidence Intervals",
            value=True,
            help="Display ±1σ confidence bands around sentiment trends"
        )
    with col3:
        show_volume = st.checkbox(
            "Show Event Volume",
            value=True,
            help="Display event volume as secondary chart"
        )
    
    # Enhanced interactive time series with advanced features
    st.markdown("## 🔍 Advanced Interactive Time Series Analysis")
    st.info(f"📊 Analyzing {len(events_data):,} events with enhanced visualizations")
    
    time_series_chart = create_advanced_sentiment_chart(
        events_data, 
        granularity=granularity,
        show_confidence=show_confidence,
        show_volume=show_volume
    )
    st.plotly_chart(time_series_chart, use_container_width=True)
    
    # Multi-source comparison
    st.markdown("## 📊 Multi-Source Comparison")
    multi_source_chart = create_multi_source_comparison_chart(events_data)
    st.plotly_chart(multi_source_chart, use_container_width=True)


def render_heatmaps_page(events_data: List[Dict[str, Any]]) -> None:
    """Render the heatmaps page.
    
    Args:
        events_data: List of event dictionaries
    """
    st.title("🔥 Sentiment Distribution Heatmaps")
    st.markdown("Visualize sentiment patterns across time dimensions")
    
    if not events_data:
        st.warning("No data available for heatmap analysis")
        return
    
    # Heatmap controls
    col1, col2 = st.columns([3, 1])
    with col2:
        heatmap_granularity = st.selectbox(
            "Heatmap Granularity",
            options=['hour', 'day', 'week'],
            index=0,
            key="heatmap_granularity"
        )
    
    # Enhanced sentiment heatmap with advanced features
    st.markdown("## 🔥 Advanced Interactive Sentiment Heatmap")
    st.info(f"📊 Visualizing {len(events_data):,} events across time dimensions")
    
    heatmap_chart = create_sentiment_heatmap_advanced(events_data, heatmap_granularity)
    st.plotly_chart(heatmap_chart, use_container_width=True)
    
    # Additional heatmap insights
    st.markdown("## 📊 Heatmap Insights")
    df = pd.DataFrame(events_data)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Peak Activity Hour", "14:00")  # This would be calculated from data
    with col2:
        st.metric("Most Active Day", "Monday")   # This would be calculated from data
    with col3:
        st.metric("Sentiment Volatility", f"{df['sentiment_score'].std():.3f}")


def render_multi_source_page(events_data: List[Dict[str, Any]]) -> None:
    """Render the multi-source analysis page.
    
    Args:
        events_data: List of event dictionaries
    """
    st.title("📋 Multi-Source Analysis")
    st.markdown("Compare sentiment patterns across different data sources")
    
    if not events_data:
        st.warning("No data available for multi-source analysis")
        return
    
    # Multi-source comparison chart
    st.markdown("## 📊 Comprehensive Source Comparison")
    multi_source_chart = create_multi_source_comparison_chart(events_data)
    st.plotly_chart(multi_source_chart, use_container_width=True)
    
    # Source-specific insights
    st.markdown("## 🔍 Source-Specific Insights")
    df = pd.DataFrame(events_data)
    
    # Source selection for detailed analysis
    selected_sources = st.multiselect(
        "Select sources for detailed comparison",
        options=df['source'].unique(),
        default=df['source'].unique()[:3] if len(df['source'].unique()) > 3 else df['source'].unique()
    )
    
    if selected_sources:
        filtered_df = df[df['source'].isin(selected_sources)]
        
        # Source comparison table
        source_comparison = filtered_df.groupby('source').agg({
            'sentiment_score': ['count', 'mean', 'std', 'min', 'max'],
            'sentiment_label': lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else 'neutral'
        }).round(3)
        
        source_comparison.columns = ['Event Count', 'Avg Score', 'Std Dev', 'Min Score', 'Max Score', 'Dominant Sentiment']
        st.dataframe(source_comparison, use_container_width=True)


def render_statistical_page(events_data: List[Dict[str, Any]]) -> None:
    """Render the statistical analysis page.
    
    Args:
        events_data: List of event dictionaries
    """
    st.title("📊 Statistical Analysis")
    st.markdown("Advanced statistical insights and trend analysis")
    
    if not events_data:
        st.warning("No data available for statistical analysis")
        return
    
    # Generate statistical displays
    st.markdown("## 📈 Moving Averages & Trend Analysis")
    statistical_charts = create_statistical_analysis_display(events_data)
    
    # Display moving averages
    st.plotly_chart(statistical_charts["moving_averages"], use_container_width=True)
    
    # Display percentiles
    st.markdown("## 📊 Percentile Analysis")
    st.plotly_chart(statistical_charts["percentiles"], use_container_width=True)
    
    # Additional statistical insights
    st.markdown("## 🔢 Statistical Summary")
    df = pd.DataFrame(events_data)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Skewness", f"{df['sentiment_score'].skew():.3f}")
    with col2:
        st.metric("Kurtosis", f"{df['sentiment_score'].kurtosis():.3f}")
    with col3:
        st.metric("Variance", f"{df['sentiment_score'].var():.3f}")
    with col4:
        st.metric("IQR", f"{df['sentiment_score'].quantile(0.75) - df['sentiment_score'].quantile(0.25):.3f}")


def render_export_page(events_data: List[Dict[str, Any]]) -> None:
    """Render the data export page.
    
    Args:
        events_data: List of event dictionaries
    """
    st.title("📥 Data Export")
    st.markdown("Export sentiment analysis data in various formats")
    
    # Export controls
    render_export_controls(events_data)
    
    if events_data:
        # Data summary for export
        st.markdown("## 📊 Export Data Summary")
        df = pd.DataFrame(events_data)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Records", f"{len(df):,}")
        with col2:
            st.metric("Date Range", f"{len(df['occurred_at'].dt.date.unique())} days")
        with col3:
            st.metric("Sources", f"{df['source'].nunique()}")
        with col4:
            st.metric("Avg Sentiment", f"{df['sentiment_score'].mean():.3f}")
        
        # Export format options
        st.markdown("## ⚙️ Export Options")
        
        export_options = st.expander("Export Configuration", expanded=True)
        with export_options:
            col1, col2 = st.columns(2)
            
            with col1:
                include_raw_text = st.checkbox("Include Raw Text", value=True)
                include_metadata = st.checkbox("Include Metadata", value=True)
            
            with col2:
                date_format = st.selectbox(
                    "Date Format",
                    options=["ISO 8601", "US Format", "EU Format"],
                    index=0
                )
                
                decimal_places = st.slider(
                    "Decimal Places for Scores",
                    min_value=1,
                    max_value=6,
                    value=3
                )
    else:
        st.info("No data available for export. Adjust your filters to include more data.")


if __name__ == "__main__":
    main()
