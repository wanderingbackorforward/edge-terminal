"""
Model Metadata Models
Track deployed models and their performance on edge device
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
import json
from sqlalchemy import Column, Integer, Float, String, Index, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class ModelMetadata(Base):
    """
    Metadata for deployed ML models on edge device
    Local replica of cloud model registry
    """

    __tablename__ = "model_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(100), unique=True, nullable=False)
    model_version = Column(String(20), nullable=False)
    model_type = Column(String(20), nullable=False)  # lightgbm, xgboost, lstm, ensemble

    # Model Artifact
    onnx_path = Column(String(255), nullable=False)
    onnx_checksum = Column(String(64))  # SHA256
    model_size_bytes = Column(Integer)

    # Training Metadata
    training_date = Column(Float)  # Unix timestamp
    training_data_range = Column(String(100))  # e.g., 'rings_1-500'
    training_project_id = Column(String(50))

    # Geological Context
    geological_zone = Column(String(50))  # soft_clay, sand_silt, transition, all

    # Validation Metrics
    validation_r2 = Column(Float)
    validation_rmse = Column(Float)  # mm
    validation_mae = Column(Float)  # mm

    # Feature Configuration
    feature_list = Column(String(1000))  # JSON array
    feature_engineering_version = Column(String(20))

    # Output Format Configuration
    output_format_version = Column(String(20), default="v2_confidence")
    # v1_lower_bound: [settlement, lower_bound] (legacy)
    # v2_confidence: [settlement, confidence] (new)
    # Only applies to 2-output models; ignored for other output counts

    # Hyperparameters
    hyperparameters = Column(String(2000))  # JSON object

    # Deployment Status
    deployment_status = Column(String(20), default="staged")  # staged, active, retired, failed
    deployed_at = Column(Float)
    retired_at = Column(Float)

    # Edge-Specific Metadata
    load_time_seconds = Column(Float)
    avg_inference_time_ms = Column(Float)

    created_at = Column(Float, default=lambda: datetime.utcnow().timestamp())
    updated_at = Column(Float, default=lambda: datetime.utcnow().timestamp())

    __table_args__ = (
        Index("idx_model_metadata_status", "deployment_status"),
        Index("idx_model_metadata_zone", "geological_zone"),
    )

    def get_feature_list(self) -> List[str]:
        """Parse feature_list JSON to Python list"""
        if self.feature_list:
            return json.loads(self.feature_list)
        return []

    def set_feature_list(self, features: List[str]):
        """Serialize feature list to JSON"""
        self.feature_list = json.dumps(features)

    def get_hyperparameters(self) -> Dict[str, Any]:
        """Parse hyperparameters JSON to Python dict"""
        if self.hyperparameters:
            return json.loads(self.hyperparameters)
        return {}

    def set_hyperparameters(self, params: Dict[str, Any]):
        """Serialize hyperparameters to JSON"""
        self.hyperparameters = json.dumps(params)

    def activate(self):
        """Mark model as active"""
        self.deployment_status = "active"
        self.deployed_at = datetime.utcnow().timestamp()
        self.updated_at = datetime.utcnow().timestamp()

    def retire(self):
        """Mark model as retired"""
        self.deployment_status = "retired"
        self.retired_at = datetime.utcnow().timestamp()
        self.updated_at = datetime.utcnow().timestamp()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "model_type": self.model_type,
            "onnx_path": self.onnx_path,
            "geological_zone": self.geological_zone,
            "validation_r2": self.validation_r2,
            "validation_rmse": self.validation_rmse,
            "validation_mae": self.validation_mae,
            "deployment_status": self.deployment_status,
            "deployed_at": self.deployed_at,
            "training_date": self.training_date,
            "training_data_range": self.training_data_range,
        }

    def __repr__(self) -> str:
        return (
            f"<ModelMetadata(name={self.model_name}, version={self.model_version}, "
            f"status={self.deployment_status}, R²={self.validation_r2:.3f})>"
        )


class ModelPerformanceMetric(Base):
    """
    Performance metrics for deployed models
    Tracks accuracy over time and detects concept drift
    """

    __tablename__ = "model_performance_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(100), ForeignKey("model_metadata.model_name"), nullable=False)
    evaluation_date = Column(Float, default=lambda: datetime.utcnow().timestamp())

    # Evaluation Window
    evaluation_data_range = Column(String(100))  # e.g., 'rings_501-550'
    num_predictions = Column(Integer)

    # Accuracy Metrics
    r2_score = Column(Float)
    rmse = Column(Float)  # mm
    mae = Column(Float)  # mm
    mape = Column(Float)  # Mean absolute percentage error

    # Confidence Calibration
    confidence_coverage = Column(Float)  # Fraction within CI

    # Drift Detection
    drift_detected = Column(Integer, default=0)  # Boolean
    drift_severity = Column(String(20))  # none, minor, moderate, severe
    baseline_rmse = Column(Float)  # Original validation RMSE
    rmse_increase_percent = Column(Float)  # % increase

    # Trigger Information
    triggered_retraining = Column(Integer, default=0)  # Boolean
    retraining_reason = Column(String(100))

    created_at = Column(Float, default=lambda: datetime.utcnow().timestamp())

    __table_args__ = (
        Index("idx_model_performance_date", "evaluation_date"),
        Index("idx_model_performance_drift", "drift_detected"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "model_name": self.model_name,
            "evaluation_date": self.evaluation_date,
            "evaluation_data_range": self.evaluation_data_range,
            "num_predictions": self.num_predictions,
            "r2_score": self.r2_score,
            "rmse": self.rmse,
            "mae": self.mae,
            "mape": self.mape,
            "confidence_coverage": self.confidence_coverage,
            "drift_detected": bool(self.drift_detected),
            "drift_severity": self.drift_severity,
            "rmse_increase_percent": self.rmse_increase_percent,
            "triggered_retraining": bool(self.triggered_retraining),
            "retraining_reason": self.retraining_reason,
        }

    def __repr__(self) -> str:
        return (
            f"<ModelPerformanceMetric(model={self.model_name}, "
            f"RMSE={self.rmse:.2f}mm, drift={bool(self.drift_detected)})>"
        )
