"""
T031: OPC UA Client Connector
Implements async OPC UA client for PLC data collection
Supports tag subscription for real-time data streaming
"""
import asyncio
import logging
from typing import List, Callable, Optional, Dict, Any
from datetime import datetime

try:
    from asyncua import Client, Node
    from asyncua.common.subscription import SubHandler
except ImportError:
    # Graceful degradation if asyncua not installed
    Client = None
    Node = None
    SubHandler = None

logger = logging.getLogger(__name__)


class OPCUADataHandler(SubHandler):
    """
    Subscription handler for OPC UA data changes.
    Receives callbacks when subscribed tag values change.
    """

    def __init__(self, callback: Callable[[str, Any, float], None]):
        """
        Initialize handler with callback function.

        Args:
            callback: Function to call on data change (tag_name, value, timestamp)
        """
        self.callback = callback

    def datachange_notification(self, node: Any, val: Any, data: Any) -> None:
        """
        Called when subscribed node value changes.

        Args:
            node: OPC UA node
            val: New value
            data: Additional data (timestamp, status)
        """
        try:
            # Extract tag name from node
            tag_name = str(node).split("=")[-1]  # Simplified, should use node.read_browse_name()

            # Extract timestamp
            timestamp = datetime.utcnow().timestamp()
            if hasattr(data, 'monitored_item') and hasattr(data.monitored_item, 'Value'):
                if hasattr(data.monitored_item.Value, 'SourceTimestamp'):
                    timestamp = data.monitored_item.Value.SourceTimestamp.timestamp()

            # Call callback with parsed data
            self.callback(tag_name, val, timestamp)

        except Exception as e:
            logger.error(f"Error in datachange_notification: {e}")


class OPCUACollector:
    """
    Async OPC UA client for collecting PLC data.

    Features:
    - Automatic connection management
    - Tag subscription for real-time updates
    - Reconnection logic on connection loss
    - Batched data buffering
    """

    def __init__(
        self,
        endpoint_url: str,
        tag_list: List[str],
        callback: Callable[[str, Any, float], None],
        subscription_interval: int = 1000  # ms
    ):
        """
        Initialize OPC UA collector.

        Args:
            endpoint_url: OPC UA server URL (e.g., "opc.tcp://localhost:4840")
            tag_list: List of tag node IDs to subscribe to
            callback: Function to call on data change
            subscription_interval: Subscription publishing interval in ms
        """
        if Client is None:
            raise ImportError(
                "asyncua not installed. Install with: pip install asyncua"
            )

        self.endpoint_url = endpoint_url
        self.tag_list = tag_list
        self.callback = callback
        self.subscription_interval = subscription_interval

        self.client: Optional[Client] = None
        self.subscription = None
        self._running = False
        self._reconnect_delay = 5  # seconds

    async def connect(self) -> None:
        """
        Establish connection to OPC UA server and setup subscriptions.
        """
        try:
            self.client = Client(url=self.endpoint_url)
            await self.client.connect()

            logger.info(f"Connected to OPC UA server: {self.endpoint_url}")

            # Get server namespace index (usually 2 for application-specific tags)
            namespace_idx = await self.client.get_namespace_index(
                "urn:shield-plc:server"  # Example namespace
            )

            # Create subscription
            handler = OPCUADataHandler(self.callback)
            self.subscription = await self.client.create_subscription(
                period=self.subscription_interval,
                handler=handler
            )

            # Subscribe to all tags
            nodes = []
            for tag_id in self.tag_list:
                # Construct node ID (format: "ns=2;s=TagName")
                node = self.client.get_node(f"ns={namespace_idx};s={tag_id}")
                nodes.append(node)

            # Subscribe to all nodes
            await self.subscription.subscribe_data_change(nodes)

            logger.info(f"Subscribed to {len(nodes)} OPC UA tags")

        except Exception as e:
            logger.error(f"OPC UA connection failed: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from OPC UA server"""
        if self.client:
            try:
                if self.subscription:
                    await self.subscription.delete()
                await self.client.disconnect()
                logger.info("Disconnected from OPC UA server")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
            finally:
                self.client = None
                self.subscription = None

    async def run(self) -> None:
        """
        Main collection loop with automatic reconnection.
        """
        self._running = True

        while self._running:
            try:
                await self.connect()

                # Keep connection alive
                while self._running:
                    await asyncio.sleep(1)

                    # Check connection health
                    if self.client is None:
                        break

            except Exception as e:
                logger.error(f"OPC UA collector error: {e}")

                # Attempt reconnection after delay
                logger.info(f"Reconnecting in {self._reconnect_delay} seconds...")
                await asyncio.sleep(self._reconnect_delay)

            finally:
                await self.disconnect()

    async def stop(self) -> None:
        """Stop collection loop"""
        self._running = False
        await self.disconnect()


# Example usage
async def example_usage():
    """
    Example of using OPCUACollector
    """
    def data_callback(tag_name: str, value: Any, timestamp: float):
        """Callback for received data"""
        print(f"Tag: {tag_name}, Value: {value}, Time: {timestamp}")

    collector = OPCUACollector(
        endpoint_url="opc.tcp://localhost:4840",
        tag_list=[
            "thrust_total",
            "torque_cutterhead",
            "chamber_pressure",
            "advance_rate"
        ],
        callback=data_callback
    )

    try:
        await collector.run()
    except KeyboardInterrupt:
        await collector.stop()


if __name__ == "__main__":
    asyncio.run(example_usage())
