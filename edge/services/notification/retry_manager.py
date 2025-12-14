"""
Notification Retry Manager
Handles retry logic for failed notification deliveries
Implements Feature 003 - Real-Time Warning System (FR-014)
"""
import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import time

from edge.models.warning_event import WarningEvent
from edge.services.notification.notification_router import NotificationRouter

logger = logging.getLogger(__name__)


@dataclass
class RetryTask:
    """Represents a notification retry task"""
    warning: WarningEvent
    channel: str  # "email" or "sms"
    recipients: List[str]
    attempt: int = 0
    max_attempts: int = 3
    next_retry_time: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    last_error: Optional[str] = None

    def should_retry(self) -> bool:
        """Check if task should be retried"""
        return (
            self.attempt < self.max_attempts
            and time.time() >= self.next_retry_time
        )

    def is_expired(self, max_age_hours: int = 24) -> bool:
        """Check if task has expired"""
        age_hours = (time.time() - self.created_at) / 3600
        return age_hours > max_age_hours

    def calculate_next_retry(self, base_delay: int = 60):
        """
        Calculate next retry time using exponential backoff

        Args:
            base_delay: Base delay in seconds (default: 60s)

        Backoff schedule:
        - Attempt 1: 60s
        - Attempt 2: 300s (5 min)
        - Attempt 3: 900s (15 min)
        """
        delays = [60, 300, 900]  # 1 min, 5 min, 15 min
        delay = delays[min(self.attempt, len(delays) - 1)]
        self.next_retry_time = time.time() + delay


class NotificationRetryManager:
    """
    Manage retry logic for failed notification deliveries

    Features:
    - Exponential backoff (1min → 5min → 15min)
    - Maximum 3 retry attempts
    - Automatic expiration after 24 hours
    - Periodic cleanup of expired tasks
    - Statistics tracking
    """

    def __init__(
        self,
        router: NotificationRouter,
        max_attempts: int = 3,
        max_task_age_hours: int = 24,
        cleanup_interval_seconds: int = 3600
    ):
        """
        Initialize retry manager

        Args:
            router: NotificationRouter instance
            max_attempts: Maximum retry attempts per task
            max_task_age_hours: Maximum task age before expiration
            cleanup_interval_seconds: Interval for cleanup task (default: 1 hour)
        """
        self.router = router
        self.max_attempts = max_attempts
        self.max_task_age_hours = max_task_age_hours
        self.cleanup_interval = cleanup_interval_seconds

        # Retry queue: warning_id → {channel → RetryTask}
        self.retry_queue: Dict[str, Dict[str, RetryTask]] = {}

        # Statistics
        self.stats = {
            "total_queued": 0,
            "total_retried": 0,
            "total_succeeded": 0,
            "total_failed": 0,
            "total_expired": 0,
        }

        # Background task for periodic retry and cleanup
        self._retry_task: Optional[asyncio.Task] = None
        self._running = False

        logger.info(
            f"RetryManager initialized: max_attempts={max_attempts}, "
            f"max_age={max_task_age_hours}h"
        )

    async def start(self):
        """Start background retry and cleanup task"""
        if self._running:
            logger.warning("RetryManager already running")
            return

        self._running = True
        self._retry_task = asyncio.create_task(self._retry_loop())
        logger.info("RetryManager started")

    async def stop(self):
        """Stop background retry task"""
        self._running = False
        if self._retry_task:
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass
        logger.info("RetryManager stopped")

    def queue_retry(
        self,
        warning: WarningEvent,
        channel: str,
        recipients: List[str],
        error: Optional[str] = None
    ):
        """
        Queue a notification for retry

        Args:
            warning: Warning event that failed to send
            channel: Failed channel ("email" or "sms")
            recipients: List of recipients
            error: Optional error message
        """
        if channel not in ["email", "sms"]:
            logger.error(f"Invalid retry channel: {channel}")
            return

        # Create retry task
        task = RetryTask(
            warning=warning,
            channel=channel,
            recipients=recipients,
            max_attempts=self.max_attempts,
            last_error=error
        )
        task.calculate_next_retry()

        # Add to queue
        warning_id = warning.warning_id
        if warning_id not in self.retry_queue:
            self.retry_queue[warning_id] = {}

        self.retry_queue[warning_id][channel] = task
        self.stats["total_queued"] += 1

        logger.info(
            f"Queued retry for warning {warning_id} on {channel} "
            f"(next attempt in {task.next_retry_time - time.time():.0f}s)"
        )

    async def _retry_loop(self):
        """Background loop for retrying failed notifications"""
        while self._running:
            try:
                # Process retry queue
                await self._process_retry_queue()

                # Cleanup expired tasks
                self._cleanup_expired_tasks()

                # Wait before next iteration (check every 30s)
                await asyncio.sleep(30)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in retry loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Back off on error

    async def _process_retry_queue(self):
        """Process all retry tasks that are due"""
        tasks_to_remove = []

        for warning_id, channel_tasks in self.retry_queue.items():
            for channel, task in list(channel_tasks.items()):
                # Check if task should be retried
                if not task.should_retry():
                    continue

                # Attempt retry
                logger.info(
                    f"Retrying {channel} notification for warning {warning_id} "
                    f"(attempt {task.attempt + 1}/{task.max_attempts})"
                )

                success = await self._retry_notification(task)
                task.attempt += 1
                self.stats["total_retried"] += 1

                if success:
                    # Retry succeeded - remove from queue
                    self.stats["total_succeeded"] += 1
                    channel_tasks.pop(channel, None)
                    logger.info(
                        f"Retry succeeded for warning {warning_id} on {channel} "
                        f"(attempt {task.attempt})"
                    )
                else:
                    # Retry failed
                    if task.attempt >= task.max_attempts:
                        # Max attempts reached - give up
                        self.stats["total_failed"] += 1
                        channel_tasks.pop(channel, None)
                        logger.error(
                            f"Retry failed permanently for warning {warning_id} on {channel} "
                            f"(max attempts reached)"
                        )
                    else:
                        # Schedule next retry
                        task.calculate_next_retry()
                        logger.warning(
                            f"Retry failed for warning {warning_id} on {channel} "
                            f"(attempt {task.attempt}/{task.max_attempts}), "
                            f"next attempt in {task.next_retry_time - time.time():.0f}s"
                        )

            # Remove warning from queue if all channels completed
            if not channel_tasks:
                tasks_to_remove.append(warning_id)

        # Clean up completed warnings
        for warning_id in tasks_to_remove:
            self.retry_queue.pop(warning_id, None)

    async def _retry_notification(self, task: RetryTask) -> bool:
        """
        Attempt to resend notification

        Args:
            task: Retry task to process

        Returns:
            True if retry succeeded, False otherwise
        """
        try:
            if task.channel == "email":
                if not self.router.email:
                    logger.error("Email notifier not available")
                    return False

                success = await self.router.email.send_warning_async(
                    task.warning,
                    task.recipients
                )
                return success

            elif task.channel == "sms":
                if not self.router.sms:
                    logger.error("SMS client not available")
                    return False

                sent_count = await self.router.sms.send_warning_async(
                    task.warning,
                    task.recipients
                )
                return sent_count > 0

            else:
                logger.error(f"Unknown channel: {task.channel}")
                return False

        except Exception as e:
            task.last_error = str(e)
            logger.error(
                f"Retry attempt failed for {task.channel}: {e}",
                exc_info=True
            )
            return False

    def _cleanup_expired_tasks(self):
        """Remove expired tasks from retry queue"""
        expired_count = 0
        warnings_to_remove = []

        for warning_id, channel_tasks in self.retry_queue.items():
            channels_to_remove = []

            for channel, task in channel_tasks.items():
                if task.is_expired(self.max_task_age_hours):
                    channels_to_remove.append(channel)
                    expired_count += 1
                    self.stats["total_expired"] += 1
                    logger.warning(
                        f"Retry task expired for warning {warning_id} on {channel} "
                        f"(age: {(time.time() - task.created_at) / 3600:.1f}h)"
                    )

            # Remove expired channels
            for channel in channels_to_remove:
                channel_tasks.pop(channel, None)

            # Mark warning for removal if all channels expired
            if not channel_tasks:
                warnings_to_remove.append(warning_id)

        # Remove warnings with no remaining tasks
        for warning_id in warnings_to_remove:
            self.retry_queue.pop(warning_id, None)

        if expired_count > 0:
            logger.info(f"Cleaned up {expired_count} expired retry tasks")

    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get current retry queue status

        Returns:
            Dict with queue statistics and pending tasks
        """
        total_pending = sum(len(tasks) for tasks in self.retry_queue.values())

        pending_by_channel = {"email": 0, "sms": 0}
        for channel_tasks in self.retry_queue.values():
            for channel in channel_tasks.keys():
                if channel in pending_by_channel:
                    pending_by_channel[channel] += 1

        return {
            "pending_warnings": len(self.retry_queue),
            "pending_tasks": total_pending,
            "pending_by_channel": pending_by_channel,
            "statistics": self.stats.copy()
        }

    def get_statistics(self) -> Dict[str, int]:
        """Get retry statistics"""
        return self.stats.copy()

    def reset_statistics(self):
        """Reset statistics counters"""
        self.stats = {
            "total_queued": 0,
            "total_retried": 0,
            "total_succeeded": 0,
            "total_failed": 0,
            "total_expired": 0,
        }
        logger.info("Retry statistics reset")

    def clear_queue(self):
        """Clear all pending retry tasks"""
        count = sum(len(tasks) for tasks in self.retry_queue.values())
        self.retry_queue.clear()
        logger.warning(f"Cleared {count} pending retry tasks")
