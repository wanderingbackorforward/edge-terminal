#!/usr/bin/env python3
"""
Data Cleanup Automation Script

Removes old data from edge database to manage storage.
Applies retention policies while preserving ring summaries.

Retention Policy:
- Ring summaries: Keep forever (compact representation)
- PLC logs: Configurable (default 90 days)
- Attitude logs: Configurable (default 90 days)
- Monitoring logs: Configurable (default 180 days)
- Synced data: Can be deleted after cloud sync

Usage:
    python cleanup_old_data.py --dry-run
    python cleanup_old_data.py --retention-days 90
    python cleanup_old_data.py --delete-synced
    python cleanup_old_data.py --vacuum
"""
import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from edge.database.manager import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/data_cleanup.log')
    ]
)
logger = logging.getLogger(__name__)


class DataCleanupManager:
    """Manages data cleanup and retention policies"""

    def __init__(
        self,
        db_path: str = "data/edge.db",
        dry_run: bool = False
    ):
        """
        Initialize cleanup manager.

        Args:
            db_path: Path to database
            dry_run: Dry run mode (no deletions)
        """
        self.db_manager = DatabaseManager(db_path)
        self.dry_run = dry_run

        # Statistics
        self.stats = {
            'plc_logs_deleted': 0,
            'attitude_logs_deleted': 0,
            'monitoring_logs_deleted': 0,
            'space_reclaimed_mb': 0.0
        }

    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get information about a table"""
        with self.db_manager.get_connection() as conn:
            # Count total records
            cursor = conn.execute(f"SELECT COUNT(*) as count FROM {table_name}")
            total_count = cursor.fetchone()['count']

            # Get oldest and newest timestamps
            cursor = conn.execute(
                f"SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest FROM {table_name}"
            )
            result = cursor.fetchone()

            oldest = result['oldest'] if result['oldest'] else None
            newest = result['newest'] if result['newest'] else None

        return {
            'total_records': total_count,
            'oldest_timestamp': oldest,
            'newest_timestamp': newest,
            'oldest_date': datetime.fromtimestamp(oldest) if oldest else None,
            'newest_date': datetime.fromtimestamp(newest) if newest else None
        }

    def get_database_size(self) -> float:
        """Get database file size in MB"""
        db_path = Path(self.db_manager.db_path)
        if db_path.exists():
            return db_path.stat().st_size / (1024 * 1024)
        return 0.0

    def cleanup_old_records(
        self,
        table_name: str,
        retention_days: int,
        additional_condition: str = ""
    ) -> int:
        """
        Delete records older than retention period.

        Args:
            table_name: Table to clean
            retention_days: Days to retain
            additional_condition: Additional WHERE conditions

        Returns:
            Number of records deleted
        """
        cutoff_timestamp = (datetime.now() - timedelta(days=retention_days)).timestamp()

        logger.info(
            f"Cleaning {table_name}: deleting records older than "
            f"{datetime.fromtimestamp(cutoff_timestamp)}"
        )

        # Count records to delete
        where_clause = f"WHERE timestamp < {cutoff_timestamp}"
        if additional_condition:
            where_clause += f" AND {additional_condition}"

        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT COUNT(*) as count FROM {table_name} {where_clause}"
            )
            count_to_delete = cursor.fetchone()['count']

        if count_to_delete == 0:
            logger.info(f"No records to delete from {table_name}")
            return 0

        logger.info(f"Found {count_to_delete} records to delete from {table_name}")

        if not self.dry_run:
            with self.db_manager.transaction() as conn:
                conn.execute(f"DELETE FROM {table_name} {where_clause}")

            logger.info(f"Deleted {count_to_delete} records from {table_name}")
        else:
            logger.info(f"[DRY RUN] Would delete {count_to_delete} records from {table_name}")

        return count_to_delete

    def cleanup_synced_data(self) -> int:
        """
        Delete data that has been synced to cloud.

        Returns:
            Total records deleted
        """
        logger.info("Cleaning synced data...")

        total_deleted = 0

        # Delete synced ring summaries' raw data
        # First, get ring numbers that have been synced
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute("""
                SELECT ring_number
                FROM ring_summary
                WHERE synced_to_cloud = 1
            """)
            synced_rings = [row['ring_number'] for row in cursor.fetchall()]

        if not synced_rings:
            logger.info("No synced rings found")
            return 0

        logger.info(f"Found {len(synced_rings)} synced rings")

        # Delete PLC logs for synced rings
        ring_list = ','.join(str(r) for r in synced_rings)

        for table_name in ['plc_logs', 'attitude_logs', 'monitoring_logs']:
            if not self.dry_run:
                with self.db_manager.transaction() as conn:
                    cursor = conn.execute(
                        f"DELETE FROM {table_name} WHERE ring_number IN ({ring_list})"
                    )
                    deleted = cursor.rowcount
                    total_deleted += deleted
                    logger.info(f"Deleted {deleted} records from {table_name} for synced rings")
            else:
                with self.db_manager.get_connection() as conn:
                    cursor = conn.execute(
                        f"SELECT COUNT(*) as count FROM {table_name} WHERE ring_number IN ({ring_list})"
                    )
                    would_delete = cursor.fetchone()['count']
                    total_deleted += would_delete
                    logger.info(
                        f"[DRY RUN] Would delete {would_delete} records from {table_name}"
                    )

        return total_deleted

    def vacuum_database(self) -> None:
        """Vacuum database to reclaim space"""
        logger.info("Vacuuming database...")

        size_before = self.get_database_size()

        if not self.dry_run:
            with self.db_manager.get_connection() as conn:
                conn.execute("VACUUM")

            size_after = self.get_database_size()
            space_reclaimed = size_before - size_after

            logger.info(
                f"Vacuum complete. Space reclaimed: {space_reclaimed:.2f} MB "
                f"({size_before:.2f} MB -> {size_after:.2f} MB)"
            )

            self.stats['space_reclaimed_mb'] = space_reclaimed
        else:
            logger.info(
                f"[DRY RUN] Would vacuum database (current size: {size_before:.2f} MB)"
            )

    def analyze_database(self) -> None:
        """Analyze database and update statistics"""
        logger.info("Analyzing database...")

        if not self.dry_run:
            with self.db_manager.get_connection() as conn:
                conn.execute("ANALYZE")

            logger.info("Database analysis complete")
        else:
            logger.info("[DRY RUN] Would analyze database")

    def print_database_statistics(self) -> None:
        """Print database statistics"""
        logger.info("\n" + "=" * 60)
        logger.info("DATABASE STATISTICS")
        logger.info("=" * 60)

        db_size = self.get_database_size()
        logger.info(f"Database size: {db_size:.2f} MB")

        # Table statistics
        for table_name in ['plc_logs', 'attitude_logs', 'monitoring_logs', 'ring_summary']:
            try:
                info = self.get_table_info(table_name)
                logger.info(f"\n{table_name}:")
                logger.info(f"  Total records:  {info['total_records']:,}")
                if info['oldest_date']:
                    logger.info(f"  Oldest record:  {info['oldest_date']}")
                if info['newest_date']:
                    logger.info(f"  Newest record:  {info['newest_date']}")
            except Exception as e:
                logger.warning(f"Could not get info for {table_name}: {e}")

        logger.info("=" * 60)

    def run_cleanup(
        self,
        retention_days_plc: int = 90,
        retention_days_attitude: int = 90,
        retention_days_monitoring: int = 180,
        delete_synced: bool = False,
        vacuum: bool = False
    ) -> None:
        """
        Run cleanup process.

        Args:
            retention_days_plc: Retention for PLC logs
            retention_days_attitude: Retention for attitude logs
            retention_days_monitoring: Retention for monitoring logs
            delete_synced: Delete synced data
            vacuum: Run VACUUM after cleanup
        """
        logger.info("Starting data cleanup process...")
        logger.info(f"Dry run mode: {self.dry_run}")

        # Print initial statistics
        self.print_database_statistics()

        # Cleanup old records
        logger.info("\n--- Cleaning Old Records ---")

        self.stats['plc_logs_deleted'] = self.cleanup_old_records(
            'plc_logs', retention_days_plc
        )

        self.stats['attitude_logs_deleted'] = self.cleanup_old_records(
            'attitude_logs', retention_days_attitude
        )

        self.stats['monitoring_logs_deleted'] = self.cleanup_old_records(
            'monitoring_logs', retention_days_monitoring
        )

        # Delete synced data if requested
        if delete_synced:
            logger.info("\n--- Cleaning Synced Data ---")
            synced_deleted = self.cleanup_synced_data()
            logger.info(f"Deleted {synced_deleted} synced records")

        # Vacuum database
        if vacuum:
            logger.info("\n--- Database Maintenance ---")
            self.vacuum_database()
            self.analyze_database()

        # Print final statistics
        logger.info("\n" + "=" * 60)
        logger.info("CLEANUP COMPLETE")
        logger.info("=" * 60)
        logger.info(f"PLC logs deleted:        {self.stats['plc_logs_deleted']:,}")
        logger.info(f"Attitude logs deleted:   {self.stats['attitude_logs_deleted']:,}")
        logger.info(f"Monitoring logs deleted: {self.stats['monitoring_logs_deleted']:,}")
        logger.info(f"Space reclaimed:         {self.stats['space_reclaimed_mb']:.2f} MB")
        logger.info("=" * 60)

        # Print final database statistics
        self.print_database_statistics()


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Data cleanup automation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would be deleted
  python cleanup_old_data.py --dry-run

  # Delete PLC/attitude logs older than 90 days
  python cleanup_old_data.py --retention-days 90

  # Delete all synced data and vacuum
  python cleanup_old_data.py --delete-synced --vacuum

  # Custom retention for different log types
  python cleanup_old_data.py --plc-retention 60 --monitoring-retention 180
        """
    )

    parser.add_argument(
        '--db-path',
        type=str,
        default='data/edge.db',
        help='Path to database (default: data/edge.db)'
    )

    # Retention policies
    parser.add_argument(
        '--retention-days',
        type=int,
        help='Default retention days for all logs'
    )
    parser.add_argument(
        '--plc-retention',
        type=int,
        default=90,
        help='Retention days for PLC logs (default: 90)'
    )
    parser.add_argument(
        '--attitude-retention',
        type=int,
        default=90,
        help='Retention days for attitude logs (default: 90)'
    )
    parser.add_argument(
        '--monitoring-retention',
        type=int,
        default=180,
        help='Retention days for monitoring logs (default: 180)'
    )

    # Cleanup options
    parser.add_argument(
        '--delete-synced',
        action='store_true',
        help='Delete data that has been synced to cloud'
    )
    parser.add_argument(
        '--vacuum',
        action='store_true',
        help='Vacuum database after cleanup to reclaim space'
    )

    # Execution options
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run mode (no deletions)'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )

    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_arguments()

    # Set log level
    logging.getLogger().setLevel(args.log_level)

    # Create cleanup manager
    cleanup_manager = DataCleanupManager(
        db_path=args.db_path,
        dry_run=args.dry_run
    )

    # Apply retention days override
    plc_retention = args.retention_days if args.retention_days else args.plc_retention
    attitude_retention = args.retention_days if args.retention_days else args.attitude_retention
    monitoring_retention = args.retention_days if args.retention_days else args.monitoring_retention

    # Run cleanup
    cleanup_manager.run_cleanup(
        retention_days_plc=plc_retention,
        retention_days_attitude=attitude_retention,
        retention_days_monitoring=monitoring_retention,
        delete_synced=args.delete_synced,
        vacuum=args.vacuum
    )


if __name__ == '__main__':
    main()
