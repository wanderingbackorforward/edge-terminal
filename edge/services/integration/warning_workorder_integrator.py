"""
Warning to Work Order Integrator (T203)
Integrates warning engine with work order auto-creator
Automatically generates work orders when ALARM level warnings are triggered
"""
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from edge.models.warning_event import WarningEvent
from edge.services.workorder.work_order_manager import WorkOrderManager

logger = logging.getLogger(__name__)


class WarningWorkOrderIntegrator:
    """
    Integrates Warning Engine output with Work Order auto-creation

    Responsibilities:
    - Monitors new warnings from warning engine
    - Triggers work order creation for ALARM level warnings
    - Optionally creates work orders for repeated WARNING level warnings
    - Prevents duplicate work orders for same warning

    Implements FR-034 to FR-040 (closed-loop management)
    """

    def __init__(
        self,
        db_session: Session,
        auto_create_on_alarm: bool = True,
        auto_create_on_repeated_warning: bool = True,
        warning_repeat_threshold: int = 3,
    ):
        """
        Initialize integrator

        Args:
            db_session: Database session
            auto_create_on_alarm: Auto-create work order on ALARM level
            auto_create_on_repeated_warning: Auto-create on repeated WARNING
            warning_repeat_threshold: Number of warnings before auto-create
        """
        self.db = db_session
        self.work_order_manager = WorkOrderManager(db_session)

        self.auto_create_on_alarm = auto_create_on_alarm
        self.auto_create_on_repeated_warning = auto_create_on_repeated_warning
        self.warning_repeat_threshold = warning_repeat_threshold

        # Track warning counts per indicator for repeat detection
        self._warning_counts: Dict[str, int] = {}
        # Track processed warning IDs to prevent duplicates
        self._processed_warnings: set = set()

        logger.info(
            f"WarningWorkOrderIntegrator initialized: "
            f"alarm_auto={auto_create_on_alarm}, "
            f"repeated_auto={auto_create_on_repeated_warning}, "
            f"threshold={warning_repeat_threshold}"
        )

    def process_warnings(self, warnings: List[WarningEvent]) -> List[Dict[str, Any]]:
        """
        Process warnings and create work orders as needed

        This is the main entry point called after warning engine generates warnings.

        Args:
            warnings: List of WarningEvent from warning engine

        Returns:
            List of created work orders
        """
        created_work_orders = []

        for warning in warnings:
            work_order = self._process_single_warning(warning)
            if work_order:
                created_work_orders.append(work_order)

        if created_work_orders:
            logger.info(
                f"Created {len(created_work_orders)} work orders "
                f"from {len(warnings)} warnings"
            )

        return created_work_orders

    def _process_single_warning(
        self, warning: WarningEvent
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single warning for potential work order creation

        Args:
            warning: WarningEvent to process

        Returns:
            Created work order dict, or None
        """
        # Skip if already processed
        if warning.warning_id in self._processed_warnings:
            return None

        # Mark as processed
        self._processed_warnings.add(warning.warning_id)

        # Check if should create work order
        should_create = False
        reason = ""

        # Rule 1: ALARM level always creates work order
        if self.auto_create_on_alarm and warning.warning_level == "ALARM":
            should_create = True
            reason = "ALARM level warning"

        # Rule 2: Repeated WARNING level warnings
        elif self.auto_create_on_repeated_warning and warning.warning_level == "WARNING":
            indicator_key = f"{warning.indicator_name}_{warning.ring_number}"
            self._warning_counts[indicator_key] = (
                self._warning_counts.get(indicator_key, 0) + 1
            )

            if self._warning_counts[indicator_key] >= self.warning_repeat_threshold:
                should_create = True
                reason = f"Repeated WARNING ({self._warning_counts[indicator_key]}x)"
                # Reset count after creating work order
                self._warning_counts[indicator_key] = 0

        # Rule 3: Combined warnings (multiple simultaneous violations)
        elif warning.warning_type == "combined":
            should_create = True
            reason = "Combined warning (multiple violations)"

        if should_create:
            work_order = self.work_order_manager.process_warning(warning)
            if work_order:
                logger.info(
                    f"Auto-created work order {work_order['work_order_id']} "
                    f"for warning {warning.warning_id} ({reason})"
                )
                return work_order

        return None

    def clear_tracking(self):
        """Clear internal tracking state"""
        self._warning_counts.clear()
        self._processed_warnings.clear()
        self.work_order_manager.generator.clear_tracking()
        logger.debug("Cleared integrator tracking state")

    def get_pending_work_orders(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get pending work orders for dashboard display"""
        return self.work_order_manager.list_work_orders(
            status="pending", limit=limit
        )

    def get_work_order_stats(self) -> Dict[str, int]:
        """Get work order statistics"""
        return self.work_order_manager.get_stats()


def integrate_warning_engine_with_workorders(
    warning_engine,
    db_session: Session,
    **integrator_kwargs
) -> WarningWorkOrderIntegrator:
    """
    Factory function to create and attach integrator to warning engine

    This modifies the warning engine to automatically trigger work order
    creation after warnings are generated.

    Args:
        warning_engine: WarningEngine instance
        db_session: Database session
        **integrator_kwargs: Additional integrator configuration

    Returns:
        WarningWorkOrderIntegrator instance
    """
    integrator = WarningWorkOrderIntegrator(db_session, **integrator_kwargs)

    # Store original evaluate_ring method
    original_evaluate_ring = warning_engine.evaluate_ring

    def wrapped_evaluate_ring(*args, **kwargs):
        """Wrapped evaluate_ring that also processes work orders"""
        warnings = original_evaluate_ring(*args, **kwargs)

        if warnings:
            # Process warnings for work order creation
            integrator.process_warnings(warnings)

        return warnings

    # Replace method with wrapped version
    warning_engine.evaluate_ring = wrapped_evaluate_ring

    logger.info("Warning engine integrated with work order auto-creator")

    return integrator
