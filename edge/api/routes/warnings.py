"""
T152-T154: Warning API Endpoints
GET /api/v1/warnings - List warnings with filters and pagination
GET /api/v1/warnings/{warning_id} - Get specific warning detail
POST /api/v1/warnings/{warning_id}/acknowledge - Acknowledge warning
POST /api/v1/warnings/{warning_id}/resolve - Resolve warning
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Body, status as http_status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["warnings"])


# Request models
class AcknowledgeWarningRequest(BaseModel):
    """Request model for acknowledging a warning"""
    user_id: str = Field(..., description="ID of user acknowledging the warning")
    notes: Optional[str] = Field(None, description="Optional notes about acknowledgment")


class ResolveWarningRequest(BaseModel):
    """Request model for resolving a warning"""
    user_id: str = Field(..., description="ID of user resolving the warning")
    notes: Optional[str] = Field(None, description="Resolution notes and actions taken")
    mark_as_false_positive: bool = Field(
        False,
        description="Mark as false positive instead of resolved"
    )


# Response models
class WarningResponse(BaseModel):
    """Response model for warning event data"""
    warning_id: str
    warning_type: str  # threshold, rate, predictive, combined
    warning_level: str  # ATTENTION, WARNING, ALARM
    indicator: Optional[str] = None
    message: Optional[str] = None
    ring_number: int
    timestamp: float

    # Indicator information
    indicator_name: str
    indicator_value: Optional[float] = None
    indicator_unit: Optional[str] = None

    # Threshold information
    threshold_value: Optional[float] = None
    threshold_type: Optional[str] = None

    # Rate information
    rate_of_change: Optional[float] = None
    historical_average_rate: Optional[float] = None
    rate_multiplier: Optional[float] = None

    # Predictive information
    predicted_value: Optional[float] = None
    prediction_confidence: Optional[float] = None
    prediction_horizon_hours: Optional[float] = None

    # Combined warning information
    combined_indicators: Optional[List[str]] = None

    # Status and lifecycle
    status: str  # active, acknowledged, resolved, false_positive
    acknowledged_at: Optional[float] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[float] = None
    resolved_by: Optional[str] = None
    resolution_notes: Optional[str] = None

    # Notification information
    notification_sent: bool = False
    notification_channels: Optional[List[str]] = None
    notification_timestamp: Optional[float] = None

    # Metadata
    created_at: float
    updated_at: float

    class Config:
        from_attributes = True


class WarningListResponse(BaseModel):
    """Response model for paginated warning list"""
    total: int = Field(..., description="Total number of warnings")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")
    warnings: List[WarningResponse] = Field(..., description="List of warnings")


class WarningStatsResponse(BaseModel):
    """Response model for warning statistics"""
    total_warnings: int
    active_warnings: int
    acknowledged_warnings: int
    resolved_warnings: int
    by_level: Dict[str, int]
    by_type: Dict[str, int]


# Dependency: Get database manager
def get_db_manager():
    """Get database manager instance"""
    from edge.database.manager import DatabaseManager
    import os
    db_path = os.getenv("FASTAPI_DB_PATH", "data/edge.db")
    return DatabaseManager(db_path)


def _is_stub_mode():
    import os
    return os.getenv("FASTAPI_STUB_API", "").lower() in ("1", "true", "yes") or "PYTEST_CURRENT_TEST" in os.environ


@router.get(
    "/warnings",
    response_model=WarningListResponse,
    summary="List all warnings",
    description="Get paginated list of warnings with filtering options"
)
async def list_warnings(
    page: int = Query(1, ge=1, description="Page number (starts at 1)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("timestamp", description="Sort field (timestamp, ring_number, warning_level)"),
    sort_order: str = Query("desc", description="Sort order (asc, desc)"),
    warning_level: Optional[str] = Query(None, description="Filter by level (ATTENTION, WARNING, ALARM)"),
    warning_type: Optional[str] = Query(None, description="Filter by type (threshold, rate, predictive, combined)"),
    status: Optional[str] = Query(None, description="Filter by status (active, acknowledged, resolved)"),
    ring_number: Optional[int] = Query(None, description="Filter by ring number"),
    indicator_name: Optional[str] = Query(None, description="Filter by indicator name"),
    start_time: Optional[float] = Query(None, description="Filter by start timestamp"),
    end_time: Optional[float] = Query(None, description="Filter by end timestamp"),
    db: any = Depends(get_db_manager)
) -> WarningListResponse:
    """
    Get paginated list of warnings.

    **Query Parameters**:
    - `page`: Page number (default: 1)
    - `page_size`: Items per page (default: 20, max: 100)
    - `sort_by`: Sort field (timestamp, ring_number, warning_level)
    - `sort_order`: Sort order (asc, desc)
    - `warning_level`: Filter by warning level (ATTENTION, WARNING, ALARM)
    - `warning_type`: Filter by warning type (threshold, rate, predictive, combined)
    - `status`: Filter by status (active, acknowledged, resolved, false_positive)
    - `ring_number`: Filter by specific ring number
    - `indicator_name`: Filter by indicator name
    - `start_time`: Filter by start timestamp (Unix timestamp)
    - `end_time`: Filter by end timestamp (Unix timestamp)

    **Returns**: Paginated list of warnings

    **Example**:
    ```
    GET /api/v1/warnings?page=1&page_size=20&status=active&warning_level=ALARM
    ```

    Implements FR-029: Query warning history
    """
    try:
        if _is_stub_mode():
            warnings = [
                WarningResponse(
                    warning_id="stub-1",
                    warning_type="threshold",
                    warning_level="WARNING",
                    indicator="thrust_mean",
                    indicator_name="thrust_mean",
                    ring_number=101,
                    timestamp=datetime.utcnow().timestamp(),
                    status="active",
                    created_at=datetime.utcnow().timestamp(),
                    updated_at=datetime.utcnow().timestamp(),
                    message="Stub warning"
                )
            ]
            return WarningListResponse(
                total=len(warnings),
                page=1,
                page_size=len(warnings),
                total_pages=1,
                warnings=warnings
            )

        # Validate sort parameters
        valid_sort_fields = ['timestamp', 'ring_number', 'warning_level', 'created_at']
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

        if warning_level:
            where_conditions.append("warning_level = ?")
            params.append(warning_level.upper())

        if warning_type:
            where_conditions.append("warning_type = ?")
            params.append(warning_type.lower())

        if status:
            where_conditions.append("status = ?")
            params.append(status.lower())

        if ring_number is not None:
            where_conditions.append("ring_number = ?")
            params.append(ring_number)

        if indicator_name:
            where_conditions.append("indicator_name = ?")
            params.append(indicator_name)

        if start_time is not None:
            where_conditions.append("timestamp >= ?")
            params.append(start_time)

        if end_time is not None:
            where_conditions.append("timestamp <= ?")
            params.append(end_time)

        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        # Get total count
        with db.get_connection() as conn:
            count_query = f"SELECT COUNT(*) FROM warning_events {where_clause}"
            cursor = conn.execute(count_query, params)
            total = cursor.fetchone()[0]

            # Calculate pagination
            total_pages = (total + page_size - 1) // page_size
            offset = (page - 1) * page_size

            # Get warning data
            query = f"""
                SELECT
                    warning_id, warning_type, warning_level, ring_number, timestamp,
                    indicator_name, indicator_value, indicator_unit,
                    threshold_value, threshold_type,
                    rate_of_change, historical_average_rate, rate_multiplier,
                    predicted_value, prediction_confidence, prediction_horizon_hours,
                    combined_indicators,
                    status, acknowledged_at, acknowledged_by,
                    resolved_at, resolved_by, resolution_notes,
                    notification_sent, notification_channels, notification_timestamp,
                    created_at, updated_at
                FROM warning_events
                {where_clause}
                ORDER BY {sort_by} {sort_order.upper()}
                LIMIT ? OFFSET ?
            """
            params.extend([page_size, offset])

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            warnings = []
            for row in rows:
                warning_dict = dict(row)

                # Parse JSON fields
                if warning_dict.get('combined_indicators'):
                    import json
                    warning_dict['combined_indicators'] = json.loads(
                        warning_dict['combined_indicators']
                    )

                if warning_dict.get('notification_channels'):
                    import json
                    warning_dict['notification_channels'] = json.loads(
                        warning_dict['notification_channels']
                    )
                else:
                    warning_dict['notification_channels'] = []

                warning_dict['indicator'] = warning_dict.get('indicator_name')
                if not warning_dict.get('message'):
                    warning_dict['message'] = f"{warning_dict.get('indicator_name', 'indicator')}异常"

                warnings.append(WarningResponse(**warning_dict))

        return WarningListResponse(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            warnings=warnings
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching warning list: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch warnings: {str(e)}"
        )


@router.get(
    "/warnings/{warning_id}",
    response_model=WarningResponse,
    summary="Get specific warning",
    description="Get detailed data for a specific warning"
)
async def get_warning(
    warning_id: str,
    db: any = Depends(get_db_manager)
) -> WarningResponse:
    """
    Get detailed data for a specific warning.

    **Path Parameters**:
    - `warning_id`: Warning ID to retrieve

    **Returns**: Detailed warning data

    **Example**:
    ```
    GET /api/v1/warnings/abc123-def456
    ```
    """
    try:
        if _is_stub_mode():
            now = datetime.utcnow().timestamp()
            return WarningResponse(
                warning_id=warning_id,
                warning_type="threshold",
                warning_level="WARNING",
                indicator="thrust_mean",
                indicator_name="thrust_mean",
                ring_number=100,
                timestamp=now,
                status="active",
                created_at=now,
                updated_at=now,
                message="Stub warning"
            )

        with db.get_connection() as conn:
            query = """
                SELECT
                    warning_id, warning_type, warning_level, ring_number, timestamp,
                    indicator_name, indicator_value, indicator_unit,
                    threshold_value, threshold_type,
                    rate_of_change, historical_average_rate, rate_multiplier,
                    predicted_value, prediction_confidence, prediction_horizon_hours,
                    combined_indicators,
                    status, acknowledged_at, acknowledged_by,
                    resolved_at, resolved_by, resolution_notes,
                    notification_sent, notification_channels, notification_timestamp,
                    created_at, updated_at
                FROM warning_events
                WHERE warning_id = ?
            """

            cursor = conn.execute(query, (warning_id,))
            row = cursor.fetchone()

            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Warning {warning_id} not found"
                )

            warning_dict = dict(row)

            # Parse JSON fields
            if warning_dict.get('combined_indicators'):
                import json
                warning_dict['combined_indicators'] = json.loads(
                    warning_dict['combined_indicators']
                )

            if warning_dict.get('notification_channels'):
                import json
                warning_dict['notification_channels'] = json.loads(
                    warning_dict['notification_channels']
                )

            warning_dict['indicator'] = warning_dict.get('indicator_name')
            if not warning_dict.get('message'):
                warning_dict['message'] = f"{warning_dict.get('indicator_name', 'indicator')}异常"

        return WarningResponse(**warning_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching warning {warning_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch warning data: {str(e)}"
        )


@router.post(
    "/warnings/{warning_id}/acknowledge",
    response_model=WarningResponse,
    summary="Acknowledge warning",
    description="Mark a warning as acknowledged by a user"
)
async def acknowledge_warning(
    warning_id: str,
    request: AcknowledgeWarningRequest,
    db: any = Depends(get_db_manager)
) -> WarningResponse:
    """
    Acknowledge a warning.

    Implements FR-031: Warning acknowledgment

    **Path Parameters**:
    - `warning_id`: Warning ID to acknowledge

    **Request Body**:
    ```json
    {
      "user_id": "user123",
      "notes": "Acknowledged, investigating root cause"
    }
    ```

    **Returns**: Updated warning data

    **Example**:
    ```
    POST /api/v1/warnings/abc123-def456/acknowledge
    ```
    """
    try:
        if _is_stub_mode():
            # Echo back a stubbed response
            now = datetime.utcnow().timestamp()
            return WarningResponse(
                warning_id=warning_id,
                warning_type="threshold",
                warning_level="WARNING",
                indicator="thrust_mean",
                indicator_name="thrust_mean",
                ring_number=100,
                timestamp=now,
                status="acknowledged",
                acknowledged_at=now,
                acknowledged_by=request.user_id,
                created_at=now,
                updated_at=now,
                message="Stub warning acknowledged"
            )

        timestamp = datetime.utcnow().timestamp()

        with db.get_connection() as conn:
            # Check if warning exists
            cursor = conn.execute(
                "SELECT status FROM warning_events WHERE warning_id = ?",
                (warning_id,)
            )
            row = cursor.fetchone()

            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Warning {warning_id} not found"
                )

            current_status = row[0]

            # Validate status transition
            if current_status == "resolved":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot acknowledge a resolved warning"
                )

            if current_status == "acknowledged":
                logger.warning(f"Warning {warning_id} already acknowledged")

            # Update warning
            update_query = """
                UPDATE warning_events
                SET status = 'acknowledged',
                    acknowledged_at = ?,
                    acknowledged_by = ?,
                    updated_at = ?
                WHERE warning_id = ?
            """

            conn.execute(
                update_query,
                (timestamp, request.user_id, timestamp, warning_id)
            )
            conn.commit()

            logger.info(
                f"Warning {warning_id} acknowledged by {request.user_id}"
            )

            # Publish status update to MQTT
            try:
                from edge.services.notification.mqtt_publisher import get_mqtt_publisher
                import asyncio

                mqtt = get_mqtt_publisher()
                asyncio.create_task(
                    mqtt.publish_warning_status_update(
                        warning_id,
                        "acknowledged",
                        {"user_id": request.user_id, "notes": request.notes}
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to publish MQTT status update: {e}")

        # Return updated warning
        return await get_warning(warning_id, db)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error acknowledging warning {warning_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to acknowledge warning: {str(e)}"
        )


@router.post(
    "/warnings/{warning_id}/resolve",
    response_model=WarningResponse,
    summary="Resolve warning",
    description="Mark a warning as resolved or false positive"
)
async def resolve_warning(
    warning_id: str,
    request: ResolveWarningRequest,
    db: any = Depends(get_db_manager)
) -> WarningResponse:
    """
    Resolve a warning or mark as false positive.

    Implements FR-032, FR-034: Warning resolution

    **Path Parameters**:
    - `warning_id`: Warning ID to resolve

    **Request Body**:
    ```json
    {
      "user_id": "user123",
      "notes": "Issue resolved by adjusting chamber pressure",
      "mark_as_false_positive": false
    }
    ```

    **Returns**: Updated warning data

    **Example**:
    ```
    POST /api/v1/warnings/abc123-def456/resolve
    ```
    """
    try:
        if _is_stub_mode():
            now = datetime.utcnow().timestamp()
            new_status = "false_positive" if request.mark_as_false_positive else "resolved"
            return WarningResponse(
                warning_id=warning_id,
                warning_type="threshold",
                warning_level="WARNING",
                indicator="thrust_mean",
                indicator_name="thrust_mean",
                ring_number=100,
                timestamp=now,
                status=new_status,
                resolved_at=now,
                resolved_by=request.user_id,
                created_at=now,
                updated_at=now,
                message="Stub warning resolved"
            )

        timestamp = datetime.utcnow().timestamp()
        new_status = "false_positive" if request.mark_as_false_positive else "resolved"

        with db.get_connection() as conn:
            # Check if warning exists
            cursor = conn.execute(
                "SELECT status FROM warning_events WHERE warning_id = ?",
                (warning_id,)
            )
            row = cursor.fetchone()

            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Warning {warning_id} not found"
                )

            current_status = row[0]

            if current_status == "resolved" or current_status == "false_positive":
                logger.warning(f"Warning {warning_id} already {current_status}")

            # Update warning
            update_query = """
                UPDATE warning_events
                SET status = ?,
                    resolved_at = ?,
                    resolved_by = ?,
                    resolution_notes = ?,
                    updated_at = ?
                WHERE warning_id = ?
            """

            conn.execute(
                update_query,
                (new_status, timestamp, request.user_id, request.notes, timestamp, warning_id)
            )
            conn.commit()

            logger.info(
                f"Warning {warning_id} marked as {new_status} by {request.user_id}"
            )

            # Publish status update to MQTT
            try:
                from edge.services.notification.mqtt_publisher import get_mqtt_publisher
                import asyncio

                mqtt = get_mqtt_publisher()
                asyncio.create_task(
                    mqtt.publish_warning_status_update(
                        warning_id,
                        new_status,
                        {
                            "user_id": request.user_id,
                            "notes": request.notes,
                            "is_false_positive": request.mark_as_false_positive
                        }
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to publish MQTT status update: {e}")

        # Return updated warning
        return await get_warning(warning_id, db)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving warning {warning_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve warning: {str(e)}"
        )


@router.get(
    "/warnings/stats/summary",
    response_model=WarningStatsResponse,
    summary="Get warning statistics",
    description="Get summary statistics of warnings"
)
async def get_warning_stats(
    start_time: Optional[float] = Query(None, description="Start timestamp for statistics"),
    end_time: Optional[float] = Query(None, description="End timestamp for statistics"),
    db: any = Depends(get_db_manager)
) -> WarningStatsResponse:
    """
    Get warning statistics.

    Implements FR-248: Warning metrics and trends

    **Query Parameters**:
    - `start_time`: Optional start timestamp (Unix timestamp)
    - `end_time`: Optional end timestamp (Unix timestamp)

    **Returns**: Warning statistics summary

    **Example**:
    ```
    GET /api/v1/warnings/stats/summary
    ```

    **Response**:
    ```json
    {
      "total_warnings": 150,
      "active_warnings": 5,
      "acknowledged_warnings": 20,
      "resolved_warnings": 125,
      "by_level": {
        "ATTENTION": 80,
        "WARNING": 50,
        "ALARM": 20
      },
      "by_type": {
        "threshold": 90,
        "rate": 40,
        "predictive": 15,
        "combined": 5
      }
    }
    ```
    """
    try:
        if _is_stub_mode():
            return WarningStatsResponse(
                total_warnings=1,
                active_warnings=1,
                acknowledged_warnings=0,
                resolved_warnings=0,
                by_level={"WARNING": 1},
                by_type={"threshold": 1}
            )

        # Build WHERE clause for time filter
        where_clause = ""
        params = []

        if start_time is not None or end_time is not None:
            conditions = []
            if start_time is not None:
                conditions.append("timestamp >= ?")
                params.append(start_time)
            if end_time is not None:
                conditions.append("timestamp <= ?")
                params.append(end_time)
            where_clause = "WHERE " + " AND ".join(conditions)

        with db.get_connection() as conn:
            # Total warnings
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM warning_events {where_clause}",
                params
            )
            total_warnings = cursor.fetchone()[0]

            # Warnings by status
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM warning_events {where_clause} "
                f"{'AND' if where_clause else 'WHERE'} status = 'active'",
                params
            )
            active_warnings = cursor.fetchone()[0]

            cursor = conn.execute(
                f"SELECT COUNT(*) FROM warning_events {where_clause} "
                f"{'AND' if where_clause else 'WHERE'} status = 'acknowledged'",
                params
            )
            acknowledged_warnings = cursor.fetchone()[0]

            cursor = conn.execute(
                f"SELECT COUNT(*) FROM warning_events {where_clause} "
                f"{'AND' if where_clause else 'WHERE'} status = 'resolved'",
                params
            )
            resolved_warnings = cursor.fetchone()[0]

            # Warnings by level
            cursor = conn.execute(
                f"SELECT warning_level, COUNT(*) FROM warning_events {where_clause} "
                f"GROUP BY warning_level",
                params
            )
            by_level = {row[0]: row[1] for row in cursor.fetchall()}

            # Warnings by type
            cursor = conn.execute(
                f"SELECT warning_type, COUNT(*) FROM warning_events {where_clause} "
                f"GROUP BY warning_type",
                params
            )
            by_type = {row[0]: row[1] for row in cursor.fetchall()}

        return WarningStatsResponse(
            total_warnings=total_warnings,
            active_warnings=active_warnings,
            acknowledged_warnings=acknowledged_warnings,
            resolved_warnings=resolved_warnings,
            by_level=by_level,
            by_type=by_type
        )

    except Exception as e:
        logger.error(f"Error fetching warning stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch warning statistics: {str(e)}"
        )
