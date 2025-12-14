"""
T034: Data Source Manager
Orchestrates multiple data collectors and manages data flow
Loads configuration and manages lifecycle of all collectors
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional
import yaml
from datetime import datetime

from edge.services.collector.opcua_client import OPCUACollector
from edge.services.collector.modbus_client import ModbusTCPCollector
from edge.services.collector.rest_client import RESTAPICollector
from edge.services.collector.buffer_writer import BufferWriter
from edge.services.cleaner.threshold_validator import ThresholdValidator
from edge.services.cleaner.interpolator import DataInterpolator
from edge.services.cleaner.reasonableness_checker import ReasonablenessChecker
from edge.services.cleaner.calibration import CalibrationApplicator
from edge.services.cleaner.quality_metrics import QualityMetricsTracker

logger = logging.getLogger(__name__)


class DataSourceManager:
    """
    Manages all data collection sources and data quality pipeline.

    Features:
    - Loads configuration from sources.yaml
    - Orchestrates OPC UA, Modbus TCP, REST API collectors
    - Manages data quality pipeline
    - Buffers and writes data to database
    - Provides unified status and statistics
    """

    def __init__(
        self,
        config_path: str = "edge/config/sources.yaml",
        db_manager = None
    ):
        """
        Initialize data source manager.

        Args:
            config_path: Path to sources configuration file
            db_manager: DatabaseManager instance
        """
        self.config_path = config_path
        self.db_manager = db_manager

        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Collectors
        self.collectors: Dict[str, Any] = {}
        self.collector_tasks: List[asyncio.Task] = []

        # Data quality pipeline
        self.quality_enabled = self.config.get('data_quality', {})
        self.threshold_validator = None
        self.interpolator = None
        self.reasonableness_checker = None
        self.calibration_applicator = None
        self.quality_metrics = None

        # Buffer writer
        self.buffer_writer = None

        # State
        self.running = False

    async def initialize(self) -> None:
        """Initialize all components"""
        logger.info("Initializing Data Source Manager...")

        # Initialize data quality components
        if self.quality_enabled.get('enable_threshold_validation', True):
            self.threshold_validator = ThresholdValidator()
            logger.info("Threshold validator initialized")

        if self.quality_enabled.get('enable_interpolation', True):
            self.interpolator = DataInterpolator()
            logger.info("Interpolator initialized")

        if self.quality_enabled.get('enable_reasonableness_check', True):
            self.reasonableness_checker = ReasonablenessChecker()
            logger.info("Reasonableness checker initialized")

        if self.quality_enabled.get('enable_calibration', True):
            self.calibration_applicator = CalibrationApplicator()
            logger.info("Calibration applicator initialized")

        if self.quality_enabled.get('enable_quality_metrics', True):
            self.quality_metrics = QualityMetricsTracker()
            logger.info("Quality metrics tracker initialized")

        # Initialize buffer writer
        if self.db_manager:
            buffer_config = self.config.get('buffer', {})
            self.buffer_writer = BufferWriter(
                db_manager=self.db_manager,
                max_size=buffer_config.get('max_size', 10000),
                flush_interval=buffer_config.get('flush_interval', 5.0),
                flush_threshold=buffer_config.get('flush_threshold', 1000),
                overflow_strategy=buffer_config.get('overflow_strategy', 'drop_oldest')
            )
            await self.buffer_writer.start()
            logger.info("Buffer writer initialized")

        # Initialize collectors
        await self._initialize_collectors()

        logger.info("Data Source Manager initialization complete")

    async def _initialize_collectors(self) -> None:
        """Initialize all configured data collectors"""
        sources = self.config.get('sources', {})

        for source_id, source_config in sources.items():
            if not source_config.get('enabled', False):
                logger.info(f"Source '{source_id}' is disabled, skipping")
                continue

            source_type = source_config.get('type')

            try:
                if source_type == 'opcua':
                    collector = self._create_opcua_collector(source_id, source_config)
                    self.collectors[source_id] = collector
                    logger.info(f"OPC UA collector '{source_id}' initialized")

                elif source_type == 'modbus':
                    collector = self._create_modbus_collector(source_id, source_config)
                    self.collectors[source_id] = collector
                    logger.info(f"Modbus TCP collector '{source_id}' initialized")

                elif source_type == 'rest':
                    collector = self._create_rest_collector(source_id, source_config)
                    self.collectors[source_id] = collector
                    logger.info(f"REST API collector '{source_id}' initialized")

                elif source_type == 'manual':
                    logger.info(f"Manual entry source '{source_id}' configured")

                else:
                    logger.warning(f"Unknown source type '{source_type}' for '{source_id}'")

            except Exception as e:
                logger.error(f"Failed to initialize collector '{source_id}': {e}")

    def _create_opcua_collector(self, source_id: str, config: Dict[str, Any]) -> OPCUACollector:
        """Create OPC UA collector from configuration"""
        endpoint_url = config['endpoint_url']
        tags = [tag['name'] for tag in config.get('tags', [])]

        def data_callback(tag_name: str, value: Any, timestamp: float):
            """Callback for OPC UA data"""
            asyncio.create_task(
                self._process_plc_data(source_id, tag_name, value, timestamp)
            )

        collector = OPCUACollector(
            endpoint_url=endpoint_url,
            tag_list=tags,
            namespace_index=config.get('namespace_index', 2),
            callback=data_callback,
            subscription_interval=config.get('subscription_interval', 1000)
        )

        return collector

    def _create_modbus_collector(self, source_id: str, config: Dict[str, Any]) -> ModbusTCPCollector:
        """Create Modbus TCP collector from configuration"""
        host = config['host']
        port = config.get('port', 502)

        # Build register map
        register_map = {}
        for reg in config.get('registers', []):
            register_map[reg['name']] = {
                'address': reg['address'],
                'count': reg.get('count', 2),
                'type': reg.get('data_type', 'float32')
            }

        def data_callback(tag_name: str, value: Any, timestamp: float):
            """Callback for Modbus data"""
            asyncio.create_task(
                self._process_attitude_data(source_id, tag_name, value, timestamp)
            )

        collector = ModbusTCPCollector(
            host=host,
            port=port,
            register_map=register_map,
            callback=data_callback,
            poll_interval=config.get('poll_interval', 1.0)
        )

        return collector

    def _create_rest_collector(self, source_id: str, config: Dict[str, Any]) -> RESTAPICollector:
        """Create REST API collector from configuration"""
        import os

        base_url = config['base_url']
        endpoints = config.get('endpoints', {})

        # Get authentication token
        auth_token = None
        auth_config = config.get('authentication', {})
        if auth_config.get('type') == 'bearer':
            token_env_var = auth_config.get('token_env_var')
            if token_env_var:
                auth_token = os.getenv(token_env_var)
                if not auth_token:
                    logger.warning(f"Auth token not found in env var: {token_env_var}")

        def data_callback(
            sensor_type: str,
            value: Any,
            location: Optional[str],
            unit: Optional[str],
            timestamp: float,
            endpoint: str
        ):
            """Callback for REST API data"""
            asyncio.create_task(
                self._process_monitoring_data(
                    source_id, sensor_type, value, location, unit, timestamp, endpoint
                )
            )

        connection_config = config.get('connection', {})
        collector = RESTAPICollector(
            base_url=base_url,
            endpoints=endpoints,
            callback=data_callback,
            auth_token=auth_token,
            timeout=connection_config.get('timeout', 10),
            max_retries=connection_config.get('max_retries', 3)
        )

        return collector

    async def _process_plc_data(
        self,
        source_id: str,
        tag_name: str,
        value: Any,
        timestamp: float
    ) -> None:
        """Process PLC data through quality pipeline"""
        try:
            # Threshold validation
            if self.threshold_validator:
                is_valid, reason = self.threshold_validator.validate(tag_name, value)
                if self.quality_metrics:
                    self.quality_metrics.record_validation(tag_name, is_valid, reason)
                if not is_valid:
                    logger.debug(f"PLC data rejected: {tag_name}={value}, reason: {reason}")
                    return

            # Calibration
            was_calibrated = False
            if self.calibration_applicator:
                value, was_calibrated = self.calibration_applicator.calibrate(
                    tag_name, value, timestamp
                )
                if self.quality_metrics:
                    self.quality_metrics.record_calibration(tag_name, was_calibrated)

            # Determine quality flag
            quality_flag = 'calibrated' if was_calibrated else 'raw'

            # Write to buffer
            if self.buffer_writer:
                self.buffer_writer.add_plc_log(
                    tag_name=tag_name,
                    value=value,
                    timestamp=timestamp,
                    source_id=source_id,
                    data_quality_flag=quality_flag
                )

        except Exception as e:
            logger.error(f"Error processing PLC data: {e}")

    async def _process_attitude_data(
        self,
        source_id: str,
        tag_name: str,
        value: Any,
        timestamp: float
    ) -> None:
        """Process attitude/guidance data"""
        try:
            # Store in temporary dict for batch processing
            # In real implementation, accumulate all attitude parameters
            # and write complete record

            logger.debug(f"Attitude data: {tag_name}={value}")

            # For now, just log - full implementation would accumulate
            # all parameters (pitch, roll, yaw, deviations) and write
            # complete attitude_log record

        except Exception as e:
            logger.error(f"Error processing attitude data: {e}")

    async def _process_monitoring_data(
        self,
        source_id: str,
        sensor_type: str,
        value: Any,
        location: Optional[str],
        unit: Optional[str],
        timestamp: float,
        endpoint: str
    ) -> None:
        """Process monitoring data from REST API"""
        try:
            # Basic validation
            if value is None:
                logger.debug(f"Null value from {endpoint}, skipping")
                return

            # Threshold validation
            if self.threshold_validator:
                is_valid, reason = self.threshold_validator.validate(sensor_type, value)
                if self.quality_metrics:
                    self.quality_metrics.record_validation(sensor_type, is_valid, reason)
                if not is_valid:
                    logger.debug(
                        f"Monitoring data rejected: {sensor_type}={value}, reason: {reason}"
                    )
                    return

            # Write to buffer (monitoring_logs table)
            if self.buffer_writer:
                self.buffer_writer.add_monitoring_log(
                    sensor_type=sensor_type,
                    value=value,
                    sensor_location=location,
                    unit=unit,
                    timestamp=timestamp,
                    source_id=source_id,
                    data_quality_flag='raw'
                )

            logger.debug(
                f"Monitoring data: {sensor_type}={value} {unit or ''} @ {location or 'unknown'}"
            )

        except Exception as e:
            logger.error(f"Error processing monitoring data: {e}")

    async def start(self) -> None:
        """Start all collectors"""
        if self.running:
            logger.warning("Data Source Manager already running")
            return

        self.running = True
        logger.info("Starting Data Source Manager...")

        # Start all collectors
        for source_id, collector in self.collectors.items():
            try:
                task = asyncio.create_task(collector.run())
                self.collector_tasks.append(task)
                logger.info(f"Started collector: {source_id}")
            except Exception as e:
                logger.error(f"Failed to start collector '{source_id}': {e}")

        logger.info("Data Source Manager started")

    async def stop(self) -> None:
        """Stop all collectors"""
        if not self.running:
            return

        self.running = False
        logger.info("Stopping Data Source Manager...")

        # Stop all collectors
        for source_id, collector in self.collectors.items():
            try:
                await collector.stop()
                logger.info(f"Stopped collector: {source_id}")
            except Exception as e:
                logger.error(f"Error stopping collector '{source_id}': {e}")

        # Cancel all tasks
        for task in self.collector_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self.collector_tasks.clear()

        # Stop buffer writer
        if self.buffer_writer:
            await self.buffer_writer.stop()

        logger.info("Data Source Manager stopped")

    def get_status(self) -> Dict[str, Any]:
        """Get status of all collectors and components"""
        collector_status = {}
        for source_id, collector in self.collectors.items():
            # Check if collector has status method
            if hasattr(collector, 'client') and collector.client:
                connected = getattr(collector.client, 'connected', False)
                collector_status[source_id] = {
                    'running': self.running,
                    'connected': connected
                }
            else:
                collector_status[source_id] = {
                    'running': self.running,
                    'connected': False
                }

        buffer_stats = self.buffer_writer.get_statistics() if self.buffer_writer else {}

        quality_stats = {}
        if self.quality_metrics:
            quality_stats = self.quality_metrics.get_quality_summary()

        return {
            'running': self.running,
            'collectors': collector_status,
            'buffer': buffer_stats,
            'quality': quality_stats
        }


# Example usage
if __name__ == "__main__":
    import sys
    sys.path.append('/home/monss/tunnel-su-1/shield-tunneling-icp')

    from edge.database.manager import DatabaseManager

    async def example_usage():
        """Example of using DataSourceManager"""
        db = DatabaseManager("data/edge.db")
        manager = DataSourceManager(
            config_path="edge/config/sources.yaml",
            db_manager=db
        )

        await manager.initialize()

        # Start data collection
        await manager.start()

        # Run for 10 seconds
        await asyncio.sleep(10)

        # Get status
        status = manager.get_status()
        print("\nStatus:")
        print(f"Running: {status['running']}")
        print(f"Collectors: {list(status['collectors'].keys())}")
        print(f"Buffer: {status['buffer']}")

        # Stop
        await manager.stop()

    asyncio.run(example_usage())
