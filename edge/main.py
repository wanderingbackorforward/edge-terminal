"""
T060: Main FastAPI Application for Edge Services
Orchestrates all edge components and provides REST API
"""
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from edge.api.routes import rings, manual_logs, health, warnings, predictions
from edge.database.manager import DatabaseManager
DataSourceManager = None  # Lazy import to speed up tests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/edge.log', mode='a')
    ]
)

logger = logging.getLogger(__name__)


# Global instances
db_manager = None
source_manager = None


def get_db_manager() -> DatabaseManager:
    """
    Provide a singleton instance of DatabaseManager.
    Lazily initialize to support unit tests that import app without running lifespan hooks.
    """
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager("data/edge.db")
    return db_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("=" * 60)
    logger.info("Starting Edge Services...")
    logger.info("=" * 60)

    try:
        # Initialize database
        global db_manager
        db_manager = DatabaseManager("data/edge.db")
        logger.info("✓ Database manager initialized")

        # Initialize data source manager
        skip_sources = os.getenv("SKIP_SOURCE_MANAGER", "").lower() in ("1", "true", "yes") or "PYTEST_CURRENT_TEST" in os.environ
        if skip_sources:
            logger.info("SKIP_SOURCE_MANAGER enabled - skipping data source initialization")
        else:
            from edge.services.collector.source_manager import DataSourceManager as DSM
            global DataSourceManager
            DataSourceManager = DSM
            global source_manager
            source_manager = DataSourceManager(
                config_path="edge/config/sources.yaml",
                db_manager=db_manager
            )
            await source_manager.initialize()
            logger.info("✓ Data source manager initialized")

        # Start data collection (optional - can be controlled via API)
        # await source_manager.start()
        # logger.info("✓ Data collection started")

        logger.info("=" * 60)
        logger.info("Edge Services started successfully!")
        logger.info("API documentation: http://localhost:8000/docs")
        logger.info("=" * 60)

        yield  # Application runs here

    except Exception as e:
        logger.error(f"Error during startup: {e}", exc_info=True)
        raise

    finally:
        # Shutdown
        logger.info("=" * 60)
        logger.info("Shutting down Edge Services...")
        logger.info("=" * 60)

        try:
            if source_manager:
                await source_manager.stop()
                logger.info("✓ Data source manager stopped")

            logger.info("Edge Services shutdown complete")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)


# Toggle lifespan for testing
disable_lifespan = os.getenv("DISABLE_LIFESPAN", "").lower() in ("1", "true", "yes")

# Create FastAPI application
app = FastAPI(
    title="Shield Tunneling Edge API",
    description="""
    Edge services for shield tunneling intelligent control platform.

    ## Features
    - Real-time data collection from PLC and guidance systems
    - Data quality pipeline (validation, calibration, interpolation)
    - Ring-based data aggregation and feature engineering
    - Manual data entry
    - Health monitoring

    ## Data Flow
    1. **Collection**: OPC UA, Modbus TCP, Manual Entry
    2. **Quality**: Threshold validation, calibration, reasonableness checks
    3. **Aggregation**: Ring-level statistical features
    4. **Persistence**: SQLite database with ring summaries
    5. **API**: Query ring data, submit manual logs

    ## Getting Started
    - View API documentation at `/docs`
    - Check system health at `/health`
    - Query ring data at `/api/v1/rings`
    """,
    version="1.0.0",
    lifespan=None if disable_lifespan else lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)


# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "*"  # dev only
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled errors.
    """
    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True,
        extra={
            "method": request.method,
            "url": str(request.url),
            "client": request.client.host if request.client else "unknown"
        }
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "message": str(exc),
            "path": str(request.url.path)
        }
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handler for 404 errors"""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "Not found",
            "message": f"Endpoint {request.url.path} not found",
            "path": str(request.url.path)
        }
    )


# Include routers
app.include_router(rings.router)
app.include_router(manual_logs.router)
app.include_router(health.router)
app.include_router(warnings.router)
app.include_router(predictions.router)


# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint - API information
    """
    return {
        "name": "Shield Tunneling Edge API",
        "version": "1.0.0",
        "status": "running",
        "documentation": "/docs",
        "health_check": "/api/v1/health",
        "endpoints": {
            "rings": "/api/v1/rings",
            "manual_logs": "/api/v1/manual-logs",
            "health": "/api/v1/health"
        }
    }


# Control endpoints for data collection
@app.post("/api/v1/control/start-collection", tags=["control"])
async def start_data_collection():
    """
    Start data collection from configured sources.

    This endpoint starts all enabled data collectors (OPC UA, Modbus TCP, etc.)
    """
    try:
        if not source_manager:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"error": "Source manager not initialized"}
            )

        await source_manager.start()
        logger.info("Data collection started via API")

        return {
            "status": "success",
            "message": "Data collection started",
            "collectors": list(source_manager.collectors.keys())
        }

    except Exception as e:
        logger.error(f"Error starting data collection: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": str(e)}
        )


@app.post("/api/v1/control/stop-collection", tags=["control"])
async def stop_data_collection():
    """
    Stop data collection from all sources.
    """
    try:
        if not source_manager:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"error": "Source manager not initialized"}
            )

        await source_manager.stop()
        logger.info("Data collection stopped via API")

        return {
            "status": "success",
            "message": "Data collection stopped"
        }

    except Exception as e:
        logger.error(f"Error stopping data collection: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": str(e)}
        )


@app.get("/api/v1/control/status", tags=["control"])
async def get_collection_status():
    """
    Get status of data collection system.
    """
    try:
        if not source_manager:
            return {
                "status": "unavailable",
                "message": "Source manager not initialized"
            }

        status_info = source_manager.get_status()

        return {
            "status": "ok",
            "collection_status": status_info
        }

    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": str(e)}
        )


# Dependency injection helpers
def get_db():
    """Get database manager instance"""
    return db_manager


def get_source_manager():
    """Get source manager instance"""
    return source_manager


# Development server
if __name__ == "__main__":
    import uvicorn

    # Create logs directory if not exists
    Path("logs").mkdir(exist_ok=True)

    # Create data directory if not exists
    Path("data").mkdir(exist_ok=True)

    # Run server
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes (development only)
        log_level="info"
    )
