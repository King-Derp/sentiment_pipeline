"""
Core components for the Sentiment Analysis Service.
"""

from .data_fetcher import fetch_and_claim_raw_events

__all__ = [
    "fetch_and_claim_raw_events",
]
