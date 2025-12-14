"""
Threshold-Based Warning Checker
Evaluates absolute values against configured thresholds
Implements Feature 003 - Real-Time Warning System
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import uuid

from edge.models.warning_threshold import WarningThreshold
from edge.models.warning_event import WarningEvent

logger = logging.getLogger(__name__)


class ThresholdChecker:
    """
    Checks if indicator values exceed configured thresholds

    Implements FR-031: Threshold-based warnings
    - Settlement > 30mm → WARNING
    - Chamber pressure out of range → ALARM
    - Torque/thrust exceeding limits → WARNING/ALARM
    """

    def __init__(self, thresholds: Dict[str, WarningThreshold]):
        """
        Args:
            thresholds: Dict mapping indicator_name → WarningThreshold config
        """
        self.thresholds = thresholds
        logger.info(f"ThresholdChecker initialized with {len(thresholds)} threshold configs")

    def check(
        self,
        ring_number: int,
        indicator_name: str,
        indicator_value: float,
        geological_zone: str = "all",
        timestamp: Optional[float] = None
    ) -> Optional[WarningEvent]:
        """
        Check if indicator value violates threshold

        Args:
            ring_number: Ring number being evaluated
            indicator_name: Name of indicator (e.g., 'settlement_value', 'mean_chamber_pressure')
            indicator_value: Current value
            geological_zone: Geological zone for zone-specific thresholds
            timestamp: Event timestamp (defaults to now)

        Returns:
            WarningEvent if threshold violated, None otherwise
        """
        if timestamp is None:
            timestamp = datetime.utcnow().timestamp()

        # Look up threshold config (zone-specific first, then 'all' fallback)
        threshold_config = self._get_threshold_config(indicator_name, geological_zone)

        if not threshold_config:
            logger.debug(f"No threshold config found for {indicator_name} in zone {geological_zone}")
            return None

        if not threshold_config.enabled:
            logger.debug(f"Threshold {indicator_name} is disabled")
            return None

        # Evaluate value against thresholds
        warning_level = threshold_config.evaluate_threshold(indicator_value)

        if warning_level is None:
            # Value is within normal range
            return None

        # Determine which bound was violated
        threshold_value, threshold_type = self._identify_violated_threshold(
            indicator_value, threshold_config, warning_level
        )

        # Create warning event
        warning_event = WarningEvent(
            warning_id=str(uuid.uuid4()),
            warning_type="threshold",
            warning_level=warning_level,
            ring_number=ring_number,
            timestamp=timestamp,
            indicator_name=indicator_name,
            indicator_value=indicator_value,
            indicator_unit=threshold_config.indicator_unit,
            threshold_value=threshold_value,
            threshold_type=threshold_type,
            status="active",
        )

        # Set notification channels based on level
        channels = threshold_config.get_notification_channels(warning_level)
        warning_event.set_notification_channels(channels)

        logger.warning(
            f"Threshold violation detected: {indicator_name}={indicator_value}{threshold_config.indicator_unit} "
            f"exceeds {warning_level} threshold {threshold_value} (ring {ring_number})"
        )

        return warning_event

    def _get_threshold_config(
        self, indicator_name: str, geological_zone: str
    ) -> Optional[WarningThreshold]:
        """Get threshold config, preferring zone-specific over 'all'"""
        # Try zone-specific first
        key = f"{indicator_name}_{geological_zone}"
        if key in self.thresholds:
            return self.thresholds[key]

        # Fallback to 'all' zones
        key = f"{indicator_name}_all"
        if key in self.thresholds:
            return self.thresholds[key]

        return None

    def _identify_violated_threshold(
        self, value: float, config: WarningThreshold, level: str
    ) -> tuple:
        """
        Identify which specific threshold was violated

        Returns:
            (threshold_value, threshold_type) tuple
            threshold_type: 'upper', 'lower', or 'range'
        """
        lower = config.get_threshold_value(level, "lower")
        upper = config.get_threshold_value(level, "upper")

        # Check lower bound violation
        if lower is not None and value < lower:
            return (lower, "lower")

        # Check upper bound violation
        if upper is not None and value > upper:
            return (upper, "upper")

        # If both bounds exist and value is between them but triggered (shouldn't happen)
        if lower is not None and upper is not None:
            return ((lower + upper) / 2, "range")

        # Fallback (shouldn't reach here)
        return (upper if upper is not None else lower, "unknown")

    def check_batch(
        self,
        ring_number: int,
        indicators: Dict[str, float],
        geological_zone: str = "all",
        timestamp: Optional[float] = None
    ) -> list:
        """
        Check multiple indicators for threshold violations

        Args:
            ring_number: Ring number being evaluated
            indicators: Dict mapping indicator_name → value
            geological_zone: Geological zone
            timestamp: Event timestamp

        Returns:
            List of WarningEvent objects for all violations
        """
        warnings = []

        for indicator_name, value in indicators.items():
            warning = self.check(
                ring_number, indicator_name, value, geological_zone, timestamp
            )
            if warning:
                warnings.append(warning)

        if warnings:
            logger.info(f"Threshold check for ring {ring_number}: {len(warnings)} violations detected")

        return warnings
