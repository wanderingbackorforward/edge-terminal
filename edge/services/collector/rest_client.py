"""
REST API Client Connector
Collects data from external monitoring systems via REST API
Supports polling and webhook modes
"""
import asyncio
import logging
from typing import Dict, Any, Callable, Optional, List
from datetime import datetime
import aiohttp

logger = logging.getLogger(__name__)


class RESTAPICollector:
    """
    Async REST API client for collecting monitoring data.

    Features:
    - Polling-based data collection
    - Configurable poll intervals per endpoint
    - Bearer token authentication
    - Automatic retry with exponential backoff
    - JSON response parsing
    """

    def __init__(
        self,
        base_url: str,
        endpoints: Dict[str, Dict[str, Any]],
        callback: Callable,
        auth_token: Optional[str] = None,
        timeout: int = 10,
        max_retries: int = 3
    ):
        """
        Initialize REST API collector.

        Args:
            base_url: Base URL of the API
            endpoints: Dict of endpoint configurations
                      {name: {path: str, method: str, poll_interval: int}}
            callback: Function to call with collected data
            auth_token: Bearer token for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts on failure
        """
        self.base_url = base_url.rstrip('/')
        self.endpoints = endpoints
        self.callback = callback
        self.auth_token = auth_token
        self.timeout = timeout
        self.max_retries = max_retries

        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> None:
        """Start REST API collector"""
        if self._running:
            logger.warning("REST API collector already running")
            return

        self._running = True

        # Create aiohttp session
        headers = {}
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'

        timeout_config = aiohttp.ClientTimeout(total=self.timeout)
        self._session = aiohttp.ClientSession(
            headers=headers,
            timeout=timeout_config
        )

        # Start polling tasks for each endpoint
        for endpoint_name, config in self.endpoints.items():
            task = asyncio.create_task(
                self._poll_endpoint(endpoint_name, config)
            )
            self._tasks.append(task)

        logger.info(
            f"REST API collector started: {len(self.endpoints)} endpoints, "
            f"base_url={self.base_url}"
        )

    async def stop(self) -> None:
        """Stop REST API collector"""
        if not self._running:
            return

        self._running = False

        # Cancel all polling tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._tasks.clear()

        # Close session
        if self._session:
            await self._session.close()
            self._session = None

        logger.info("REST API collector stopped")

    async def _poll_endpoint(
        self,
        endpoint_name: str,
        config: Dict[str, Any]
    ) -> None:
        """
        Poll a specific endpoint periodically.

        Args:
            endpoint_name: Endpoint identifier
            config: Endpoint configuration
        """
        path = config['path']
        method = config.get('method', 'GET').upper()
        poll_interval = config.get('poll_interval', 60)  # seconds

        url = f"{self.base_url}{path}"

        logger.info(
            f"Starting polling for endpoint '{endpoint_name}': "
            f"{method} {url} every {poll_interval}s"
        )

        while self._running:
            try:
                # Fetch data
                data = await self._fetch_data(url, method, endpoint_name)

                if data:
                    # Process data
                    await self._process_data(endpoint_name, data)

                # Wait for next poll
                await asyncio.sleep(poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    f"Error polling endpoint '{endpoint_name}': {e}",
                    exc_info=True
                )
                # Back off on error
                await asyncio.sleep(min(poll_interval, 30))

    async def _fetch_data(
        self,
        url: str,
        method: str,
        endpoint_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch data from endpoint with retry logic.

        Args:
            url: Full URL to fetch
            method: HTTP method
            endpoint_name: Endpoint name for logging

        Returns:
            Parsed JSON data or None on failure
        """
        for attempt in range(self.max_retries):
            try:
                if method == 'GET':
                    async with self._session.get(url) as response:
                        response.raise_for_status()
                        data = await response.json()

                elif method == 'POST':
                    async with self._session.post(url) as response:
                        response.raise_for_status()
                        data = await response.json()

                else:
                    logger.error(f"Unsupported HTTP method: {method}")
                    return None

                logger.debug(
                    f"Fetched data from '{endpoint_name}': "
                    f"{response.status}, {len(data) if isinstance(data, (list, dict)) else 0} items"
                )

                return data

            except aiohttp.ClientError as e:
                logger.warning(
                    f"Request failed for '{endpoint_name}' "
                    f"(attempt {attempt + 1}/{self.max_retries}): {e}"
                )

                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    await asyncio.sleep(2 ** attempt)
                else:
                    logger.error(
                        f"Max retries reached for '{endpoint_name}'"
                    )
                    return None

            except Exception as e:
                logger.error(
                    f"Unexpected error fetching '{endpoint_name}': {e}",
                    exc_info=True
                )
                return None

        return None

    async def _process_data(
        self,
        endpoint_name: str,
        data: Any
    ) -> None:
        """
        Process fetched data and call callback.

        Args:
            endpoint_name: Endpoint name
            data: Fetched data (dict or list)
        """
        try:
            timestamp = datetime.utcnow().timestamp()

            # Handle different data formats
            if isinstance(data, list):
                # List of sensor readings
                for item in data:
                    await self._process_item(endpoint_name, item, timestamp)

            elif isinstance(data, dict):
                # Single reading or structured data
                if 'sensors' in data or 'readings' in data:
                    # Structured format with sensor array
                    sensors = data.get('sensors') or data.get('readings')
                    for sensor in sensors:
                        await self._process_item(endpoint_name, sensor, timestamp)
                else:
                    # Single sensor reading
                    await self._process_item(endpoint_name, data, timestamp)

        except Exception as e:
            logger.error(f"Error processing data from '{endpoint_name}': {e}")

    async def _process_item(
        self,
        endpoint_name: str,
        item: Dict[str, Any],
        timestamp: float
    ) -> None:
        """
        Process individual sensor item.

        Args:
            endpoint_name: Endpoint name
            item: Sensor data item
            timestamp: Collection timestamp
        """
        try:
            # Extract sensor type and value
            # Support common formats:
            # 1. {sensor_type: "...", value: ..., location: "..."}
            # 2. {type: "...", reading: ..., id: "..."}
            # 3. {name: "...", value: ...}

            sensor_type = (
                item.get('sensor_type') or
                item.get('type') or
                item.get('name') or
                endpoint_name
            )

            value = (
                item.get('value') or
                item.get('reading') or
                item.get('measurement')
            )

            location = (
                item.get('location') or
                item.get('sensor_location') or
                item.get('id')
            )

            unit = item.get('unit')

            if value is None:
                logger.debug(f"No value found in item: {item}")
                return

            # Call callback
            if self.callback:
                self.callback(
                    sensor_type=sensor_type,
                    value=value,
                    location=location,
                    unit=unit,
                    timestamp=timestamp,
                    endpoint=endpoint_name
                )

        except Exception as e:
            logger.error(f"Error processing item: {e}, item={item}")

    def get_status(self) -> Dict[str, Any]:
        """Get collector status"""
        return {
            'running': self._running,
            'base_url': self.base_url,
            'endpoints': list(self.endpoints.keys()),
            'active_tasks': len(self._tasks)
        }


# Example usage
async def example_usage():
    """Example of using RESTAPICollector"""

    def data_callback(
        sensor_type: str,
        value: Any,
        location: Optional[str],
        unit: Optional[str],
        timestamp: float,
        endpoint: str
    ):
        """Callback for received data"""
        print(
            f"[{endpoint}] {sensor_type} @ {location}: "
            f"{value} {unit or ''} (timestamp: {timestamp})"
        )

    # Configure endpoints
    endpoints = {
        'surface_settlement': {
            'path': '/api/v1/sensors/settlement',
            'method': 'GET',
            'poll_interval': 60  # Poll every 60 seconds
        },
        'building_tilt': {
            'path': '/api/v1/sensors/tilt',
            'method': 'GET',
            'poll_interval': 300  # Poll every 5 minutes
        },
        'groundwater': {
            'path': '/api/v1/sensors/groundwater',
            'method': 'GET',
            'poll_interval': 600  # Poll every 10 minutes
        }
    }

    collector = RESTAPICollector(
        base_url="http://monitoring-system.local:8080",
        endpoints=endpoints,
        callback=data_callback,
        auth_token="your-auth-token-here",
        timeout=10,
        max_retries=3
    )

    try:
        await collector.start()

        # Run for 5 minutes
        await asyncio.sleep(300)

        status = collector.get_status()
        print(f"\nCollector status: {status}")

    finally:
        await collector.stop()


if __name__ == "__main__":
    asyncio.run(example_usage())
