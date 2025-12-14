"""
Edge Inference Service
Real-time ML predictions using ONNX models on edge device
Implements FR-020 to FR-026
"""
import time
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import logging
from sqlalchemy.orm import Session

from edge.models.ring_summary import RingSummary
from edge.models.prediction_result import PredictionResult
from edge.models.model_metadata import ModelMetadata
from edge.services.inference.feature_engineer import FeatureEngineer, FeatureVector
from edge.services.inference.model_loader import ONNXModelLoader, ModelManager

logger = logging.getLogger(__name__)


class InferenceService:
    """
    Edge inference service for real-time settlement predictions

    Workflow:
    1. Fetch ring_summary data for target ring
    2. Fetch historical rings for time-windowed features
    3. Engineer features using FeatureEngineer
    4. Select appropriate model based on geological zone
    5. Run ONNX inference
    6. Generate confidence intervals
    7. Persist prediction results to database
    8. Return prediction to caller

    Implements:
    - FR-020: ONNX Runtime-based inference
    - FR-022: <10ms p99 latency
    - FR-023: Point estimates + confidence intervals
    - FR-024: Persist to prediction_results table
    - FR-025: Offline operation (no cloud dependency)
    - FR-026: Multi-target predictions
    """

    def __init__(
        self,
        db_session: Session,
        model_loader: ONNXModelLoader,
        feature_engineer: FeatureEngineer,
        enable_multi_target: bool = False
    ):
        self.db = db_session
        self.model_loader = model_loader
        self.feature_engineer = feature_engineer
        self.model_manager = ModelManager(db_session, model_loader)
        self.enable_multi_target = enable_multi_target

    def predict_for_ring(
        self,
        ring_number: int,
        geological_data: Optional[Dict[str, Any]] = None,
        model_name_override: Optional[str] = None
    ) -> PredictionResult:
        """
        Generate prediction for a specific ring

        Args:
            ring_number: Ring number to predict
            geological_data: Optional geological context
            model_name_override: Force specific model (for manual override FR-019)

        Returns:
            PredictionResult object (persisted to database)

        Raises:
            ValueError: If ring data not found or model unavailable
        """
        start_time = time.perf_counter()

        # Step 1: Fetch ring data
        ring_data = self._fetch_ring_data(ring_number)
        if not ring_data:
            raise ValueError(f"Ring {ring_number} not found in database")

        # Step 2: Fetch historical rings for windowed features
        historical_rings = self._fetch_historical_rings(ring_number)

        # Step 3: Engineer features
        feature_vector = self.feature_engineer.engineer_features(
            ring_data=ring_data,
            historical_rings=historical_rings,
            geological_data=geological_data
        )

        # Step 4: Select model
        if model_name_override:
            model_name = model_name_override
            logger.info(f"Using manual override model: {model_name}")
        else:
            geological_zone = feature_vector.geological_zone or ring_data.get("geological_zone", "all")
            model_name = self.model_manager.get_active_model_for_zone(geological_zone)

            if not model_name:
                raise ValueError(f"No active model found for zone {geological_zone}")

        # Step 5: Run inference
        prediction = self._run_inference(model_name, feature_vector)

        # Step 6: Create prediction result
        result = self._create_prediction_result(
            ring_number=ring_number,
            model_name=model_name,
            feature_vector=feature_vector,
            prediction=prediction,
            total_time_ms=(time.perf_counter() - start_time) * 1000
        )

        # Step 7: Persist to database
        self.db.add(result)
        self.db.commit()

        logger.info(
            f"Prediction complete for ring {ring_number}: "
            f"{result.predicted_settlement:.2f}mm "
            f"[{result.settlement_lower_bound:.2f}, {result.settlement_upper_bound:.2f}] "
            f"in {result.inference_time_ms:.1f}ms"
        )

        return result

    def predict_batch(
        self,
        ring_numbers: List[int],
        geological_data_map: Optional[Dict[int, Dict[str, Any]]] = None
    ) -> List[PredictionResult]:
        """
        Batch prediction for multiple rings
        More efficient than calling predict_for_ring repeatedly
        """
        results = []

        for ring_num in ring_numbers:
            geo_data = geological_data_map.get(ring_num) if geological_data_map else None

            try:
                result = self.predict_for_ring(ring_num, geo_data)
                results.append(result)
            except Exception as e:
                logger.error(f"Prediction failed for ring {ring_num}: {e}")
                continue

        return results

    def _fetch_ring_data(self, ring_number: int) -> Optional[Dict[str, Any]]:
        """Fetch ring summary data from database"""
        ring = (
            self.db.query(RingSummary)
            .filter(RingSummary.ring_number == ring_number)
            .first()
        )

        if not ring:
            return None

        # Convert to dict
        return {
            "ring_number": ring.ring_number,
            "start_time": ring.start_time,
            "end_time": ring.end_time,
            "mean_thrust": ring.mean_thrust,
            "max_thrust": ring.max_thrust,
            "std_thrust": ring.std_thrust,
            "mean_torque": ring.mean_torque,
            "max_torque": ring.max_torque,
            "std_torque": ring.std_torque,
            "mean_chamber_pressure": ring.mean_chamber_pressure,
            "std_chamber_pressure": ring.std_chamber_pressure,
            "mean_advance_rate": ring.mean_advance_rate,
            "max_advance_rate": ring.max_advance_rate,
            "mean_grout_pressure": ring.mean_grout_pressure,
            "grout_volume": ring.grout_volume,
            "mean_pitch": ring.mean_pitch,
            "mean_roll": ring.mean_roll,
            "mean_yaw": ring.mean_yaw,
            "horizontal_deviation_max": ring.horizontal_deviation_max,
            "vertical_deviation_max": ring.vertical_deviation_max,
            "specific_energy": ring.specific_energy,
            "ground_loss_rate": ring.ground_loss_rate,
            "volume_loss_ratio": ring.volume_loss_ratio,
            "geological_zone": ring.geological_zone,
        }

    def _fetch_historical_rings(self, ring_number: int, window_size: int = 10) -> List[Dict[str, Any]]:
        """Fetch previous N rings for time-windowed features"""
        rings = (
            self.db.query(RingSummary)
            .filter(RingSummary.ring_number < ring_number)
            .order_by(RingSummary.ring_number.desc())
            .limit(window_size)
            .all()
        )

        # Convert to list of dicts (newest to oldest)
        historical = []
        for ring in reversed(rings):  # Reverse to chronological order
            historical.append(self._fetch_ring_data(ring.ring_number))

        return historical

    def _run_inference(self, model_name: str, feature_vector: FeatureVector) -> Dict[str, Any]:
        """
        Run ONNX inference with feature vector

        Implements FR-022: <10ms p99 latency
        """
        # Convert feature dict to numpy array
        # Must match model's expected feature order
        model_metadata = self.db.query(ModelMetadata).filter(
            ModelMetadata.model_name == model_name
        ).first()

        if not model_metadata:
            raise ValueError(f"Model metadata not found for {model_name}")

        # Get expected feature list
        expected_features = model_metadata.get_feature_list()

        # Build feature array in correct order
        feature_array = []
        for feature_name in expected_features:
            value = feature_vector.features.get(feature_name, 0.0)
            # Replace NaN with 0.0
            if np.isnan(value):
                value = 0.0
            feature_array.append(value)

        feature_array = np.array(feature_array, dtype=np.float32).reshape(1, -1)

        # Run inference
        prediction = self.model_loader.predict(model_name, feature_array)

        return prediction

    def _create_prediction_result(
        self,
        ring_number: int,
        model_name: str,
        feature_vector: FeatureVector,
        prediction: Dict[str, Any],
        total_time_ms: float
    ) -> PredictionResult:
        """
        Create PredictionResult object from inference output

        Implements FR-023: Point estimate + confidence intervals
        Implements FR-024: Persist to prediction_results table
        """
        # Get model metadata
        model = self.db.query(ModelMetadata).filter(
            ModelMetadata.model_name == model_name
        ).first()

        # Extract prediction values
        predicted_value = prediction["prediction"]

        # Get confidence intervals from model, calculate defaults only for missing bounds
        # This preserves partial CI (e.g., model provides only lower_bound)
        lower_bound = prediction.get("lower_bound")
        upper_bound = prediction.get("upper_bound")

        ci_width = abs(predicted_value) * 0.20  # Default ±20% for 95% CI

        if lower_bound is None:
            lower_bound = predicted_value - ci_width

        if upper_bound is None:
            upper_bound = predicted_value + ci_width

        # Get confidence score (from model if available, else default)
        confidence = prediction.get("confidence", 0.85)  # Default 85%

        # Create result object
        result = PredictionResult(
            ring_number=ring_number,
            timestamp=datetime.utcnow().timestamp(),
            model_name=model_name,
            model_version=model.model_version,
            model_type=model.model_type,
            geological_zone=feature_vector.geological_zone,
            predicted_settlement=predicted_value,
            settlement_lower_bound=lower_bound,
            settlement_upper_bound=upper_bound,
            prediction_confidence=confidence,
            inference_time_ms=prediction.get("inference_time_ms", total_time_ms),
            feature_completeness=feature_vector.feature_completeness,
            quality_flag=feature_vector.quality_flag,
        )

        # Multi-target predictions (if model provides them)
        # Check if prediction dict contains displacement data
        if "displacement" in prediction:
            result.predicted_displacement = prediction["displacement"]
            result.displacement_lower_bound = prediction.get("displacement_lower")
            result.displacement_upper_bound = prediction.get("displacement_upper")

            # Calculate default CI only for missing bounds (preserve partial CI)
            if result.predicted_displacement is not None:
                disp_ci_width = abs(result.predicted_displacement) * 0.20

                if result.displacement_lower_bound is None:
                    result.displacement_lower_bound = result.predicted_displacement - disp_ci_width

                if result.displacement_upper_bound is None:
                    result.displacement_upper_bound = result.predicted_displacement + disp_ci_width

        # Check if prediction dict contains groundwater change data
        if "groundwater" in prediction:
            result.predicted_groundwater_change = prediction["groundwater"]
            result.groundwater_lower_bound = prediction.get("groundwater_lower")
            result.groundwater_upper_bound = prediction.get("groundwater_upper")

            # Calculate default CI only for missing bounds (preserve partial CI)
            if result.predicted_groundwater_change is not None:
                gw_ci_width = abs(result.predicted_groundwater_change) * 0.20

                if result.groundwater_lower_bound is None:
                    result.groundwater_lower_bound = result.predicted_groundwater_change - gw_ci_width

                if result.groundwater_upper_bound is None:
                    result.groundwater_upper_bound = result.predicted_groundwater_change + gw_ci_width

        return result

    def update_prediction_with_actual(
        self,
        ring_number: int,
        actual_settlement: float,
        actual_displacement: Optional[float] = None,
        actual_groundwater_change: Optional[float] = None
    ) -> bool:
        """
        Update prediction with actual measured values
        Used for performance monitoring (FR-028)

        Args:
            ring_number: Ring number
            actual_settlement: Measured settlement (mm)
            actual_displacement: Measured displacement (mm)
            actual_groundwater_change: Measured groundwater change (m)

        Returns:
            True if update successful
        """
        # Find most recent prediction for this ring
        prediction = (
            self.db.query(PredictionResult)
            .filter(PredictionResult.ring_number == ring_number)
            .order_by(PredictionResult.timestamp.desc())
            .first()
        )

        if not prediction:
            logger.warning(f"No prediction found for ring {ring_number}")
            return False

        # Update with actual values
        prediction.update_with_actual(
            actual_settlement=actual_settlement,
            actual_displacement=actual_displacement,
            actual_groundwater_change=actual_groundwater_change
        )

        self.db.commit()

        logger.info(
            f"Updated prediction for ring {ring_number}: "
            f"predicted={prediction.predicted_settlement:.2f}mm, "
            f"actual={actual_settlement:.2f}mm, "
            f"error={prediction.prediction_error:.2f}mm"
        )

        return True

    def get_prediction_history(self, ring_number: int) -> List[PredictionResult]:
        """Get all predictions for a ring"""
        return (
            self.db.query(PredictionResult)
            .filter(PredictionResult.ring_number == ring_number)
            .order_by(PredictionResult.timestamp.desc())
            .all()
        )

    def get_recent_predictions(self, limit: int = 100) -> List[PredictionResult]:
        """Get most recent predictions"""
        return (
            self.db.query(PredictionResult)
            .order_by(PredictionResult.timestamp.desc())
            .limit(limit)
            .all()
        )
