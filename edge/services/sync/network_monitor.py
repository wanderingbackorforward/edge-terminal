"""
Network Connectivity Monitor
Monitors network connectivity to cloud services
Tracks online/offline state for store-and-forward sync
"""
import asyncio
import logging
from typing import Optional, Callable
from datetime import datetime
import aiohttp

logger = logging.getLogger(__name__)


class NetworkMonitor:
    """
    Monitors network connectivity to cloud endpoint.
    
    Features:
    - Periodic health checks to cloud API
    - Online/offline state tracking
    - Callback notifications on state changes
    - Configurable check interval and timeout
    """

    def __init__(
        self,
        cloud_endpoint: str,
        health_check_path: str = "/health",
        check_interval: float = 30.0,
        timeout: float = 10.0,
        on_state_change: Optional[Callable] = None
    ):
        """
        Initialize network monitor.

        Args:
            cloud_endpoint: Base URL of cloud API (e.g., "http://cloud.example.com:8001")
            health_check_path: Health check endpoint path
            check_interval: Seconds between health checks
            timeout: HTTP request timeout in seconds
            on_state_change: Callback function(is_online: bool) called on state changes
        """
        self.cloud_endpoint = cloud_endpoint.rstrip('/')
        self.health_check_path = health_check_path
        self.check_interval = check_interval
        self.timeout = timeout
        self.on_state_change = on_state_change

        self._is_online = False
        self._last_check_time: Optional[datetime] = None
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Statistics
        self._stats = {
            'total_checks': 0,
            'successful_checks': 0,
            'failed_checks': 0,
            'state_changes': 0,
            'total_uptime_seconds': 0.0,
            'total_downtime_seconds': 0.0
        }

    async def start(self) -> None:
        """Start network monitoring"""
        if self._running:
            logger.warning("Network monitor already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Network monitor started: {self.cloud_endpoint}")

    async def stop(self) -> None:
        """Stop network monitoring"""
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Network monitor stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._running:
            try:
                await self._perform_health_check()
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
                await asyncio.sleep(self.check_interval)

    async def _perform_health_check(self) -> None:
        """Perform health check to cloud endpoint"""
        self._stats['total_checks'] += 1
        check_time = datetime.now()

        try:
            url = f"{self.cloud_endpoint}{self.health_check_path}"
            timeout_config = aiohttp.ClientTimeout(total=self.timeout)

            async with aiohttp.ClientSession(timeout=timeout_config) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        await self._handle_success(check_time)
                    else:
                        await self._handle_failure(
                            check_time, 
                            f"HTTP {response.status}"
                        )

        except aiohttp.ClientError as e:
            await self._handle_failure(check_time, f"Connection error: {e}")

        except asyncio.TimeoutError:
            await self._handle_failure(check_time, "Timeout")

        except Exception as e:
            await self._handle_failure(check_time, f"Unexpected error: {e}")

    async def _handle_success(self, check_time: datetime) -> None:
        """Handle successful health check"""
        self._stats['successful_checks'] += 1
        self._consecutive_successes += 1
        self._consecutive_failures = 0
        self._last_check_time = check_time

        # Consider online after 1 successful check
        if not self._is_online:
            await self._set_online(True)
            logger.info("Network connection established")

    async def _handle_failure(self, check_time: datetime, reason: str) -> None:
        """Handle failed health check"""
        self._stats['failed_checks'] += 1
        self._consecutive_failures += 1
        self._consecutive_successes = 0
        self._last_check_time = check_time

        logger.debug(f"Health check failed: {reason}")

        # Consider offline after 3 consecutive failures
        if self._is_online and self._consecutive_failures >= 3:
            await self._set_online(False)
            logger.warning("Network connection lost")

    async def _set_online(self, is_online: bool) -> None:
        """Set online state and trigger callback"""
        if self._is_online != is_online:
            self._is_online = is_online
            self._stats['state_changes'] += 1

            # Call state change callback
            if self.on_state_change:
                try:
                    if asyncio.iscoroutinefunction(self.on_state_change):
                        await self.on_state_change(is_online)
                    else:
                        self.on_state_change(is_online)
                except Exception as e:
                    logger.error(f"Error in state change callback: {e}", exc_info=True)

    def is_online(self) -> bool:
        """Get current online status"""
        return self._is_online

    def get_last_check_time(self) -> Optional[datetime]:
        """Get timestamp of last health check"""
        return self._last_check_time

    def get_statistics(self) -> dict:
        """Get monitoring statistics"""
        return {
            'is_online': self._is_online,
            'consecutive_failures': self._consecutive_failures,
            'consecutive_successes': self._consecutive_successes,
            'last_check_time': self._last_check_time.isoformat() if self._last_check_time else None,
            **self._stats
        }

    def reset_statistics(self) -> None:
        """Reset statistics counters"""
        self._stats = {
            'total_checks': 0,
            'successful_checks': 0,
            'failed_checks': 0,
            'state_changes': 0,
            'total_uptime_seconds': 0.0,
            'total_downtime_seconds': 0.0
        }


# Example usage
async def example_usage():
    """Example of using NetworkMonitor"""

    def on_state_change(is_online: bool):
        """Callback for state changes"""
        if is_online:
            print("✅ Network is ONLINE - syncing enabled")
        else:
            print("⚠️  Network is OFFLINE - store-and-forward mode")

    monitor = NetworkMonitor(
        cloud_endpoint="http://localhost:8001",
        health_check_path="/health",
        check_interval=10.0,
        timeout=5.0,
        on_state_change=on_state_change
    )

    try:
        await monitor.start()

        # Run for 1 minute
        await asyncio.sleep(60)

        # Get statistics
        stats = monitor.get_statistics()
        print(f"\nMonitoring statistics:")
        print(f"  Total checks: {stats['total_checks']}")
        print(f"  Successful: {stats['successful_checks']}")
        print(f"  Failed: {stats['failed_checks']}")
        print(f"  State changes: {stats['state_changes']}")
        print(f"  Currently online: {stats['is_online']}")

    finally:
        await monitor.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(example_usage())
