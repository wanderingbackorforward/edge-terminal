"""
Disk Space Monitor
Monitors available disk space for edge device
Triggers alerts when space runs low
"""
import asyncio
import logging
import shutil
from typing import Optional, Callable
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class DiskMonitor:
    """
    Monitors disk space usage on edge device.

    Features:
    - Periodic disk space checks
    - Configurable warning/critical thresholds
    - Callback notifications when thresholds crossed
    - Statistics tracking
    - Multi-path monitoring support
    """

    def __init__(
        self,
        paths_to_monitor: list[str],
        warning_threshold_gb: float = 5.0,
        critical_threshold_gb: float = 2.0,
        check_interval: float = 300.0,  # 5 minutes
        on_low_space: Optional[Callable] = None
    ):
        """
        Initialize disk monitor.

        Args:
            paths_to_monitor: List of paths to monitor (e.g., ['/app/data', '/app/logs'])
            warning_threshold_gb: Warning threshold in GB
            critical_threshold_gb: Critical threshold in GB
            check_interval: Seconds between checks
            on_low_space: Callback function(level: str, free_gb: float) called when space low
        """
        self.paths_to_monitor = [Path(p) for p in paths_to_monitor]
        self.warning_threshold_gb = warning_threshold_gb
        self.critical_threshold_gb = critical_threshold_gb
        self.check_interval = check_interval
        self.on_low_space = on_low_space

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._current_state = 'normal'  # normal, warning, critical
        self._last_check_time: Optional[datetime] = None

        # Statistics
        self._stats = {
            'total_checks': 0,
            'warning_events': 0,
            'critical_events': 0,
            'min_free_space_gb': None,
            'max_free_space_gb': None
        }

    async def start(self) -> None:
        """Start disk monitoring"""
        if self._running:
            logger.warning("Disk monitor already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(
            f"Disk monitor started: checking {len(self.paths_to_monitor)} paths "
            f"every {self.check_interval}s"
        )

    async def stop(self) -> None:
        """Stop disk monitoring"""
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Disk monitor stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._running:
            try:
                await self._perform_check()
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in disk monitor loop: {e}", exc_info=True)
                await asyncio.sleep(self.check_interval)

    async def _perform_check(self) -> None:
        """Perform disk space check"""
        self._stats['total_checks'] += 1
        self._last_check_time = datetime.now()

        try:
            # Get minimum free space across all monitored paths
            min_free_gb = float('inf')
            min_free_path = None

            for path in self.paths_to_monitor:
                if not path.exists():
                    logger.warning(f"Path does not exist: {path}")
                    continue

                usage = shutil.disk_usage(path)
                free_gb = usage.free / (1024 ** 3)  # Convert to GB

                if free_gb < min_free_gb:
                    min_free_gb = free_gb
                    min_free_path = path

                logger.debug(
                    f"Disk space on {path}: "
                    f"{free_gb:.2f} GB free / "
                    f"{usage.total / (1024 ** 3):.2f} GB total "
                    f"({usage.percent}% used)"
                )

            # Update statistics
            if self._stats['min_free_space_gb'] is None or min_free_gb < self._stats['min_free_space_gb']:
                self._stats['min_free_space_gb'] = min_free_gb

            if self._stats['max_free_space_gb'] is None or min_free_gb > self._stats['max_free_space_gb']:
                self._stats['max_free_space_gb'] = min_free_gb

            # Check thresholds
            previous_state = self._current_state

            if min_free_gb <= self.critical_threshold_gb:
                self._current_state = 'critical'
                if previous_state != 'critical':
                    self._stats['critical_events'] += 1
                    logger.error(
                        f"CRITICAL: Low disk space on {min_free_path}: "
                        f"{min_free_gb:.2f} GB free (threshold: {self.critical_threshold_gb} GB)"
                    )
                    await self._trigger_callback('critical', min_free_gb)

            elif min_free_gb <= self.warning_threshold_gb:
                self._current_state = 'warning'
                if previous_state == 'normal':
                    self._stats['warning_events'] += 1
                    logger.warning(
                        f"WARNING: Low disk space on {min_free_path}: "
                        f"{min_free_gb:.2f} GB free (threshold: {self.warning_threshold_gb} GB)"
                    )
                    await self._trigger_callback('warning', min_free_gb)

            else:
                if previous_state != 'normal':
                    logger.info(
                        f"Disk space recovered to normal: {min_free_gb:.2f} GB free"
                    )
                self._current_state = 'normal'

        except Exception as e:
            logger.error(f"Error performing disk check: {e}", exc_info=True)

    async def _trigger_callback(self, level: str, free_gb: float) -> None:
        """Trigger low space callback"""
        if self.on_low_space:
            try:
                if asyncio.iscoroutinefunction(self.on_low_space):
                    await self.on_low_space(level, free_gb)
                else:
                    self.on_low_space(level, free_gb)
            except Exception as e:
                logger.error(f"Error in low space callback: {e}", exc_info=True)

    def get_current_state(self) -> str:
        """Get current disk state: normal, warning, or critical"""
        return self._current_state

    def get_last_check_time(self) -> Optional[datetime]:
        """Get timestamp of last check"""
        return self._last_check_time

    async def get_current_usage(self) -> dict:
        """
        Get current disk usage for all monitored paths.

        Returns:
            Dict with usage info per path
        """
        usage_info = {}

        for path in self.paths_to_monitor:
            if not path.exists():
                usage_info[str(path)] = {'error': 'Path does not exist'}
                continue

            try:
                usage = shutil.disk_usage(path)
                usage_info[str(path)] = {
                    'total_gb': usage.total / (1024 ** 3),
                    'used_gb': usage.used / (1024 ** 3),
                    'free_gb': usage.free / (1024 ** 3),
                    'percent_used': usage.percent
                }
            except Exception as e:
                usage_info[str(path)] = {'error': str(e)}

        return usage_info

    def get_statistics(self) -> dict:
        """Get monitoring statistics"""
        return {
            'current_state': self._current_state,
            'last_check_time': self._last_check_time.isoformat() if self._last_check_time else None,
            **self._stats
        }

    def reset_statistics(self) -> None:
        """Reset statistics counters"""
        self._stats = {
            'total_checks': 0,
            'warning_events': 0,
            'critical_events': 0,
            'min_free_space_gb': None,
            'max_free_space_gb': None
        }


# Example usage
async def example_usage():
    """Example of using DiskMonitor"""

    def on_low_space(level: str, free_gb: float):
        """Callback for low space events"""
        if level == 'critical':
            print(f"🚨 CRITICAL: Only {free_gb:.2f} GB free - purge old data immediately!")
        elif level == 'warning':
            print(f"⚠️  WARNING: Only {free_gb:.2f} GB free - consider purging old data")

    monitor = DiskMonitor(
        paths_to_monitor=['/app/data', '/app/logs'],
        warning_threshold_gb=5.0,
        critical_threshold_gb=2.0,
        check_interval=60.0,  # Check every minute for demo
        on_low_space=on_low_space
    )

    try:
        await monitor.start()

        # Get current usage
        usage = await monitor.get_current_usage()
        print("\nCurrent disk usage:")
        for path, info in usage.items():
            if 'error' in info:
                print(f"  {path}: {info['error']}")
            else:
                print(
                    f"  {path}: {info['free_gb']:.2f} GB free / "
                    f"{info['total_gb']:.2f} GB total "
                    f"({info['percent_used']:.1f}% used)"
                )

        # Run for 5 minutes
        await asyncio.sleep(300)

        # Get statistics
        stats = monitor.get_statistics()
        print(f"\nMonitoring statistics:")
        print(f"  Total checks: {stats['total_checks']}")
        print(f"  Current state: {stats['current_state']}")
        print(f"  Warning events: {stats['warning_events']}")
        print(f"  Critical events: {stats['critical_events']}")
        if stats['min_free_space_gb']:
            print(f"  Min free space: {stats['min_free_space_gb']:.2f} GB")

    finally:
        await monitor.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(example_usage())
