"""
Prediction Result Model
Stores ML prediction outputs for each ring
"""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, Float, String, Index, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class PredictionResult(Base):
    """
    ML prediction results for settlement and ground response indicators
    One or more records per ring (can have multiple model predictions)
    """

    __tablename__ = "prediction_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ring_number = Column(Integer, ForeignKey("ring_summary.ring_number"), nullable=False)
    timestamp = Column(Float, default=lambda: datetime.utcnow().timestamp())

    # Model Information
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(20), nullable=False)
    model_type = Column(String(20), nullable=False)  # lightgbm, xgboost, lstm
    geological_zone = Column(String(50))

    # Settlement Predictions (Primary Target)
    predicted_settlement = Column(Float)  # mm
    settlement_lower_bound = Column(Float)  # mm (95% CI)
    settlement_upper_bound = Column(Float)  # mm (95% CI)

    # Additional Predictions (Multi-Target)
    predicted_displacement = Column(Float)  # mm
    displacement_lower_bound = Column(Float)
    displacement_upper_bound = Column(Float)

    predicted_groundwater_change = Column(Float)  # m
    groundwater_lower_bound = Column(Float)
    groundwater_upper_bound = Column(Float)

    # Prediction Metadata
    prediction_confidence = Column(Float)  # 0.0-1.0
    inference_time_ms = Column(Float)  # Latency tracking
    feature_completeness = Column(Float)  # 0.0-1.0

    # Quality Flags
    quality_flag = Column(String(50), default="normal")

    # Performance Tracking (filled with lag)
    actual_settlement = Column(Float)  # mm (measured)
    actual_displacement = Column(Float)  # mm
    actual_groundwater_change = Column(Float)  # m
    prediction_error = Column(Float)  # mm (predicted - actual)
    absolute_error = Column(Float)  # mm (|predicted - actual|)

    created_at = Column(Float, default=lambda: datetime.utcnow().timestamp())

    __table_args__ = (
        Index("idx_prediction_ring_number", "ring_number"),
        Index("idx_prediction_timestamp", "timestamp"),
        Index("idx_prediction_model_version", "model_version"),
        Index("idx_prediction_quality_flag", "quality_flag"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "ring_number": self.ring_number,
            "timestamp": self.timestamp,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "model_type": self.model_type,
            "geological_zone": self.geological_zone,
            "predicted_settlement": self.predicted_settlement,
            "settlement_lower_bound": self.settlement_lower_bound,
            "settlement_upper_bound": self.settlement_upper_bound,
            "predicted_displacement": self.predicted_displacement,
            "predicted_groundwater_change": self.predicted_groundwater_change,
            "prediction_confidence": self.prediction_confidence,
            "inference_time_ms": self.inference_time_ms,
            "feature_completeness": self.feature_completeness,
            "quality_flag": self.quality_flag,
            "actual_settlement": self.actual_settlement,
            "prediction_error": self.prediction_error,
            "absolute_error": self.absolute_error,
        }

    def update_with_actual(self, actual_settlement: float,
                          actual_displacement: Optional[float] = None,
                          actual_groundwater_change: Optional[float] = None):
        """Update prediction with actual measured values and calculate errors"""
        self.actual_settlement = actual_settlement
        if actual_displacement is not None:
            self.actual_displacement = actual_displacement
        if actual_groundwater_change is not None:
            self.actual_groundwater_change = actual_groundwater_change

        # Calculate errors
        if self.predicted_settlement is not None:
            self.prediction_error = self.predicted_settlement - actual_settlement
            self.absolute_error = abs(self.prediction_error)

    def __repr__(self) -> str:
        return (
            f"<PredictionResult(ring={self.ring_number}, "
            f"model={self.model_name}, predicted={self.predicted_settlement:.1f}mm, "
            f"actual={self.actual_settlement:.1f}mm if self.actual_settlement else 'pending')>"
        )
