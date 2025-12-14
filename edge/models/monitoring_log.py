"""
T053: Monitoring Log Model
Represents sensor data (surface settlement, deep displacement, groundwater)
Variable frequency (hourly to per-ring)
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, Float, String, Index
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class MonitoringLog(Base):
    """
    Monitoring sensor data log entry
    Stores various sensor types with spatial locations
    """

    __tablename__ = "monitoring_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Float, nullable=False, index=True)
    ring_number = Column(Integer, nullable=True, index=True)
    sensor_type = Column(String(50), nullable=False)  # 'surface_settlement', 'deep_displacement', 'groundwater_level'
    sensor_location = Column(String(100), nullable=True)  # Spatial identifier or sensor ID
    value = Column(Float, nullable=True)
    unit = Column(String(20), nullable=True)  # 'mm', 'bar', 'm'
    source_id = Column(String(50), nullable=False)
    data_quality_flag = Column(String(20), default="raw")
    created_at = Column(Float, default=lambda: datetime.utcnow().timestamp())

    __table_args__ = (
        Index("idx_monitoring_type_timestamp", "sensor_type", "timestamp"),
        Index("idx_monitoring_ring_type", "ring_number", "sensor_type"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "ring_number": self.ring_number,
            "sensor_type": self.sensor_type,
            "sensor_location": self.sensor_location,
            "value": self.value,
            "unit": self.unit,
            "source_id": self.source_id,
            "data_quality_flag": self.data_quality_flag,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"<MonitoringLog(id={self.id}, type={self.sensor_type}, "
            f"value={self.value}{self.unit}, ring={self.ring_number})>"
        )
