"""
T054: Ring Summary Model
Represents aggregated, aligned data for each tunnel ring
This is the core entity for analysis and ML features
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, Float, String, Index
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class RingSummary(Base):
    """
    Aggregated ring data with aligned PLC, attitude, and monitoring data
    One record per ring excavation cycle
    """

    __tablename__ = "ring_summary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ring_number = Column(Integer, unique=True, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)

    # PLC Aggregated Features
    mean_thrust = Column(Float)
    max_thrust = Column(Float)
    min_thrust = Column(Float)
    std_thrust = Column(Float)
    mean_torque = Column(Float)
    max_torque = Column(Float)
    min_torque = Column(Float)
    std_torque = Column(Float)
    mean_chamber_pressure = Column(Float)
    max_chamber_pressure = Column(Float)
    std_chamber_pressure = Column(Float)
    mean_advance_rate = Column(Float)
    max_advance_rate = Column(Float)
    mean_grout_pressure = Column(Float)
    grout_volume = Column(Float)

    # Attitude Aggregated Features
    mean_pitch = Column(Float)
    mean_roll = Column(Float)
    mean_yaw = Column(Float)
    max_pitch = Column(Float)
    max_roll = Column(Float)
    horizontal_deviation_max = Column(Float)
    vertical_deviation_max = Column(Float)

    # Derived Engineering Indicators
    specific_energy = Column(Float)  # kJ/m³
    ground_loss_rate = Column(Float)  # m³
    volume_loss_ratio = Column(Float)  # %

    # Time-Lagged Monitoring Data
    settlement_value = Column(Float)  # mm
    displacement_value = Column(Float)  # mm
    groundwater_level = Column(Float)  # m

    # Metadata
    data_completeness_flag = Column(String(20), default="incomplete")
    geological_zone = Column(String(50))
    synced_to_cloud = Column(Integer, default=0)
    cloud_sync_at = Column(Float, nullable=True)
    created_at = Column(Float, default=lambda: datetime.utcnow().timestamp())
    updated_at = Column(Float, default=lambda: datetime.utcnow().timestamp())

    __table_args__ = (
        Index("idx_ring_number", "ring_number"),
        Index("idx_ring_sync_status", "synced_to_cloud"),
        Index("idx_ring_geological_zone", "geological_zone"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "ring_number": self.ring_number,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "mean_thrust": self.mean_thrust,
            "max_thrust": self.max_thrust,
            "mean_torque": self.mean_torque,
            "mean_chamber_pressure": self.mean_chamber_pressure,
            "mean_advance_rate": self.mean_advance_rate,
            "settlement_value": self.settlement_value,
            "specific_energy": self.specific_energy,
            "ground_loss_rate": self.ground_loss_rate,
            "geological_zone": self.geological_zone,
            "data_completeness_flag": self.data_completeness_flag,
        }

    def __repr__(self) -> str:
        return (
            f"<RingSummary(ring={self.ring_number}, "
            f"thrust={self.mean_thrust}, settlement={self.settlement_value})>"
        )
