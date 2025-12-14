"""
Work Order Generator (T181)
Automatically generates work orders from warnings based on configurable rules
"""
import logging
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session

from edge.models.warning_event import WarningEvent

logger = logging.getLogger(__name__)


class WorkOrderGenerator:
    """
    Generates work orders from warning events

    Implements automatic work order creation based on:
    - Warning level (ALARM always generates, WARNING configurable)
    - Indicator type (maps to work order category)
    - Threshold exceedance severity

    Features:
    - Configurable generation rules per indicator
    - Duplicate prevention (one work order per unique warning)
    - Priority mapping from warning severity
    - Verification requirements based on indicator type
    """

    # Default rules for work order generation
    DEFAULT_RULES = {
        # indicator_name -> generation config
        "cumulative_settlement": {
            "generate_on_warning": True,
            "generate_on_attention": False,
            "category": "settlement",
            "verification_required": True,
            "verification_ring_count": 10,
        },
        "settlement_rate": {
            "generate_on_warning": True,
            "generate_on_attention": False,
            "category": "settlement",
            "verification_required": True,
            "verification_ring_count": 5,
        },
        "chamber_pressure": {
            "generate_on_warning": True,
            "generate_on_attention": False,
            "category": "chamber_pressure",
            "verification_required": True,
            "verification_ring_count": 3,
        },
        "thrust_total": {
            "generate_on_warning": True,
            "generate_on_attention": False,
            "category": "torque",
            "verification_required": False,
        },
        "torque_cutterhead": {
            "generate_on_warning": True,
            "generate_on_attention": False,
            "category": "torque",
            "verification_required": False,
        },
        "horizontal_deviation": {
            "generate_on_warning": True,
            "generate_on_attention": False,
            "category": "alignment",
            "verification_required": True,
            "verification_ring_count": 5,
        },
        "vertical_deviation": {
            "generate_on_warning": True,
            "generate_on_attention": False,
            "category": "alignment",
            "verification_required": True,
            "verification_ring_count": 5,
        },
    }

    # Priority mapping from warning level
    PRIORITY_MAP = {
        "ALARM": "critical",
        "WARNING": "high",
        "ATTENTION": "medium",
    }

    def __init__(
        self,
        db_session: Session,
        rules: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        """
        Initialize work order generator

        Args:
            db_session: Database session for persistence
            rules: Custom generation rules (merges with defaults)
        """
        self.db = db_session
        self.rules = {**self.DEFAULT_RULES}
        if rules:
            self.rules.update(rules)

        # Track generated work orders to prevent duplicates
        self._generated_warning_ids: set = set()

        logger.info(f"WorkOrderGenerator initialized with {len(self.rules)} rules")

    def should_generate(self, warning: WarningEvent) -> bool:
        """
        Determine if a warning should generate a work order

        Args:
            warning: Warning event to evaluate

        Returns:
            True if work order should be generated
        """
        # Always generate for ALARM level
        if warning.warning_level == "ALARM":
            return True

        # Check indicator-specific rules
        indicator_name = warning.indicator_name
        rule = self.rules.get(indicator_name, {})

        if warning.warning_level == "WARNING":
            return rule.get("generate_on_warning", True)
        elif warning.warning_level == "ATTENTION":
            return rule.get("generate_on_attention", False)

        return False

    def generate_from_warning(
        self,
        warning: WarningEvent,
        force: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a work order from a warning event

        Args:
            warning: Source warning event
            force: Force generation even if rules don't match

        Returns:
            Work order dict if generated, None otherwise
        """
        # Check if already generated
        if warning.warning_id in self._generated_warning_ids:
            logger.debug(f"Work order already generated for warning {warning.warning_id}")
            return None

        # Check generation rules
        if not force and not self.should_generate(warning):
            logger.debug(
                f"Skipping work order generation for {warning.indicator_name} "
                f"{warning.warning_level} warning"
            )
            return None

        # Get rule config
        rule = self.rules.get(warning.indicator_name, {})

        # Generate work order
        work_order = {
            "work_order_id": str(uuid.uuid4()),
            "warning_id": warning.warning_id,
            "title": self._generate_title(warning),
            "description": self._generate_description(warning),
            "category": rule.get("category", "other"),
            "priority": self.PRIORITY_MAP.get(warning.warning_level, "medium"),
            "ring_number": warning.ring_number,
            "indicator_name": warning.indicator_name,
            "status": "pending",
            "verification_required": rule.get("verification_required", False),
            "verification_ring_count": rule.get("verification_ring_count", 5),
            "created_at": datetime.utcnow().timestamp(),
            "metadata": {
                "source": "auto_generated",
                "warning_level": warning.warning_level,
                "indicator_value": warning.indicator_value,
                "threshold_value": warning.threshold_value,
                "timestamp": warning.timestamp,
            },
        }

        # Track as generated
        self._generated_warning_ids.add(warning.warning_id)

        logger.info(
            f"Generated work order {work_order['work_order_id']} "
            f"from {warning.warning_level} warning for {warning.indicator_name} "
            f"on ring {warning.ring_number}"
        )

        return work_order

    def generate_batch(
        self,
        warnings: List[WarningEvent],
    ) -> List[Dict[str, Any]]:
        """
        Generate work orders from multiple warnings

        Args:
            warnings: List of warning events

        Returns:
            List of generated work orders
        """
        work_orders = []

        for warning in warnings:
            work_order = self.generate_from_warning(warning)
            if work_order:
                work_orders.append(work_order)

        if work_orders:
            logger.info(
                f"Generated {len(work_orders)} work orders "
                f"from {len(warnings)} warnings"
            )

        return work_orders

    def _generate_title(self, warning: WarningEvent) -> str:
        """Generate descriptive title for work order"""
        indicator_display = warning.indicator_name.replace("_", " ").title()
        return (
            f"{warning.warning_level} - {indicator_display} "
            f"Violation on Ring {warning.ring_number}"
        )

    def _generate_description(self, warning: WarningEvent) -> str:
        """Generate detailed description for work order"""
        lines = [
            f"Automatic work order generated from {warning.warning_level} level warning.",
            "",
            f"Ring Number: {warning.ring_number}",
            f"Indicator: {warning.indicator_name}",
            f"Current Value: {warning.indicator_value:.2f}" if warning.indicator_value else "",
            f"Threshold: {warning.threshold_value:.2f}" if warning.threshold_value else "",
            f"Warning Time: {datetime.fromtimestamp(warning.timestamp).isoformat()}",
            "",
            "Action Required:",
            "- Investigate the cause of the threshold violation",
            "- Assess impact on tunneling operations",
            "- Implement corrective measures if needed",
            "- Document actions taken for verification",
        ]
        return "\n".join(filter(None, lines))

    def clear_tracking(self):
        """Clear the generated warning IDs tracking set"""
        self._generated_warning_ids.clear()
        logger.debug("Cleared work order generation tracking")
