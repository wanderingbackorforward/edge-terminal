"""
ONNX Model Loader and Manager
Loads and manages ONNX models for edge inference
Implements FR-002, FR-020, FR-021
"""
from __future__ import annotations

import os
import time
import hashlib
import numpy as np
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

try:
    import onnxruntime as ort
except ImportError:
    ort = None
    logging.warning("onnxruntime not installed. ONNX inference will not be available.")

from edge.models.model_metadata import ModelMetadata

logger = logging.getLogger(__name__)


class ONNXModelLoader:
    """
    Loads and manages ONNX models for low-latency edge inference

    Features:
    - Load ONNX models with integrity verification
    - Manage model lifecycle (load, activate, retire)
    - Track loading time and inference statistics
    - Support multiple model instances
    """

    def __init__(self, models_dir: str = "edge/models_onnx"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # Active inference sessions
        self.sessions: Dict[str, ort.InferenceSession] = {}

        # Model metadata cache
        self.metadata_cache: Dict[str, ModelMetadata] = {}

        # Performance tracking
        self.inference_times: Dict[str, List[float]] = {}

        if ort is None:
            logger.error("onnxruntime not installed. Install with: pip install onnxruntime")

    def load_model(
        self,
        model_metadata: ModelMetadata,
        verify_checksum: bool = True,
        warm_up: bool = True
    ) -> bool:
        """
        Load ONNX model from file and prepare for inference

        Args:
            model_metadata: Model metadata with onnx_path and checksum
            verify_checksum: Whether to verify SHA256 checksum
            warm_up: Whether to run warm-up inference

        Returns:
            True if successful, False otherwise

        Implements FR-021: Model loading within 5 seconds
        """
        if ort is None:
            logger.error("Cannot load model: onnxruntime not installed")
            return False

        start_time = time.time()

        try:
            # Resolve model path
            model_path = Path(model_metadata.onnx_path)
            if not model_path.is_absolute():
                model_path = self.models_dir / model_path

            if not model_path.exists():
                logger.error(f"Model file not found: {model_path}")
                return False

            # Verify checksum if requested
            if verify_checksum and model_metadata.onnx_checksum:
                if not self._verify_checksum(model_path, model_metadata.onnx_checksum):
                    logger.error(f"Checksum verification failed for {model_path}")
                    return False

            # Load ONNX model
            logger.info(f"Loading ONNX model: {model_metadata.model_name} from {model_path}")

            # Configure session options for edge device
            session_options = ort.SessionOptions()
            session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            session_options.intra_op_num_threads = 2  # Limit threads on edge device
            session_options.inter_op_num_threads = 2

            # Create inference session
            session = ort.InferenceSession(str(model_path), session_options)

            # Store session
            self.sessions[model_metadata.model_name] = session
            self.metadata_cache[model_metadata.model_name] = model_metadata
            self.inference_times[model_metadata.model_name] = []

            load_time = time.time() - start_time

            # Update metadata with load time
            model_metadata.load_time_seconds = load_time
            model_metadata.model_size_bytes = model_path.stat().st_size

            logger.info(
                f"Model {model_metadata.model_name} loaded successfully in {load_time:.2f}s "
                f"({model_metadata.model_size_bytes / 1024 / 1024:.1f} MB)"
            )

            # Warm up with dummy inference
            if warm_up:
                self._warm_up_model(model_metadata.model_name, session)

            # Check if load time meets requirement (5 seconds)
            if load_time > 5.0:
                logger.warning(f"Load time {load_time:.2f}s exceeds 5s requirement")

            return True

        except Exception as e:
            logger.error(f"Failed to load model {model_metadata.model_name}: {e}", exc_info=True)
            return False

    def predict(
        self,
        model_name: str,
        feature_vector: np.ndarray
    ) -> Dict[str, Any]:
        """
        Run inference using loaded ONNX model

        Args:
            model_name: Name of the model to use
            feature_vector: Input features as numpy array (shape: [1, n_features])

        Returns:
            Dictionary with predictions and metadata

        Implements FR-022: Inference within 10ms (p99)
        """
        if model_name not in self.sessions:
            raise ValueError(f"Model {model_name} not loaded")

        session = self.sessions[model_name]
        start_time = time.perf_counter()

        try:
            # Get input/output names
            input_name = session.get_inputs()[0].name
            output_names = [output.name for output in session.get_outputs()]

            # Ensure correct shape
            if feature_vector.ndim == 1:
                feature_vector = feature_vector.reshape(1, -1)

            # Run inference
            outputs = session.run(output_names, {input_name: feature_vector.astype(np.float32)})

            # Calculate inference time
            inference_time_ms = (time.perf_counter() - start_time) * 1000

            # Track inference times for performance monitoring
            self.inference_times[model_name].append(inference_time_ms)

            # Keep only last 1000 measurements
            if len(self.inference_times[model_name]) > 1000:
                self.inference_times[model_name] = self.inference_times[model_name][-1000:]

            # Update average inference time in metadata
            if model_name in self.metadata_cache:
                self.metadata_cache[model_name].avg_inference_time_ms = np.mean(
                    self.inference_times[model_name]
                )

            # Parse outputs based on model output count
            result = {
                "inference_time_ms": inference_time_ms,
            }

            num_outputs = len(outputs)

            # Single-target models (settlement only)
            if num_outputs == 1:
                # 1 output: [settlement]
                result["prediction"] = float(outputs[0][0, 0])

            elif num_outputs == 2:
                # 2 outputs: Format depends on output_format_version
                result["prediction"] = float(outputs[0][0, 0])
                second_value = float(outputs[1][0, 0])

                # Check metadata for format version (NULL-safe)
                model_meta = self.metadata_cache.get(model_name)
                format_version = model_meta.output_format_version if model_meta else None

                if format_version == 'v2_confidence':
                    # New format: [settlement, confidence]
                    result["confidence"] = second_value
                else:
                    # Legacy format (v1_lower_bound or NULL): [settlement, lower_bound]
                    result["lower_bound"] = second_value

                    # Warn if format not explicitly set (helps identify models needing migration)
                    if format_version is None:
                        logger.warning(
                            f"Model {model_name} has 2 outputs but no output_format_version in metadata. "
                            f"Defaulting to legacy 'v1_lower_bound' format [settlement, lower_bound]. "
                            f"If this model outputs confidence scores, please update model_metadata "
                            f"SET output_format_version='v2_confidence' WHERE model_name='{model_name}'."
                        )

            elif num_outputs == 3:
                # 3 outputs: [settlement, lower, upper]
                result["prediction"] = float(outputs[0][0, 0])
                result["lower_bound"] = float(outputs[1][0, 0])
                result["upper_bound"] = float(outputs[2][0, 0])

            elif num_outputs == 4:
                # 4 outputs: [settlement, confidence, lower, upper]
                result["prediction"] = float(outputs[0][0, 0])
                result["confidence"] = float(outputs[1][0, 0])
                result["lower_bound"] = float(outputs[2][0, 0])
                result["upper_bound"] = float(outputs[3][0, 0])

            # Multi-target models
            elif num_outputs == 6:
                # 6 outputs: [settlement, lower, upper, displacement, displacement_lower, displacement_upper]
                result["prediction"] = float(outputs[0][0, 0])
                result["lower_bound"] = float(outputs[1][0, 0])
                result["upper_bound"] = float(outputs[2][0, 0])

                result["displacement"] = float(outputs[3][0, 0])
                result["displacement_lower"] = float(outputs[4][0, 0])
                result["displacement_upper"] = float(outputs[5][0, 0])

            elif num_outputs == 8:
                # 8 outputs: [settlement, confidence, lower, upper,
                #             displacement, displacement_confidence, displacement_lower, displacement_upper]
                result["prediction"] = float(outputs[0][0, 0])
                result["confidence"] = float(outputs[1][0, 0])
                result["lower_bound"] = float(outputs[2][0, 0])
                result["upper_bound"] = float(outputs[3][0, 0])

                result["displacement"] = float(outputs[4][0, 0])
                result["displacement_confidence"] = float(outputs[5][0, 0])
                result["displacement_lower"] = float(outputs[6][0, 0])
                result["displacement_upper"] = float(outputs[7][0, 0])

            elif num_outputs == 9:
                # 9 outputs: [settlement, lower, upper,
                #             displacement, displacement_lower, displacement_upper,
                #             groundwater, groundwater_lower, groundwater_upper]
                result["prediction"] = float(outputs[0][0, 0])
                result["lower_bound"] = float(outputs[1][0, 0])
                result["upper_bound"] = float(outputs[2][0, 0])

                result["displacement"] = float(outputs[3][0, 0])
                result["displacement_lower"] = float(outputs[4][0, 0])
                result["displacement_upper"] = float(outputs[5][0, 0])

                result["groundwater"] = float(outputs[6][0, 0])
                result["groundwater_lower"] = float(outputs[7][0, 0])
                result["groundwater_upper"] = float(outputs[8][0, 0])

                logger.debug(f"Multi-target prediction: settlement={result['prediction']:.2f}mm, "
                           f"displacement={result['displacement']:.2f}mm, "
                           f"groundwater={result['groundwater']:.2f}m")

            elif num_outputs == 12:
                # 12 outputs: [settlement, confidence, lower, upper,
                #              displacement, displacement_confidence, displacement_lower, displacement_upper,
                #              groundwater, groundwater_confidence, groundwater_lower, groundwater_upper]
                result["prediction"] = float(outputs[0][0, 0])
                result["confidence"] = float(outputs[1][0, 0])
                result["lower_bound"] = float(outputs[2][0, 0])
                result["upper_bound"] = float(outputs[3][0, 0])

                result["displacement"] = float(outputs[4][0, 0])
                result["displacement_confidence"] = float(outputs[5][0, 0])
                result["displacement_lower"] = float(outputs[6][0, 0])
                result["displacement_upper"] = float(outputs[7][0, 0])

                result["groundwater"] = float(outputs[8][0, 0])
                result["groundwater_confidence"] = float(outputs[9][0, 0])
                result["groundwater_lower"] = float(outputs[10][0, 0])
                result["groundwater_upper"] = float(outputs[11][0, 0])

                logger.debug(f"Multi-target prediction with confidence: "
                           f"settlement={result['prediction']:.2f}mm (conf={result['confidence']:.2%}), "
                           f"displacement={result['displacement']:.2f}mm (conf={result['displacement_confidence']:.2%}), "
                           f"groundwater={result['groundwater']:.2f}m (conf={result['groundwater_confidence']:.2%})")

            else:
                # Unsupported output count - fallback to settlement only
                logger.warning(f"Unexpected number of outputs ({num_outputs}). "
                             "Supported: 1-4 (single-target), 6 (2-target), 8 (2-target+conf), "
                             "9 (3-target), 12 (3-target+conf). Using first output as settlement.")
                result["prediction"] = float(outputs[0][0, 0])

            # Log warning if latency exceeds threshold
            if inference_time_ms > 10.0:
                logger.warning(f"Inference time {inference_time_ms:.2f}ms exceeds 10ms target")

            return result

        except Exception as e:
            logger.error(f"Inference failed for model {model_name}: {e}", exc_info=True)
            raise

    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """Get model input/output metadata"""
        if model_name not in self.sessions:
            raise ValueError(f"Model {model_name} not loaded")

        session = self.sessions[model_name]
        inputs = session.get_inputs()
        outputs = session.get_outputs()

        return {
            "model_name": model_name,
            "input_name": inputs[0].name,
            "input_shape": inputs[0].shape,
            "input_type": inputs[0].type,
            "output_names": [o.name for o in outputs],
            "output_shapes": [o.shape for o in outputs],
        }

    def get_performance_stats(self, model_name: str) -> Dict[str, float]:
        """Get inference performance statistics"""
        if model_name not in self.inference_times or not self.inference_times[model_name]:
            return {}

        times = self.inference_times[model_name]

        return {
            "mean_ms": np.mean(times),
            "median_ms": np.median(times),
            "p95_ms": np.percentile(times, 95),
            "p99_ms": np.percentile(times, 99),
            "min_ms": np.min(times),
            "max_ms": np.max(times),
            "num_inferences": len(times),
        }

    def unload_model(self, model_name: str):
        """Unload model from memory"""
        if model_name in self.sessions:
            del self.sessions[model_name]
            logger.info(f"Model {model_name} unloaded")

        if model_name in self.metadata_cache:
            del self.metadata_cache[model_name]

        if model_name in self.inference_times:
            del self.inference_times[model_name]

    def list_loaded_models(self) -> List[str]:
        """Get list of currently loaded models"""
        return list(self.sessions.keys())

    def _verify_checksum(self, file_path: Path, expected_checksum: str) -> bool:
        """Verify SHA256 checksum of model file"""
        sha256 = hashlib.sha256()

        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)

        actual_checksum = sha256.hexdigest()

        if actual_checksum != expected_checksum:
            logger.error(
                f"Checksum mismatch: expected {expected_checksum}, "
                f"got {actual_checksum}"
            )
            return False

        return True

    def _warm_up_model(self, model_name: str, session: ort.InferenceSession):
        """Run warm-up inference to initialize model"""
        try:
            # Get input shape
            input_shape = session.get_inputs()[0].shape

            # Create dummy input (handle dynamic dimensions)
            dummy_shape = [1 if isinstance(d, str) else d for d in input_shape]
            if -1 in dummy_shape:
                dummy_shape = [1 if d == -1 else d for d in dummy_shape]

            dummy_input = np.zeros(dummy_shape, dtype=np.float32)

            input_name = session.get_inputs()[0].name
            _ = session.run(None, {input_name: dummy_input})

            logger.info(f"Model {model_name} warmed up successfully")

        except Exception as e:
            logger.warning(f"Warm-up failed for {model_name}: {e}")


class ModelManager:
    """
    High-level model management
    Handles model selection, activation, and switching
    """

    def __init__(self, db_session, model_loader: ONNXModelLoader):
        self.db = db_session
        self.loader = model_loader
        self.active_models: Dict[str, str] = {}  # zone -> model_name mapping

    def get_active_model_for_zone(self, geological_zone: str) -> Optional[str]:
        """
        Get active model name for a geological zone
        Implements FR-015, FR-017
        """
        # Check cache first
        if geological_zone in self.active_models:
            return self.active_models[geological_zone]

        # Query database for active model
        model = (
            self.db.query(ModelMetadata)
            .filter(
                ModelMetadata.deployment_status == "active",
                ModelMetadata.geological_zone.in_([geological_zone, "all"])
            )
            .order_by(ModelMetadata.deployed_at.desc())
            .first()
        )

        if model:
            self.active_models[geological_zone] = model.model_name
            return model.model_name

        return None

    def activate_model(self, model_name: str) -> bool:
        """
        Activate a model for production use
        Implements FR-007 (model deployment)
        """
        model = self.db.query(ModelMetadata).filter(ModelMetadata.model_name == model_name).first()

        if not model:
            logger.error(f"Model {model_name} not found in database")
            return False

        # Load model if not already loaded
        if model_name not in self.loader.sessions:
            success = self.loader.load_model(model)
            if not success:
                logger.error(f"Failed to load model {model_name}")
                return False

        # Activate in database
        model.activate()
        self.db.commit()

        # Update cache
        zone = model.geological_zone or "all"
        self.active_models[zone] = model_name

        logger.info(f"Model {model_name} activated for zone {zone}")
        return True

    def retire_model(self, model_name: str):
        """Retire a model from production"""
        model = self.db.query(ModelMetadata).filter(ModelMetadata.model_name == model_name).first()

        if model:
            model.retire()
            self.db.commit()

            # Remove from cache
            zone = model.geological_zone or "all"
            if zone in self.active_models and self.active_models[zone] == model_name:
                del self.active_models[zone]

            logger.info(f"Model {model_name} retired")
