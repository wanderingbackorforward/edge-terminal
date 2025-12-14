"""
Ring Summary Uploader
Uploads ring summary data to cloud API
Handles batch uploads and error recovery
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
import aiohttp

logger = logging.getLogger(__name__)


class RingUploader:
    """
    Uploads ring summaries to cloud API.
    
    Features:
    - Batch uploads for efficiency
    - Automatic retry with exponential backoff
    - Authentication with API key
    - Upload progress tracking
    """

    def __init__(
        self,
        cloud_endpoint: str,
        api_key: str,
        edge_device_id: str,
        project_id: int,
        batch_size: int = 50,
        timeout: float = 30.0,
        max_retries: int = 3
    ):
        """
        Initialize ring uploader.

        Args:
            cloud_endpoint: Base URL of cloud API
            api_key: API key for authentication
            edge_device_id: Unique ID of this edge device
            project_id: Project ID for this deployment
            batch_size: Maximum rings per upload batch
            timeout: HTTP request timeout
            max_retries: Maximum retry attempts
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
            'total_rings_uploaded': 0,
            'total_bytes_uploaded': 0
        }

    async def upload_batch(
        self,
        ring_summaries: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Upload batch of ring summaries to cloud.

        Args:
            ring_summaries: List of ring summary dictionaries

        Returns:
            Dict with upload result:
            {
                'success': bool,
                'uploaded_count': int,
                'failed_count': int,
                'error': Optional[str]
            }
        """
        if not ring_summaries:
            return {
                'success': True,
                'uploaded_count': 0,
                'failed_count': 0,
                'error': None
            }

        # Split into batches if needed
        batches = [
            ring_summaries[i:i + self.batch_size]
            for i in range(0, len(ring_summaries), self.batch_size)
        ]

        total_uploaded = 0
        total_failed = 0

        for batch in batches:
            result = await self._upload_single_batch(batch)

            if result['success']:
                total_uploaded += len(batch)
            else:
                total_failed += len(batch)

        self._stats['total_uploads'] += len(batches)

        return {
            'success': total_failed == 0,
            'uploaded_count': total_uploaded,
            'failed_count': total_failed,
            'error': None if total_failed == 0 else f"{total_failed} rings failed to upload"
        }

    async def _upload_single_batch(
        self,
        batch: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Upload single batch with retry logic"""
        url = f"{self.cloud_endpoint}/api/ring-summaries"

        # Prepare payload
        payload = {
            'edge_device_id': self.edge_device_id,
            'project_id': self.project_id,
            'rings': batch
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
                            self._stats['total_rings_uploaded'] += len(batch)

                            logger.info(
                                f"Uploaded {len(batch)} rings "
                                f"(attempt {attempt + 1}/{self.max_retries})"
                            )

                            return {
                                'success': True,
                                'response': response_data
                            }

                        elif response.status == 400:
                            # Bad request - don't retry
                            error_text = await response.text()
                            logger.error(f"Upload rejected by server: {error_text}")
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
                            # Server error - retry
                            error_text = await response.text()
                            logger.warning(
                                f"Upload failed with HTTP {response.status}: {error_text} "
                                f"(attempt {attempt + 1}/{self.max_retries})"
                            )

                            if attempt < self.max_retries - 1:
                                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                            else:
                                self._stats['failed_uploads'] += 1
                                return {
                                    'success': False,
                                    'error': f"HTTP {response.status}: {error_text}"
                                }

            except aiohttp.ClientError as e:
                logger.warning(
                    f"Upload connection error: {e} "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    self._stats['failed_uploads'] += 1
                    return {
                        'success': False,
                        'error': f"Connection error: {e}"
                    }

            except asyncio.TimeoutError:
                logger.warning(
                    f"Upload timeout "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    self._stats['failed_uploads'] += 1
                    return {
                        'success': False,
                        'error': "Timeout"
                    }

            except Exception as e:
                logger.error(f"Unexpected upload error: {e}", exc_info=True)
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
            'total_rings_uploaded': 0,
            'total_bytes_uploaded': 0
        }


# Example usage
async def example_usage():
    """Example of using RingUploader"""

    uploader = RingUploader(
        cloud_endpoint="http://localhost:8001",
        api_key="test-api-key",
        edge_device_id="edge-001",
        project_id=1,
        batch_size=50
    )

    # Prepare ring summaries
    rings = [
        {
            'ring_number': 100,
            'start_time': 1700000000,
            'end_time': 1700002700,
            'mean_thrust': 12000.0,
            'mean_torque': 900.0,
            'data_completeness_flag': 'complete'
        },
        {
            'ring_number': 101,
            'start_time': 1700002700,
            'end_time': 1700005400,
            'mean_thrust': 12500.0,
            'mean_torque': 920.0,
            'data_completeness_flag': 'complete'
        }
    ]

    # Upload
    result = await uploader.upload_batch(rings)

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
    print(f"  Total rings uploaded: {stats['total_rings_uploaded']}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(example_usage())
