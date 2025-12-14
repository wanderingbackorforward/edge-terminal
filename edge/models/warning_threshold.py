"""
Warning Threshold Model
Configurable thresholds for warning system
Implements Feature 003 - Real-Time Warning System
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, Integer, Float, String, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class WarningThreshold(Base):
    """
    Configurable warning thresholds for indicators

    Supports three warning mechanisms:
    1. Threshold-based: Absolute value comparisons
    2. Rate-based: Change rate vs. historical average
    3. Predictive: Forecasted values approaching thresholds
    """

    __tablename__ = "warning_thresholds"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Indicator Configuration
    indicator_name = Column(String(50), nullable=False)
    indicator_unit = Column(String(20))
    geological_zone = Column(String(50), default="all")

    # Threshold Values (NULL means no limit in that direction)
    attention_lower = Column(Float)
    attention_upper = Column(Float)
    warning_lower = Column(Float)
    warning_upper = Column(Float)
    alarm_lower = Column(Float)
    alarm_upper = Column(Float)

    # Rate-Based Configuration
    rate_window_size = Column(Integer, default=10)
    rate_attention_multiplier = Column(Float, default=2.0)
    rate_warning_multiplier = Column(Float, default=3.0)
    rate_alarm_multiplier = Column(Float, default=5.0)

    # Predictive Configuration
    predictive_enabled = Column(Boolean, default=True)
    predictive_horizon_hours = Column(Float, default=24.0)
    predictive_threshold_percentage = Column(Float, default=0.9)

    # Hysteresis Configuration
    hysteresis_percentage = Column(Float, default=0.05)
    min_duration_seconds = Column(Integer, default=60)

    # Notification Routing
    attention_channels = Column(String, default='["mqtt"]')
    warning_channels = Column(String, default='["mqtt", "email"]')
    alarm_channels = Column(String, default='["mqtt", "email", "sms"]')

    # Status
    enabled = Column(Boolean, default=True)
    description = Column(String)

    # Metadata
    created_at = Column(Float, default=lambda: datetime.utcnow().timestamp())
    updated_at = Column(Float, default=lambda: datetime.utcnow().timestamp())

    __table_args__ = (
        Index("idx_thresholds_indicator_zone", "indicator_name", "geological_zone", unique=True),
        Index("idx_thresholds_indicator", "indicator_name"),
        Index("idx_thresholds_enabled", "enabled"),
        Index("idx_thresholds_zone", "geological_zone"),
    )

    def get_notification_channels(self, level: str) -> List[str]:
        """Get notification channels for specific warning level"""
        if level == "ATTENTION":
            return json.loads(self.attention_channels) if self.attention_channels else []
        elif level == "WARNING":
            return json.loads(self.warning_channels) if self.warning_channels else []
        elif level == "ALARM":
            return json.loads(self.alarm_channels) if self.alarm_channels else []
        return []

    def set_notification_channels(self, level: str, channels: List[str]):
        """Set notification channels for specific warning level"""
        channels_json = json.dumps(channels)
        if level == "ATTENTION":
            self.attention_channels = channels_json
        elif level == "WARNING":
            self.warning_channels = channels_json
        elif level == "ALARM":
            self.alarm_channels = channels_json

    def evaluate_threshold(self, value: float) -> Optional[str]:
        """
        Evaluate value against thresholds

        Returns:
            Warning level ('ATTENTION', 'WARNING', 'ALARM') or None if normal
        """
        # Check ALARM thresholds first (most critical)
        if self.alarm_lower is not None and value < self.alarm_lower:
            return "ALARM"
        if self.alarm_upper is not None and value > self.alarm_upper:
            return "ALARM"

        # Check WARNING thresholds
        if self.warning_lower is not None and value < self.warning_lower:
            return "WARNING"
        if self.warning_upper is not None and value > self.warning_upper:
            return "WARNING"

        # Check ATTENTION thresholds
        if self.attention_lower is not None and value < self.attention_lower:
            return "ATTENTION"
        if self.attention_upper is not None and value > self.attention_upper:
            return "ATTENTION"

        return None

    def get_threshold_value(self, level: str, bound_type: str) -> Optional[float]:
        """
        Get threshold value for specific level and bound type

        Args:
            level: 'ATTENTION', 'WARNING', or 'ALARM'
            bound_type: 'lower' or 'upper'

        Returns:
            Threshold value or None
        """
        if level == "ATTENTION":
            return self.attention_lower if bound_type == "lower" else self.attention_upper
        elif level == "WARNING":
            return self.warning_lower if bound_type == "lower" else self.warning_upper
        elif level == "ALARM":
            return self.alarm_lower if bound_type == "lower" else self.alarm_upper
        return None

    def calculate_hysteresis_bounds(self, threshold: float) -> tuple:
        """
        Calculate hysteresis bounds to prevent oscillation

        Returns:
            (lower_bound, upper_bound) with hysteresis buffer
        """
        buffer = abs(threshold * self.hysteresis_percentage)
        return (threshold - buffer, threshold + buffer)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "indicator_name": self.indicator_name,
            "indicator_unit": self.indicator_unit,
            "geological_zone": self.geological_zone,
            "thresholds": {
                "attention": {"lower": self.attention_lower, "upper": self.attention_upper},
                "warning": {"lower": self.warning_lower, "upper": self.warning_upper},
                "alarm": {"lower": self.alarm_lower, "upper": self.alarm_upper},
            },
            "rate_config": {
                "window_size": self.rate_window_size,
                "multipliers": {
                    "attention": self.rate_attention_multiplier,
                    "warning": self.rate_warning_multiplier,
                    "alarm": self.rate_alarm_multiplier,
                },
            },
            "predictive_enabled": self.predictive_enabled,
            "enabled": self.enabled,
            "description": self.description,
        }
