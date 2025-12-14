"""
Data Purger
Deletes old raw data files after successful cloud sync
Manages disk space by removing synced logs
"""
import asyncio
import logging
from typing import Optional, List
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DataPurger:
    """
    Purges old raw data files after successful sync.

    Features:
    - Delete raw logs older than retention period
    - Verify sync before deletion
    - Preserve ring_summary table data
    - Safety checks to prevent accidental deletion
    - Statistics tracking
    """

    def __init__(
        self,
        db_manager,
        raw_data_path: str,
        retention_days: int = 30,
        dry_run: bool = False
    ):
        """
        Initialize data purger.

        Args:
            db_manager: DatabaseManager instance
            raw_data_path: Path to raw data directory
            retention_days: Keep raw data for this many days
            dry_run: If True, only log what would be deleted (don't delete)
        """
        self.db_manager = db_manager
        self.raw_data_path = Path(raw_data_path)
        self.retention_days = retention_days
        self.dry_run = dry_run

        # Statistics
        self._stats = {
            'total_purge_runs': 0,
            'files_deleted': 0,
            'bytes_freed': 0,
            'files_skipped': 0,
            'errors': 0
        }

    async def purge_old_data(self) -> dict:
        """
        Purge old raw data files.

        Returns:
            Dict with purge results:
            {
                'success': bool,
                'files_deleted': int,
                'bytes_freed': int,
                'files_skipped': int,
                'errors': List[str]
            }
        """
        self._stats['total_purge_runs'] += 1

        logger.info(
            f"Starting data purge: retention={self.retention_days} days, "
            f"dry_run={self.dry_run}"
        )

        errors = []
        files_deleted = 0
        bytes_freed = 0
        files_skipped = 0

        try:
            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            cutoff_timestamp = cutoff_date.timestamp()

            logger.info(f"Purging raw data older than: {cutoff_date.isoformat()}")

            # Get list of synced ring numbers (safe to delete)
            synced_rings = await self._get_synced_rings(cutoff_timestamp)
            logger.info(f"Found {len(synced_rings)} synced rings older than cutoff")

            if not synced_rings:
                logger.info("No old synced data to purge")
                return {
                    'success': True,
                    'files_deleted': 0,
                    'bytes_freed': 0,
                    'files_skipped': 0,
                    'errors': []
                }

            # Find raw data files to delete
            if not self.raw_data_path.exists():
                logger.warning(f"Raw data path does not exist: {self.raw_data_path}")
                return {
                    'success': True,
                    'files_deleted': 0,
                    'bytes_freed': 0,
                    'files_skipped': 0,
                    'errors': []
                }

            # Search for CSV files matching synced rings
            for ring_number in synced_rings:
                files = self._find_ring_files(ring_number)

                for file_path in files:
                    try:
                        # Safety check: verify file is old enough
                        file_age_days = (
                            datetime.now() - datetime.fromtimestamp(file_path.stat().st_mtime)
                        ).days

                        if file_age_days < self.retention_days:
                            logger.debug(
                                f"Skipping recent file (age {file_age_days} days): {file_path.name}"
                            )
                            files_skipped += 1
                            continue

                        # Get file size before deletion
                        file_size = file_path.stat().st_size

                        if self.dry_run:
                            logger.info(f"[DRY RUN] Would delete: {file_path.name} ({file_size} bytes)")
                            files_deleted += 1
                            bytes_freed += file_size
                        else:
                            # Delete file
                            file_path.unlink()
                            logger.info(f"Deleted: {file_path.name} ({file_size} bytes)")
                            files_deleted += 1
                            bytes_freed += file_size

                    except Exception as e:
                        error_msg = f"Error deleting {file_path.name}: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        self._stats['errors'] += 1

            # Update statistics
            self._stats['files_deleted'] += files_deleted
            self._stats['bytes_freed'] += bytes_freed
            self._stats['files_skipped'] += files_skipped

            result = {
                'success': len(errors) == 0,
                'files_deleted': files_deleted,
                'bytes_freed': bytes_freed,
                'bytes_freed_mb': bytes_freed / (1024 * 1024),
                'files_skipped': files_skipped,
                'errors': errors
            }

            logger.info(
                f"Purge complete: deleted {files_deleted} files "
                f"({bytes_freed / (1024 * 1024):.2f} MB freed), "
                f"skipped {files_skipped} files, "
                f"errors: {len(errors)}"
            )

            return result

        except Exception as e:
            error_msg = f"Error during purge: {e}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)
            self._stats['errors'] += 1

            return {
                'success': False,
                'files_deleted': files_deleted,
                'bytes_freed': bytes_freed,
                'bytes_freed_mb': bytes_freed / (1024 * 1024),
                'files_skipped': files_skipped,
                'errors': errors
            }

    async def _get_synced_rings(self, cutoff_timestamp: float) -> List[int]:
        """
        Get list of ring numbers that have been synced to cloud.

        Args:
            cutoff_timestamp: Only consider rings older than this

        Returns:
            List of ring numbers safe to delete
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT DISTINCT rs.ring_number
                    FROM ring_summary rs
                    WHERE rs.start_time < ?
                    AND rs.sync_status = 'synced'
                    AND rs.data_completeness_flag IN ('complete', 'acceptable')
                    ORDER BY rs.ring_number
                    """,
                    (cutoff_timestamp,)
                )
                rows = cursor.fetchall()

            return [row['ring_number'] for row in rows]

        except Exception as e:
            logger.error(f"Error getting synced rings: {e}", exc_info=True)
            return []

    def _find_ring_files(self, ring_number: int) -> List[Path]:
        """
        Find raw data files for a specific ring.

        Args:
            ring_number: Ring number to find files for

        Returns:
            List of file paths
        """
        files = []

        try:
            # Pattern: ring_XXXXX_*.csv
            pattern = f"ring_{ring_number:05d}_*.csv"
            files.extend(self.raw_data_path.glob(pattern))

            # Also check subdirectories (date-based organization)
            for subdir in self.raw_data_path.iterdir():
                if subdir.is_dir():
                    files.extend(subdir.glob(pattern))

        except Exception as e:
            logger.error(f"Error finding files for ring {ring_number}: {e}", exc_info=True)

        return files

    async def purge_unsynced_old_data(self, max_age_days: int = 90) -> dict:
        """
        Emergency purge: delete very old unsynced data to free space.

        This is a safety measure when disk space is critically low.
        Only deletes data older than max_age_days.

        Args:
            max_age_days: Delete unsynced data older than this (default 90 days)

        Returns:
            Dict with purge results
        """
        logger.warning(
            f"Emergency purge: deleting unsynced data older than {max_age_days} days"
        )

        errors = []
        files_deleted = 0
        bytes_freed = 0

        try:
            cutoff_date = datetime.now() - timedelta(days=max_age_days)

            if not self.raw_data_path.exists():
                return {
                    'success': True,
                    'files_deleted': 0,
                    'bytes_freed': 0,
                    'errors': []
                }

            # Find all CSV files
            for file_path in self.raw_data_path.rglob("*.csv"):
                try:
                    # Check file age
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)

                    if file_mtime < cutoff_date:
                        file_size = file_path.stat().st_size

                        if self.dry_run:
                            logger.warning(
                                f"[DRY RUN] Would delete old unsynced: {file_path.name}"
                            )
                        else:
                            file_path.unlink()
                            logger.warning(f"Deleted old unsynced: {file_path.name}")

                        files_deleted += 1
                        bytes_freed += file_size

                except Exception as e:
                    error_msg = f"Error deleting {file_path.name}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            logger.warning(
                f"Emergency purge complete: deleted {files_deleted} files "
                f"({bytes_freed / (1024 * 1024):.2f} MB freed)"
            )

            return {
                'success': len(errors) == 0,
                'files_deleted': files_deleted,
                'bytes_freed': bytes_freed,
                'bytes_freed_mb': bytes_freed / (1024 * 1024),
                'errors': errors
            }

        except Exception as e:
            error_msg = f"Error during emergency purge: {e}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)

            return {
                'success': False,
                'files_deleted': files_deleted,
                'bytes_freed': bytes_freed,
                'bytes_freed_mb': bytes_freed / (1024 * 1024),
                'errors': errors
            }

    def get_statistics(self) -> dict:
        """Get purge statistics"""
        return dict(self._stats)

    def reset_statistics(self) -> None:
        """Reset statistics counters"""
        self._stats = {
            'total_purge_runs': 0,
            'files_deleted': 0,
            'bytes_freed': 0,
            'files_skipped': 0,
            'errors': 0
        }


# Example usage
async def example_usage():
    """Example of using DataPurger"""
    from edge.services.database.database_manager import DatabaseManager

    # Initialize database
    db_manager = DatabaseManager(db_path='/app/data/shield.db')
    await db_manager.initialize()

    # Create purger
    purger = DataPurger(
        db_manager=db_manager,
        raw_data_path='/app/data/raw',
        retention_days=30,
        dry_run=True  # Safe mode for demo
    )

    # Purge old synced data
    result = await purger.purge_old_data()

    print(f"\nPurge result:")
    print(f"  Success: {result['success']}")
    print(f"  Files deleted: {result['files_deleted']}")
    print(f"  Space freed: {result['bytes_freed_mb']:.2f} MB")
    print(f"  Files skipped: {result['files_skipped']}")
    print(f"  Errors: {len(result['errors'])}")

    # Get statistics
    stats = purger.get_statistics()
    print(f"\nStatistics:")
    print(f"  Total purge runs: {stats['total_purge_runs']}")
    print(f"  Files deleted: {stats['files_deleted']}")
    print(f"  Bytes freed: {stats['bytes_freed'] / (1024 * 1024):.2f} MB")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(example_usage())
