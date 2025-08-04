"""
Clean, streamlined Streamlit dashboard for sentiment analysis.

This is a simplified version focusing on core functionality:
- Single-page dashboard with organized sections
- Clean filters and controls
- Essential visualizations only
- Working unlimited data fetching
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from loguru import logger

from dashboard_service.chart_simple import create_simple_sentiment_chart
from dashboard_service.chart_advanced import create_advanced_sentiment_chart
from dashboard_service.config import get_settings
from dashboard_service.api import SentimentAPIClient
from dashboard_service.utils.logging import setup_logging


def setup_page_config() -> None:
    """Configure Streamlit page settings."""
    st.set_page_config(
        page_title="Sentiment Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
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
    
    if 'fetch_mode' not in st.session_state:
        st.session_state.fetch_mode = "Comprehensive"
    
    if 'fetch_limit' not in st.session_state:
        st.session_state.fetch_limit = 10000


def fetch_events_data(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    source: Optional[str] = None,
    sentiment_label: Optional[str] = None,
    limit: int = 10000
) -> List[Dict[str, Any]]:
    """Fetch events data with unlimited pagination support."""
    try:
        # DISABLE CACHE for debugging - ensure fresh data every time
        logger.info(f"FETCHING FRESH DATA - NO CACHE")
        logger.info(f"Date range: {start_time} to {end_time}")
        logger.info(f"Source: {source}, Sentiment: {sentiment_label}, Limit: {limit}")
        logger.info(f"Fetch mode: {st.session_state.fetch_mode}")
        
        client = get_api_client()
        logger.info(f"Fetching events: start={start_time}, end={end_time}, source={source}, sentiment={sentiment_label}, mode={st.session_state.fetch_mode}")
        
        all_events = []
        
        # Use unlimited fetching for comprehensive and unlimited modes
        if st.session_state.fetch_mode in ["Comprehensive", "Unlimited"]:
            mode_name = "Comprehensive" if st.session_state.fetch_mode == "Comprehensive" else "ALL available"
            with st.spinner(f'🚀 Fetching {mode_name} events in date range...'):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Ensure we have valid date range
                if not start_time or not end_time:
                    st.error("Please select a valid date range for comprehensive fetching")
                    return []
                
                # Log the actual date range being used
                logger.info(f"Fetching events for date range: {start_time} to {end_time}")
                st.info(f"📅 Fetching events from {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}")
                
                # Time-based chunking for large date ranges
                time_diff = end_time - start_time
                days_diff = time_diff.days
                
                # More aggressive chunking for better coverage
                if days_diff <= 1:
                    chunk_count = 1  # Single day
                elif days_diff <= 7:
                    chunk_count = days_diff  # Daily chunks
                elif days_diff <= 30:
                    chunk_count = min(15, days_diff // 2)  # 2-day chunks
                else:
                    chunk_count = min(30, days_diff // 7)  # Weekly chunks
                
                chunk_count = max(1, chunk_count)
                chunk_duration = time_diff / chunk_count
                
                logger.info(f"Using {chunk_count} chunks for {days_diff} days ({chunk_duration} per chunk)")
                
                for i in range(chunk_count):
                    chunk_start = start_time + (chunk_duration * i)
                    chunk_end = start_time + (chunk_duration * (i + 1))
                    
                    progress = (i + 1) / chunk_count
                    progress_bar.progress(progress)
                    status_text.text(f"Fetching chunk {i+1}/{chunk_count} ({len(all_events):,} events loaded)")
                    
                    # Log chunk details for debugging
                    logger.info(f"Processing chunk {i+1}/{chunk_count}: {chunk_start} to {chunk_end}")
                    
                    # Fetch all events in this chunk with proper pagination
                    chunk_events = []
                    cursor = None
                    page_limit = 10000
                    max_pages = 100  # Increased for unlimited mode
                    
                    for page in range(max_pages):
                        try:
                            page_events = client.get_events(
                                start_time=chunk_start,
                                end_time=chunk_end,
                                source=source,
                                sentiment_label=sentiment_label,
                                limit=page_limit,
                                cursor=cursor
                            )
                            
                            if not page_events:
                                break
                            
                            chunk_events.extend(page_events)
                            
                            if len(page_events) < page_limit:
                                break
                            
                            # Generate cursor for next page
                            last_event = page_events[-1]
                            import base64
                            import json
                            cursor_data = {
                                "timestamp": last_event.occurred_at.isoformat(),
                                "id": last_event.id
                            }
                            cursor_json = json.dumps(cursor_data)
                            cursor = base64.b64encode(cursor_json.encode()).decode()
                            
                        except Exception as e:
                            logger.warning(f"Error in pagination: {str(e)}")
                            break
                    
                    all_events.extend(chunk_events)
                    logger.info(f"Chunk {i+1}: {len(chunk_events)} events, total: {len(all_events)}")
                
                progress_bar.empty()
                status_text.empty()
                
                if all_events:
                    # Remove duplicates
                    unique_events = {}
                    for event in all_events:
                        if hasattr(event, 'id') and event.id not in unique_events:
                            unique_events[event.id] = event
                    all_events = list(unique_events.values())
                    st.success(f"✅ Fetched {len(all_events):,} unique events")
        else:
            # Standard fetch for limited mode
            all_events = client.get_events(
                start_time=start_time,
                end_time=end_time,
                source=source,
                sentiment_label=sentiment_label,
                limit=min(limit, 10000)  # Respect API limit
            )
        
        # Convert to dict format
        events_data = []
        for event in all_events:
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
        
        logger.info(f"Final result: {len(events_data)} events")
        
        # Log date range of actual data for debugging
        if events_data:
            df_temp = pd.DataFrame(events_data)
            df_temp['occurred_at'] = pd.to_datetime(df_temp['occurred_at'])
            actual_start = df_temp['occurred_at'].min()
            actual_end = df_temp['occurred_at'].max()
            logger.info(f"Actual data range: {actual_start} to {actual_end}")
            
            # Check if data is within expected range
            if start_time and end_time:
                logger.info(f"Expected range: {start_time} to {end_time}")
                
                # Handle timezone comparison safely
                try:
                    # Convert to same timezone for comparison
                    if actual_start.tz is not None:
                        # Data is timezone-aware, make filter dates timezone-aware
                        start_time_tz = start_time.replace(tzinfo=actual_start.tz) if start_time.tzinfo is None else start_time
                        end_time_tz = end_time.replace(tzinfo=actual_end.tz) if end_time.tzinfo is None else end_time
                    else:
                        # Data is timezone-naive, make filter dates timezone-naive
                        start_time_tz = start_time.replace(tzinfo=None) if start_time.tzinfo else start_time
                        end_time_tz = end_time.replace(tzinfo=None) if end_time.tzinfo else end_time
                        actual_start = actual_start.replace(tzinfo=None)
                        actual_end = actual_end.replace(tzinfo=None)
                    
                    if actual_start < start_time_tz or actual_end > end_time_tz:
                        logger.warning(f"Data outside expected range! API filtering may not be working.")
                    else:
                        logger.info(f"Data is within expected range ✓")
                except Exception as e:
                    logger.warning(f"Could not compare date ranges due to timezone issue: {e}")
        
        return events_data
        
    except Exception as e:
        logger.error(f"Error fetching events: {str(e)}")
        st.error(f"Error fetching data: {str(e)}")
        return []


def render_sidebar() -> Dict[str, Any]:
    """Render clean sidebar with essential controls."""
    st.sidebar.title("📊 Sentiment Dashboard")
    
    # API Status
    st.sidebar.markdown("### 🔗 Connection Status")
    try:
        health = st.session_state.api_client.health_check()
        st.sidebar.success("✅ API Connected")
    except Exception as e:
        st.sidebar.error(f"❌ API Error")
    
    # Data Fetching Mode
    st.sidebar.markdown("### ⚙️ Data Fetching")
    fetch_mode = st.sidebar.radio(
        "Fetch Mode",
        options=["Limited", "Comprehensive", "Unlimited"],
        index=["Limited", "Comprehensive", "Unlimited"].index(st.session_state.fetch_mode),
        help="Limited: Fast (≤10k events), Comprehensive: Balanced (≤50k events), Unlimited: All available events"
    )
    st.session_state.fetch_mode = fetch_mode
    
    if fetch_mode == "Limited":
        limit = st.sidebar.slider("Event Limit", 1000, 10000, 5000, 1000)
        st.session_state.fetch_limit = limit
    elif fetch_mode == "Comprehensive":
        st.sidebar.info("📊 Comprehensive mode uses chunking to fetch more than 10k events")
        st.session_state.fetch_limit = 10000  # Use API limit for chunking
    else:
        st.sidebar.info("🚀 Unlimited mode fetches ALL events in date range")
        st.session_state.fetch_limit = 10000  # Use API limit for chunking
    
    # Filters
    st.sidebar.markdown("### 🔍 Filters")
    
    # Date range
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=datetime.now().date() - timedelta(days=7),
            max_value=datetime.now().date()
        )
    with col2:
        end_date = st.date_input(
            "End Date",
            value=datetime.now().date(),
            max_value=datetime.now().date()
        )
    
    # Convert to datetime
    start_time = datetime.combine(start_date, datetime.min.time())
    end_time = datetime.combine(end_date, datetime.max.time())
    
    # Source filter
    source = st.sidebar.selectbox(
        "Source",
        options=["All", "reddit", "twitter"],
        index=0
    )
    source = None if source == "All" else source
    
    # Sentiment filter
    sentiment_label = st.sidebar.selectbox(
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


def render_overview_metrics(events_data: List[Dict[str, Any]]) -> None:
    """Render key metrics overview."""
    if not events_data:
        st.warning("No data available for the selected filters")
        return
    
    df = pd.DataFrame(events_data)
    
    # Key metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("📊 Total Events", f"{len(df):,}")
    
    with col2:
        avg_sentiment = df['sentiment_score'].mean()
        st.metric("📈 Avg Sentiment", f"{avg_sentiment:.3f}")
    
    with col3:
        positive_count = len(df[df['sentiment_label'] == 'positive'])
        positive_pct = (positive_count / len(df)) * 100
        st.metric("😊 Positive", f"{positive_count:,}", f"{positive_pct:.1f}%")
    
    with col4:
        negative_count = len(df[df['sentiment_label'] == 'negative'])
        negative_pct = (negative_count / len(df)) * 100
        st.metric("😞 Negative", f"{negative_count:,}", f"{negative_pct:.1f}%")
    
    with col5:
        neutral_count = len(df[df['sentiment_label'] == 'neutral'])
        neutral_pct = (neutral_count / len(df)) * 100
        st.metric("😐 Neutral", f"{neutral_count:,}", f"{neutral_pct:.1f}%")


def render_sentiment_distribution_chart(events_data: List[Dict[str, Any]]) -> go.Figure:
    """Create sentiment distribution pie chart."""
    if not events_data:
        return go.Figure()
    
    df = pd.DataFrame(events_data)
    sentiment_counts = df['sentiment_label'].value_counts()
    
    colors = {
        'positive': '#2E8B57',
        'negative': '#DC143C',
        'neutral': '#4682B4'
    }
    
    fig = go.Figure(data=[
        go.Pie(
            labels=[label.title() for label in sentiment_counts.index],
            values=sentiment_counts.values,
            hole=0.3,
            marker_colors=[colors.get(label, '#666666') for label in sentiment_counts.index],
            textinfo='label+percent+value'
        )
    ])
    
    fig.update_layout(
        title="Sentiment Distribution",
        height=400,
        showlegend=True
    )
    
    return fig


def render_source_analysis_chart(events_data: List[Dict[str, Any]]) -> go.Figure:
    """Create source analysis bar chart."""
    if not events_data:
        return go.Figure()
    
    df = pd.DataFrame(events_data)
    source_sentiment = df.groupby(['source', 'sentiment_label']).size().unstack(fill_value=0)
    
    fig = go.Figure()
    
    colors = {
        'positive': '#2E8B57',
        'negative': '#DC143C',
        'neutral': '#4682B4'
    }
    
    for sentiment in source_sentiment.columns:
        fig.add_trace(go.Bar(
            name=sentiment.title(),
            x=source_sentiment.index,
            y=source_sentiment[sentiment],
            marker_color=colors.get(sentiment, '#666666')
        ))
    
    fig.update_layout(
        title="Events by Source and Sentiment",
        xaxis_title="Source",
        yaxis_title="Event Count",
        barmode='stack',
        height=400
    )
    
    return fig


def main() -> None:
    """Main streamlined dashboard application."""
    # Setup
    setup_page_config()
    setup_logging()
    initialize_session_state()
    
    # Header
    st.title("📊 Sentiment Analysis Dashboard")
    st.markdown("**Real-time sentiment monitoring and analytics**")
    
    # Sidebar filters
    filters = render_sidebar()
    
    # Debug: Show selected date range
    st.info(f"📅 Selected Date Range: {filters['start_time'].strftime('%Y-%m-%d')} to {filters['end_time'].strftime('%Y-%m-%d')}")
    
    # Add refresh button for debugging
    if st.button("🔄 Refresh Data (No Cache)"):
        st.cache_data.clear()
        st.rerun()
    
    # Fetch data
    with st.spinner("Loading data..."):
        events_data = fetch_events_data(
            start_time=filters["start_time"],
            end_time=filters["end_time"],
            source=filters["source"],
            sentiment_label=filters["sentiment_label"],
            limit=st.session_state.fetch_limit
        )
    
    # Debug: Show actual data date range
    if events_data:
        df_temp = pd.DataFrame(events_data)
        df_temp['occurred_at'] = pd.to_datetime(df_temp['occurred_at'])
        actual_start = df_temp['occurred_at'].min()
        actual_end = df_temp['occurred_at'].max()
        st.info(f"📊 Actual Data Range: {actual_start.strftime('%Y-%m-%d')} to {actual_end.strftime('%Y-%m-%d')} ({len(events_data):,} events)")
    
    # Overview metrics
    st.markdown("## 📈 Overview")
    render_overview_metrics(events_data)
    
    if events_data:
        # Main visualizations
        st.markdown("## 📊 Visualizations")
        
        # Chart controls
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            granularity = st.selectbox(
                "Time Granularity",
                options=['hour', 'day', 'week', 'month'],
                index=1
            )
        with col2:
            chart_type = st.selectbox(
                "Chart Type",
                options=['Simple', 'Advanced'],
                index=0
            )
        with col3:
            if chart_type == 'Advanced':
                show_volume = st.checkbox("Show Volume", value=True)
            else:
                show_volume = False
        
        # Time series chart
        st.markdown("### 📈 Sentiment Trends Over Time")
        if chart_type == 'Advanced':
            chart = create_advanced_sentiment_chart(
                events_data, 
                granularity=granularity,
                show_confidence=True,
                show_volume=show_volume
            )
        else:
            chart = create_simple_sentiment_chart(events_data, granularity)
        
        st.plotly_chart(chart, use_container_width=True)
        
        # Secondary charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🥧 Sentiment Distribution")
            dist_chart = render_sentiment_distribution_chart(events_data)
            st.plotly_chart(dist_chart, use_container_width=True)
        
        with col2:
            st.markdown("### 📋 Analysis by Source")
            source_chart = render_source_analysis_chart(events_data)
            st.plotly_chart(source_chart, use_container_width=True)
        
        # Data summary
        st.markdown("## 📋 Data Summary")
        df = pd.DataFrame(events_data)
        
        # Summary statistics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Date Range", f"{len(df['occurred_at'].dt.date.unique())} days")
        with col2:
            st.metric("Sources", f"{df['source'].nunique()}")
        with col3:
            st.metric("Std Deviation", f"{df['sentiment_score'].std():.3f}")
        with col4:
            if 'confidence' in df.columns and not df['confidence'].isna().all():
                st.metric("Avg Confidence", f"{df['confidence'].mean():.3f}")
            else:
                st.metric("Score Range", f"{df['sentiment_score'].max() - df['sentiment_score'].min():.3f}")
        
        # Recent events sample
        with st.expander("📋 Recent Events Sample", expanded=False):
            # Sort by occurred_at descending to show most recent events first
            recent_df = df.sort_values('occurred_at', ascending=False).head(100)
            sample_df = recent_df[['occurred_at', 'source', 'sentiment_label', 'sentiment_score', 'raw_text']]
            sample_df['occurred_at'] = sample_df['occurred_at'].dt.strftime('%Y-%m-%d %H:%M')
            sample_df['raw_text'] = sample_df['raw_text'].str[:100] + '...'
            st.dataframe(sample_df, use_container_width=True)
    
    # Footer
    st.markdown("---")
    st.markdown("*Sentiment Pipeline Dashboard v2.0 - Streamlined Edition*")


if __name__ == "__main__":
    main()
