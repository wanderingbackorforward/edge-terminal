"""
Prediction to Warning Integrator (T204)
Integrates prediction service with warning engine for predictive early warnings
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class PredictionWarningIntegrator:
    """
    Integrates Prediction Service output with Warning Engine

    Responsibilities:
    - Receives prediction results from inference service
    - Evaluates predictions against future thresholds
    - Triggers predictive warnings when thresholds likely to be exceeded
    - Provides prediction context to warning engine

    Implements FR-006: Predictive Early Warning
    """

    def __init__(
        self,
        db_session: Session,
        warning_engine,
        settlement_warning_threshold: float = 30.0,  # mm
        settlement_alarm_threshold: float = 40.0,    # mm
        confidence_threshold: float = 0.7,           # Minimum prediction confidence
        prediction_horizon_hours: float = 6.0,       # Hours ahead to check
    ):
        """
        Initialize integrator

        Args:
            db_session: Database session
            warning_engine: WarningEngine instance
            settlement_warning_threshold: Settlement value for WARNING level
            settlement_alarm_threshold: Settlement value for ALARM level
            confidence_threshold: Minimum confidence to trigger warning
            prediction_horizon_hours: Prediction lookahead window
        """
        self.db = db_session
        self.warning_engine = warning_engine

        self.settlement_warning_threshold = settlement_warning_threshold
        self.settlement_alarm_threshold = settlement_alarm_threshold
        self.confidence_threshold = confidence_threshold
        self.prediction_horizon_hours = prediction_horizon_hours

        # Track processed predictions to prevent duplicates
        self._processed_predictions: set = set()

        logger.info(
            f"PredictionWarningIntegrator initialized: "
            f"warning_threshold={settlement_warning_threshold}mm, "
            f"alarm_threshold={settlement_alarm_threshold}mm, "
            f"confidence={confidence_threshold}"
        )

    def process_prediction(
        self,
        prediction: Dict[str, Any],
        ring_number: int,
        geological_zone: str = "all",
    ) -> List[Dict[str, Any]]:
        """
        Process a prediction result and generate predictive warnings if needed

        Args:
            prediction: Prediction result dict from inference service
            ring_number: Current ring number
            geological_zone: Current geological zone

        Returns:
            List of generated predictive warnings
        """
        prediction_id = prediction.get("prediction_id")

        # Skip if already processed
        if prediction_id and prediction_id in self._processed_predictions:
            return []

        if prediction_id:
            self._processed_predictions.add(prediction_id)

        warnings = []

        # Extract prediction values
        predicted_settlement = prediction.get("predicted_settlement")
        confidence = prediction.get("prediction_confidence", 0.8)
        confidence_upper = prediction.get("confidence_upper")

        if predicted_settlement is None:
            return warnings

        # Check if confidence meets threshold
        if confidence < self.confidence_threshold:
            logger.debug(
                f"Prediction confidence {confidence:.2f} below threshold "
                f"{self.confidence_threshold}, skipping warning check"
            )
            return warnings

        # Use upper confidence bound for conservative warning
        check_value = confidence_upper if confidence_upper else predicted_settlement

        # Evaluate against thresholds
        warning_level = None
        if check_value >= self.settlement_alarm_threshold:
            warning_level = "ALARM"
        elif check_value >= self.settlement_warning_threshold:
            warning_level = "WARNING"
        elif check_value >= self.settlement_warning_threshold * 0.9:
            # 90% of warning threshold triggers ATTENTION
            warning_level = "ATTENTION"

        if warning_level:
            warning_data = {
                "warning_type": "predictive",
                "warning_level": warning_level,
                "ring_number": ring_number,
                "indicator_name": "predicted_settlement",
                "predicted_value": predicted_settlement,
                "confidence_lower": prediction.get("confidence_lower"),
                "confidence_upper": confidence_upper,
                "prediction_confidence": confidence,
                "threshold_value": (
                    self.settlement_alarm_threshold
                    if warning_level == "ALARM"
                    else self.settlement_warning_threshold
                ),
                "prediction_horizon_hours": self.prediction_horizon_hours,
                "geological_zone": geological_zone,
                "timestamp": datetime.utcnow().timestamp(),
            }

            warnings.append(warning_data)

            logger.info(
                f"Generated predictive {warning_level} warning: "
                f"predicted settlement {predicted_settlement:.2f}mm "
                f"(upper bound {check_value:.2f}mm) on ring {ring_number}"
            )

        return warnings

    def evaluate_prediction_batch(
        self,
        predictions: List[Dict[str, Any]],
        geological_zone: str = "all",
    ) -> List[Dict[str, Any]]:
        """
        Evaluate multiple predictions for warnings

        Args:
            predictions: List of prediction dicts
            geological_zone: Current geological zone

        Returns:
            List of all generated warnings
        """
        all_warnings = []

        for pred in predictions:
            ring_number = pred.get("ring_number", 0)
            warnings = self.process_prediction(pred, ring_number, geological_zone)
            all_warnings.extend(warnings)

        return all_warnings

    def clear_tracking(self):
        """Clear processed predictions tracking"""
        self._processed_predictions.clear()
        logger.debug("Cleared prediction warning integrator tracking")


def integrate_prediction_with_warnings(
    inference_service,
    warning_engine,
    db_session: Session,
    **integrator_kwargs
) -> PredictionWarningIntegrator:
    """
    Factory function to create and attach integrator

    Modifies inference service to automatically trigger warning checks
    after predictions are generated.

    Args:
        inference_service: InferenceService instance
        warning_engine: WarningEngine instance
        db_session: Database session
        **integrator_kwargs: Additional integrator configuration

    Returns:
        PredictionWarningIntegrator instance
    """
    integrator = PredictionWarningIntegrator(
        db_session, warning_engine, **integrator_kwargs
    )

    # Store original predict method if exists
    if hasattr(inference_service, 'predict'):
        original_predict = inference_service.predict

        def wrapped_predict(ring_summary, *args, **kwargs):
            """Wrapped predict that also checks for predictive warnings"""
            prediction = original_predict(ring_summary, *args, **kwargs)

            if prediction:
                ring_number = ring_summary.get(
                    "ring_number", prediction.get("ring_number", 0)
                )
                geological_zone = ring_summary.get("geological_zone", "all")

                # Generate predictive warnings
                warnings = integrator.process_prediction(
                    prediction, ring_number, geological_zone
                )

                # Attach warnings to prediction result for downstream processing
                prediction["predictive_warnings"] = warnings

            return prediction

        # Replace method with wrapped version
        inference_service.predict = wrapped_predict

        logger.info("Prediction service integrated with warning engine")

    return integrator
