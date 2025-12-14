"""
T036: Raw Data Buffer Writer
Batches data writes to database for performance optimization
Supports configurable flush strategies and overflow handling
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from collections import deque
from datetime import datetime
import threading

logger = logging.getLogger(__name__)


class BufferWriter:
    """
    Buffers incoming sensor data and writes in batches to database.

    Features:
    - Configurable buffer size and flush intervals
    - Automatic flushing on size threshold
    - Background flush timer
    - Overflow strategies (drop_oldest, drop_newest, block)
    - Thread-safe operations
    - Statistics tracking
    """

    def __init__(
        self,
        db_manager,
        max_size: int = 10000,
        flush_interval: float = 5.0,
        flush_threshold: int = 1000,
        overflow_strategy: str = "drop_oldest"
    ):
        """
        Initialize buffer writer.

        Args:
            db_manager: DatabaseManager instance
            max_size: Maximum buffer size
            flush_interval: Auto-flush interval (seconds)
            flush_threshold: Flush when buffer reaches this size
            overflow_strategy: 'drop_oldest', 'drop_newest', or 'block'
        """
        self.db_manager = db_manager
        self.max_size = max_size
        self.flush_interval = flush_interval
        self.flush_threshold = flush_threshold
        self.overflow_strategy = overflow_strategy

        self.buffer = deque()
        self.lock = threading.Lock()
        self.running = False
        self.flush_task = None

        self.stats = {
            'total_received': 0,
            'total_written': 0,
            'total_dropped': 0,
            'flush_count': 0,
            'last_flush_time': None
        }

    async def start(self) -> None:
        """Start the buffer writer and background flush timer"""
        self.running = True
        self.flush_task = asyncio.create_task(self._auto_flush_loop())
        logger.info(
            f"BufferWriter started: max_size={self.max_size}, "
            f"flush_interval={self.flush_interval}s, "
            f"threshold={self.flush_threshold}"
        )

    async def stop(self) -> None:
        """Stop the buffer writer and flush remaining data"""
        self.running = False
        if self.flush_task:
            self.flush_task.cancel()
            try:
                await self.flush_task
            except asyncio.CancelledError:
                pass

        # Flush any remaining data
        await self.flush()
        logger.info("BufferWriter stopped")

    def add_plc_log(
        self,
        tag_name: str,
        value: float,
        timestamp: float,
        source_id: str,
        ring_number: Optional[int] = None,
        data_quality_flag: str = "raw"
    ) -> bool:
        """
        Add PLC log entry to buffer.

        Args:
            tag_name: Tag identifier
            value: Sensor reading
            timestamp: Unix timestamp
            source_id: Data source identifier
            ring_number: Ring number (if available)
            data_quality_flag: Quality flag

        Returns:
            True if added successfully, False if dropped due to overflow
        """
        entry = {
            'type': 'plc_log',
            'tag_name': tag_name,
            'value': value,
            'timestamp': timestamp,
            'source_id': source_id,
            'ring_number': ring_number,
            'data_quality_flag': data_quality_flag,
            'created_at': datetime.utcnow().timestamp()
        }

        return self._add_to_buffer(entry)

    def add_attitude_log(
        self,
        timestamp: float,
        pitch: float,
        roll: float,
        yaw: float,
        horizontal_deviation: float,
        vertical_deviation: float,
        axis_deviation: float,
        source_id: str,
        ring_number: Optional[int] = None
    ) -> bool:
        """
        Add attitude log entry to buffer.

        Args:
            timestamp: Unix timestamp
            pitch, roll, yaw: Shield orientation (degrees)
            horizontal_deviation, vertical_deviation, axis_deviation: Deviations (mm)
            source_id: Data source identifier
            ring_number: Ring number (if available)

        Returns:
            True if added successfully, False if dropped
        """
        entry = {
            'type': 'attitude_log',
            'timestamp': timestamp,
            'pitch': pitch,
            'roll': roll,
            'yaw': yaw,
            'horizontal_deviation': horizontal_deviation,
            'vertical_deviation': vertical_deviation,
            'axis_deviation': axis_deviation,
            'source_id': source_id,
            'ring_number': ring_number,
            'created_at': datetime.utcnow().timestamp()
        }

        return self._add_to_buffer(entry)

    def add_monitoring_log(
        self,
        timestamp: float,
        sensor_type: str,
        value: float,
        sensor_location: Optional[str] = None,
        unit: Optional[str] = None,
        ring_number: Optional[int] = None
    ) -> bool:
        """
        Add monitoring log entry to buffer.

        Args:
            timestamp: Unix timestamp
            sensor_type: Type of monitoring sensor
            value: Sensor reading
            sensor_location: Physical location of sensor
            unit: Unit of measurement
            ring_number: Associated ring number

        Returns:
            True if added successfully, False if dropped
        """
        entry = {
            'type': 'monitoring_log',
            'timestamp': timestamp,
            'sensor_type': sensor_type,
            'value': value,
            'sensor_location': sensor_location,
            'unit': unit,
            'ring_number': ring_number,
            'created_at': datetime.utcnow().timestamp()
        }

        return self._add_to_buffer(entry)

    def _add_to_buffer(self, entry: Dict[str, Any]) -> bool:
        """
        Add entry to buffer with overflow handling.

        Args:
            entry: Data entry dictionary

        Returns:
            True if added, False if dropped
        """
        with self.lock:
            self.stats['total_received'] += 1

            # Check if buffer is full
            if len(self.buffer) >= self.max_size:
                if self.overflow_strategy == "drop_oldest":
                    self.buffer.popleft()
                    self.stats['total_dropped'] += 1
                    logger.warning(f"Buffer full, dropped oldest entry")
                elif self.overflow_strategy == "drop_newest":
                    self.stats['total_dropped'] += 1
                    logger.warning(f"Buffer full, dropped newest entry")
                    return False
                elif self.overflow_strategy == "block":
                    logger.warning(f"Buffer full, blocking not implemented in sync add")
                    return False

            self.buffer.append(entry)

            # Check if we should flush based on threshold
            if len(self.buffer) >= self.flush_threshold:
                # Schedule flush in background (non-blocking)
                asyncio.create_task(self.flush())

            return True

    async def flush(self) -> int:
        """
        Flush buffer to database.

        Returns:
            Number of records written
        """
        with self.lock:
            if not self.buffer:
                return 0

            # Get all entries from buffer
            entries = list(self.buffer)
            self.buffer.clear()

        # Group entries by type
        plc_logs = []
        attitude_logs = []
        monitoring_logs = []

        for entry in entries:
            if entry['type'] == 'plc_log':
                plc_logs.append(entry)
            elif entry['type'] == 'attitude_log':
                attitude_logs.append(entry)
            elif entry['type'] == 'monitoring_log':
                monitoring_logs.append(entry)

        written_count = 0

        try:
            # Write PLC logs
            if plc_logs:
                written_count += await self._write_plc_logs(plc_logs)

            # Write attitude logs
            if attitude_logs:
                written_count += await self._write_attitude_logs(attitude_logs)

            # Write monitoring logs
            if monitoring_logs:
                written_count += await self._write_monitoring_logs(monitoring_logs)

            self.stats['total_written'] += written_count
            self.stats['flush_count'] += 1
            self.stats['last_flush_time'] = datetime.utcnow().timestamp()

            logger.info(
                f"Flushed {written_count} records to database "
                f"(PLC: {len(plc_logs)}, Attitude: {len(attitude_logs)}, "
                f"Monitoring: {len(monitoring_logs)})"
            )

        except Exception as e:
            logger.error(f"Error flushing buffer: {e}")
            # Re-add entries to buffer if write failed
            with self.lock:
                for entry in entries:
                    if len(self.buffer) < self.max_size:
                        self.buffer.append(entry)

        return written_count

    async def _write_plc_logs(self, logs: List[Dict[str, Any]]) -> int:
        """Write PLC logs to database in batch"""
        query = """
            INSERT INTO plc_logs
            (timestamp, ring_number, tag_name, value, source_id, data_quality_flag, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """

        params_list = [
            (
                log['timestamp'],
                log.get('ring_number'),
                log['tag_name'],
                log['value'],
                log['source_id'],
                log.get('data_quality_flag', 'raw'),
                log['created_at']
            )
            for log in logs
        ]

        with self.db_manager.transaction() as conn:
            conn.executemany(query, params_list)

        return len(logs)

    async def _write_attitude_logs(self, logs: List[Dict[str, Any]]) -> int:
        """Write attitude logs to database in batch"""
        query = """
            INSERT INTO attitude_logs
            (timestamp, ring_number, pitch, roll, yaw,
             horizontal_deviation, vertical_deviation, axis_deviation,
             source_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        params_list = [
            (
                log['timestamp'],
                log.get('ring_number'),
                log['pitch'],
                log['roll'],
                log['yaw'],
                log['horizontal_deviation'],
                log['vertical_deviation'],
                log['axis_deviation'],
                log['source_id'],
                log['created_at']
            )
            for log in logs
        ]

        with self.db_manager.transaction() as conn:
            conn.executemany(query, params_list)

        return len(logs)

    async def _write_monitoring_logs(self, logs: List[Dict[str, Any]]) -> int:
        """Write monitoring logs to database in batch"""
        query = """
            INSERT INTO monitoring_logs
            (timestamp, ring_number, sensor_type, sensor_location, value, unit, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """

        params_list = [
            (
                log['timestamp'],
                log.get('ring_number'),
                log['sensor_type'],
                log.get('sensor_location'),
                log['value'],
                log.get('unit'),
                log['created_at']
            )
            for log in logs
        ]

        with self.db_manager.transaction() as conn:
            conn.executemany(query, params_list)

        return len(logs)

    async def _auto_flush_loop(self) -> None:
        """Background task to auto-flush buffer at intervals"""
        while self.running:
            try:
                await asyncio.sleep(self.flush_interval)
                await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in auto-flush loop: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get buffer statistics"""
        with self.lock:
            buffer_size = len(self.buffer)
            buffer_utilization = (buffer_size / self.max_size) * 100

        return {
            'buffer_size': buffer_size,
            'buffer_max_size': self.max_size,
            'buffer_utilization_percent': round(buffer_utilization, 2),
            'total_received': self.stats['total_received'],
            'total_written': self.stats['total_written'],
            'total_dropped': self.stats['total_dropped'],
            'drop_rate_percent': round(
                (self.stats['total_dropped'] / max(self.stats['total_received'], 1)) * 100, 2
            ),
            'flush_count': self.stats['flush_count'],
            'last_flush_time': self.stats['last_flush_time']
        }


# Example usage
if __name__ == "__main__":
    import sys
    sys.path.append('/home/monss/tunnel-su-1/shield-tunneling-icp')

    from edge.database.manager import DatabaseManager

    async def example_usage():
        """Example of using BufferWriter"""
        db = DatabaseManager("data/edge.db")
        buffer = BufferWriter(
            db_manager=db,
            max_size=100,
            flush_interval=2.0,
            flush_threshold=10
        )

        await buffer.start()

        # Simulate adding data
        for i in range(25):
            buffer.add_plc_log(
                tag_name="thrust_total",
                value=10000 + i * 100,
                timestamp=datetime.utcnow().timestamp(),
                source_id="plc_main",
                data_quality_flag="raw"
            )

            if i % 10 == 0:
                print(f"Added {i+1} records. Stats: {buffer.get_statistics()}")

        # Wait for auto-flush
        await asyncio.sleep(3)

        print("\nFinal statistics:")
        print(buffer.get_statistics())

        await buffer.stop()

    asyncio.run(example_usage())
