"""
T052: Attitude Log Model
Represents guidance system data (pitch, roll, yaw, deviations)
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, Float, String, Index
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class AttitudeLog(Base):
    """
    Attitude/guidance system data log entry
    Stores shield machine orientation and position deviations
    """

    __tablename__ = "attitude_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Float, nullable=False, index=True)
    ring_number = Column(Integer, nullable=True, index=True)
    pitch = Column(Float, nullable=True)  # degrees
    roll = Column(Float, nullable=True)  # degrees
    yaw = Column(Float, nullable=True)  # degrees
    horizontal_deviation = Column(Float, nullable=True)  # mm from design
    vertical_deviation = Column(Float, nullable=True)  # mm from design
    source_id = Column(String(50), nullable=False)
    data_quality_flag = Column(String(20), default="raw")
    created_at = Column(Float, default=lambda: datetime.utcnow().timestamp())

    __table_args__ = (Index("idx_attitude_ring", "ring_number"),)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "ring_number": self.ring_number,
            "pitch": self.pitch,
            "roll": self.roll,
            "yaw": self.yaw,
            "horizontal_deviation": self.horizontal_deviation,
            "vertical_deviation": self.vertical_deviation,
            "source_id": self.source_id,
            "data_quality_flag": self.data_quality_flag,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"<AttitudeLog(id={self.id}, ring={self.ring_number}, "
            f"h_dev={self.horizontal_deviation}, v_dev={self.vertical_deviation})>"
        )
