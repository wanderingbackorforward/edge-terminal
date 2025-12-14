"""
Warning Events Uploader
Uploads safety warning events to cloud API
Prioritizes urgent warnings with aggressive retry
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
import aiohttp

logger = logging.getLogger(__name__)


class WarningUploader:
    """
    Uploads warning events to cloud API.

    Features:
    - Small batch sizes for urgent delivery
    - Aggressive retry with exponential backoff
    - Authentication with API key
    - Priority-based upload tracking
    - Higher timeout tolerance for critical warnings
    """

    def __init__(
        self,
        cloud_endpoint: str,
        api_key: str,
        edge_device_id: str,
        project_id: int,
        batch_size: int = 20,  # Smaller batches for urgency
        timeout: float = 45.0,  # Longer timeout for critical data
        max_retries: int = 5  # More retries for warnings
    ):
        """
        Initialize warning uploader.

        Args:
            cloud_endpoint: Base URL of cloud API
            api_key: API key for authentication
            edge_device_id: Unique ID of this edge device
            project_id: Project ID for this deployment
            batch_size: Maximum warnings per upload batch (smaller for urgency)
            timeout: HTTP request timeout
            max_retries: Maximum retry attempts (more for warnings)
        """
        self.cloud_endpoint = cloud_endpoint.rstrip('/')
        self.api_key = api_key
        self.edge_device_id = edge_device_id
        self.project_id = project_id
        self.batch_size = batch_size
        self.timeout = timeout
        self.max_retries = max_retries

        # Statistics
        self._stats = {
            'total_uploads': 0,
            'successful_uploads': 0,
            'failed_uploads': 0,
            'total_warnings_uploaded': 0,
            'critical_warnings_uploaded': 0,
            'total_bytes_uploaded': 0
        }

    async def upload_batch(
        self,
        warnings: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Upload batch of warning events to cloud.

        Args:
            warnings: List of warning event dictionaries

        Returns:
            Dict with upload result:
            {
                'success': bool,
                'uploaded_count': int,
                'failed_count': int,
                'error': Optional[str]
            }
        """
        if not warnings:
            return {
                'success': True,
                'uploaded_count': 0,
                'failed_count': 0,
                'error': None
            }

        # Sort by severity (critical first) before batching
        sorted_warnings = sorted(
            warnings,
            key=lambda w: (
                0 if w.get('severity') == 'critical' else
                1 if w.get('severity') == 'high' else
                2 if w.get('severity') == 'medium' else 3
            )
        )

        # Split into batches
        batches = [
            sorted_warnings[i:i + self.batch_size]
            for i in range(0, len(sorted_warnings), self.batch_size)
        ]

        total_uploaded = 0
        total_failed = 0

        for batch in batches:
            result = await self._upload_single_batch(batch)

            if result['success']:
                total_uploaded += len(batch)
                # Count critical warnings
                critical_count = sum(
                    1 for w in batch if w.get('severity') == 'critical'
                )
                self._stats['critical_warnings_uploaded'] += critical_count
            else:
                total_failed += len(batch)

        self._stats['total_uploads'] += len(batches)

        return {
            'success': total_failed == 0,
            'uploaded_count': total_uploaded,
            'failed_count': total_failed,
            'error': None if total_failed == 0 else f"{total_failed} warnings failed to upload"
        }

    async def _upload_single_batch(
        self,
        batch: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Upload single batch with retry logic"""
        url = f"{self.cloud_endpoint}/api/warning-events"

        # Prepare payload
        payload = {
            'edge_device_id': self.edge_device_id,
            'project_id': self.project_id,
            'warnings': batch
        }

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        timeout_config = aiohttp.ClientTimeout(total=self.timeout)

        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession(timeout=timeout_config) as session:
                    async with session.post(url, json=payload, headers=headers) as response:
                        if response.status == 201 or response.status == 200:
                            # Success
                            response_data = await response.json()
                            self._stats['successful_uploads'] += 1
                            self._stats['total_warnings_uploaded'] += len(batch)

                            # Log with severity context
                            critical_count = sum(
                                1 for w in batch if w.get('severity') == 'critical'
                            )
                            logger.info(
                                f"Uploaded {len(batch)} warnings "
                                f"({critical_count} critical) "
                                f"(attempt {attempt + 1}/{self.max_retries})"
                            )

                            return {
                                'success': True,
                                'response': response_data
                            }

                        elif response.status == 400:
                            # Bad request - don't retry
                            error_text = await response.text()
                            logger.error(f"Warning upload rejected: {error_text}")
                            self._stats['failed_uploads'] += 1

                            return {
                                'success': False,
                                'error': f"Bad request: {error_text}"
                            }

                        elif response.status == 401 or response.status == 403:
                            # Authentication failed - don't retry
                            logger.error("Authentication failed - check API key")
                            self._stats['failed_uploads'] += 1

                            return {
                                'success': False,
                                'error': "Authentication failed"
                            }

                        else:
                            # Server error - retry with shorter backoff for warnings
                            error_text = await response.text()
                            logger.warning(
                                f"Warning upload failed with HTTP {response.status}: {error_text} "
                                f"(attempt {attempt + 1}/{self.max_retries})"
                            )

                            if attempt < self.max_retries - 1:
                                # Shorter backoff for warnings (1.5^attempt vs 2^attempt)
                                await asyncio.sleep(1.5 ** attempt)
                            else:
                                self._stats['failed_uploads'] += 1
                                return {
                                    'success': False,
                                    'error': f"HTTP {response.status}: {error_text}"
                                }

            except aiohttp.ClientError as e:
                logger.warning(
                    f"Warning upload connection error: {e} "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1.5 ** attempt)
                else:
                    self._stats['failed_uploads'] += 1
                    return {
                        'success': False,
                        'error': f"Connection error: {e}"
                    }

            except asyncio.TimeoutError:
                logger.warning(
                    f"Warning upload timeout "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1.5 ** attempt)
                else:
                    self._stats['failed_uploads'] += 1
                    return {
                        'success': False,
                        'error': "Timeout"
                    }

            except Exception as e:
                logger.error(f"Unexpected warning upload error: {e}", exc_info=True)
                self._stats['failed_uploads'] += 1

                return {
                    'success': False,
                    'error': f"Unexpected error: {e}"
                }

        # Should not reach here
        self._stats['failed_uploads'] += 1
        return {
            'success': False,
            'error': "Max retries reached"
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get upload statistics"""
        return dict(self._stats)

    def reset_statistics(self) -> None:
        """Reset statistics counters"""
        self._stats = {
            'total_uploads': 0,
            'successful_uploads': 0,
            'failed_uploads': 0,
            'total_warnings_uploaded': 0,
            'critical_warnings_uploaded': 0,
            'total_bytes_uploaded': 0
        }


# Example usage
async def example_usage():
    """Example of using WarningUploader"""

    uploader = WarningUploader(
        cloud_endpoint="http://localhost:8001",
        api_key="test-api-key",
        edge_device_id="edge-001",
        project_id=1,
        batch_size=20
    )

    # Prepare warning events
    warnings = [
        {
            'ring_number': 100,
            'timestamp': 1700002700,
            'warning_type': 'settlement_anomaly',
            'severity': 'critical',
            'message': 'Predicted settlement exceeds threshold: 15.2mm (threshold: 10mm)',
            'predicted_value': 15.2,
            'threshold': 10.0,
            'context': {
                'geological_zone': 'soft_clay',
                'consecutive_anomalies': 3,
                'trend': 'increasing'
            }
        },
        {
            'ring_number': 101,
            'timestamp': 1700005400,
            'warning_type': 'thrust_anomaly',
            'severity': 'high',
            'message': 'Thrust force deviation: -25% from expected',
            'predicted_value': 9000.0,
            'threshold': 12000.0,
            'context': {
                'geological_zone': 'mixed_ground',
                'deviation_percent': -25.0,
                'trend': 'decreasing'
            }
        },
        {
            'ring_number': 102,
            'timestamp': 1700008100,
            'warning_type': 'data_quality',
            'severity': 'medium',
            'message': 'Missing sensor data: pressure_sensor_3',
            'context': {
                'missing_sensors': ['pressure_sensor_3'],
                'data_completeness': 0.92
            }
        }
    ]

    # Upload
    result = await uploader.upload_batch(warnings)

    print(f"\nUpload result:")
    print(f"  Success: {result['success']}")
    print(f"  Uploaded: {result['uploaded_count']}")
    print(f"  Failed: {result['failed_count']}")

    # Statistics
    stats = uploader.get_statistics()
    print(f"\nStatistics:")
    print(f"  Total uploads: {stats['total_uploads']}")
    print(f"  Successful: {stats['successful_uploads']}")
    print(f"  Failed: {stats['failed_uploads']}")
    print(f"  Total warnings uploaded: {stats['total_warnings_uploaded']}")
    print(f"  Critical warnings: {stats['critical_warnings_uploaded']}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(example_usage())
