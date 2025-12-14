"""
MQTT Publisher for Ring Data (T202)
Publishes ring summary events to MQTT topics for real-time dashboard updates
"""
import asyncio
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from asyncio_mqtt import Client, MqttError

logger = logging.getLogger(__name__)


class RingMQTTPublisher:
    """
    Publishes ring summary data to MQTT broker

    Topic structure:
    - shield/rings/new - New ring summary events
    - shield/rings/latest - Latest ring (retained)
    - shield/rings/{ring_number} - Specific ring data
    """

    def __init__(
        self,
        broker_host: str = "localhost",
        broker_port: int = 1883,
        client_id: str = "edge-ring-publisher",
        topic_prefix: str = "shield/rings",
        qos: int = 1,
    ):
        """
        Initialize Ring MQTT publisher

        Args:
            broker_host: MQTT broker hostname
            broker_port: MQTT broker port
            client_id: MQTT client ID
            topic_prefix: Base topic prefix for rings
            qos: Quality of Service (0, 1, or 2)
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client_id = client_id
        self.topic_prefix = topic_prefix
        self.qos = qos

        self._client: Optional[Client] = None
        self._connected = False
        self._lock = asyncio.Lock()

        logger.info(f"RingMQTTPublisher initialized: {broker_host}:{broker_port}")

    async def connect(self):
        """Connect to MQTT broker"""
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
                logger.info(f"Ring publisher connected to MQTT broker")
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
                logger.info("Ring publisher disconnected from MQTT broker")
            except Exception as e:
                logger.error(f"Error during MQTT disconnect: {e}")

    async def publish_ring(self, ring_summary: Dict[str, Any]) -> bool:
        """
        Publish ring summary to MQTT

        Args:
            ring_summary: Ring summary dict with all fields

        Returns:
            True if published successfully
        """
        if not self._connected:
            try:
                await self.connect()
            except Exception as e:
                logger.error(f"Failed to connect for ring publish: {e}")
                return False

        try:
            payload_json = json.dumps(ring_summary, default=str)
            ring_number = ring_summary.get("ring_number")

            topics = [
                f"{self.topic_prefix}/new",
                f"{self.topic_prefix}/latest",
            ]

            if ring_number:
                topics.append(f"{self.topic_prefix}/{ring_number}")

            async with self._lock:
                for topic in topics:
                    retain = topic.endswith("/latest")
                    await self._client.publish(
                        topic,
                        payload=payload_json.encode(),
                        qos=self.qos,
                        retain=retain,
                    )

            logger.info(f"Published ring {ring_number} to MQTT")
            return True

        except Exception as e:
            logger.error(f"Failed to publish ring: {e}", exc_info=True)
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected


# Singleton instance
_ring_publisher: Optional[RingMQTTPublisher] = None


def get_ring_publisher(
    broker_host: str = "localhost",
    broker_port: int = 1883,
    **kwargs
) -> RingMQTTPublisher:
    """Get or create singleton Ring MQTT publisher instance"""
    global _ring_publisher

    if _ring_publisher is None:
        _ring_publisher = RingMQTTPublisher(
            broker_host=broker_host,
            broker_port=broker_port,
            **kwargs
        )

    return _ring_publisher
