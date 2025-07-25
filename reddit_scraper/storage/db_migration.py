"""Database migration and management utilities."""

import datetime
import logging
from typing import List, Optional

import psycopg2
from psycopg2.extensions import connection

from reddit_scraper.storage.db import get_connection

logger = logging.getLogger(__name__)


def create_partition(conn: connection, date: datetime.date) -> bool:
    """
    Create a partition for a specific date.
    
    Args:
        conn: PostgreSQL connection
        date: Date to create partition for
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Format date for partition name (YYYY_MM_DD)
        day_str = date.strftime('%Y_%m_%d')
        
        # Convert to SQL date format
        sql_date = date.strftime('%Y-%m-%d')
        next_day = (date + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        
        with conn.cursor() as cur:
            # Create partition if it doesn't exist
            cur.execute(f"""
            CREATE TABLE IF NOT EXISTS raw_events_{day_str}
            PARTITION OF raw_events
            FOR VALUES FROM ('{sql_date}') TO ('{next_day}');
            """)
            
            logger.info(f"Created partition raw_events_{day_str}")
            return True
            
    except Exception as e:
        logger.error(f"Failed to create partition for {date}: {str(e)}")
        return False


def create_partitions_for_range(start_date: datetime.date, 
                               end_date: datetime.date) -> bool:
    """
    Create partitions for a date range (inclusive).
    
    Args:
        start_date: First date to create partition for
        end_date: Last date to create partition for (inclusive)
        
    Returns:
        True if all partitions were created successfully, False otherwise
    """
    conn = get_connection()
    if not conn:
        logger.error("Unable to connect to PostgreSQL database")
        return False
    
    try:
        # Loop through each day in range
        current_date = start_date
        while current_date <= end_date:
            create_partition(conn, current_date)
            current_date += datetime.timedelta(days=1)
            
        return True
        
    except Exception as e:
        logger.error(f"Error creating partitions: {str(e)}")
        return False
    finally:
        conn.close()


def get_partitioned_dates() -> List[datetime.date]:
    """
    Get a list of dates for which partitions exist.
    
    Returns:
        List of dates with partitions
    """
    conn = get_connection()
    if not conn:
        logger.error("Unable to connect to PostgreSQL database")
        return []
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
            SELECT tablename 
            FROM pg_tables 
            WHERE tablename LIKE 'raw_events_%' 
              AND schemaname = 'public'
            ORDER BY tablename;
            """)
            
            partitions = cur.fetchall()
            dates = []
            
            for (partition_name,) in partitions:
                try:
                    # Extract date part (raw_events_YYYY_MM_DD)
                    date_str = partition_name[11:]  # Skip 'raw_events_'
                    year, month, day = date_str.split('_')
                    dates.append(datetime.date(int(year), int(month), int(day)))
                except (ValueError, IndexError):
                    logger.warning(f"Couldn't parse date from partition: {partition_name}")
                    
            return dates
            
    except Exception as e:
        logger.error(f"Error querying partitions: {str(e)}")
        return []
    finally:
        conn.close()


def create_missing_partitions_for_reddit_data() -> bool:
    """
    Create partitions for all dates with Reddit data in storage.
    
    Returns:
        True if successful, False otherwise
    """
    conn = get_connection()
    if not conn:
        logger.error("Unable to connect to PostgreSQL database")
        return False
    
    try:
        with conn.cursor() as cur:
            # Find min and max dates in existing data
            cur.execute("""
            SELECT 
                MIN(occurred_at)::date as min_date, 
                MAX(occurred_at)::date as max_date
            FROM raw_events
            WHERE source = 'reddit';
            """)
            
            result = cur.fetchone()
            if not result or not result[0] or not result[1]:
                logger.info("No Reddit data found in database")
                return True
                
            min_date, max_date = result
            
            # Get existing partitions
            existing_dates = set(get_partitioned_dates())
            
            # Create missing partitions
            current_date = min_date
            while current_date <= max_date:
                if current_date not in existing_dates:
                    create_partition(conn, current_date)
                current_date += datetime.timedelta(days=1)
                
            return True
            
    except Exception as e:
        logger.error(f"Error creating partitions for Reddit data: {str(e)}")
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    # Simple CLI for partition management
    import argparse
    import sys
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    parser = argparse.ArgumentParser(description="Database partition management")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Create partition for a specific date
    create_parser = subparsers.add_parser("create", help="Create a partition for a date")
    create_parser.add_argument("date", help="Date in YYYY-MM-DD format")
    
    # Create partitions for a date range
    range_parser = subparsers.add_parser("range", help="Create partitions for a date range")
    range_parser.add_argument("start_date", help="Start date in YYYY-MM-DD format")
    range_parser.add_argument("end_date", help="End date in YYYY-MM-DD format")
    
    # List existing partitions
    subparsers.add_parser("list", help="List existing partitions")
    
    # Auto-create partitions for all Reddit data
    subparsers.add_parser("auto", help="Auto-create partitions for Reddit data")
    
    args = parser.parse_args()
    
    if args.command == "create":
        date = datetime.date.fromisoformat(args.date)
        conn = get_connection()
        if conn:
            success = create_partition(conn, date)
            conn.close()
            sys.exit(0 if success else 1)
        sys.exit(1)
        
    elif args.command == "range":
        start_date = datetime.date.fromisoformat(args.start_date)
        end_date = datetime.date.fromisoformat(args.end_date)
        success = create_partitions_for_range(start_date, end_date)
        sys.exit(0 if success else 1)
        
    elif args.command == "list":
        dates = get_partitioned_dates()
        if dates:
            for date in dates:
                print(date.isoformat())
        else:
            print("No partitions found")
        sys.exit(0)
        
    elif args.command == "auto":
        success = create_missing_partitions_for_reddit_data()
        sys.exit(0 if success else 1)
        
    else:
        parser.print_help()
        sys.exit(1)
