"""
T051: PLC Log Model
Represents high-frequency PLC data from shield machine
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, Float, String, Index
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class PLCLog(Base):
    """
    PLC data log entry
    Stores ~100 tags @ 1Hz = 8.64M readings/day
    """

    __tablename__ = "plc_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Float, nullable=False, index=True)  # Unix timestamp
    ring_number = Column(Integer, nullable=True, index=True)
    tag_name = Column(String(100), nullable=False)
    value = Column(Float, nullable=True)
    source_id = Column(String(50), nullable=False)
    data_quality_flag = Column(String(20), default="raw")  # raw, interpolated, calibrated, rejected
    created_at = Column(Float, default=lambda: datetime.utcnow().timestamp())

    __table_args__ = (
        Index("idx_plc_tag_timestamp", "tag_name", "timestamp"),
        Index("idx_plc_quality", "data_quality_flag"),
        Index("idx_plc_ring_tag", "ring_number", "tag_name"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "ring_number": self.ring_number,
            "tag_name": self.tag_name,
            "value": self.value,
            "source_id": self.source_id,
            "data_quality_flag": self.data_quality_flag,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"<PLCLog(id={self.id}, tag={self.tag_name}, "
            f"value={self.value}, ring={self.ring_number})>"
        )
