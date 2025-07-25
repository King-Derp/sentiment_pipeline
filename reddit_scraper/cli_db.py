"""Command-line interface for PostgreSQL database management."""

import logging
import os
import sys
import datetime
import json
from typing import Optional, List

import typer
from typing_extensions import Annotated
import psycopg2

from reddit_scraper.config import Config
from reddit_scraper.storage.db import get_connection, ensure_schema, ensure_partition
from reddit_scraper.storage.db_migration import (
    create_partition,
    create_partitions_for_range,
    get_partitioned_dates,
    create_missing_partitions_for_reddit_data
)

app = typer.Typer(help="PostgreSQL Database Management Commands")
logger = logging.getLogger(__name__)


def setup_logging(log_level: str = "INFO") -> None:
    """Set up basic logging configuration."""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler()]
    )


@app.command("test")
def test_connection(
    config: Annotated[str, typer.Option("--config", "-c", help="Path to configuration file")] = "config.yaml",
    loglevel: Annotated[str, typer.Option("--loglevel", "-l", help="Logging level")] = "INFO",
    local: Annotated[bool, typer.Option("--local", help="Use localhost instead of configured host")] = False,
) -> None:
    """Test the PostgreSQL connection and database schema setup."""
    setup_logging(loglevel)
    
    # Load configuration
    config_obj = Config.from_files(config)
    
    if not config_obj.postgres.enabled:
        logger.error("PostgreSQL is not enabled in configuration")
        sys.exit(1)
    
    # Override host if running locally
    host = "localhost" if local else config_obj.postgres.host
    port = 5433 if local else config_obj.postgres.port
    
    # Set environment variables for the local connection
    if local:
        os.environ["PG_HOST"] = host
        os.environ["PG_PORT"] = str(port)
    
    # Display connection parameters (without password)
    logger.info(f"Connecting to PostgreSQL at {host}:{port}")
    logger.info(f"Database: {config_obj.postgres.database}, User: {config_obj.postgres.user}")
    
    # Test connection
    conn = get_connection()
    if not conn:
        logger.error("Connection failed! Check PostgreSQL credentials and connectivity.")
        sys.exit(1)
        
    logger.info("✓ Connected to PostgreSQL successfully")
    
    # Check schema
    try:
        if ensure_schema(conn):
            logger.info("✓ Database schema is properly configured")
        else:
            logger.error("Failed to ensure database schema")
            sys.exit(1)
            
        # Check for today's partition
        today = datetime.date.today()
        day_str = today.strftime('%Y_%m_%d')
        
        if ensure_partition(conn, day_str):
            logger.info(f"✓ Partition for today ({day_str}) exists")
        else:
            logger.error(f"Failed to ensure partition for today ({day_str})")
            sys.exit(1)
            
        # Check permissions by writing a test record
        try:
            with conn.cursor() as cur:
                cur.execute("""
                INSERT INTO raw_events 
                (source, source_id, occurred_at, payload)
                VALUES 
                ('test', 'connection-test', NOW(), '{"test": true}')
                ON CONFLICT (source_id, occurred_at) DO NOTHING
                """)
                logger.info("✓ Write permissions verified")
                
                # Delete the test record
                cur.execute("DELETE FROM raw_events WHERE source = 'test' AND source_id = 'connection-test'")
        except psycopg2.errors.UniqueViolation:
            # This is also okay - means the conflict clause worked
            logger.info("✓ Write permissions verified (conflict handling)")
            pass
        except Exception as e:
            logger.error(f"Write permission test failed: {str(e)}")
            sys.exit(1)
            
        # All checks passed
        logger.info("✓ All connection and schema tests passed")
        
    finally:
        conn.close()


@app.command("partitions")
def manage_partitions(
    list: Annotated[bool, typer.Option("--list", help="List existing partitions")] = False,
    create_date: Annotated[Optional[str], typer.Option("--create", help="Create partition for date (YYYY-MM-DD)")] = None,
    range_start: Annotated[Optional[str], typer.Option("--range-start", help="Start date for range (YYYY-MM-DD)")] = None,
    range_end: Annotated[Optional[str], typer.Option("--range-end", help="End date for range (YYYY-MM-DD)")] = None,
    auto: Annotated[bool, typer.Option("--auto", help="Auto-create partitions for existing data")] = False,
    config: Annotated[str, typer.Option("--config", "-c", help="Path to configuration file")] = "config.yaml",
    loglevel: Annotated[str, typer.Option("--loglevel", "-l", help="Logging level")] = "INFO",
) -> None:
    """Manage database partitions for the raw_events table."""
    setup_logging(loglevel)
    
    # Load configuration
    config_obj = Config.from_files(config)
    
    if not config_obj.postgres.enabled:
        logger.error("PostgreSQL is not enabled in configuration")
        sys.exit(1)
    
    if list:
        # List existing partitions
        dates = get_partitioned_dates()
        if dates:
            logger.info(f"Found {len(dates)} existing partitions:")
            for date in sorted(dates):
                print(date.strftime("%Y-%m-%d"))
        else:
            logger.info("No partitions found")
    
    if create_date:
        # Create partition for a specific date
        try:
            date = datetime.date.fromisoformat(create_date)
            conn = get_connection()
            if conn:
                if create_partition(conn, date):
                    logger.info(f"✓ Created partition for {create_date}")
                else:
                    logger.error(f"Failed to create partition for {create_date}")
                    sys.exit(1)
                conn.close()
        except ValueError:
            logger.error(f"Invalid date format: {create_date}. Use YYYY-MM-DD")
            sys.exit(1)
    
    if range_start and range_end:
        # Create partitions for a date range
        try:
            start_date = datetime.date.fromisoformat(range_start)
            end_date = datetime.date.fromisoformat(range_end)
            
            if end_date < start_date:
                logger.error("End date must be after start date")
                sys.exit(1)
                
            if create_partitions_for_range(start_date, end_date):
                logger.info(f"✓ Created partitions for range {range_start} to {range_end}")
            else:
                logger.error(f"Failed to create partitions for range")
                sys.exit(1)
        except ValueError:
            logger.error(f"Invalid date format. Use YYYY-MM-DD")
            sys.exit(1)
            
    if auto:
        # Auto-create partitions for all data
        if create_missing_partitions_for_reddit_data():
            logger.info("✓ Auto-created partitions for all existing data")
        else:
            logger.error("Failed to auto-create partitions")
            sys.exit(1)
            
    # If no action was specified, show help
    if not any([list, create_date, (range_start and range_end), auto]):
        ctx = typer.Context(manage_partitions)
        print(manage_partitions.__doc__)
        print("\nOptions:")
        print(ctx.command.get_help(ctx))


@app.command("info")
def db_info(
    config: Annotated[str, typer.Option("--config", "-c", help="Path to configuration file")] = "config.yaml",
    loglevel: Annotated[str, typer.Option("--loglevel", "-l", help="Logging level")] = "INFO",
    local: Annotated[bool, typer.Option("--local", help="Use localhost instead of configured host")] = False,
) -> None:
    """Display database statistics and information."""
    setup_logging(loglevel)
    
    # Load configuration
    config_obj = Config.from_files(config)
    
    if not config_obj.postgres.enabled:
        logger.error("PostgreSQL is not enabled in configuration")
        sys.exit(1)
    
    # Override host if running locally
    if local:
        host = "localhost"
        port = 5433
        os.environ["PG_HOST"] = host
        os.environ["PG_PORT"] = str(port)
        logger.info(f"Connecting to PostgreSQL at {host}:{port}")
    
    conn = get_connection()
    if not conn:
        logger.error("Connection failed! Check PostgreSQL credentials and connectivity.")
        sys.exit(1)
        
    try:
        stats = {}
        
        # Get database version
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            stats["postgres_version"] = cur.fetchone()[0]
            
            # Get record counts
            cur.execute("SELECT COUNT(*) FROM raw_events;")
            stats["total_records"] = cur.fetchone()[0]
            
            cur.execute("SELECT source, COUNT(*) FROM raw_events GROUP BY source ORDER BY COUNT(*) DESC;")
            stats["records_by_source"] = {row[0]: row[1] for row in cur.fetchall()}
            
            # Get partition info
            cur.execute("""
            SELECT 
                tablename,
                pg_size_pretty(pg_total_relation_size(tablename::text)) as size,
                pg_relation_size(tablename::text) as raw_size
            FROM pg_tables
            WHERE tablename LIKE 'raw_events_%'
            ORDER BY raw_size DESC
            LIMIT 10;
            """)
            partitions = cur.fetchall()
            stats["top_partitions"] = [
                {"name": row[0], "size": row[1]} for row in partitions
            ]
            
            # Get date range
            cur.execute("""
            SELECT 
                TO_CHAR(MIN(occurred_at), 'YYYY-MM-DD HH24:MI:SS') as earliest,
                TO_CHAR(MAX(occurred_at), 'YYYY-MM-DD HH24:MI:SS') as latest
            FROM raw_events;
            """)
            date_range = cur.fetchone()
            if date_range[0]:
                stats["date_range"] = {
                    "earliest": date_range[0],
                    "latest": date_range[1]
                }
            
        # Print the statistics
        print(f"\nDatabase Information:")
        print(f"--------------------")
        print(f"PostgreSQL Version: {stats.get('postgres_version', 'Unknown')}")
        print(f"Total Records:      {stats.get('total_records', 0):,}")
        print("\nRecords by Source:")
        for source, count in stats.get('records_by_source', {}).items():
            print(f"  - {source}: {count:,}")
            
        if 'date_range' in stats:
            print("\nDate Range:")
            print(f"  - Earliest: {stats['date_range']['earliest']}")
            print(f"  - Latest:   {stats['date_range']['latest']}")
            
        print("\nTop Partitions by Size:")
        for partition in stats.get('top_partitions', []):
            print(f"  - {partition['name']}: {partition['size']}")
        
        print("\nFor more detailed metrics, use the metrics command with --format json")
        
    finally:
        conn.close()


if __name__ == "__main__":
    app()
