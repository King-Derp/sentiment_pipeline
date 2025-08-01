"""
Simple chart creation module for debugging chart issues.
"""
import pandas as pd
import plotly.graph_objects as go
from typing import List, Dict, Any
from loguru import logger


def create_simple_sentiment_chart(events_data: List[Dict[str, Any]], granularity: str = 'hour') -> go.Figure:
    """Create a simple working time series chart for debugging.
    
    Args:
        events_data: List of event dictionaries
        granularity: Time granularity ('minute', 'hour', 'day', 'week')
    
    Returns:
        Simple Plotly figure
    """
    if not events_data:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        return fig
    
    try:
        # Convert to DataFrame
        df = pd.DataFrame(events_data)
        logger.info(f"Chart data: {len(df)} events")
        logger.info(f"Sample timestamps: {df['occurred_at'].head().tolist()}")
        
        # Parse timestamps
        df['occurred_at'] = pd.to_datetime(df['occurred_at'])
        logger.info(f"Parsed timestamp range: {df['occurred_at'].min()} to {df['occurred_at'].max()}")
        
        # Simple time grouping
        if granularity == 'hour':
            df['time_group'] = df['occurred_at'].dt.floor('h')
        elif granularity == 'day':
            df['time_group'] = df['occurred_at'].dt.floor('D')
        elif granularity == 'week':
            df['time_group'] = df['occurred_at'].dt.to_period('W').dt.start_time
        else:
            df['time_group'] = df['occurred_at'].dt.floor('h')
        
        logger.info(f"Time groups: {df['time_group'].nunique()} unique groups")
        
        # Simple aggregation
        agg_data = df.groupby(['time_group', 'sentiment_label'])['sentiment_score'].mean().reset_index()
        logger.info(f"Aggregated data: {len(agg_data)} rows")
        logger.info(f"Sentiment labels: {agg_data['sentiment_label'].unique().tolist()}")
        
        # Create simple chart
        fig = go.Figure()
        
        colors = {'positive': 'green', 'negative': 'red', 'neutral': 'blue'}
        
        for sentiment in agg_data['sentiment_label'].unique():
            data = agg_data[agg_data['sentiment_label'] == sentiment]
            logger.info(f"Adding trace for {sentiment}: {len(data)} points")
            
            fig.add_trace(go.Scatter(
                x=data['time_group'],
                y=data['sentiment_score'],
                mode='lines+markers',
                name=sentiment.title(),
                line=dict(color=colors.get(sentiment, 'gray'))
            ))
        
        fig.update_layout(
            title=f"Simple Sentiment Chart - {granularity.title()} ({len(df)} events)",
            xaxis_title="Time",
            yaxis_title="Sentiment Score",
            height=400
        )
        
        logger.info("Chart created successfully")
        return fig
        
    except Exception as e:
        logger.error(f"Error creating simple chart: {str(e)}")
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        return fig
