"""
T061: Background Task Scheduler
Schedules and executes periodic tasks for edge services
- Ring data alignment
- Data quality checks
- Database maintenance
- Cloud synchronization triggers
"""
import asyncio
import logging
from typing import Dict, Any, Callable, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
import traceback

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    """Represents a scheduled task"""
    name: str
    func: Callable
    interval_seconds: float
    enabled: bool = True
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    run_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None


class TaskScheduler:
    """
    Background task scheduler with interval-based execution.

    Features:
    - Interval-based task scheduling
    - Async task execution
    - Error handling and retry
    - Task statistics
    - Enable/disable tasks dynamically
    """

    def __init__(self):
        """Initialize task scheduler"""
        self.tasks: Dict[str, ScheduledTask] = {}
        self.running = False
        self.scheduler_task = None

    def register_task(
        self,
        name: str,
        func: Callable,
        interval_seconds: float,
        enabled: bool = True
    ) -> None:
        """
        Register a periodic task.

        Args:
            name: Task identifier
            func: Async function to execute
            interval_seconds: Execution interval in seconds
            enabled: Whether task is enabled
        """
        now = datetime.utcnow().timestamp()

        task = ScheduledTask(
            name=name,
            func=func,
            interval_seconds=interval_seconds,
            enabled=enabled,
            next_run=now + interval_seconds
        )

        self.tasks[name] = task
        logger.info(
            f"Registered task '{name}': "
            f"interval={interval_seconds}s, enabled={enabled}"
        )

    def enable_task(self, name: str) -> bool:
        """Enable a task"""
        if name in self.tasks:
            self.tasks[name].enabled = True
            logger.info(f"Enabled task '{name}'")
            return True
        return False

    def disable_task(self, name: str) -> bool:
        """Disable a task"""
        if name in self.tasks:
            self.tasks[name].enabled = False
            logger.info(f"Disabled task '{name}'")
            return True
        return False

    def update_interval(self, name: str, interval_seconds: float) -> bool:
        """Update task interval"""
        if name in self.tasks:
            self.tasks[name].interval_seconds = interval_seconds
            logger.info(f"Updated task '{name}' interval to {interval_seconds}s")
            return True
        return False

    async def start(self) -> None:
        """Start the task scheduler"""
        if self.running:
            logger.warning("Task scheduler already running")
            return

        self.running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Task scheduler started")

    async def stop(self) -> None:
        """Stop the task scheduler"""
        if not self.running:
            return

        self.running = False

        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass

        logger.info("Task scheduler stopped")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop"""
        logger.info("Scheduler loop started")

        while self.running:
            try:
                now = datetime.utcnow().timestamp()

                # Check all tasks
                for task in self.tasks.values():
                    if not task.enabled:
                        continue

                    # Check if task should run
                    if task.next_run is None or now >= task.next_run:
                        # Execute task
                        asyncio.create_task(self._execute_task(task))

                        # Schedule next run
                        task.next_run = now + task.interval_seconds

                # Sleep briefly before next check
                await asyncio.sleep(1.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)
                await asyncio.sleep(5.0)  # Back off on error

        logger.info("Scheduler loop stopped")

    async def _execute_task(self, task: ScheduledTask) -> None:
        """
        Execute a scheduled task.

        Args:
            task: Task to execute
        """
        start_time = datetime.utcnow().timestamp()

        try:
            logger.debug(f"Executing task '{task.name}'")

            # Execute task function
            if asyncio.iscoroutinefunction(task.func):
                await task.func()
            else:
                # Run sync function in executor
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, task.func)

            # Update statistics
            task.last_run = start_time
            task.run_count += 1

            duration = datetime.utcnow().timestamp() - start_time
            logger.info(
                f"Task '{task.name}' completed in {duration:.2f}s "
                f"(run #{task.run_count})"
            )

        except Exception as e:
            task.error_count += 1
            task.last_error = str(e)

            logger.error(
                f"Error executing task '{task.name}': {e}",
                exc_info=True,
                extra={
                    'task_name': task.name,
                    'error_count': task.error_count,
                    'traceback': traceback.format_exc()
                }
            )

    def get_task_status(self, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get status of tasks.

        Args:
            name: Optional task name to get specific task status

        Returns:
            Dictionary with task status information
        """
        if name:
            if name not in self.tasks:
                return {"error": f"Task '{name}' not found"}

            task = self.tasks[name]
            return self._format_task_status(task)

        # Return status of all tasks
        return {
            'scheduler_running': self.running,
            'total_tasks': len(self.tasks),
            'enabled_tasks': sum(1 for t in self.tasks.values() if t.enabled),
            'tasks': {
                name: self._format_task_status(task)
                for name, task in self.tasks.items()
            }
        }

    def _format_task_status(self, task: ScheduledTask) -> Dict[str, Any]:
        """Format task status for display"""
        now = datetime.utcnow().timestamp()

        return {
            'name': task.name,
            'enabled': task.enabled,
            'interval_seconds': task.interval_seconds,
            'run_count': task.run_count,
            'error_count': task.error_count,
            'last_run': task.last_run,
            'last_run_ago_seconds': (
                round(now - task.last_run, 1)
                if task.last_run else None
            ),
            'next_run': task.next_run,
            'next_run_in_seconds': (
                round(task.next_run - now, 1)
                if task.next_run else None
            ),
            'last_error': task.last_error
        }


# Example background tasks
async def ring_alignment_task(db_manager, config_path: str = "edge/config/alignment.yaml"):
    """
    Periodic task to align ring data.

    Detects new rings and calculates aggregated features.
    """
    logger.info("Running ring alignment task")

    try:
        from edge.services.aligner.ring_detector import RingBoundaryDetector
        from edge.services.aligner.plc_aggregator import PLCAggregator
        from edge.services.aligner.attitude_aggregator import AttitudeAggregator
        from edge.services.aligner.derived_indicators import DerivedIndicatorCalculator
        from edge.services.aligner.settlement_associator import SettlementAssociator
        from edge.services.aligner.ring_summary_writer import RingSummaryWriter

        # Get last processed ring
        with db_manager.get_connection() as conn:
            cursor = conn.execute(
                "SELECT MAX(ring_number) as last_ring FROM ring_summary"
            )
            result = cursor.fetchone()
            last_ring = result['last_ring'] if result['last_ring'] else 0

        # Check for next ring
        next_ring = last_ring + 1

        # Initialize components
        detector = RingBoundaryDetector(config_path)
        plc_agg = PLCAggregator()
        attitude_agg = AttitudeAggregator()
        derived_calc = DerivedIndicatorCalculator()
        settlement_assoc = SettlementAssociator()
        writer = RingSummaryWriter()

        # Get last ring end time
        if last_ring > 0:
            with db_manager.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT end_time FROM ring_summary WHERE ring_number = ?",
                    (last_ring,)
                )
                result = cursor.fetchone()
                last_end_time = result['end_time'] if result else None
        else:
            last_end_time = None

        # Try to detect next ring
        if last_end_time:
            try:
                start_time, end_time = detector.detect_ring_boundary(
                    db_manager, next_ring, last_ring_end_time=last_end_time
                )

                # Aggregate data
                plc_features = plc_agg.aggregate_ring_data(
                    db_manager, next_ring, start_time, end_time
                )

                attitude_features = attitude_agg.aggregate_ring_data(
                    db_manager, next_ring, start_time, end_time
                )

                duration_min = (end_time - start_time) / 60
                derived_indicators = derived_calc.calculate_all_indicators(
                    plc_features, duration_min
                )

                settlement_features = settlement_assoc.associate_settlement_data(
                    db_manager, next_ring, end_time
                )

                # Write to database
                writer.write_ring_summary(
                    db_manager, next_ring, start_time, end_time,
                    plc_features, attitude_features,
                    derived_indicators, settlement_features
                )

                logger.info(f"Ring {next_ring} aligned and persisted")

            except Exception as e:
                logger.warning(f"Could not detect/align ring {next_ring}: {e}")

    except Exception as e:
        logger.error(f"Error in ring alignment task: {e}", exc_info=True)


async def data_cleanup_task(db_manager, retention_days: int = 30):
    """
    Periodic task to clean up old raw data.

    Removes raw logs older than retention period after aggregation.
    """
    logger.info("Running data cleanup task")

    try:
        cutoff_time = datetime.utcnow().timestamp() - (retention_days * 86400)

        with db_manager.transaction() as conn:
            # Delete old PLC logs (keep if not yet aggregated)
            conn.execute(
                """
                DELETE FROM plc_logs
                WHERE timestamp < ?
                  AND ring_number IN (
                      SELECT ring_number FROM ring_summary
                      WHERE data_completeness_flag = 'complete'
                  )
                """,
                (cutoff_time,)
            )

            deleted = conn.total_changes
            logger.info(f"Cleaned up {deleted} old PLC log records")

    except Exception as e:
        logger.error(f"Error in data cleanup task: {e}", exc_info=True)


# Example usage
if __name__ == "__main__":
    async def example_task():
        """Example periodic task"""
        logger.info("Example task executed!")

    async def main():
        """Example usage of task scheduler"""
        scheduler = TaskScheduler()

        # Register tasks
        scheduler.register_task(
            name="example_task",
            func=example_task,
            interval_seconds=5.0
        )

        # Start scheduler
        await scheduler.start()

        # Run for 30 seconds
        await asyncio.sleep(30)

        # Get status
        status = scheduler.get_task_status()
        print(f"\nScheduler status: {status}")

        # Stop scheduler
        await scheduler.stop()

    asyncio.run(main())
