"""
MQTT Publisher for Prediction Results (T202)
Publishes prediction results to MQTT topics for real-time dashboard updates
"""
import asyncio
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from asyncio_mqtt import Client, MqttError

logger = logging.getLogger(__name__)


class PredictionMQTTPublisher:
    """
    Publishes prediction results to MQTT broker

    Topic structure:
    - shield/predictions/new - New prediction events
    - shield/predictions/latest - Latest prediction (retained)
    - shield/predictions/ring/{ring_number} - Prediction for specific ring
    """

    def __init__(
        self,
        broker_host: str = "localhost",
        broker_port: int = 1883,
        client_id: str = "edge-prediction-publisher",
        topic_prefix: str = "shield/predictions",
        qos: int = 1,
    ):
        """
        Initialize Prediction MQTT publisher

        Args:
            broker_host: MQTT broker hostname
            broker_port: MQTT broker port
            client_id: MQTT client ID
            topic_prefix: Base topic prefix for predictions
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

        logger.info(f"PredictionMQTTPublisher initialized: {broker_host}:{broker_port}")

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
                logger.info(f"Prediction publisher connected to MQTT broker")
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
                logger.info("Prediction publisher disconnected from MQTT broker")
            except Exception as e:
                logger.error(f"Error during MQTT disconnect: {e}")

    async def publish_prediction(self, prediction: Dict[str, Any]) -> bool:
        """
        Publish prediction result to MQTT

        Args:
            prediction: Prediction result dict

        Returns:
            True if published successfully
        """
        if not self._connected:
            try:
                await self.connect()
            except Exception as e:
                logger.error(f"Failed to connect for prediction publish: {e}")
                return False

        try:
            payload_json = json.dumps(prediction, default=str)
            ring_number = prediction.get("ring_number")

            topics = [
                f"{self.topic_prefix}/new",
                f"{self.topic_prefix}/latest",
            ]

            if ring_number:
                topics.append(f"{self.topic_prefix}/ring/{ring_number}")

            async with self._lock:
                for topic in topics:
                    retain = topic.endswith("/latest")
                    await self._client.publish(
                        topic,
                        payload=payload_json.encode(),
                        qos=self.qos,
                        retain=retain,
                    )

            logger.info(f"Published prediction for ring {ring_number} to MQTT")
            return True

        except Exception as e:
            logger.error(f"Failed to publish prediction: {e}", exc_info=True)
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected


# Singleton instance
_prediction_publisher: Optional[PredictionMQTTPublisher] = None


def get_prediction_publisher(
    broker_host: str = "localhost",
    broker_port: int = 1883,
    **kwargs
) -> PredictionMQTTPublisher:
    """Get or create singleton Prediction MQTT publisher instance"""
    global _prediction_publisher

    if _prediction_publisher is None:
        _prediction_publisher = PredictionMQTTPublisher(
            broker_host=broker_host,
            broker_port=broker_port,
            **kwargs
        )

    return _prediction_publisher
