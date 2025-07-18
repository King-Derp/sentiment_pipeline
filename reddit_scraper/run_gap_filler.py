import asyncio
import argparse
from reddit_scraper.cli import fill_gaps

# This script provides a robust entry point for the async 'fill_gaps' command.
# It uses Python's standard `argparse` and `asyncio` libraries to avoid any
# issues with how `typer` handles async execution in some container environments.
# 
# Updated to use the enhanced TargetedHistoricalScraper for gap filling instead
# of the deprecated GapFillerScraper. The TargetedHistoricalScraper now includes
# gap-filling functionality via the run_for_window() method.

async def main():
    parser = argparse.ArgumentParser(description="Find and fill time gaps in submissions data.")
    parser.add_argument("--config", "-c", default="config.yaml", help="Path to configuration file")
    parser.add_argument("--loglevel", "-l", default="INFO", help="Logging level")
    parser.add_argument("--min-duration", type=int, default=600, help="Minimum gap duration in seconds to fill")
    parser.add_argument("--dry-run", action="store_true", help="Find and list gaps without filling them")
    
    args = parser.parse_args()
    
    # Await the original async fill_gaps function with the parsed arguments
    await fill_gaps(
        config=args.config,
        loglevel=args.loglevel,
        min_duration=args.min_duration,
        dry_run=args.dry_run,
    )

if __name__ == "__main__":
    asyncio.run(main())

