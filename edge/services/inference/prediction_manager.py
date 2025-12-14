"""
Prediction Manager
Main orchestrator for the prediction system
Coordinates feature engineering, inference, and performance monitoring
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from sqlalchemy.orm import Session

from edge.services.inference.feature_engineer import FeatureEngineer
from edge.services.inference.model_loader import ONNXModelLoader, ModelManager
from edge.services.inference.inference_service import InferenceService
from edge.services.inference.performance_monitor import PerformanceMonitor
from edge.models.prediction_result import PredictionResult
from edge.models.model_metadata import ModelMetadata

logger = logging.getLogger(__name__)


class PredictionManager:
    """
    Main prediction system orchestrator

    Responsibilities:
    - Initialize and manage all prediction components
    - Coordinate automatic predictions for new rings
    - Schedule performance monitoring
    - Handle model updates and deployments
    - Provide unified API for predictions

    This is the primary interface for the prediction system
    """

    def __init__(
        self,
        db_session: Session,
        models_dir: str = "edge/models_onnx",
        feature_window_size: int = 10,
        enable_auto_monitoring: bool = True,
        monitoring_interval: int = 50  # Evaluate every N predictions
    ):
        self.db = db_session

        # Initialize components
        self.feature_engineer = FeatureEngineer(
            version="1.0.0",
            window_size=feature_window_size
        )

        self.model_loader = ONNXModelLoader(models_dir=models_dir)

        self.inference_service = InferenceService(
            db_session=db_session,
            model_loader=self.model_loader,
            feature_engineer=self.feature_engineer,
            enable_multi_target=False  # Can be enabled later
        )

        self.performance_monitor = PerformanceMonitor(
            db_session=db_session,
            drift_threshold=0.20,  # 20% RMSE increase
            evaluation_window=50,
            min_samples=20
        )

        self.model_manager = ModelManager(db_session, self.model_loader)

        # Auto-monitoring settings
        self.enable_auto_monitoring = enable_auto_monitoring
        self.monitoring_interval = monitoring_interval
        self.predictions_since_last_eval = 0

        logger.info("PredictionManager initialized")

    def initialize(self):
        """
        Initialize the prediction system
        - Load active models
        - Verify database schema
        - Run health checks
        """
        logger.info("Initializing prediction system...")

        # Load all active models from database
        active_models = self.db.query(ModelMetadata).filter(
            ModelMetadata.deployment_status == "active"
        ).all()

        if not active_models:
            logger.warning("No active models found in database")
            return

        success_count = 0
        for model in active_models:
            try:
                if self.model_loader.load_model(model, verify_checksum=True):
                    success_count += 1
                    logger.info(f"Loaded model: {model.model_name}")
                else:
                    logger.error(f"Failed to load model: {model.model_name}")
            except Exception as e:
                logger.error(f"Error loading model {model.model_name}: {e}")

        logger.info(f"Loaded {success_count}/{len(active_models)} active models")

    def predict(
        self,
        ring_number: int,
        geological_data: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = None
    ) -> PredictionResult:
        """
        Generate prediction for a ring

        Args:
            ring_number: Ring number to predict
            geological_data: Optional geological context
            model_name: Optional model override

        Returns:
            PredictionResult object

        This is the main prediction API
        """
        result = self.inference_service.predict_for_ring(
            ring_number=ring_number,
            geological_data=geological_data,
            model_name_override=model_name
        )

        # Increment prediction counter
        self.predictions_since_last_eval += 1

        # Trigger automatic monitoring if enabled
        if self.enable_auto_monitoring and self.predictions_since_last_eval >= self.monitoring_interval:
            self._trigger_auto_monitoring()

        return result

    def predict_batch(
        self,
        ring_numbers: List[int],
        geological_data_map: Optional[Dict[int, Dict[str, Any]]] = None
    ) -> List[PredictionResult]:
        """Batch prediction for multiple rings"""
        return self.inference_service.predict_batch(ring_numbers, geological_data_map)

    def update_with_actual(
        self,
        ring_number: int,
        actual_settlement: float,
        actual_displacement: Optional[float] = None,
        actual_groundwater_change: Optional[float] = None
    ) -> bool:
        """
        Update prediction with actual measured values
        Used for performance tracking
        """
        return self.inference_service.update_prediction_with_actual(
            ring_number=ring_number,
            actual_settlement=actual_settlement,
            actual_displacement=actual_displacement,
            actual_groundwater_change=actual_groundwater_change
        )

    def deploy_model(
        self,
        model_file_path: str,
        model_name: str,
        model_version: str,
        model_type: str,
        geological_zone: str = "all",
        validation_metrics: Optional[Dict[str, float]] = None,
        feature_list: Optional[List[str]] = None,
        activate: bool = True,
        output_format_version: str = "v2_confidence"
    ) -> bool:
        """
        Deploy a new model to the edge device

        Args:
            model_file_path: Path to ONNX model file
            model_name: Model identifier
            model_version: Version string (e.g., "1.0.0")
            model_type: Model type (lightgbm, xgboost, lstm)
            geological_zone: Target geological zone
            validation_metrics: Training validation metrics
            feature_list: Required feature names in order
            activate: Whether to activate immediately
            output_format_version: ONNX output format for 2-output models
                - 'v1_lower_bound': [settlement, lower_bound] (legacy)
                - 'v2_confidence': [settlement, confidence] (default, new)
                Ignored for models with other output counts

        Returns:
            True if deployment successful
        """
        try:
            # Create model metadata
            model_metadata = ModelMetadata(
                model_name=model_name,
                model_version=model_version,
                model_type=model_type,
                onnx_path=model_file_path,
                geological_zone=geological_zone,
                deployment_status="staged",  # Start as staged
                output_format_version=output_format_version
            )

            # Set validation metrics if provided
            if validation_metrics:
                model_metadata.validation_r2 = validation_metrics.get("r2")
                model_metadata.validation_rmse = validation_metrics.get("rmse")
                model_metadata.validation_mae = validation_metrics.get("mae")

            # Set feature list if provided
            if feature_list:
                model_metadata.set_feature_list(feature_list)

            # Calculate checksum
            import hashlib
            sha256 = hashlib.sha256()
            with open(model_file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    sha256.update(chunk)
            model_metadata.onnx_checksum = sha256.hexdigest()

            # Save to database
            self.db.add(model_metadata)
            self.db.commit()

            logger.info(f"Model metadata created for {model_name}")

            # Load model
            if not self.model_loader.load_model(model_metadata, verify_checksum=True):
                logger.error(f"Failed to load model {model_name}")
                return False

            # Activate if requested
            if activate:
                if not self.model_manager.activate_model(model_name):
                    logger.error(f"Failed to activate model {model_name}")
                    return False

            logger.info(f"Model {model_name} deployed successfully")
            return True

        except Exception as e:
            logger.error(f"Model deployment failed: {e}", exc_info=True)
            return False

    def rollback_model(self, model_name: str, previous_version: str) -> bool:
        """
        Rollback to a previous model version
        Implements FR-007: Model rollback
        """
        try:
            # Retire current model
            self.model_manager.retire_model(model_name)

            # Activate previous version
            previous_model_name = f"{model_name}_{previous_version}"
            success = self.model_manager.activate_model(previous_model_name)

            if success:
                logger.info(f"Rolled back {model_name} to version {previous_version}")
            else:
                logger.error(f"Rollback failed for {model_name}")

            return success

        except Exception as e:
            logger.error(f"Rollback error: {e}", exc_info=True)
            return False

    def evaluate_model(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Evaluate model performance and return report"""
        metric = self.performance_monitor.evaluate_model(model_name)

        if not metric:
            return None

        return metric.to_dict()

    def get_performance_report(self, model_name: str) -> Dict[str, Any]:
        """Get comprehensive performance report for a model"""
        return self.performance_monitor.generate_performance_report(model_name)

    def get_drift_alerts(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent drift detection alerts"""
        alerts = self.performance_monitor.get_drift_alerts(days)
        return [a.to_dict() for a in alerts]

    def get_status(self) -> Dict[str, Any]:
        """Get system status"""
        loaded_models = self.model_loader.list_loaded_models()

        model_stats = {}
        for model_name in loaded_models:
            stats = self.model_loader.get_performance_stats(model_name)
            model_stats[model_name] = stats

        active_models_count = self.db.query(ModelMetadata).filter(
            ModelMetadata.deployment_status == "active"
        ).count()

        total_predictions = self.db.query(PredictionResult).count()

        return {
            "status": "operational",
            "loaded_models": loaded_models,
            "active_models_count": active_models_count,
            "total_predictions": total_predictions,
            "predictions_since_last_eval": self.predictions_since_last_eval,
            "model_performance_stats": model_stats,
            "feature_engineering_version": self.feature_engineer.version,
        }

    def _trigger_auto_monitoring(self):
        """Automatically evaluate all active models"""
        logger.info("Triggering automatic performance monitoring")

        try:
            metrics = self.performance_monitor.evaluate_all_active_models()

            for metric in metrics:
                if metric.drift_detected:
                    logger.warning(
                        f"Drift detected in {metric.model_name}: "
                        f"{metric.drift_severity} severity, "
                        f"RMSE increase: {metric.rmse_increase_percent:.1f}%"
                    )

                if metric.triggered_retraining:
                    logger.warning(
                        f"Retraining triggered for {metric.model_name}: "
                        f"{metric.retraining_reason}"
                    )

            # Reset counter
            self.predictions_since_last_eval = 0

        except Exception as e:
            logger.error(f"Auto-monitoring failed: {e}", exc_info=True)

    def shutdown(self):
        """Clean shutdown of prediction system"""
        logger.info("Shutting down prediction system...")

        # Unload all models
        for model_name in self.model_loader.list_loaded_models():
            self.model_loader.unload_model(model_name)

        logger.info("Prediction system shut down")
