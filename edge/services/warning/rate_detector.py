"""
Rate-Based Anomaly Detector
Detects abnormal rate of change compared to historical averages
Implements Feature 003 - Real-Time Warning System
"""
import logging
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
import statistics

from edge.models.warning_threshold import WarningThreshold
from edge.models.warning_event import WarningEvent
from edge.models.ring_summary import RingSummary

logger = logging.getLogger(__name__)


class RateDetector:
    """
    Detects abnormal rate of change for indicators

    Implements FR-032: Rate-based warnings
    - Settlement rate > 3× historical average → WARNING
    - Torque/thrust rapid changes → ATTENTION/WARNING
    """

    # Mapping from threshold indicator names to RingSummary field names
    # This handles cases where threshold configs use different names than DB fields
    INDICATOR_FIELD_MAP = {
        'cumulative_settlement': 'settlement_value',
        'chamber_pressure': 'mean_chamber_pressure',
        'advance_rate_daily': 'mean_advance_rate',
        'displacement': 'displacement_value',
        'groundwater_level': 'groundwater_level',
        # Direct mappings (already correct)
        'mean_thrust': 'mean_thrust',
        'mean_torque': 'mean_torque',
        'mean_chamber_pressure': 'mean_chamber_pressure',
        'mean_advance_rate': 'mean_advance_rate',
        'settlement_value': 'settlement_value',
        'displacement_value': 'displacement_value',
    }

    def __init__(self, db_session: Session, thresholds: Dict[str, WarningThreshold]):
        """
        Args:
            db_session: Database session for querying historical data
            thresholds: Dict mapping indicator_name → WarningThreshold config
        """
        self.db = db_session
        self.thresholds = thresholds
        logger.info(f"RateDetector initialized with {len(thresholds)} threshold configs")

    def check(
        self,
        ring_number: int,
        indicator_name: str,
        indicator_value: float,
        geological_zone: str = "all",
        timestamp: Optional[float] = None
    ) -> Optional[WarningEvent]:
        """
        Check if indicator's rate of change is abnormal

        Args:
            ring_number: Current ring number
            indicator_name: Name of indicator (e.g., 'cumulative_settlement')
            indicator_value: Current value
            geological_zone: Geological zone
            timestamp: Event timestamp (defaults to now)

        Returns:
            WarningEvent if rate is abnormal, None otherwise
        """
        if timestamp is None:
            timestamp = datetime.utcnow().timestamp()

        # Get threshold config
        threshold_config = self._get_threshold_config(indicator_name, geological_zone)
        if not threshold_config or not threshold_config.enabled:
            return None

        window_size = threshold_config.rate_window_size

        # Query historical rings
        historical_data = self._get_historical_data(
            ring_number, indicator_name, window_size
        )

        if len(historical_data) < 2:
            logger.debug(
                f"Insufficient historical data for rate detection: "
                f"{len(historical_data)} rings (need >= 2)"
            )
            return None

        # Calculate current rate of change
        current_rate = self._calculate_rate(historical_data[-1], historical_data[-2])

        # Calculate historical average rate
        historical_rates = self._calculate_historical_rates(historical_data[:-1])
        if not historical_rates:
            logger.debug("No historical rates available")
            return None

        avg_historical_rate = statistics.mean(historical_rates)

        # Avoid division by zero
        if abs(avg_historical_rate) < 1e-9:
            logger.debug(f"Historical average rate too small: {avg_historical_rate}")
            return None

        # Calculate rate multiplier
        rate_multiplier = abs(current_rate) / abs(avg_historical_rate)

        # Evaluate against threshold multipliers
        warning_level = None
        if rate_multiplier >= threshold_config.rate_alarm_multiplier:
            warning_level = "ALARM"
        elif rate_multiplier >= threshold_config.rate_warning_multiplier:
            warning_level = "WARNING"
        elif rate_multiplier >= threshold_config.rate_attention_multiplier:
            warning_level = "ATTENTION"

        if warning_level is None:
            return None

        # Create warning event
        warning_event = WarningEvent(
            warning_id=str(uuid.uuid4()),
            warning_type="rate",
            warning_level=warning_level,
            ring_number=ring_number,
            timestamp=timestamp,
            indicator_name=indicator_name,
            indicator_value=indicator_value,
            indicator_unit=threshold_config.indicator_unit,
            rate_of_change=current_rate,
            historical_average_rate=avg_historical_rate,
            rate_multiplier=rate_multiplier,
            status="active",
        )

        # Set notification channels
        channels = threshold_config.get_notification_channels(warning_level)
        warning_event.set_notification_channels(channels)

        logger.warning(
            f"Rate anomaly detected: {indicator_name} rate={current_rate:.2f}/ring "
            f"(historical avg={avg_historical_rate:.2f}/ring, "
            f"multiplier={rate_multiplier:.1f}×) ring {ring_number}"
        )

        return warning_event

    def _get_threshold_config(
        self, indicator_name: str, geological_zone: str
    ) -> Optional[WarningThreshold]:
        """Get threshold config, preferring zone-specific over 'all'"""
        key = f"{indicator_name}_{geological_zone}"
        if key in self.thresholds:
            return self.thresholds[key]

        key = f"{indicator_name}_all"
        if key in self.thresholds:
            return self.thresholds[key]

        return None

    def _get_historical_data(
        self, current_ring: int, indicator_name: str, window_size: int
    ) -> List[Dict[str, Any]]:
        """
        Query historical ring data for rate calculation

        Returns:
            List of dicts with 'ring_number' and 'value' keys, ordered by ring_number
        """
        # Query previous rings
        rings = (
            self.db.query(RingSummary)
            .filter(RingSummary.ring_number <= current_ring)
            .order_by(RingSummary.ring_number.desc())
            .limit(window_size + 1)
            .all()
        )

        if not rings:
            return []

        # Extract indicator values
        data = []
        # Map indicator name to actual RingSummary field name
        field_name = self.INDICATOR_FIELD_MAP.get(indicator_name, indicator_name)

        for ring in reversed(rings):  # Chronological order
            value = getattr(ring, field_name, None)
            if value is not None:
                data.append({"ring_number": ring.ring_number, "value": value})

        return data

    def _calculate_rate(self, current: Dict, previous: Dict) -> float:
        """
        Calculate rate of change between two data points

        Returns:
            Rate per ring (value_change / ring_difference)
        """
        ring_diff = current["ring_number"] - previous["ring_number"]
        if ring_diff == 0:
            return 0.0

        value_diff = current["value"] - previous["value"]
        return value_diff / ring_diff

    def _calculate_historical_rates(self, historical_data: List[Dict]) -> List[float]:
        """
        Calculate rates for all consecutive pairs in historical data

        Returns:
            List of rates
        """
        if len(historical_data) < 2:
            return []

        rates = []
        for i in range(len(historical_data) - 1):
            rate = self._calculate_rate(historical_data[i + 1], historical_data[i])
            rates.append(rate)

        return rates
