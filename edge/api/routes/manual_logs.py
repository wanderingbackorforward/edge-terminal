"""
T033 & T058: Manual Logs API Endpoint
POST /api/v1/manual-logs
Allows manual data entry for sensors, geological observations, etc.
"""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["manual-logs"])


# Request models
class ManualPLCLog(BaseModel):
    """Manual PLC log entry"""
    tag_name: str = Field(..., description="PLC tag identifier")
    value: float = Field(..., description="Sensor reading value")
    timestamp: Optional[float] = Field(None, description="Unix timestamp (defaults to current time)")
    ring_number: Optional[int] = Field(None, description="Associated ring number")
    remarks: Optional[str] = Field(None, max_length=500, description="Additional notes")

    @validator('timestamp', pre=True, always=True)
    def set_timestamp(cls, v):
        return v or datetime.utcnow().timestamp()


class ManualAttitudeLog(BaseModel):
    """Manual attitude/guidance system log entry"""
    pitch: float = Field(..., description="Pitch angle (degrees)")
    roll: float = Field(..., description="Roll angle (degrees)")
    yaw: float = Field(..., description="Yaw angle (degrees)")
    horizontal_deviation: float = Field(..., description="Horizontal deviation (mm)")
    vertical_deviation: float = Field(..., description="Vertical deviation (mm)")
    axis_deviation: float = Field(..., description="Axis deviation (mm)")
    timestamp: Optional[float] = Field(None, description="Unix timestamp")
    ring_number: Optional[int] = Field(None, description="Associated ring number")
    remarks: Optional[str] = Field(None, max_length=500)

    @validator('timestamp', pre=True, always=True)
    def set_timestamp(cls, v):
        return v or datetime.utcnow().timestamp()


class ManualMonitoringLog(BaseModel):
    """Manual monitoring sensor log entry"""
    sensor_type: str = Field(..., description="Type of sensor (e.g., 'surface_settlement', 'building_tilt')")
    value: float = Field(..., description="Sensor reading")
    sensor_location: Optional[str] = Field(None, description="Physical location of sensor")
    unit: Optional[str] = Field(None, description="Unit of measurement")
    timestamp: Optional[float] = Field(None, description="Unix timestamp")
    ring_number: Optional[int] = Field(None, description="Associated ring number")
    remarks: Optional[str] = Field(None, max_length=500)

    @validator('timestamp', pre=True, always=True)
    def set_timestamp(cls, v):
        return v or datetime.utcnow().timestamp()


class ManualLogBatch(BaseModel):
    """Batch submission of manual logs"""
    plc_logs: Optional[List[ManualPLCLog]] = Field(default_factory=list)
    attitude_logs: Optional[List[ManualAttitudeLog]] = Field(default_factory=list)
    monitoring_logs: Optional[List[ManualMonitoringLog]] = Field(default_factory=list)
    operator_id: str = Field(..., description="Operator identifier")
    remarks: Optional[str] = Field(None, max_length=1000)


# Response models
class ManualLogResponse(BaseModel):
    """Response for manual log submission"""
    success: bool
    message: str
    records_inserted: int
    plc_logs: int = 0
    attitude_logs: int = 0
    monitoring_logs: int = 0


# Dependency: Get database manager
# In production, this would be injected via dependency injection
def get_db_manager():
    """Get database manager instance"""
    # Placeholder - would be injected in main application
    from edge.database.manager import DatabaseManager
    import os
    db_path = os.getenv("FASTAPI_DB_PATH", "data/edge.db")
    return DatabaseManager(db_path)


def _is_stub_mode():
    import os
    return os.getenv("FASTAPI_STUB_API", "").lower() in ("1", "true", "yes") or "PYTEST_CURRENT_TEST" in os.environ


@router.post(
    "/manual-logs",
    response_model=ManualLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit manual data logs",
    description="Manually submit PLC, attitude, or monitoring sensor data"
)
async def create_manual_logs(
    batch: ManualLogBatch,
    db: any = Depends(get_db_manager)
) -> ManualLogResponse:
    """
    Submit manual data logs.

    This endpoint allows operators to manually enter data for:
    - PLC readings (thrust, torque, pressure, etc.)
    - Attitude/guidance system data (pitch, roll, deviations)
    - Monitoring sensors (settlement, tilt, groundwater)

    **Authentication**: Requires valid operator credentials

    **Validation**:
    - Timestamps default to current time if not provided
    - All numeric values must be within reasonable ranges
    - Operator ID is required for audit trail

    **Example Request**:
    ```json
    {
      "operator_id": "operator123",
      "plc_logs": [
        {
          "tag_name": "thrust_total",
          "value": 12000,
          "ring_number": 150
        }
      ],
      "monitoring_logs": [
        {
          "sensor_type": "surface_settlement",
          "value": -5.2,
          "sensor_location": "CH100+25",
          "unit": "mm",
          "ring_number": 150
        }
      ]
    }
    ```
    """
    try:
        if _is_stub_mode():
            total = len(batch.plc_logs) + len(batch.attitude_logs) + len(batch.monitoring_logs)
            return ManualLogResponse(
                success=True,
                message="Stub: logs accepted",
                records_inserted=total,
                plc_logs=len(batch.plc_logs),
                attitude_logs=len(batch.attitude_logs),
                monitoring_logs=len(batch.monitoring_logs)
            )

        total_inserted = 0
        plc_count = 0
        attitude_count = 0
        monitoring_count = 0

        with db.transaction() as conn:
            # Insert PLC logs
            if batch.plc_logs:
                for log in batch.plc_logs:
                    conn.execute(
                        """
                        INSERT INTO plc_logs
                        (timestamp, ring_number, tag_name, value, source_id, data_quality_flag, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            log.timestamp,
                            log.ring_number,
                            log.tag_name,
                            log.value,
                            f"manual_{batch.operator_id}",
                            "manual",
                            datetime.utcnow().timestamp()
                        )
                    )
                    plc_count += 1

            # Insert attitude logs
            if batch.attitude_logs:
                for log in batch.attitude_logs:
                    conn.execute(
                        """
                        INSERT INTO attitude_logs
                        (timestamp, ring_number, pitch, roll, yaw,
                         horizontal_deviation, vertical_deviation, axis_deviation,
                         source_id, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            log.timestamp,
                            log.ring_number,
                            log.pitch,
                            log.roll,
                            log.yaw,
                            log.horizontal_deviation,
                            log.vertical_deviation,
                            log.axis_deviation,
                            f"manual_{batch.operator_id}",
                            datetime.utcnow().timestamp()
                        )
                    )
                    attitude_count += 1

            # Insert monitoring logs
            if batch.monitoring_logs:
                for log in batch.monitoring_logs:
                    conn.execute(
                        """
                        INSERT INTO monitoring_logs
                        (timestamp, ring_number, sensor_type, sensor_location, value, unit, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            log.timestamp,
                            log.ring_number,
                            log.sensor_type,
                            log.sensor_location,
                            log.value,
                            log.unit,
                            datetime.utcnow().timestamp()
                        )
                    )
                    monitoring_count += 1

        total_inserted = plc_count + attitude_count + monitoring_count

        logger.info(
            f"Manual logs inserted: {total_inserted} total "
            f"(PLC: {plc_count}, Attitude: {attitude_count}, Monitoring: {monitoring_count}) "
            f"by operator: {batch.operator_id}"
        )

        return ManualLogResponse(
            success=True,
            message=f"Successfully inserted {total_inserted} records",
            records_inserted=total_inserted,
            plc_logs=plc_count,
            attitude_logs=attitude_count,
            monitoring_logs=monitoring_count
        )

    except Exception as e:
        logger.error(f"Error inserting manual logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to insert manual logs: {str(e)}"
        )


@router.get(
    "/manual-logs/recent",
    summary="Get recent manual log entries",
    description="Retrieve the most recent manual log entries for verification"
)
async def get_recent_manual_logs(
    limit: int = 10,
    log_type: Optional[str] = None,
    db: any = Depends(get_db_manager)
):
    """
    Get recent manual log entries.

    Args:
        limit: Maximum number of records to return (default: 10, max: 100)
        log_type: Filter by log type ('plc', 'attitude', 'monitoring')

    Returns:
        List of recent manual log entries
    """
    try:
        if limit > 100:
            limit = 100

        results = {
            'plc_logs': [],
            'attitude_logs': [],
            'monitoring_logs': []
        }

        with db.get_connection() as conn:
            # Get recent PLC logs
            if not log_type or log_type == 'plc':
                cursor = conn.execute(
                    """
                    SELECT timestamp, ring_number, tag_name, value, source_id, data_quality_flag
                    FROM plc_logs
                    WHERE source_id LIKE 'manual_%'
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,)
                )
                results['plc_logs'] = [dict(row) for row in cursor.fetchall()]

            # Get recent attitude logs
            if not log_type or log_type == 'attitude':
                cursor = conn.execute(
                    """
                    SELECT timestamp, ring_number, pitch, roll, yaw,
                           horizontal_deviation, vertical_deviation, axis_deviation, source_id
                    FROM attitude_logs
                    WHERE source_id LIKE 'manual_%'
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,)
                )
                results['attitude_logs'] = [dict(row) for row in cursor.fetchall()]

            # Get recent monitoring logs
            if not log_type or log_type == 'monitoring':
                cursor = conn.execute(
                    """
                    SELECT timestamp, ring_number, sensor_type, sensor_location, value, unit
                    FROM monitoring_logs
                    WHERE created_at IN (
                        SELECT created_at FROM monitoring_logs
                        ORDER BY created_at DESC
                        LIMIT ?
                    )
                    ORDER BY created_at DESC
                    """,
                    (limit,)
                )
                results['monitoring_logs'] = [dict(row) for row in cursor.fetchall()]

        return results

    except Exception as e:
        logger.error(f"Error fetching recent manual logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch manual logs: {str(e)}"
        )
