"""Main bi-directional reconciliation execution script."""

import asyncio
import logging
import json
import sys
import os
from pathlib import Path
from datetime import datetime

from .reconciler import BiDirectionalReconciler

# Configure logging
output_dir = Path(__file__).parent / "outputs"
output_dir.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(output_dir / f'bidirectional_reconciliation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """Execute the complete bi-directional reconciliation process."""
    logger.info("=== Starting Bi-Directional Data Reconciliation Process ===")
    
    # Check for dry run mode
    dry_run = os.environ.get('RECONCILIATION_DRY_RUN', 'false').lower() == 'true'
    if dry_run:
        logger.info("DRY RUN MODE - Analysis only, no changes will be made")
    
    # Initialize reconciler
    csv_path = "data/reddit_finance.csv"
    reconciler = BiDirectionalReconciler(csv_path)
    
    start_time = datetime.now()
    
    try:
        # Phase 1: Analyze data differences
        logger.info("Phase 1: Analyzing data differences")
        differences = await reconciler.analyze_data_differences()
        
        if not dry_run:
            # Phase 2: Reconcile CSV-only records to database
            logger.info("Phase 2: Reconciling CSV-only records to database")
            inserted_count = await reconciler.reconcile_csv_to_db(differences['csv_only'])
            
            # Phase 3: Reconcile DB-only records to CSV
            logger.info("Phase 3: Reconciling DB-only records to CSV")
            exported_count = await reconciler.reconcile_db_to_csv(differences['db_only'])
            
            # Phase 4: Resolve conflicts for duplicate records
            logger.info("Phase 4: Resolving conflicts for duplicate records")
            conflicts_resolved = await reconciler.resolve_conflicts(differences['duplicates'])
        else:
            logger.info("DRY RUN: Skipping actual reconciliation operations")
            inserted_count = 0
            exported_count = 0
            conflicts_resolved = 0
        
        # Phase 5: Generate comprehensive report
        logger.info("Phase 5: Generating bi-directional reconciliation report")
        end_time = datetime.now()
        reconciler.stats.processing_time_seconds = (end_time - start_time).total_seconds()
        
        report = reconciler.generate_report()
        
        # Save report
        report_path = output_dir / f"bidirectional_reconciliation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Bi-directional reconciliation complete! Report saved to: {report_path}")
        logger.info(f"Summary:")
        logger.info(f"  - Records inserted to DB: {inserted_count}")
        logger.info(f"  - Records exported to CSV: {exported_count}")
        logger.info(f"  - Conflicts resolved: {conflicts_resolved}")
        logger.info(f"  - Total processing time: {reconciler.stats.processing_time_seconds:.2f} seconds")
        
        if dry_run:
            logger.info("DRY RUN COMPLETE - No actual changes were made")
        
    except Exception as e:
        logger.error(f"Bi-directional reconciliation failed: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
