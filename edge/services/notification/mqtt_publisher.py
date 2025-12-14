"""
MQTT Publisher for Warning Notifications
Publishes warning events to MQTT topics for real-time dashboard updates
Implements Feature 003 - Real-Time Warning System
"""
import asyncio
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from asyncio_mqtt import Client, MqttError

from edge.models.warning_event import WarningEvent

logger = logging.getLogger(__name__)


class MQTTPublisher:
    """
    Publishes warning events to MQTT broker

    Implements:
    - FR-010: Dashboard highlighting for ATTENTION level
    - FR-011: Dashboard + email for WARNING level
    - FR-012: Dashboard + SMS + email for ALARM level
    - FR-025: Edge-local notification channels

    Topic structure:
    - shield/warnings/all - All warning events
    - shield/warnings/attention - ATTENTION level warnings
    - shield/warnings/warning - WARNING level warnings
    - shield/warnings/alarm - ALARM level warnings
    - shield/warnings/ring/{ring_number} - Warnings for specific ring
    """

    def __init__(
        self,
        broker_host: str = "localhost",
        broker_port: int = 1883,
        client_id: str = "edge-warning-publisher",
        topic_prefix: str = "shield/warnings",
        qos: int = 1,
        retain: bool = True,
    ):
        """
        Initialize MQTT publisher

        Args:
            broker_host: MQTT broker hostname
            broker_port: MQTT broker port
            client_id: MQTT client ID
            topic_prefix: Base topic prefix for warnings
            qos: Quality of Service (0, 1, or 2)
            retain: Whether to retain messages on broker
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client_id = client_id
        self.topic_prefix = topic_prefix
        self.qos = qos
        self.retain = retain

        self._client: Optional[Client] = None
        self._connected = False
        self._lock = asyncio.Lock()

        logger.info(
            f"MQTTPublisher initialized: {broker_host}:{broker_port}, "
            f"topic_prefix={topic_prefix}"
        )

    async def connect(self):
        """
        Connect to MQTT broker

        Implements graceful connection with retry logic
        """
        if self._connected:
            return

        async with self._lock:
            try:
                self._client = Client(
                    hostname=self.broker_host,
                    port=self.broker_port,
                    client_id=self.client_id,
                )
                await self._client.__aenter__()
                self._connected = True
                logger.info(
                    f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}"
                )
            except MqttError as e:
                logger.error(f"Failed to connect to MQTT broker: {e}")
                self._connected = False
                raise

    async def disconnect(self):
        """Disconnect from MQTT broker"""
        if not self._connected or not self._client:
            return

        async with self._lock:
            try:
                await self._client.__aexit__(None, None, None)
                self._connected = False
                logger.info("Disconnected from MQTT broker")
            except Exception as e:
                logger.error(f"Error during MQTT disconnect: {e}")

    async def publish_warning(self, warning: WarningEvent) -> bool:
        """
        Publish a single warning event to MQTT

        Publishes to multiple topics:
        1. shield/warnings/all - All warnings
        2. shield/warnings/{level} - Level-specific topic
        3. shield/warnings/ring/{ring_number} - Ring-specific topic

        Args:
            warning: WarningEvent to publish

        Returns:
            True if published successfully, False otherwise

        Implements FR-010, FR-011, FR-012
        """
        if not self._connected:
            logger.warning("Not connected to MQTT broker, attempting to connect...")
            try:
                await self.connect()
            except Exception as e:
                logger.error(f"Failed to connect for warning publish: {e}")
                return False

        try:
            # Serialize warning to JSON
            payload = self._serialize_warning(warning)
            payload_json = json.dumps(payload)

            # Publish to multiple topics
            topics = [
                f"{self.topic_prefix}/all",
                f"{self.topic_prefix}/{warning.warning_level.lower()}",
                f"{self.topic_prefix}/ring/{warning.ring_number}",
            ]

            async with self._lock:
                for topic in topics:
                    await self._client.publish(
                        topic,
                        payload=payload_json.encode(),
                        qos=self.qos,
                        retain=self.retain,
                    )

            logger.info(
                f"Published warning {warning.warning_id} to MQTT "
                f"(level={warning.warning_level}, ring={warning.ring_number})"
            )

            # Update notification tracking
            warning.notification_sent = True
            warning.notification_timestamp = datetime.utcnow().timestamp()

            return True

        except MqttError as e:
            logger.error(
                f"MQTT error publishing warning {warning.warning_id}: {e}",
                exc_info=True
            )
            self._connected = False  # Mark as disconnected for retry
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error publishing warning {warning.warning_id}: {e}",
                exc_info=True
            )
            return False

    async def publish_warnings_batch(self, warnings: List[WarningEvent]) -> Dict[str, int]:
        """
        Publish multiple warnings in batch

        Args:
            warnings: List of WarningEvent objects

        Returns:
            Dict with success/failure counts: {"success": N, "failed": M}
        """
        results = {"success": 0, "failed": 0}

        for warning in warnings:
            success = await self.publish_warning(warning)
            if success:
                results["success"] += 1
            else:
                results["failed"] += 1

        logger.info(
            f"Batch publish completed: {results['success']} succeeded, "
            f"{results['failed']} failed"
        )

        return results

    async def publish_warning_status_update(
        self,
        warning_id: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Publish warning status update (acknowledged, resolved)

        Used for FR-031, FR-032 (warning lifecycle management)

        Args:
            warning_id: Warning ID
            status: New status (acknowledged, resolved, false_positive)
            metadata: Optional metadata (user_id, notes, etc.)

        Returns:
            True if published successfully
        """
        if not self._connected:
            try:
                await self.connect()
            except Exception:
                return False

        try:
            payload = {
                "warning_id": warning_id,
                "status": status,
                "timestamp": datetime.utcnow().timestamp(),
                "metadata": metadata or {},
            }

            topic = f"{self.topic_prefix}/status_updates"

            async with self._lock:
                await self._client.publish(
                    topic,
                    payload=json.dumps(payload).encode(),
                    qos=self.qos,
                    retain=False,  # Status updates don't need retention
                )

            logger.info(f"Published status update for warning {warning_id}: {status}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish status update: {e}", exc_info=True)
            return False

    def _serialize_warning(self, warning: WarningEvent) -> Dict[str, Any]:
        """
        Serialize WarningEvent to JSON-compatible dict

        Returns a dashboard-friendly format with all relevant fields
        """
        return {
            "warning_id": warning.warning_id,
            "warning_type": warning.warning_type,
            "warning_level": warning.warning_level,
            "ring_number": warning.ring_number,
            "timestamp": warning.timestamp,
            "indicator_name": warning.indicator_name,
            "indicator_value": warning.indicator_value,
            "indicator_unit": warning.indicator_unit,
            "threshold_value": warning.threshold_value,
            "threshold_type": warning.threshold_type,
            "rate_of_change": warning.rate_of_change,
            "historical_average_rate": warning.historical_average_rate,
            "rate_multiplier": warning.rate_multiplier,
            "predicted_value": warning.predicted_value,
            "prediction_confidence": warning.prediction_confidence,
            "prediction_horizon_hours": warning.prediction_horizon_hours,
            "combined_indicators": warning.get_combined_indicators(),
            "status": warning.status,
            "notification_channels": warning.get_notification_channels(),
            "created_at": warning.created_at,
            # Human-readable message
            "message": self._format_warning_message(warning),
        }

    def _format_warning_message(self, warning: WarningEvent) -> str:
        """
        Format human-readable warning message

        Implements FR-227: Clear, actionable warning messages
        """
        if warning.warning_type == "threshold":
            return (
                f"{warning.warning_level}: {warning.indicator_name} = "
                f"{warning.indicator_value:.2f}{warning.indicator_unit or ''} "
                f"exceeds {warning.threshold_type} threshold "
                f"{warning.threshold_value:.2f}{warning.indicator_unit or ''} "
                f"(Ring {warning.ring_number})"
            )
        elif warning.warning_type == "rate":
            return (
                f"{warning.warning_level}: {warning.indicator_name} rate of change "
                f"({warning.rate_of_change:.2f}/ring) is {warning.rate_multiplier:.1f}× "
                f"historical average ({warning.historical_average_rate:.2f}/ring) "
                f"(Ring {warning.ring_number})"
            )
        elif warning.warning_type == "predictive":
            return (
                f"{warning.warning_level}: Predicted {warning.indicator_name} "
                f"({warning.predicted_value:.2f}{warning.indicator_unit or ''}) "
                f"expected to approach threshold "
                f"{warning.threshold_value:.2f}{warning.indicator_unit or ''} "
                f"within {warning.prediction_horizon_hours:.0f} hours "
                f"(Ring {warning.ring_number}, confidence: {warning.prediction_confidence:.0%})"
            )
        elif warning.warning_type == "combined":
            indicators = warning.get_combined_indicators() or []
            return (
                f"{warning.warning_level}: Multiple simultaneous violations - "
                f"{', '.join(indicators)} (Ring {warning.ring_number})"
            )
        else:
            return (
                f"{warning.warning_level}: {warning.indicator_name} warning "
                f"(Ring {warning.ring_number})"
            )

    async def publish_system_status(self, status: Dict[str, Any]) -> bool:
        """
        Publish warning system health status

        Implements FR-252: System health monitoring

        Args:
            status: Dict with system status info
                   Example: {"connected": true, "warnings_active": 3, "last_check": timestamp}

        Returns:
            True if published successfully
        """
        if not self._connected:
            try:
                await self.connect()
            except Exception:
                return False

        try:
            topic = f"{self.topic_prefix}/system/status"
            payload = {
                **status,
                "timestamp": datetime.utcnow().timestamp(),
            }

            async with self._lock:
                await self._client.publish(
                    topic,
                    payload=json.dumps(payload).encode(),
                    qos=0,  # Status updates can use QoS 0
                    retain=True,
                )

            return True

        except Exception as e:
            logger.error(f"Failed to publish system status: {e}")
            return False

    @property
    def is_connected(self) -> bool:
        """Check if connected to MQTT broker"""
        return self._connected


# Singleton instance for global access
_mqtt_publisher: Optional[MQTTPublisher] = None


def get_mqtt_publisher(
    broker_host: str = "localhost",
    broker_port: int = 1883,
    **kwargs
) -> MQTTPublisher:
    """
    Get or create singleton MQTT publisher instance

    Args:
        broker_host: MQTT broker hostname
        broker_port: MQTT broker port
        **kwargs: Additional publisher configuration

    Returns:
        MQTTPublisher instance
    """
    global _mqtt_publisher

    if _mqtt_publisher is None:
        _mqtt_publisher = MQTTPublisher(
            broker_host=broker_host,
            broker_port=broker_port,
            **kwargs
        )

    return _mqtt_publisher
