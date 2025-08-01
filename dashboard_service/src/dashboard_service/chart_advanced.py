"""
Advanced chart creation module with enhanced features for large datasets.

This module provides advanced charting capabilities now that unlimited data fetching is working.
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from typing import List, Dict, Any, Optional
from loguru import logger
import numpy as np


def create_advanced_sentiment_chart(
    events_data: List[Dict[str, Any]], 
    granularity: str = 'hour',
    show_confidence: bool = True,
    show_volume: bool = True
) -> go.Figure:
    """
    Create an advanced interactive time series chart with enhanced features.
    
    Args:
        events_data: List of event dictionaries
        granularity: Time granularity ('minute', 'hour', 'day', 'week', 'month')
        show_confidence: Whether to show confidence intervals
        show_volume: Whether to show event volume as secondary y-axis
    
    Returns:
        Advanced Plotly figure with subplots and enhanced interactivity
    """
    if not events_data:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available for advanced chart",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        return fig
    
    try:
        # Convert to DataFrame
        df = pd.DataFrame(events_data)
        logger.info(f"Advanced chart: processing {len(df)} events")
        
        # Parse timestamps
        df['occurred_at'] = pd.to_datetime(df['occurred_at'])
        
        # Time grouping with proper frequency strings
        freq_map = {
            'minute': '1min',
            'hour': '1h', 
            'day': '1D',
            'week': 'W-MON',  # Week starting Monday
            'month': 'MS'     # Month start
        }
        
        freq = freq_map.get(granularity, '1h')
        
        # Handle week and month granularities specially
        if granularity == 'week':
            # Group by week starting Monday
            df['time_group'] = df['occurred_at'].dt.to_period('W-MON').dt.start_time
        elif granularity == 'month':
            # Group by month start
            df['time_group'] = df['occurred_at'].dt.to_period('M').dt.start_time
        else:
            # Use standard floor for other granularities
            df['time_group'] = df['occurred_at'].dt.floor(freq)
        
        # Advanced aggregation with statistics
        agg_funcs = {
            'sentiment_score': ['mean', 'std', 'count', 'min', 'max'],
            'confidence': ['mean'] if 'confidence' in df.columns else []
        }
        
        # Remove empty aggregation functions
        agg_funcs = {k: v for k, v in agg_funcs.items() if v}
        
        # Group by time and sentiment label
        grouped = df.groupby(['time_group', 'sentiment_label']).agg(agg_funcs).reset_index()
        
        # Flatten column names
        grouped.columns = [
            '_'.join(col).strip('_') if isinstance(col, tuple) else col 
            for col in grouped.columns
        ]
        
        # Create subplot figure
        subplot_titles = ["Sentiment Trends Over Time"]
        if show_volume:
            subplot_titles.append("Event Volume")
            
        fig = make_subplots(
            rows=2 if show_volume else 1,
            cols=1,
            subplot_titles=subplot_titles,
            specs=[[{"secondary_y": True}], [{"secondary_y": False}]] if show_volume else [[{"secondary_y": True}]],
            vertical_spacing=0.1
        )
        
        # Color mapping for sentiments
        colors = {
            'positive': '#2E8B57',  # Sea Green
            'negative': '#DC143C',  # Crimson
            'neutral': '#4682B4'    # Steel Blue
        }
        
        # Plot sentiment trends
        for sentiment in grouped['sentiment_label'].unique():
            sentiment_data = grouped[grouped['sentiment_label'] == sentiment]
            
            # Main sentiment line
            fig.add_trace(
                go.Scatter(
                    x=sentiment_data['time_group'],
                    y=sentiment_data['sentiment_score_mean'],
                    mode='lines+markers',
                    name=f'{sentiment.title()} Sentiment',
                    line=dict(color=colors.get(sentiment, '#666666'), width=2),
                    marker=dict(size=6),
                    hovertemplate=(
                        f'<b>{sentiment.title()}</b><br>' +
                        'Time: %{x}<br>' +
                        'Avg Sentiment: %{y:.3f}<br>' +
                        'Events: %{customdata[0]}<br>' +
                        '<extra></extra>'
                    ),
                    customdata=sentiment_data[['sentiment_score_count']].values
                ),
                row=1, col=1
            )
            
            # Add confidence intervals if available and requested
            if show_confidence and 'sentiment_score_std' in sentiment_data.columns:
                std_values = sentiment_data['sentiment_score_std'].fillna(0)
                upper_bound = sentiment_data['sentiment_score_mean'] + std_values
                lower_bound = sentiment_data['sentiment_score_mean'] - std_values
                
                # Upper confidence bound
                fig.add_trace(
                    go.Scatter(
                        x=sentiment_data['time_group'],
                        y=upper_bound,
                        mode='lines',
                        line=dict(width=0),
                        showlegend=False,
                        hoverinfo='skip'
                    ),
                    row=1, col=1
                )
                
                # Lower confidence bound with fill
                fig.add_trace(
                    go.Scatter(
                        x=sentiment_data['time_group'],
                        y=lower_bound,
                        mode='lines',
                        line=dict(width=0),
                        fill='tonexty',
                        fillcolor=f'rgba({",".join(map(str, [int(colors.get(sentiment, "#666666")[1:3], 16), int(colors.get(sentiment, "#666666")[3:5], 16), int(colors.get(sentiment, "#666666")[5:7], 16)]))}, 0.2)',
                        name=f'{sentiment.title()} ±1σ',
                        showlegend=True,
                        hoverinfo='skip'
                    ),
                    row=1, col=1
                )
        
        # Add volume chart if requested
        if show_volume:
            volume_data = df.groupby('time_group').size().reset_index(name='event_count')
            
            fig.add_trace(
                go.Bar(
                    x=volume_data['time_group'],
                    y=volume_data['event_count'],
                    name='Event Volume',
                    marker_color='rgba(70, 130, 180, 0.7)',
                    hovertemplate=(
                        '<b>Event Volume</b><br>' +
                        'Time: %{x}<br>' +
                        'Events: %{y}<br>' +
                        '<extra></extra>'
                    )
                ),
                row=2, col=1
            )
        
        # Update layout
        fig.update_layout(
            title=f"Advanced Sentiment Analysis - {granularity.title()} View ({len(df):,} events)",
            height=600 if show_volume else 400,
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        # Update axes
        fig.update_xaxes(title_text="Time", row=1, col=1)
        fig.update_yaxes(title_text="Sentiment Score", row=1, col=1)
        
        if show_volume:
            fig.update_xaxes(title_text="Time", row=2, col=1)
            fig.update_yaxes(title_text="Event Count", row=2, col=1)
        
        logger.info(f"Advanced chart created successfully with {len(grouped)} data points")
        return fig
        
    except Exception as e:
        logger.error(f"Error creating advanced chart: {str(e)}")
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error creating advanced chart: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        return fig


def create_sentiment_heatmap_advanced(
    events_data: List[Dict[str, Any]], 
    time_granularity: str = 'hour'
) -> go.Figure:
    """
    Create an advanced sentiment heatmap with better handling of large datasets.
    
    Args:
        events_data: List of event dictionaries
        time_granularity: Time granularity for heatmap ('hour', 'day', 'week')
    
    Returns:
        Advanced Plotly heatmap figure
    """
    if not events_data:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available for heatmap",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        return fig
    
    try:
        df = pd.DataFrame(events_data)
        df['occurred_at'] = pd.to_datetime(df['occurred_at'])
        
        # Create time dimensions for heatmap
        if time_granularity == 'hour':
            df['hour'] = df['occurred_at'].dt.hour
            df['day'] = df['occurred_at'].dt.date
            pivot_data = df.groupby(['day', 'hour', 'sentiment_label']).size().unstack(fill_value=0)
        elif time_granularity == 'day':
            df['day_of_week'] = df['occurred_at'].dt.day_name()
            df['week'] = df['occurred_at'].dt.isocalendar().week
            pivot_data = df.groupby(['week', 'day_of_week', 'sentiment_label']).size().unstack(fill_value=0)
        else:  # week
            df['week'] = df['occurred_at'].dt.isocalendar().week
            df['month'] = df['occurred_at'].dt.month
            pivot_data = df.groupby(['month', 'week', 'sentiment_label']).size().unstack(fill_value=0)
        
        # Create heatmap subplots for each sentiment
        sentiments = ['positive', 'negative', 'neutral']
        available_sentiments = [s for s in sentiments if s in pivot_data.columns]
        
        fig = make_subplots(
            rows=len(available_sentiments),
            cols=1,
            subplot_titles=[f'{s.title()} Sentiment Heatmap' for s in available_sentiments],
            vertical_spacing=0.1
        )
        
        colors = {
            'positive': 'Greens',
            'negative': 'Reds', 
            'neutral': 'Blues'
        }
        
        for i, sentiment in enumerate(available_sentiments):
            sentiment_data = pivot_data[sentiment].unstack(level=0, fill_value=0)
            
            fig.add_trace(
                go.Heatmap(
                    z=sentiment_data.values,
                    x=sentiment_data.columns,
                    y=sentiment_data.index,
                    colorscale=colors.get(sentiment, 'Viridis'),
                    showscale=True,
                    hovertemplate=(
                        f'<b>{sentiment.title()} Events</b><br>' +
                        'Time: %{x}<br>' +
                        'Period: %{y}<br>' +
                        'Count: %{z}<br>' +
                        '<extra></extra>'
                    )
                ),
                row=i+1, col=1
            )
        
        fig.update_layout(
            title=f"Sentiment Distribution Heatmap - {time_granularity.title()} View ({len(df):,} events)",
            height=200 * len(available_sentiments) + 100
        )
        
        return fig
        
    except Exception as e:
        logger.error(f"Error creating advanced heatmap: {str(e)}")
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error creating heatmap: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        return fig
