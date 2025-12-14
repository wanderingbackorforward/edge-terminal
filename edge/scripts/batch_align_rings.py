#!/usr/bin/env python3
"""
Batch Ring Alignment Script

Aligns multiple rings in batch mode. Useful for:
- Initial data processing after deployment
- Re-processing rings after algorithm updates
- Fixing incomplete ring summaries
- Backfilling historical data

Usage:
    python batch_align_rings.py --start-ring 100 --end-ring 200
    python batch_align_rings.py --ring-list 100,101,105,110
    python batch_align_rings.py --all --force
    python batch_align_rings.py --incomplete-only
"""
import asyncio
import argparse
import logging
import sys
from typing import List, Optional
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from edge.database.manager import DatabaseManager
from edge.services.aligner.ring_detector import RingBoundaryDetector
from edge.services.aligner.plc_aggregator import PLCAggregator
from edge.services.aligner.attitude_aggregator import AttitudeAggregator
from edge.services.aligner.derived_indicators import DerivedIndicatorsCalculator
from edge.services.aligner.settlement_associator import SettlementAssociator
from edge.services.aligner.ring_summary_writer import RingSummaryWriter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/batch_alignment.log')
    ]
)
logger = logging.getLogger(__name__)


class BatchRingAligner:
    """Batch ring alignment processor"""

    def __init__(
        self,
        db_path: str = "data/edge.db",
        force_reprocess: bool = False,
        dry_run: bool = False
    ):
        """
        Initialize batch aligner.

        Args:
            db_path: Path to database
            force_reprocess: Reprocess existing ring summaries
            dry_run: Dry run mode (no writes)
        """
        self.db_manager = DatabaseManager(db_path)
        self.force_reprocess = force_reprocess
        self.dry_run = dry_run

        # Initialize alignment components
        self.ring_detector = RingBoundaryDetector()
        self.plc_aggregator = PLCAggregator()
        self.attitude_aggregator = AttitudeAggregator()
        self.derived_calculator = DerivedIndicatorsCalculator()
        self.settlement_associator = SettlementAssociator()
        self.summary_writer = RingSummaryWriter()

        # Statistics
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'rings_with_data': 0,
            'rings_without_data': 0
        }

    def get_all_ring_numbers(self) -> List[int]:
        """Get all distinct ring numbers from plc_logs"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute("""
                SELECT DISTINCT ring_number
                FROM plc_logs
                WHERE ring_number IS NOT NULL
                ORDER BY ring_number
            """)
            results = cursor.fetchall()

        return [row['ring_number'] for row in results]

    def get_incomplete_ring_numbers(self) -> List[int]:
        """Get ring numbers with incomplete data"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute("""
                SELECT ring_number
                FROM ring_summary
                WHERE data_completeness_flag != 'complete'
                ORDER BY ring_number
            """)
            results = cursor.fetchall()

        return [row['ring_number'] for row in results]

    def ring_exists(self, ring_number: int) -> bool:
        """Check if ring summary exists"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM ring_summary WHERE ring_number = ?",
                (ring_number,)
            )
            result = cursor.fetchone()

        return result['count'] > 0

    def align_ring(self, ring_number: int) -> bool:
        """
        Align single ring.

        Args:
            ring_number: Ring number to align

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Processing ring {ring_number}...")

            # Check if already exists and skip if not forcing
            if self.ring_exists(ring_number) and not self.force_reprocess:
                logger.info(f"Ring {ring_number} already exists, skipping (use --force to reprocess)")
                self.stats['skipped'] += 1
                return True

            # Detect ring boundaries
            # For batch processing, we need to get the previous ring's end time
            prev_ring_end = self._get_previous_ring_end_time(ring_number)

            boundary = self.ring_detector.detect_ring_boundary(
                self.db_manager, ring_number, prev_ring_end
            )

            if not boundary:
                logger.warning(f"Could not detect boundaries for ring {ring_number}")
                self.stats['rings_without_data'] += 1
                return False

            start_time, end_time = boundary
            logger.info(
                f"Ring {ring_number} boundaries: "
                f"{datetime.fromtimestamp(start_time)} - {datetime.fromtimestamp(end_time)}"
            )

            # Aggregate PLC data
            plc_features = self.plc_aggregator.aggregate_ring_data(
                self.db_manager, ring_number, start_time, end_time
            )

            if not plc_features:
                logger.warning(f"No PLC data for ring {ring_number}")

            # Aggregate attitude data
            attitude_features = self.attitude_aggregator.aggregate_ring_data(
                self.db_manager, ring_number, start_time, end_time
            )

            # Calculate derived indicators
            derived_indicators = {}
            if plc_features:
                derived_indicators = self.derived_calculator.calculate_all_indicators(
                    plc_features, attitude_features, duration=(end_time - start_time)
                )

            # Associate settlement data
            settlement_features = self.settlement_associator.associate_settlement_data(
                self.db_manager, ring_number, end_time
            )

            # Get geological zone (if available)
            geological_zone = self._get_geological_zone(ring_number)

            # Write ring summary
            if not self.dry_run:
                success = self.summary_writer.write_ring_summary(
                    db_manager=self.db_manager,
                    ring_number=ring_number,
                    start_time=start_time,
                    end_time=end_time,
                    plc_features=plc_features,
                    attitude_features=attitude_features,
                    derived_indicators=derived_indicators,
                    settlement_features=settlement_features,
                    geological_zone=geological_zone
                )

                if not success:
                    logger.error(f"Failed to write ring summary for ring {ring_number}")
                    return False
            else:
                logger.info(f"[DRY RUN] Would write ring summary for ring {ring_number}")

            logger.info(f"Successfully processed ring {ring_number}")
            self.stats['rings_with_data'] += 1
            return True

        except Exception as e:
            logger.error(f"Error processing ring {ring_number}: {e}", exc_info=True)
            return False

    def _get_previous_ring_end_time(self, ring_number: int) -> Optional[float]:
        """Get end time of previous ring"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT end_time
                FROM ring_summary
                WHERE ring_number < ?
                ORDER BY ring_number DESC
                LIMIT 1
                """,
                (ring_number,)
            )
            result = cursor.fetchone()

        return result['end_time'] if result else None

    def _get_geological_zone(self, ring_number: int) -> Optional[str]:
        """Get geological zone for ring (from manual logs or config)"""
        # This is a placeholder - in real implementation, would query
        # geological zone database or manual logs
        return None

    async def process_rings(self, ring_numbers: List[int]) -> None:
        """
        Process multiple rings.

        Args:
            ring_numbers: List of ring numbers to process
        """
        logger.info(f"Starting batch alignment for {len(ring_numbers)} rings")
        logger.info(f"Force reprocess: {self.force_reprocess}")
        logger.info(f"Dry run mode: {self.dry_run}")

        start_time = datetime.now()

        for ring_number in ring_numbers:
            self.stats['total_processed'] += 1

            success = self.align_ring(ring_number)

            if success:
                self.stats['successful'] += 1
            else:
                self.stats['failed'] += 1

            # Progress indicator
            if self.stats['total_processed'] % 10 == 0:
                self._print_progress()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Print final statistics
        self._print_final_statistics(duration)

    def _print_progress(self) -> None:
        """Print progress update"""
        logger.info(
            f"Progress: {self.stats['total_processed']} processed, "
            f"{self.stats['successful']} successful, "
            f"{self.stats['failed']} failed, "
            f"{self.stats['skipped']} skipped"
        )

    def _print_final_statistics(self, duration: float) -> None:
        """Print final statistics"""
        logger.info("\n" + "=" * 60)
        logger.info("BATCH ALIGNMENT COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total processed:      {self.stats['total_processed']}")
        logger.info(f"Successful:           {self.stats['successful']}")
        logger.info(f"Failed:               {self.stats['failed']}")
        logger.info(f"Skipped:              {self.stats['skipped']}")
        logger.info(f"Rings with data:      {self.stats['rings_with_data']}")
        logger.info(f"Rings without data:   {self.stats['rings_without_data']}")
        logger.info(f"Duration:             {duration:.2f} seconds")

        if self.stats['total_processed'] > 0:
            avg_time = duration / self.stats['total_processed']
            logger.info(f"Average per ring:     {avg_time:.2f} seconds")

        # Component statistics
        logger.info("\nComponent Statistics:")
        logger.info(f"Ring detector:        {self.ring_detector.get_statistics()}")
        logger.info(f"PLC aggregator:       {self.plc_aggregator.get_statistics()}")
        logger.info(f"Attitude aggregator:  {self.attitude_aggregator.get_statistics()}")
        logger.info(f"Summary writer:       {self.summary_writer.get_statistics()}")
        logger.info("=" * 60)


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Batch ring alignment processor',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Align rings 100-200
  python batch_align_rings.py --start-ring 100 --end-ring 200

  # Align specific rings
  python batch_align_rings.py --ring-list 100,101,105,110

  # Re-align all rings (force reprocess)
  python batch_align_rings.py --all --force

  # Align only incomplete rings
  python batch_align_rings.py --incomplete-only

  # Dry run to see what would be processed
  python batch_align_rings.py --start-ring 100 --end-ring 105 --dry-run
        """
    )

    # Ring selection
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--start-ring',
        type=int,
        help='Start ring number (use with --end-ring)'
    )
    group.add_argument(
        '--ring-list',
        type=str,
        help='Comma-separated list of ring numbers (e.g., 100,101,105)'
    )
    group.add_argument(
        '--all',
        action='store_true',
        help='Process all rings in database'
    )
    group.add_argument(
        '--incomplete-only',
        action='store_true',
        help='Process only rings with incomplete data'
    )

    parser.add_argument(
        '--end-ring',
        type=int,
        help='End ring number (use with --start-ring)'
    )

    # Options
    parser.add_argument(
        '--db-path',
        type=str,
        default='data/edge.db',
        help='Path to database (default: data/edge.db)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force reprocess existing ring summaries'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run mode (no writes to database)'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )

    args = parser.parse_args()

    # Validation
    if args.start_ring is not None and args.end_ring is None:
        parser.error('--start-ring requires --end-ring')

    if args.end_ring is not None and args.start_ring is None:
        parser.error('--end-ring requires --start-ring')

    return args


async def main():
    """Main entry point"""
    args = parse_arguments()

    # Set log level
    logging.getLogger().setLevel(args.log_level)

    # Create aligner
    aligner = BatchRingAligner(
        db_path=args.db_path,
        force_reprocess=args.force,
        dry_run=args.dry_run
    )

    # Determine rings to process
    ring_numbers = []

    if args.start_ring is not None and args.end_ring is not None:
        ring_numbers = list(range(args.start_ring, args.end_ring + 1))
        logger.info(f"Processing rings {args.start_ring} to {args.end_ring}")

    elif args.ring_list:
        ring_numbers = [int(r.strip()) for r in args.ring_list.split(',')]
        logger.info(f"Processing specified rings: {ring_numbers}")

    elif args.all:
        ring_numbers = aligner.get_all_ring_numbers()
        logger.info(f"Processing all {len(ring_numbers)} rings in database")

    elif args.incomplete_only:
        ring_numbers = aligner.get_incomplete_ring_numbers()
        logger.info(f"Processing {len(ring_numbers)} incomplete rings")

    if not ring_numbers:
        logger.warning("No rings to process")
        return

    # Process rings
    await aligner.process_rings(ring_numbers)


if __name__ == '__main__':
    asyncio.run(main())
