"""
Prediction API Endpoints
Provides latest prediction and per-ring prediction lookups.
"""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from edge.database.manager import DatabaseManager
db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager("data/edge.db")
    return db_manager

router = APIRouter(prefix="/api/v1/predictions", tags=["predictions"])


class PredictionResponse(BaseModel):
    ring_number: int
    timestamp: float
    model_name: str
    model_version: str
    model_type: Optional[str] = None
    geological_zone: Optional[str] = None
    predicted_settlement: Optional[float] = None
    settlement_lower_bound: Optional[float] = None
    settlement_upper_bound: Optional[float] = None
    prediction_confidence: Optional[float] = None
    inference_time_ms: Optional[float] = None
    quality_flag: Optional[str] = None


def _row_to_prediction(row: dict) -> PredictionResponse:
    return PredictionResponse(
        ring_number=row["ring_number"],
        timestamp=row.get("timestamp") or datetime.utcnow().timestamp(),
        model_name=row.get("model_name", ""),
        model_version=row.get("model_version", ""),
        model_type=row.get("model_type"),
        geological_zone=row.get("geological_zone"),
        predicted_settlement=row.get("predicted_settlement"),
        settlement_lower_bound=row.get("settlement_lower_bound"),
        settlement_upper_bound=row.get("settlement_upper_bound"),
        prediction_confidence=row.get("prediction_confidence"),
        inference_time_ms=row.get("inference_time_ms"),
        quality_flag=row.get("quality_flag"),
    )


@router.get("/latest", response_model=PredictionResponse)
async def get_latest_prediction():
    """Return the most recent prediction result."""
    try:
        with get_db_manager().get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT *
                FROM prediction_results
                ORDER BY timestamp DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No predictions found")
            return _row_to_prediction(dict(row))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{ring_number}", response_model=PredictionResponse)
async def get_prediction(ring_number: int):
    """Return prediction result for a specific ring number."""
    try:
        with get_db_manager().get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM prediction_results WHERE ring_number = ? ORDER BY timestamp DESC LIMIT 1",
                (ring_number,),
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No prediction found for ring {ring_number}"
                )
            return _row_to_prediction(dict(row))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
