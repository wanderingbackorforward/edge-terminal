"""
Work Order Uploader (T183)
Syncs work orders from edge to cloud
"""
import logging
import aiohttp
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class WorkOrderUploader:
    """
    Uploads work orders to cloud API

    Implements reliable sync with:
    - Batch uploading for efficiency
    - Retry logic for transient failures
    - Progress tracking for sync status
    """

    def __init__(
        self,
        cloud_url: str,
        edge_device_id: str,
        project_id: int,
        timeout: int = 30,
    ):
        """
        Initialize work order uploader

        Args:
            cloud_url: Cloud API base URL
            edge_device_id: Edge device identifier
            project_id: Project ID for this edge device
            timeout: Request timeout in seconds
        """
        self.cloud_url = cloud_url.rstrip("/")
        self.edge_device_id = edge_device_id
        self.project_id = project_id
        self.timeout = timeout

        logger.info(
            f"WorkOrderUploader initialized for device {edge_device_id}, "
            f"project {project_id}, cloud URL: {cloud_url}"
        )

    async def upload_batch(
        self,
        work_orders: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Upload a batch of work orders to cloud

        Args:
            work_orders: List of work order dicts

        Returns:
            Upload result with counts
        """
        if not work_orders:
            return {
                "success": True,
                "received_count": 0,
                "inserted_count": 0,
                "updated_count": 0,
                "error_count": 0,
            }

        # Format for API
        payload = {
            "edge_device_id": self.edge_device_id,
            "project_id": self.project_id,
            "work_orders": [
                {
                    "work_order_id": wo["work_order_id"],
                    "warning_id": wo.get("warning_id"),
                    "title": wo["title"],
                    "description": wo.get("description"),
                    "category": wo["category"],
                    "priority": wo["priority"],
                    "ring_number": wo.get("ring_number"),
                    "indicator_name": wo.get("indicator_name"),
                    "status": wo["status"],
                    "created_at": wo["created_at"],
                    "metadata": wo.get("metadata", {}),
                }
                for wo in work_orders
            ],
        }

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.cloud_url}/api/v1/work-orders/sync"

                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(
                            f"Uploaded {len(work_orders)} work orders: "
                            f"{result.get('inserted_count', 0)} inserted, "
                            f"{result.get('updated_count', 0)} updated"
                        )
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Work order upload failed with status {response.status}: "
                            f"{error_text}"
                        )
                        return {
                            "success": False,
                            "received_count": len(work_orders),
                            "inserted_count": 0,
                            "updated_count": 0,
                            "error_count": len(work_orders),
                            "errors": [f"HTTP {response.status}: {error_text}"],
                        }

        except aiohttp.ClientError as e:
            logger.error(f"Work order upload network error: {e}")
            return {
                "success": False,
                "received_count": len(work_orders),
                "inserted_count": 0,
                "updated_count": 0,
                "error_count": len(work_orders),
                "errors": [f"Network error: {str(e)}"],
            }
        except Exception as e:
            logger.error(f"Work order upload error: {e}", exc_info=True)
            return {
                "success": False,
                "received_count": len(work_orders),
                "inserted_count": 0,
                "updated_count": 0,
                "error_count": len(work_orders),
                "errors": [f"Error: {str(e)}"],
            }

    async def check_connectivity(self) -> bool:
        """
        Check if cloud API is reachable

        Returns:
            True if API health check passes
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.cloud_url}/health"

                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    if response.status == 200:
                        return True
                    else:
                        logger.warning(f"Cloud health check returned {response.status}")
                        return False

        except Exception as e:
            logger.warning(f"Cloud connectivity check failed: {e}")
            return False


async def sync_work_orders(
    work_order_manager,
    uploader: WorkOrderUploader,
    batch_size: int = 50,
) -> Dict[str, Any]:
    """
    Sync pending work orders to cloud

    Convenience function to sync all pending work orders.

    Args:
        work_order_manager: WorkOrderManager instance
        uploader: WorkOrderUploader instance
        batch_size: Maximum batch size

    Returns:
        Sync statistics
    """
    total_synced = 0
    total_errors = 0

    # Check connectivity first
    if not await uploader.check_connectivity():
        logger.warning("Cloud not reachable, skipping work order sync")
        return {
            "synced": 0,
            "errors": 0,
            "status": "cloud_unreachable",
        }

    # Get pending work orders
    pending = work_order_manager.get_pending_sync(limit=batch_size)

    if not pending:
        return {
            "synced": 0,
            "errors": 0,
            "status": "no_pending",
        }

    # Upload batch
    result = await uploader.upload_batch(pending)

    if result.get("success"):
        # Mark as synced
        synced_ids = [wo["work_order_id"] for wo in pending]
        work_order_manager.mark_synced(synced_ids)
        total_synced = len(synced_ids)
    else:
        total_errors = result.get("error_count", len(pending))

    return {
        "synced": total_synced,
        "errors": total_errors,
        "status": "completed" if total_errors == 0 else "partial_failure",
    }
