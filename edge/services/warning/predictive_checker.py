"""
Predictive Early Warning Checker
Issues warnings when predicted values are expected to exceed thresholds
Implements Feature 003 - Real-Time Warning System
"""
import logging
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from edge.models.warning_threshold import WarningThreshold
from edge.models.warning_event import WarningEvent
from edge.models.prediction_result import PredictionResult

logger = logging.getLogger(__name__)


class PredictiveChecker:
    """
    Checks predicted values for potential threshold violations

    Implements FR-033: Predictive early warnings
    - Predicted settlement approaching 30mm → ATTENTION
    - Forecasted violations within 24 hours → WARNING
    - Confidence interval upper bound exceeding threshold → cautionary alert
    """

    def __init__(self, db_session: Session, thresholds: Dict[str, WarningThreshold]):
        """
        Args:
            db_session: Database session for querying predictions
            thresholds: Dict mapping indicator_name → WarningThreshold config
        """
        self.db = db_session
        self.thresholds = thresholds
        logger.info(f"PredictiveChecker initialized with {len(thresholds)} threshold configs")

    def check(
        self,
        ring_number: int,
        geological_zone: str = "all",
        timestamp: Optional[float] = None
    ) -> list:
        """
        Check if predictions indicate future threshold violations

        Args:
            ring_number: Ring number being evaluated
            geological_zone: Geological zone
            timestamp: Event timestamp (defaults to now)

        Returns:
            List of WarningEvent objects for predicted violations
        """
        if timestamp is None:
            timestamp = datetime.utcnow().timestamp()

        # Query latest prediction for this ring
        prediction = (
            self.db.query(PredictionResult)
            .filter(PredictionResult.ring_number == ring_number)
            .order_by(PredictionResult.timestamp.desc())
            .first()
        )

        if not prediction:
            logger.debug(f"No prediction found for ring {ring_number}")
            return []

        warnings = []

        # Check settlement prediction
        settlement_warning = self._check_settlement_prediction(
            ring_number, prediction, geological_zone, timestamp
        )
        if settlement_warning:
            warnings.append(settlement_warning)

        # Check displacement prediction (if available)
        if prediction.predicted_displacement is not None:
            disp_warning = self._check_displacement_prediction(
                ring_number, prediction, geological_zone, timestamp
            )
            if disp_warning:
                warnings.append(disp_warning)

        if warnings:
            logger.info(f"Predictive check for ring {ring_number}: {len(warnings)} early warnings issued")

        return warnings

    def _check_settlement_prediction(
        self,
        ring_number: int,
        prediction: PredictionResult,
        geological_zone: str,
        timestamp: float
    ) -> Optional[WarningEvent]:
        """Check predicted settlement against thresholds"""
        # Use RingSummary field name to match migration 011
        threshold_config = self._get_threshold_config("settlement_value", geological_zone)

        if not threshold_config or not threshold_config.enabled:
            return None

        if not threshold_config.predictive_enabled:
            return None

        predicted_value = prediction.predicted_settlement
        upper_bound = prediction.settlement_upper_bound
        confidence = prediction.prediction_confidence

        # Determine if prediction indicates potential violation
        warning_level, threshold_value = self._evaluate_prediction(
            predicted_value, upper_bound, threshold_config
        )

        if warning_level is None:
            return None

        # Create warning event
        warning_event = WarningEvent(
            warning_id=str(uuid.uuid4()),
            warning_type="predictive",
            warning_level=warning_level,
            ring_number=ring_number,
            timestamp=timestamp,
            indicator_name="settlement_value",  # Use RingSummary field name
            indicator_value=None,  # No actual value yet (it's a prediction)
            indicator_unit="mm",
            predicted_value=predicted_value,
            prediction_confidence=confidence,
            prediction_horizon_hours=threshold_config.predictive_horizon_hours,
            threshold_value=threshold_value,
            threshold_type="upper",
            status="active",
        )

        # Set notification channels
        channels = threshold_config.get_notification_channels(warning_level)
        warning_event.set_notification_channels(channels)

        logger.warning(
            f"Predictive warning for settlement: ring {ring_number}, "
            f"predicted={predicted_value:.2f}mm (threshold={threshold_value:.2f}mm), "
            f"confidence={confidence:.2%}, level={warning_level}"
        )

        return warning_event

    def _check_displacement_prediction(
        self,
        ring_number: int,
        prediction: PredictionResult,
        geological_zone: str,
        timestamp: float
    ) -> Optional[WarningEvent]:
        """Check predicted displacement against thresholds"""
        # Use RingSummary field name to match migration 011
        threshold_config = self._get_threshold_config("displacement_value", geological_zone)

        if not threshold_config or not threshold_config.enabled:
            return None

        if not threshold_config.predictive_enabled:
            return None

        predicted_value = prediction.predicted_displacement
        upper_bound = prediction.displacement_upper_bound
        confidence = prediction.prediction_confidence

        warning_level, threshold_value = self._evaluate_prediction(
            predicted_value, upper_bound, threshold_config
        )

        if warning_level is None:
            return None

        warning_event = WarningEvent(
            warning_id=str(uuid.uuid4()),
            warning_type="predictive",
            warning_level=warning_level,
            ring_number=ring_number,
            timestamp=timestamp,
            indicator_name="displacement_value",  # Use RingSummary field name
            indicator_value=None,
            indicator_unit="mm",
            predicted_value=predicted_value,
            prediction_confidence=confidence,
            prediction_horizon_hours=threshold_config.predictive_horizon_hours,
            threshold_value=threshold_value,
            threshold_type="upper",
            status="active",
        )

        channels = threshold_config.get_notification_channels(warning_level)
        warning_event.set_notification_channels(channels)

        return warning_event

    def _evaluate_prediction(
        self,
        predicted_value: float,
        upper_bound: Optional[float],
        config: WarningThreshold
    ) -> tuple:
        """
        Evaluate prediction against thresholds

        Returns:
            (warning_level, threshold_value) tuple
            warning_level: 'ATTENTION', 'WARNING', 'ALARM', or None
        """
        threshold_percentage = config.predictive_threshold_percentage

        # Check predicted value directly
        predicted_level = config.evaluate_threshold(predicted_value)

        # If predicted value already exceeds threshold
        if predicted_level:
            threshold_value = self._get_relevant_threshold(predicted_value, config)
            return (predicted_level, threshold_value)

        # Check if prediction is approaching threshold (within X% of limit)
        for level in ["ATTENTION", "WARNING", "ALARM"]:
            upper_threshold = config.get_threshold_value(level, "upper")
            if upper_threshold is not None:
                if predicted_value >= upper_threshold * threshold_percentage:
                    return (level, upper_threshold)

        # Check if confidence interval upper bound exceeds threshold
        if upper_bound is not None:
            upper_level = config.evaluate_threshold(upper_bound)
            if upper_level:
                threshold_value = self._get_relevant_threshold(upper_bound, config)
                # Downgrade by one level since it's just CI, not point estimate
                downgraded_level = self._downgrade_level(upper_level)
                return (downgraded_level, threshold_value)

        return (None, None)

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

    def _get_relevant_threshold(self, value: float, config: WarningThreshold) -> float:
        """Get the specific threshold value that was violated"""
        level = config.evaluate_threshold(value)
        if level:
            upper = config.get_threshold_value(level, "upper")
            if upper is not None:
                return upper
            lower = config.get_threshold_value(level, "lower")
            if lower is not None:
                return lower
        return 0.0

    def _downgrade_level(self, level: str) -> str:
        """Downgrade warning level by one step"""
        if level == "ALARM":
            return "WARNING"
        elif level == "WARNING":
            return "ATTENTION"
        else:
            return "ATTENTION"
