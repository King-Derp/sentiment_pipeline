"""
Configuration settings for the dashboard service.

This module handles environment variable loading and configuration management
using Pydantic for validation and type safety.
"""

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Dashboard service configuration settings.
    
    All settings can be overridden via environment variables.
    """
    
    # Sentiment Analyzer API Configuration
    sentiment_api_base_url: str = Field(
        default="http://localhost:8000",
        description="Base URL for the sentiment analyzer API"
    )
    sentiment_api_timeout: int = Field(
        default=30,
        description="Timeout in seconds for API requests"
    )
    
    # Dashboard Configuration
    streamlit_port: int = Field(
        default=8501,
        description="Port for Streamlit server"
    )
    streamlit_host: str = Field(
        default="0.0.0.0",
        description="Host for Streamlit server"
    )
    debug_mode: bool = Field(
        default=True,
        description="Enable debug mode"
    )
    
    # Authentication
    auth_secret_key: Optional[str] = Field(
        default=None,
        description="Secret key for authentication"
    )
    auth_algorithm: str = Field(
        default="HS256",
        description="Algorithm for JWT tokens"
    )
    
    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    log_format: str = Field(
        default="json",
        description="Logging format (json or text)"
    )
    
    # External Integrations (Optional)
    smtp_server: Optional[str] = Field(
        default=None,
        description="SMTP server for email notifications"
    )
    smtp_port: Optional[int] = Field(
        default=587,
        description="SMTP server port"
    )
    smtp_username: Optional[str] = Field(
        default=None,
        description="SMTP username"
    )
    smtp_password: Optional[str] = Field(
        default=None,
        description="SMTP password"
    )
    
    slack_webhook_url: Optional[str] = Field(
        default=None,
        description="Slack webhook URL for notifications"
    )
    
    # Cache Configuration
    cache_ttl: int = Field(
        default=300,
        description="Cache TTL in seconds"
    )
    max_cache_size: int = Field(
        default=1000,
        description="Maximum cache size"
    )
    
    # Dashboard Settings
    auto_refresh_interval: int = Field(
        default=30,
        description="Auto refresh interval in seconds"
    )
    default_page_size: int = Field(
        default=100,
        description="Default page size for data queries"
    )
    max_page_size: int = Field(
        default=1000,
        description="Maximum page size for data queries"
    )
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Returns:
        Settings: Configured settings instance
    """
    return Settings()
