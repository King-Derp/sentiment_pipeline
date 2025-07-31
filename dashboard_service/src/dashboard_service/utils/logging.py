"""
Logging configuration for the dashboard service.

This module sets up structured logging using loguru with appropriate
formatting and levels for both development and production environments.
"""

import sys
from typing import Optional

from loguru import logger

from ..config import get_settings


def setup_logging(log_level: Optional[str] = None) -> None:
    """
    Set up logging configuration.
    
    Args:
        log_level: Override log level (DEBUG, INFO, WARNING, ERROR)
    """
    settings = get_settings()
    
    # Remove default handler
    logger.remove()
    
    # Determine log level
    level = log_level or settings.log_level
    
    # Use simple human-readable format for now to avoid JSON formatting issues
    format_string = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    
    # Add console handler
    logger.add(
        sys.stderr,
        format=format_string,
        level=level,
        colorize=settings.log_format != "json",
        backtrace=settings.debug_mode,
        diagnose=settings.debug_mode
    )
    
    # Add file handler if not in debug mode
    if not settings.debug_mode:
        logger.add(
            "logs/dashboard_service.log",
            format=format_string,
            level=level,
            rotation="1 day",
            retention="30 days",
            compression="gz",
            backtrace=False,
            diagnose=False
        )
    
    logger.info(f"Logging initialized with level: {level}, format: {settings.log_format}")


def get_logger(name: str):
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Module name
        
    Returns:
        Logger instance
    """
    return logger.bind(name=name)
