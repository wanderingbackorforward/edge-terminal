"""
Model Performance Monitor
Tracks prediction accuracy and detects concept drift
Implements FR-027 to FR-032
"""
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

from edge.models.prediction_result import PredictionResult
from edge.models.model_metadata import ModelMetadata, ModelPerformanceMetric

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """
    Monitor ML model performance over time

    Features:
    - Calculate accuracy metrics (R², RMSE, MAE)
    - Detect concept drift
    - Trigger retraining requests
    - Track confidence calibration
    """

    def __init__(
        self,
        db_session: Session,
        drift_threshold: float = 0.20,  # 20% RMSE increase triggers drift alert
        evaluation_window: int = 50,  # Number of rings for rolling evaluation
        min_samples: int = 20  # Minimum samples required for evaluation
    ):
        self.db = db_session
        self.drift_threshold = drift_threshold
        self.evaluation_window = evaluation_window
        self.min_samples = min_samples

    def evaluate_model(
        self,
        model_name: str,
        start_ring: Optional[int] = None,
        end_ring: Optional[int] = None
    ) -> Optional[ModelPerformanceMetric]:
        """
        Evaluate model performance on predictions with actual values

        Implements FR-027, FR-028

        Args:
            model_name: Model to evaluate
            start_ring: Start of evaluation range (optional)
            end_ring: End of evaluation range (optional)

        Returns:
            ModelPerformanceMetric object if evaluation successful
        """
        # Fetch predictions with actual values
        query = self.db.query(PredictionResult).filter(
            PredictionResult.model_name == model_name,
            PredictionResult.actual_settlement.isnot(None),
            PredictionResult.predicted_settlement.isnot(None)
        )

        if start_ring:
            query = query.filter(PredictionResult.ring_number >= start_ring)
        if end_ring:
            query = query.filter(PredictionResult.ring_number <= end_ring)

        predictions = query.all()

        if len(predictions) < self.min_samples:
            logger.warning(
                f"Insufficient samples for evaluation: {len(predictions)} < {self.min_samples}"
            )
            return None

        # Extract predicted and actual values
        y_pred = np.array([p.predicted_settlement for p in predictions])
        y_true = np.array([p.actual_settlement for p in predictions])

        # Calculate metrics
        metrics = self._calculate_metrics(y_pred, y_true)

        # Check confidence calibration
        confidence_coverage = self._calculate_confidence_coverage(predictions)
        metrics["confidence_coverage"] = confidence_coverage

        # Get model baseline RMSE
        model = self.db.query(ModelMetadata).filter(
            ModelMetadata.model_name == model_name
        ).first()

        baseline_rmse = model.validation_rmse if model else None

        # Detect drift
        drift_detected = False
        drift_severity = "none"
        rmse_increase_percent = 0.0

        if baseline_rmse and baseline_rmse > 0:
            rmse_increase_percent = ((metrics["rmse"] - baseline_rmse) / baseline_rmse) * 100

            if rmse_increase_percent > self.drift_threshold * 100:
                drift_detected = True

                # Classify severity
                if rmse_increase_percent > 50:
                    drift_severity = "severe"
                elif rmse_increase_percent > 30:
                    drift_severity = "moderate"
                else:
                    drift_severity = "minor"

                logger.warning(
                    f"Drift detected for {model_name}: "
                    f"RMSE increased {rmse_increase_percent:.1f}% "
                    f"(baseline={baseline_rmse:.2f}mm, current={metrics['rmse']:.2f}mm)"
                )

        # Determine if retraining should be triggered
        triggered_retraining = False
        retraining_reason = None

        if drift_detected:
            triggered_retraining = True
            retraining_reason = f"drift_detected_{drift_severity}"
        elif metrics["r2"] < 0.90:  # Performance threshold from spec FR-030
            triggered_retraining = True
            retraining_reason = "performance_below_threshold"

        # Create performance metric record
        data_range = f"rings_{predictions[0].ring_number}-{predictions[-1].ring_number}"

        perf_metric = ModelPerformanceMetric(
            model_name=model_name,
            evaluation_date=datetime.utcnow().timestamp(),
            evaluation_data_range=data_range,
            num_predictions=len(predictions),
            r2_score=metrics["r2"],
            rmse=metrics["rmse"],
            mae=metrics["mae"],
            mape=metrics["mape"],
            confidence_coverage=confidence_coverage,
            drift_detected=int(drift_detected),
            drift_severity=drift_severity,
            baseline_rmse=baseline_rmse,
            rmse_increase_percent=rmse_increase_percent,
            triggered_retraining=int(triggered_retraining),
            retraining_reason=retraining_reason
        )

        # Save to database
        self.db.add(perf_metric)
        self.db.commit()

        logger.info(
            f"Model evaluation complete for {model_name}: "
            f"R²={metrics['r2']:.3f}, RMSE={metrics['rmse']:.2f}mm, "
            f"MAE={metrics['mae']:.2f}mm, drift={drift_detected}"
        )

        return perf_metric

    def evaluate_all_active_models(self) -> List[ModelPerformanceMetric]:
        """Evaluate all active models"""
        active_models = self.db.query(ModelMetadata).filter(
            ModelMetadata.deployment_status == "active"
        ).all()

        results = []

        for model in active_models:
            metric = self.evaluate_model(model.model_name)
            if metric:
                results.append(metric)

        return results

    def monitor_rolling_performance(
        self,
        model_name: str
    ) -> Optional[ModelPerformanceMetric]:
        """
        Monitor performance on most recent N predictions
        Implements FR-029: Rolling window drift detection

        Args:
            model_name: Model to monitor

        Returns:
            ModelPerformanceMetric for rolling window
        """
        # Get most recent predictions with actuals
        recent_predictions = (
            self.db.query(PredictionResult)
            .filter(
                PredictionResult.model_name == model_name,
                PredictionResult.actual_settlement.isnot(None)
            )
            .order_by(PredictionResult.ring_number.desc())
            .limit(self.evaluation_window)
            .all()
        )

        if not recent_predictions:
            return None

        # Get ring range
        start_ring = recent_predictions[-1].ring_number
        end_ring = recent_predictions[0].ring_number

        # Evaluate on this window
        return self.evaluate_model(model_name, start_ring, end_ring)

    def _calculate_metrics(self, y_pred: np.ndarray, y_true: np.ndarray) -> Dict[str, float]:
        """Calculate regression metrics"""
        # R² score
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        # RMSE
        rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))

        # MAE
        mae = np.mean(np.abs(y_true - y_pred))

        # MAPE (Mean Absolute Percentage Error)
        # Avoid division by zero
        mask = y_true != 0
        if mask.sum() > 0:
            mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100
        else:
            mape = 0.0

        return {
            "r2": float(r2),
            "rmse": float(rmse),
            "mae": float(mae),
            "mape": float(mape)
        }

    def _calculate_confidence_coverage(self, predictions: List[PredictionResult]) -> float:
        """
        Calculate fraction of actual values within confidence intervals
        Should be ~0.95 for properly calibrated 95% CI

        Implements FR-032: Confidence calibration tracking
        """
        total = 0
        within_ci = 0

        for pred in predictions:
            if (pred.actual_settlement is not None and
                pred.settlement_lower_bound is not None and
                pred.settlement_upper_bound is not None):

                total += 1

                if pred.settlement_lower_bound <= pred.actual_settlement <= pred.settlement_upper_bound:
                    within_ci += 1

        if total == 0:
            return 0.0

        return within_ci / total

    def get_performance_history(
        self,
        model_name: str,
        days: int = 30
    ) -> List[ModelPerformanceMetric]:
        """Get performance metrics history for a model"""
        cutoff_time = datetime.utcnow().timestamp() - (days * 86400)

        return (
            self.db.query(ModelPerformanceMetric)
            .filter(
                ModelPerformanceMetric.model_name == model_name,
                ModelPerformanceMetric.evaluation_date >= cutoff_time
            )
            .order_by(ModelPerformanceMetric.evaluation_date.desc())
            .all()
        )

    def get_drift_alerts(self, days: int = 7) -> List[ModelPerformanceMetric]:
        """Get recent drift detection alerts"""
        cutoff_time = datetime.utcnow().timestamp() - (days * 86400)

        return (
            self.db.query(ModelPerformanceMetric)
            .filter(
                ModelPerformanceMetric.drift_detected == 1,
                ModelPerformanceMetric.evaluation_date >= cutoff_time
            )
            .order_by(ModelPerformanceMetric.evaluation_date.desc())
            .all()
        )

    def get_retraining_queue(self) -> List[ModelPerformanceMetric]:
        """Get models that triggered retraining requests"""
        return (
            self.db.query(ModelPerformanceMetric)
            .filter(ModelPerformanceMetric.triggered_retraining == 1)
            .order_by(ModelPerformanceMetric.evaluation_date.desc())
            .limit(10)
            .all()
        )

    def generate_performance_report(self, model_name: str) -> Dict[str, any]:
        """Generate comprehensive performance report for a model"""
        # Get latest evaluation
        latest = (
            self.db.query(ModelPerformanceMetric)
            .filter(ModelPerformanceMetric.model_name == model_name)
            .order_by(ModelPerformanceMetric.evaluation_date.desc())
            .first()
        )

        if not latest:
            return {"error": "No evaluations found"}

        # Get performance history
        history = self.get_performance_history(model_name, days=30)

        # Calculate trends
        if len(history) >= 2:
            rmse_trend = history[0].rmse - history[-1].rmse  # Negative is improvement
            r2_trend = history[0].r2_score - history[-1].r2_score  # Positive is improvement
        else:
            rmse_trend = 0.0
            r2_trend = 0.0

        # Get model metadata
        model = self.db.query(ModelMetadata).filter(
            ModelMetadata.model_name == model_name
        ).first()

        return {
            "model_name": model_name,
            "model_version": model.model_version if model else "unknown",
            "deployment_status": model.deployment_status if model else "unknown",
            "latest_evaluation": {
                "date": datetime.fromtimestamp(latest.evaluation_date).isoformat(),
                "data_range": latest.evaluation_data_range,
                "num_predictions": latest.num_predictions,
                "r2_score": latest.r2_score,
                "rmse": latest.rmse,
                "mae": latest.mae,
                "mape": latest.mape,
                "confidence_coverage": latest.confidence_coverage,
            },
            "drift_status": {
                "drift_detected": bool(latest.drift_detected),
                "drift_severity": latest.drift_severity,
                "rmse_increase_percent": latest.rmse_increase_percent,
                "baseline_rmse": latest.baseline_rmse,
            },
            "trends_30d": {
                "rmse_change": rmse_trend,
                "r2_change": r2_trend,
                "num_evaluations": len(history),
            },
            "retraining": {
                "triggered": bool(latest.triggered_retraining),
                "reason": latest.retraining_reason,
            }
        }
