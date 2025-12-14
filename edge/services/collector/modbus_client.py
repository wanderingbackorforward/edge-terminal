"""
T032: Modbus TCP Client Connector
Implements async Modbus TCP client for guidance system data collection
Supports polling-based data retrieval
"""
import asyncio
import logging
from typing import List, Callable, Optional, Dict, Any
from datetime import datetime

try:
    from pymodbus.client import AsyncModbusTcpClient
    from pymodbus.exceptions import ModbusException
except ImportError:
    AsyncModbusTcpClient = None
    ModbusException = Exception

logger = logging.getLogger(__name__)


class ModbusTCPCollector:
    """
    Async Modbus TCP client for collecting guidance system data.

    Features:
    - Polling-based data collection
    - Configurable poll interval
    - Multiple register reading
    - Automatic reconnection
    - Data type conversion (int16, float32, etc.)
    """

    def __init__(
        self,
        host: str,
        port: int = 502,
        register_map: Dict[str, Dict[str, Any]] = None,
        callback: Callable[[str, Any, float], None] = None,
        poll_interval: float = 1.0  # seconds
    ):
        """
        Initialize Modbus TCP collector.

        Args:
            host: Modbus server IP address
            port: Modbus TCP port (default 502)
            register_map: Mapping of tag names to register addresses and types
                         Example: {"pitch": {"address": 100, "count": 2, "type": "float32"}}
            callback: Function to call with collected data
            poll_interval: Polling interval in seconds
        """
        if AsyncModbusTcpClient is None:
            raise ImportError(
                "pymodbus not installed. Install with: pip install pymodbus"
            )

        self.host = host
        self.port = port
        self.register_map = register_map or {}
        self.callback = callback
        self.poll_interval = poll_interval

        self.client: Optional[AsyncModbusTcpClient] = None
        self._running = False
        self._reconnect_delay = 5  # seconds

    async def connect(self) -> None:
        """Establish connection to Modbus server"""
        try:
            self.client = AsyncModbusTcpClient(
                host=self.host,
                port=self.port,
                timeout=3
            )

            await self.client.connect()

            if self.client.connected:
                logger.info(f"Connected to Modbus TCP server: {self.host}:{self.port}")
            else:
                raise ConnectionError("Failed to establish Modbus connection")

        except Exception as e:
            logger.error(f"Modbus connection failed: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from Modbus server"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from Modbus server")
            self.client = None

    async def read_registers(
        self,
        tag_name: str,
        address: int,
        count: int,
        data_type: str = "int16"
    ) -> Optional[Any]:
        """
        Read holding registers and convert to appropriate data type.

        Args:
            tag_name: Tag identifier
            address: Starting register address
            count: Number of registers to read
            data_type: Data type conversion ('int16', 'uint16', 'float32', 'int32')

        Returns:
            Converted value or None on error
        """
        if not self.client or not self.client.connected:
            return None

        try:
            # Read holding registers
            response = await self.client.read_holding_registers(
                address=address,
                count=count,
                slave=1  # Modbus slave ID
            )

            if response.isError():
                logger.error(f"Modbus read error for {tag_name}: {response}")
                return None

            # Convert register values to appropriate type
            registers = response.registers

            if data_type == "int16":
                # Single 16-bit signed integer
                value = registers[0] if registers[0] < 32768 else registers[0] - 65536

            elif data_type == "uint16":
                # Single 16-bit unsigned integer
                value = registers[0]

            elif data_type == "float32":
                # 32-bit float (2 registers, big-endian)
                import struct
                bytes_data = struct.pack('>HH', registers[0], registers[1])
                value = struct.unpack('>f', bytes_data)[0]

            elif data_type == "int32":
                # 32-bit signed integer (2 registers)
                value = (registers[0] << 16) | registers[1]
                if value >= 2**31:
                    value -= 2**32

            else:
                logger.warning(f"Unknown data type: {data_type}, returning raw")
                value = registers[0] if len(registers) == 1 else registers

            return value

        except Exception as e:
            logger.error(f"Error reading {tag_name}: {e}")
            return None

    async def poll_sensors(self) -> None:
        """
        Poll all configured sensors once.
        """
        timestamp = datetime.utcnow().timestamp()

        for tag_name, config in self.register_map.items():
            address = config['address']
            count = config.get('count', 1)
            data_type = config.get('type', 'int16')

            value = await self.read_registers(tag_name, address, count, data_type)

            if value is not None and self.callback:
                self.callback(tag_name, value, timestamp)

    async def run(self) -> None:
        """
        Main polling loop with automatic reconnection.
        """
        self._running = True

        while self._running:
            try:
                await self.connect()

                # Polling loop
                while self._running and self.client and self.client.connected:
                    await self.poll_sensors()
                    await asyncio.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"Modbus collector error: {e}")

                # Attempt reconnection after delay
                logger.info(f"Reconnecting in {self._reconnect_delay} seconds...")
                await asyncio.sleep(self._reconnect_delay)

            finally:
                await self.disconnect()

    async def stop(self) -> None:
        """Stop polling loop"""
        self._running = False
        await self.disconnect()


# Example usage
async def example_usage():
    """
    Example of using ModbusTCPCollector for guidance system data
    """
    def data_callback(tag_name: str, value: Any, timestamp: float):
        """Callback for received data"""
        print(f"Tag: {tag_name}, Value: {value}, Time: {timestamp}")

    # Register map for guidance system
    register_map = {
        "pitch": {"address": 100, "count": 2, "type": "float32"},
        "roll": {"address": 102, "count": 2, "type": "float32"},
        "yaw": {"address": 104, "count": 2, "type": "float32"},
        "horizontal_deviation": {"address": 106, "count": 2, "type": "float32"},
        "vertical_deviation": {"address": 108, "count": 2, "type": "float32"},
    }

    collector = ModbusTCPCollector(
        host="192.168.1.100",
        port=502,
        register_map=register_map,
        callback=data_callback,
        poll_interval=1.0
    )

    try:
        await collector.run()
    except KeyboardInterrupt:
        await collector.stop()


if __name__ == "__main__":
    asyncio.run(example_usage())
