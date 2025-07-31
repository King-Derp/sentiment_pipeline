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


@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_events_data(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    source: Optional[str] = None,
    sentiment_label: Optional[str] = None,
    limit: int = 1000
) -> List[Dict[str, Any]]:
    """Fetch events data with caching."""
    try:
        client = get_api_client()
        events = client.get_events(
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
        
        return events_data
    except Exception as e:
        logger.error(f"Error fetching events data: {str(e)}")
        return []


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


def create_sentiment_time_series_chart(events_data: List[Dict[str, Any]]) -> go.Figure:
    """Create time series chart for sentiment trends."""
    if not events_data:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        return fig
    
    # Convert to DataFrame for easier processing
    df = pd.DataFrame(events_data)
    df['occurred_at'] = pd.to_datetime(df['occurred_at'])
    
    # Group by hour and sentiment label
    df['hour'] = df['occurred_at'].dt.floor('H')
    hourly_sentiment = df.groupby(['hour', 'sentiment_label']).agg({
        'sentiment_score': ['mean', 'count']
    }).reset_index()
    
    # Flatten column names
    hourly_sentiment.columns = ['hour', 'sentiment_label', 'avg_score', 'count']
    
    # Create subplots
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('Average Sentiment Score Over Time', 'Event Count Over Time'),
        vertical_spacing=0.1
    )
    
    # Color mapping for sentiment labels
    color_map = {
        'positive': '#2E8B57',  # Sea Green
        'negative': '#DC143C',  # Crimson
        'neutral': '#4682B4'    # Steel Blue
    }
    
    # Add sentiment score traces
    for sentiment in hourly_sentiment['sentiment_label'].unique():
        data = hourly_sentiment[hourly_sentiment['sentiment_label'] == sentiment]
        fig.add_trace(
            go.Scatter(
                x=data['hour'],
                y=data['avg_score'],
                mode='lines+markers',
                name=f'{sentiment.title()} Score',
                line=dict(color=color_map.get(sentiment, '#666666')),
                hovertemplate='<b>%{fullData.name}</b><br>' +
                             'Time: %{x}<br>' +
                             'Avg Score: %{y:.3f}<extra></extra>'
            ),
            row=1, col=1
        )
    
    # Add event count traces
    for sentiment in hourly_sentiment['sentiment_label'].unique():
        data = hourly_sentiment[hourly_sentiment['sentiment_label'] == sentiment]
        fig.add_trace(
            go.Scatter(
                x=data['hour'],
                y=data['count'],
                mode='lines+markers',
                name=f'{sentiment.title()} Count',
                line=dict(color=color_map.get(sentiment, '#666666'), dash='dash'),
                hovertemplate='<b>%{fullData.name}</b><br>' +
                             'Time: %{x}<br>' +
                             'Count: %{y}<extra></extra>',
                showlegend=False
            ),
            row=2, col=1
        )
    
    # Update layout
    fig.update_layout(
        height=600,
        title_text="Sentiment Analysis Trends",
        hovermode='x unified'
    )
    
    fig.update_xaxes(title_text="Time", row=2, col=1)
    fig.update_yaxes(title_text="Average Sentiment Score", row=1, col=1)
    fig.update_yaxes(title_text="Event Count", row=2, col=1)
    
    return fig


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


def render_overview_metrics(filters: dict) -> None:
    """
    Render overview metrics cards.
    
    Args:
        filters: Filter parameters
    """
    st.markdown("## 📊 Overview Metrics")
    
    try:
        # Fetch events data using cached function
        events_data = fetch_events_data(
            start_time=filters["start_time"],
            end_time=filters["end_time"],
            source=filters["source"],
            sentiment_label=filters["sentiment_label"],
            limit=1000
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
            st.info("No data available for the selected filters.")
            
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
    """Main application function."""
    # Setup
    setup_page_config()
    setup_logging()
    initialize_session_state()
    
    # Render sidebar
    render_sidebar()
    
    # Main content
    st.title("📊 Sentiment Analysis Dashboard")
    st.markdown("Real-time sentiment monitoring and analytics")
    
    # Auto-refresh logic
    if st.session_state.auto_refresh:
        time_since_refresh = (datetime.now() - st.session_state.last_refresh).total_seconds()
        if time_since_refresh >= st.session_state.refresh_interval:
            st.session_state.last_refresh = datetime.now()
            st.rerun()
    
    # Render filters
    filters = render_filters()
    
    # Render main content
    render_overview_metrics(filters)
    
    # Fetch data for visualizations
    events_data = fetch_events_data(
        start_time=filters["start_time"],
        end_time=filters["end_time"],
        source=filters["source"],
        sentiment_label=filters["sentiment_label"],
        limit=1000
    )
    
    # Render visualizations if we have data
    if events_data:
        st.markdown("## 📈 Visualizations")
        
        # Create tabs for different visualizations
        tab1, tab2, tab3 = st.tabs(["📊 Time Series", "🥧 Distribution", "📋 By Source"])
        
        with tab1:
            st.markdown("### Sentiment Trends Over Time")
            time_series_chart = create_sentiment_time_series_chart(events_data)
            st.plotly_chart(time_series_chart, use_container_width=True)
        
        with tab2:
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
        
        with tab3:
            st.markdown("### Analysis by Source")
            source_chart = create_source_analysis_chart(events_data)
            st.plotly_chart(source_chart, use_container_width=True)
            
            # Show source statistics table
            st.markdown("### Source Statistics")
            source_stats = df.groupby('source').agg({
                'sentiment_score': ['count', 'mean', 'std'],
                'sentiment_label': lambda x: x.value_counts().to_dict()
            }).round(3)
            
            # Flatten column names for display
            source_stats.columns = ['Event Count', 'Avg Sentiment', 'Sentiment Std', 'Label Distribution']
            st.dataframe(source_stats, use_container_width=True)
    
    # Render recent events table
    render_recent_events(filters)
    
    # Footer
    st.markdown("---")
    st.markdown("*Dashboard Service v1.0.0 - Built with Streamlit*")


if __name__ == "__main__":
    main()
