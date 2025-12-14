"""
Cloud Sync Manager
Orchestrates all cloud synchronization components
Manages store-and-forward, monitoring, and data lifecycle
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from edge.services.sync.network_monitor import NetworkMonitor
from edge.services.sync.buffer_manager import BufferManager
from edge.services.sync.ring_uploader import RingUploader
from edge.services.sync.prediction_uploader import PredictionUploader
from edge.services.sync.warning_uploader import WarningUploader
from edge.services.sync.disk_monitor import DiskMonitor
from edge.services.sync.data_purger import DataPurger

logger = logging.getLogger(__name__)


class SyncManager:
    """
    Main synchronization orchestrator for edge-to-cloud sync.

    Responsibilities:
    - Monitor network connectivity
    - Buffer data when offline
    - Sync data when online
    - Monitor disk space
    - Purge old data
    - Provide unified status and statistics

    Architecture:
    - Store-and-forward pattern for offline resilience
    - Priority-based sync (warnings > predictions > rings)
    - Automatic retry with exponential backoff
    - Disk space management with automatic cleanup
    """

    def __init__(
        self,
        db_manager,
        config: Dict[str, Any]
    ):
        """
        Initialize sync manager.

        Args:
            db_manager: DatabaseManager instance
            config: Configuration dict with:
                - cloud_endpoint: Cloud API URL
                - api_key: Authentication key
                - edge_device_id: Unique device identifier
                - project_id: Project ID
                - raw_data_path: Path to raw data directory
                - sync_interval: Seconds between sync attempts (default 60)
                - purge_interval: Seconds between purge runs (default 3600)
        """
        self.db_manager = db_manager
        self.config = config

        # Extract config
        self.cloud_endpoint = config['cloud_endpoint']
        self.api_key = config['api_key']
        self.edge_device_id = config['edge_device_id']
        self.project_id = config['project_id']
        self.sync_interval = config.get('sync_interval', 60.0)
        self.purge_interval = config.get('purge_interval', 3600.0)

        # Initialize components
        self.network_monitor = NetworkMonitor(
            cloud_endpoint=self.cloud_endpoint,
            check_interval=30.0,
            on_state_change=self._on_network_state_change
        )

        self.buffer_manager = BufferManager(
            db_manager=db_manager,
            max_buffer_size=config.get('max_buffer_size', 10000)
        )

        self.ring_uploader = RingUploader(
            cloud_endpoint=self.cloud_endpoint,
            api_key=self.api_key,
            edge_device_id=self.edge_device_id,
            project_id=self.project_id,
            batch_size=config.get('ring_batch_size', 50)
        )

        self.prediction_uploader = PredictionUploader(
            cloud_endpoint=self.cloud_endpoint,
            api_key=self.api_key,
            edge_device_id=self.edge_device_id,
            project_id=self.project_id,
            batch_size=config.get('prediction_batch_size', 100)
        )

        self.warning_uploader = WarningUploader(
            cloud_endpoint=self.cloud_endpoint,
            api_key=self.api_key,
            edge_device_id=self.edge_device_id,
            project_id=self.project_id,
            batch_size=config.get('warning_batch_size', 20)
        )

        self.disk_monitor = DiskMonitor(
            paths_to_monitor=config.get('paths_to_monitor', ['/app/data', '/app/logs']),
            warning_threshold_gb=config.get('disk_warning_threshold_gb', 5.0),
            critical_threshold_gb=config.get('disk_critical_threshold_gb', 2.0),
            on_low_space=self._on_low_disk_space
        )

        self.data_purger = DataPurger(
            db_manager=db_manager,
            raw_data_path=config['raw_data_path'],
            retention_days=config.get('retention_days', 30)
        )

        # State
        self._running = False
        self._sync_task: Optional[asyncio.Task] = None
        self._purge_task: Optional[asyncio.Task] = None
        self._last_sync_time: Optional[datetime] = None
        self._last_purge_time: Optional[datetime] = None

        # Statistics
        self._stats = {
            'sync_cycles': 0,
            'successful_syncs': 0,
            'failed_syncs': 0,
            'purge_cycles': 0,
            'total_items_synced': 0
        }

    async def start(self) -> None:
        """Start sync manager and all components"""
        if self._running:
            logger.warning("Sync manager already running")
            return

        logger.info("Starting sync manager...")

        try:
            # Initialize buffer manager
            await self.buffer_manager.initialize()

            # Start monitoring
            await self.network_monitor.start()
            await self.disk_monitor.start()

            # Start sync and purge loops
            self._running = True
            self._sync_task = asyncio.create_task(self._sync_loop())
            self._purge_task = asyncio.create_task(self._purge_loop())

            logger.info(
                f"Sync manager started: "
                f"device={self.edge_device_id}, "
                f"endpoint={self.cloud_endpoint}"
            )

        except Exception as e:
            logger.error(f"Error starting sync manager: {e}", exc_info=True)
            await self.stop()
            raise

    async def stop(self) -> None:
        """Stop sync manager and all components"""
        if not self._running:
            return

        logger.info("Stopping sync manager...")

        self._running = False

        # Cancel tasks
        for task in [self._sync_task, self._purge_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Stop monitors
        await self.network_monitor.stop()
        await self.disk_monitor.stop()

        logger.info("Sync manager stopped")

    async def _sync_loop(self) -> None:
        """Main synchronization loop"""
        while self._running:
            try:
                await self._perform_sync()
                await asyncio.sleep(self.sync_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in sync loop: {e}", exc_info=True)
                await asyncio.sleep(self.sync_interval)

    async def _perform_sync(self) -> None:
        """Perform synchronization cycle"""
        self._stats['sync_cycles'] += 1
        self._last_sync_time = datetime.now()

        # Check if online
        if not self.network_monitor.is_online():
            logger.debug("Offline - skipping sync")
            return

        try:
            total_synced = 0

            # Priority 1: Sync warnings (most urgent)
            warnings_synced = await self._sync_warnings()
            total_synced += warnings_synced

            # Priority 2: Sync predictions
            predictions_synced = await self._sync_predictions()
            total_synced += predictions_synced

            # Priority 3: Sync ring summaries
            rings_synced = await self._sync_rings()
            total_synced += rings_synced

            if total_synced > 0:
                self._stats['successful_syncs'] += 1
                self._stats['total_items_synced'] += total_synced
                logger.info(
                    f"Sync cycle complete: {total_synced} items synced "
                    f"(warnings={warnings_synced}, predictions={predictions_synced}, rings={rings_synced})"
                )
            else:
                logger.debug("Sync cycle: no new data to sync")

        except Exception as e:
            self._stats['failed_syncs'] += 1
            logger.error(f"Error in sync cycle: {e}", exc_info=True)

    async def _sync_warnings(self) -> int:
        """Sync warning events"""
        try:
            # Get warnings from buffer
            batch = await self.buffer_manager.get_batch(
                batch_size=self.warning_uploader.batch_size,
                item_type='warning'
            )

            if not batch:
                return 0

            # Extract payloads
            warnings = [item['payload'] for item in batch]

            # Upload
            result = await self.warning_uploader.upload_batch(warnings)

            # Update buffer
            if result['success']:
                for item in batch:
                    await self.buffer_manager.mark_synced(item['id'])
                return len(batch)
            else:
                for item in batch:
                    await self.buffer_manager.mark_failed(item['id'])
                logger.warning(f"Warning sync failed: {result.get('error')}")
                return 0

        except Exception as e:
            logger.error(f"Error syncing warnings: {e}", exc_info=True)
            return 0

    async def _sync_predictions(self) -> int:
        """Sync prediction results"""
        try:
            # Get predictions from buffer
            batch = await self.buffer_manager.get_batch(
                batch_size=self.prediction_uploader.batch_size,
                item_type='prediction'
            )

            if not batch:
                return 0

            # Extract payloads
            predictions = [item['payload'] for item in batch]

            # Upload
            result = await self.prediction_uploader.upload_batch(predictions)

            # Update buffer
            if result['success']:
                for item in batch:
                    await self.buffer_manager.mark_synced(item['id'])
                return len(batch)
            else:
                for item in batch:
                    await self.buffer_manager.mark_failed(item['id'])
                logger.warning(f"Prediction sync failed: {result.get('error')}")
                return 0

        except Exception as e:
            logger.error(f"Error syncing predictions: {e}", exc_info=True)
            return 0

    async def _sync_rings(self) -> int:
        """Sync ring summaries"""
        try:
            # Get rings from buffer
            batch = await self.buffer_manager.get_batch(
                batch_size=self.ring_uploader.batch_size,
                item_type='ring_summary'
            )

            if not batch:
                return 0

            # Extract payloads
            rings = [item['payload'] for item in batch]

            # Upload
            result = await self.ring_uploader.upload_batch(rings)

            # Update buffer
            if result['success']:
                for item in batch:
                    await self.buffer_manager.mark_synced(item['id'])

                    # Mark as synced in database
                    await self._mark_ring_synced(item['item_id'])

                return len(batch)
            else:
                for item in batch:
                    await self.buffer_manager.mark_failed(item['id'])
                logger.warning(f"Ring sync failed: {result.get('error')}")
                return 0

        except Exception as e:
            logger.error(f"Error syncing rings: {e}", exc_info=True)
            return 0

    async def _mark_ring_synced(self, ring_id: int) -> None:
        """Mark ring as synced in database"""
        try:
            with self.db_manager.transaction() as conn:
                conn.execute(
                    "UPDATE ring_summary SET sync_status = 'synced' WHERE id = ?",
                    (ring_id,)
                )
        except Exception as e:
            logger.error(f"Error marking ring {ring_id} as synced: {e}", exc_info=True)

    async def _purge_loop(self) -> None:
        """Periodic data purge loop"""
        while self._running:
            try:
                await asyncio.sleep(self.purge_interval)
                await self._perform_purge()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in purge loop: {e}", exc_info=True)

    async def _perform_purge(self) -> None:
        """Perform data purge cycle"""
        self._stats['purge_cycles'] += 1
        self._last_purge_time = datetime.now()

        try:
            result = await self.data_purger.purge_old_data()

            if result['success'] and result['files_deleted'] > 0:
                logger.info(
                    f"Purge complete: deleted {result['files_deleted']} files "
                    f"({result['bytes_freed_mb']:.2f} MB freed)"
                )

        except Exception as e:
            logger.error(f"Error in purge cycle: {e}", exc_info=True)

    async def _on_network_state_change(self, is_online: bool) -> None:
        """Callback when network state changes"""
        if is_online:
            logger.info("Network ONLINE - syncing enabled")
            # Trigger immediate sync
            if self._running:
                asyncio.create_task(self._perform_sync())
        else:
            logger.warning("Network OFFLINE - store-and-forward mode")

    async def _on_low_disk_space(self, level: str, free_gb: float) -> None:
        """Callback when disk space is low"""
        logger.warning(f"Low disk space ({level}): {free_gb:.2f} GB free")

        if level == 'critical':
            # Emergency purge
            logger.warning("Triggering emergency purge")
            result = await self.data_purger.purge_unsynced_old_data(max_age_days=90)
            logger.warning(
                f"Emergency purge: freed {result['bytes_freed_mb']:.2f} MB"
            )

        elif level == 'warning':
            # Normal purge
            logger.info("Triggering normal purge")
            asyncio.create_task(self._perform_purge())

    async def queue_ring_summary(self, ring_id: int, payload: Dict[str, Any]) -> bool:
        """
        Queue ring summary for sync.

        Args:
            ring_id: Ring ID in database
            payload: Ring summary data

        Returns:
            True if queued successfully
        """
        return await self.buffer_manager.add_item(
            item_type='ring_summary',
            item_id=ring_id,
            payload=payload,
            priority=0
        )

    async def queue_prediction(self, prediction_id: int, payload: Dict[str, Any]) -> bool:
        """
        Queue prediction result for sync.

        Args:
            prediction_id: Prediction ID in database
            payload: Prediction data

        Returns:
            True if queued successfully
        """
        return await self.buffer_manager.add_item(
            item_type='prediction',
            item_id=prediction_id,
            payload=payload,
            priority=1
        )

    async def queue_warning(self, warning_id: int, payload: Dict[str, Any], severity: str = 'medium') -> bool:
        """
        Queue warning event for sync.

        Args:
            warning_id: Warning ID in database
            payload: Warning data
            severity: Severity level (affects priority)

        Returns:
            True if queued successfully
        """
        # Map severity to priority
        priority_map = {
            'critical': 10,
            'high': 5,
            'medium': 2,
            'low': 1
        }
        priority = priority_map.get(severity, 2)

        return await self.buffer_manager.add_item(
            item_type='warning',
            item_id=warning_id,
            payload=payload,
            priority=priority
        )

    def is_online(self) -> bool:
        """Check if currently online"""
        return self.network_monitor.is_online()

    async def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive sync status.

        Returns:
            Dict with status of all components
        """
        buffer_size = await self.buffer_manager.get_buffer_size()
        buffer_by_type = await self.buffer_manager.get_buffer_size_by_type()
        disk_usage = await self.disk_monitor.get_current_usage()

        return {
            'running': self._running,
            'online': self.network_monitor.is_online(),
            'last_sync': self._last_sync_time.isoformat() if self._last_sync_time else None,
            'last_purge': self._last_purge_time.isoformat() if self._last_purge_time else None,
            'buffer': {
                'total_items': buffer_size,
                'by_type': buffer_by_type
            },
            'disk': {
                'state': self.disk_monitor.get_current_state(),
                'usage': disk_usage
            },
            'statistics': self.get_statistics()
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get combined statistics from all components"""
        return {
            'manager': dict(self._stats),
            'network': self.network_monitor.get_statistics(),
            'buffer': self.buffer_manager.get_statistics(),
            'ring_uploader': self.ring_uploader.get_statistics(),
            'prediction_uploader': self.prediction_uploader.get_statistics(),
            'warning_uploader': self.warning_uploader.get_statistics(),
            'disk': self.disk_monitor.get_statistics(),
            'purger': self.data_purger.get_statistics()
        }


# Example usage
async def example_usage():
    """Example of using SyncManager"""
    from edge.services.database.database_manager import DatabaseManager

    # Initialize database
    db_manager = DatabaseManager(db_path='/app/data/shield.db')
    await db_manager.initialize()

    # Configuration
    config = {
        'cloud_endpoint': 'http://localhost:8001',
        'api_key': 'test-api-key',
        'edge_device_id': 'edge-001',
        'project_id': 1,
        'raw_data_path': '/app/data/raw',
        'sync_interval': 60.0,
        'purge_interval': 3600.0
    }

    # Create sync manager
    sync_manager = SyncManager(
        db_manager=db_manager,
        config=config
    )

    try:
        # Start
        await sync_manager.start()

        # Queue some data
        await sync_manager.queue_ring_summary(
            ring_id=1,
            payload={'ring_number': 100, 'mean_thrust': 12000.0}
        )

        await sync_manager.queue_warning(
            warning_id=1,
            payload={'ring_number': 100, 'warning_type': 'settlement_anomaly'},
            severity='critical'
        )

        # Check status
        status = await sync_manager.get_status()
        print(f"\nSync Manager Status:")
        print(f"  Online: {status['online']}")
        print(f"  Buffer items: {status['buffer']['total_items']}")
        print(f"  Disk state: {status['disk']['state']}")

        # Run for a while
        await asyncio.sleep(300)

        # Final statistics
        stats = sync_manager.get_statistics()
        print(f"\nFinal Statistics:")
        print(f"  Sync cycles: {stats['manager']['sync_cycles']}")
        print(f"  Items synced: {stats['manager']['total_items_synced']}")

    finally:
        await sync_manager.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(example_usage())
