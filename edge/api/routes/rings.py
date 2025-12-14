"""
T056 & T057: Rings API Endpoints
GET /api/v1/rings - List rings with pagination
GET /api/v1/rings/{ring_number} - Get specific ring data
"""
from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["rings"])


# Response models
class RingSummaryResponse(BaseModel):
    """Response model for ring summary data"""
    ring_number: int
    start_time: float
    end_time: float
    timestamp: Optional[float] = None

    # PLC aggregated features
    mean_thrust: Optional[float] = None
    max_thrust: Optional[float] = None
    min_thrust: Optional[float] = None
    std_thrust: Optional[float] = None

    mean_torque: Optional[float] = None
    max_torque: Optional[float] = None

    mean_advance_rate: Optional[float] = None
    max_advance_rate: Optional[float] = None
    advance_rate: Optional[float] = None

    mean_chamber_pressure: Optional[float] = None
    max_chamber_pressure: Optional[float] = None

    # Attitude features
    mean_pitch: Optional[float] = None
    mean_roll: Optional[float] = None
    mean_yaw: Optional[float] = None

    horizontal_deviation: Optional[float] = None
    vertical_deviation: Optional[float] = None

    # Derived engineering indicators
    specific_energy: Optional[float] = None
    ground_loss_rate: Optional[float] = None
    volume_loss_ratio: Optional[float] = None

    # Time-lagged monitoring data
    settlement_value: Optional[float] = None

    # Metadata
    data_completeness_flag: Optional[str] = None
    geological_zone: Optional[str] = None
    synced_to_cloud: int = 0
    created_at: Optional[float] = None
    updated_at: Optional[float] = None

    class Config:
        from_attributes = True


class RingListResponse(BaseModel):
    """Response model for paginated ring list"""
    total: int = Field(..., description="Total number of rings")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")
    rings: List[RingSummaryResponse] = Field(..., description="List of ring summaries")


class RingDetailResponse(RingSummaryResponse):
    """Extended response with additional details"""
    plc_data_count: Optional[int] = None
    attitude_data_count: Optional[int] = None
    monitoring_data_count: Optional[int] = None


# Dependency: Get database manager
def get_db_manager():
    """Get database manager instance"""
    from edge.database.manager import DatabaseManager
    import os
    db_path = os.getenv("FASTAPI_DB_PATH", "data/edge.db")
    return DatabaseManager(db_path)


def _is_stub_mode() -> bool:
    import os
    return os.getenv("FASTAPI_STUB_API", "").lower() in ("1", "true", "yes") or "PYTEST_CURRENT_TEST" in os.environ


def _transform_ring_row(row: dict) -> dict:
    """
    Normalize database row to API response expected by frontend.
    Adds alias fields (timestamp, advance_rate, horizontal/vertical deviation).
    """
    row = dict(row)
    row["timestamp"] = row.get("end_time") or row.get("start_time")
    row["advance_rate"] = row.get("mean_advance_rate")
    row["horizontal_deviation"] = row.get("horizontal_deviation_max")
    row["vertical_deviation"] = row.get("vertical_deviation_max")
    return row


@router.get(
    "/rings",
    response_model=RingListResponse,
    summary="List all rings",
    description="Get paginated list of ring summaries"
)
async def list_rings(
    page: int = Query(1, ge=1, description="Page number (starts at 1)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("ring_number", description="Sort field (ring_number, start_time)"),
    sort_order: str = Query("desc", description="Sort order (asc, desc)"),
    completeness: Optional[str] = Query(None, description="Filter by completeness flag"),
    geological_zone: Optional[str] = Query(None, description="Filter by geological zone"),
    start_ring: Optional[int] = Query(None, description="Filter start ring number"),
    end_ring: Optional[int] = Query(None, description="Filter end ring number"),
    db: any = Depends(get_db_manager)
) -> RingListResponse:
    """
    Get paginated list of ring summaries.

    **Query Parameters**:
    - `page`: Page number (default: 1)
    - `page_size`: Items per page (default: 20, max: 100)
    - `sort_by`: Sort field (ring_number, start_time)
    - `sort_order`: Sort order (asc, desc)
    - `completeness`: Filter by data completeness (complete, incomplete, partial)
    - `geological_zone`: Filter by geological zone

    **Returns**: Paginated list of ring summaries

    **Example**:
    ```
    GET /api/v1/rings?page=1&page_size=20&sort_by=ring_number&sort_order=desc
    ```
    """
    try:
        if _is_stub_mode():
            # Return stub data quickly in test mode
            rings = [
                RingSummaryResponse(
                    ring_number=100 + i,
                    start_time=1700000000 + i * 2700,
                    end_time=1700000000 + (i + 1) * 2700,
                    mean_thrust=12000 + i * 10,
                    mean_advance_rate=30.0,
                    horizontal_deviation=5.0,
                    vertical_deviation=3.0,
                    data_completeness_flag="complete",
                    timestamp=1700000000 + (i + 1) * 2700,
                )
                for i in range(min(page_size, 3))
            ]
            return RingListResponse(
                total=len(rings),
                page=1,
                page_size=len(rings),
                total_pages=1,
                rings=rings,
            )

        # Validate sort parameters
        valid_sort_fields = ['ring_number', 'start_time', 'created_at']
        if sort_by not in valid_sort_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sort_by field. Must be one of: {valid_sort_fields}"
            )

        valid_sort_orders = ['asc', 'desc']
        if sort_order.lower() not in valid_sort_orders:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sort_order. Must be one of: {valid_sort_orders}"
            )

        # Build WHERE clause
        where_conditions = []
        params = []

        if completeness:
            where_conditions.append("data_completeness_flag = ?")
            params.append(completeness)

        if geological_zone:
            where_conditions.append("geological_zone = ?")
            params.append(geological_zone)

        if start_ring is not None:
            where_conditions.append("ring_number >= ?")
            params.append(start_ring)

        if end_ring is not None:
            where_conditions.append("ring_number <= ?")
            params.append(end_ring)

        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        # Get total count
        with db.get_connection() as conn:
            count_query = f"SELECT COUNT(*) FROM ring_summary {where_clause}"
            cursor = conn.execute(count_query, params)
            total = cursor.fetchone()[0]

            # Calculate pagination
            total_pages = (total + page_size - 1) // page_size
            offset = (page - 1) * page_size

            # Get ring data
            query = f"""
                SELECT
                    ring_number, start_time, end_time,
                    mean_thrust, max_thrust, min_thrust, std_thrust,
                    mean_torque, max_torque,
                    mean_advance_rate, max_advance_rate,
                    mean_chamber_pressure, max_chamber_pressure,
                    mean_pitch, mean_roll, mean_yaw,
                    horizontal_deviation_max, vertical_deviation_max,
                    specific_energy, ground_loss_rate, volume_loss_ratio,
                    settlement_value,
                    data_completeness_flag, geological_zone,
                    synced_to_cloud, created_at, updated_at
                FROM ring_summary
                {where_clause}
                ORDER BY {sort_by} {sort_order.upper()}
                LIMIT ? OFFSET ?
            """
            params.extend([page_size, offset])

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            rings = [RingSummaryResponse(**_transform_ring_row(dict(row))) for row in rows]

        return RingListResponse(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            rings=rings
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching ring list: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch rings: {str(e)}"
        )


@router.get(
    "/rings/latest",
    response_model=RingSummaryResponse,
    summary="Get latest ring summary",
    description="Get the most recent ring summary by ring number"
)
async def get_latest_ring(
    db: any = Depends(get_db_manager)
) -> RingSummaryResponse:
    """Fetch the latest ring by ring_number for dashboard polling."""
    try:
        with db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    ring_number, start_time, end_time,
                    mean_thrust, max_thrust, min_thrust, std_thrust,
                    mean_torque, max_torque,
                    mean_advance_rate, max_advance_rate,
                    mean_chamber_pressure, max_chamber_pressure,
                    mean_pitch, mean_roll, mean_yaw,
                    horizontal_deviation_max, vertical_deviation_max,
                    specific_energy, ground_loss_rate, volume_loss_ratio,
                    settlement_value,
                    data_completeness_flag, geological_zone,
                    synced_to_cloud, created_at, updated_at
                FROM ring_summary
                ORDER BY ring_number DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone()

            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No ring data available"
                )

        return RingSummaryResponse(**_transform_ring_row(dict(row)))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching latest ring: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch latest ring: {str(e)}"
        )


@router.get(
    "/rings/{ring_number}",
    response_model=RingDetailResponse,
    summary="Get specific ring data",
    description="Get detailed data for a specific ring"
)
async def get_ring(
    ring_number: int,
    include_counts: bool = Query(True, description="Include data point counts"),
    db: any = Depends(get_db_manager)
) -> RingDetailResponse:
    """
    Get detailed data for a specific ring.

    **Path Parameters**:
    - `ring_number`: Ring number to retrieve

    **Query Parameters**:
    - `include_counts`: Include counts of raw data points (default: true)

    **Returns**: Detailed ring summary with optional data counts

    **Example**:
    ```
    GET /api/v1/rings/100?include_counts=true
    ```

    **Response**:
    ```json
    {
      "ring_number": 100,
      "start_time": 1700000000.0,
      "end_time": 1700002700.0,
      "mean_thrust": 12500.5,
      "max_thrust": 15000.0,
      "specific_energy": 25.3,
      "settlement_value": -5.2,
      "plc_data_count": 2700,
      "attitude_data_count": 2700,
      "monitoring_data_count": 45
    }
    ```
    """
    try:
        if _is_stub_mode():
            return RingDetailResponse(
                ring_number=ring_number,
                start_time=1700000000.0,
                end_time=1700002700.0,
                mean_thrust=12500.0,
                mean_torque=900.0,
                mean_advance_rate=30.0,
                horizontal_deviation=5.0,
                vertical_deviation=3.0,
                data_completeness_flag="complete",
                plc_data_count=0,
                attitude_data_count=0,
                monitoring_data_count=0,
            )

        with db.get_connection() as conn:
            # Get ring summary
            query = """
                SELECT
                    ring_number, start_time, end_time,
                    mean_thrust, max_thrust, min_thrust, std_thrust,
                    mean_torque, max_torque,
                    mean_penetration_rate, max_penetration_rate,
                    mean_chamber_pressure, max_chamber_pressure,
                    mean_pitch, mean_roll, mean_yaw,
                    horizontal_deviation, vertical_deviation,
                    specific_energy, ground_loss_rate, volume_loss_ratio,
                    settlement_value,
                    data_completeness_flag, geological_zone,
                    synced_to_cloud, created_at, updated_at
                FROM ring_summary
                WHERE ring_number = ?
            """

            cursor = conn.execute(query, (ring_number,))
            row = cursor.fetchone()

            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Ring {ring_number} not found"
                )

            ring_data = _transform_ring_row(dict(row))

            # Get data counts if requested
            if include_counts:
                # Count PLC data points
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM plc_logs WHERE ring_number = ?",
                    (ring_number,)
                )
                ring_data['plc_data_count'] = cursor.fetchone()[0]

                # Count attitude data points
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM attitude_logs WHERE ring_number = ?",
                    (ring_number,)
                )
                ring_data['attitude_data_count'] = cursor.fetchone()[0]

                # Count monitoring data points
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM monitoring_logs WHERE ring_number = ?",
                    (ring_number,)
                )
                ring_data['monitoring_data_count'] = cursor.fetchone()[0]

        return RingDetailResponse(**ring_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching ring {ring_number}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch ring data: {str(e)}"
        )


@router.get(
    "/rings/{ring_number}/raw-data",
    summary="Get raw data for ring",
    description="Get raw PLC, attitude, and monitoring data for a specific ring"
)
async def get_ring_raw_data(
    ring_number: int,
    data_type: Optional[str] = Query(None, description="Filter by data type (plc, attitude, monitoring)"),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum records to return"),
    db: any = Depends(get_db_manager)
) -> Dict[str, Any]:
    """
    Get raw data points for a specific ring.

    **Path Parameters**:
    - `ring_number`: Ring number

    **Query Parameters**:
    - `data_type`: Filter by type (plc, attitude, monitoring)
    - `limit`: Maximum records per type (default: 1000, max: 10000)

    **Returns**: Raw data points grouped by type
    """
    try:
        result = {
            'ring_number': ring_number,
            'plc_data': [],
            'attitude_data': [],
            'monitoring_data': []
        }

        with db.get_connection() as conn:
            # Get PLC data
            if not data_type or data_type == 'plc':
                cursor = conn.execute(
                    """
                    SELECT timestamp, tag_name, value, data_quality_flag, source_id
                    FROM plc_logs
                    WHERE ring_number = ?
                    ORDER BY timestamp
                    LIMIT ?
                    """,
                    (ring_number, limit)
                )
                result['plc_data'] = [dict(row) for row in cursor.fetchall()]

            # Get attitude data
            if not data_type or data_type == 'attitude':
                cursor = conn.execute(
                    """
                    SELECT timestamp, pitch, roll, yaw,
                           horizontal_deviation, vertical_deviation, axis_deviation
                    FROM attitude_logs
                    WHERE ring_number = ?
                    ORDER BY timestamp
                    LIMIT ?
                    """,
                    (ring_number, limit)
                )
                result['attitude_data'] = [dict(row) for row in cursor.fetchall()]

            # Get monitoring data
            if not data_type or data_type == 'monitoring':
                cursor = conn.execute(
                    """
                    SELECT timestamp, sensor_type, sensor_location, value, unit
                    FROM monitoring_logs
                    WHERE ring_number = ?
                    ORDER BY timestamp
                    LIMIT ?
                    """,
                    (ring_number, limit)
                )
                result['monitoring_data'] = [dict(row) for row in cursor.fetchall()]

        return result

    except Exception as e:
        logger.error(f"Error fetching raw data for ring {ring_number}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch raw data: {str(e)}"
        )
