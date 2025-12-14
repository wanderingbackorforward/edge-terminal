"""
T024: Performance test for data ingestion
Tests data ingestion latency and throughput
Target: <10ms per record processing time
"""
import pytest
import asyncio
import tempfile
import os
import time
from datetime import datetime
from statistics import mean, stdev, median

from edge.database.manager import DatabaseManager
from edge.services.collector.buffer_writer import BufferWriter
from edge.services.cleaner.threshold_validator import ThresholdValidator
from edge.services.cleaner.calibration import CalibrationApplicator


class TestIngestionPerformance:
    """Performance tests for data ingestion pipeline"""

    @pytest.fixture
    def test_db(self):
        """Create temporary test database"""
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        db = DatabaseManager(db_path)

        # Create tables
        with db.transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS plc_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    ring_number INTEGER,
                    tag_name TEXT NOT NULL,
                    value REAL,
                    source_id TEXT NOT NULL,
                    data_quality_flag TEXT DEFAULT 'raw',
                    created_at REAL DEFAULT (julianday('now'))
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS monitoring_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    sensor_type TEXT NOT NULL,
                    value REAL,
                    sensor_location TEXT,
                    unit TEXT,
                    source_id TEXT NOT NULL,
                    data_quality_flag TEXT DEFAULT 'raw',
                    created_at REAL DEFAULT (julianday('now'))
                )
            """)

        yield db

        # Cleanup
        try:
            os.unlink(db_path)
        except:
            pass

    @pytest.mark.asyncio
    async def test_single_record_latency(self, test_db):
        """Test latency for processing a single record"""
        buffer_writer = BufferWriter(
            db_manager=test_db,
            max_size=10000,
            flush_interval=10.0,  # Long interval, we'll flush manually
            flush_threshold=10000
        )

        await buffer_writer.start()

        try:
            latencies = []

            # Test 100 single record writes
            for i in range(100):
                start_time = time.perf_counter()

                # Add record
                buffer_writer.add_plc_log(
                    tag_name='thrust_total',
                    value=12000.0 + i,
                    timestamp=time.time(),
                    source_id='perf_test',
                    data_quality_flag='raw'
                )

                # Force flush to database
                await buffer_writer.flush()

                end_time = time.perf_counter()
                latency_ms = (end_time - start_time) * 1000

                latencies.append(latency_ms)

            # Calculate statistics
            avg_latency = mean(latencies)
            max_latency = max(latencies)
            min_latency = min(latencies)
            median_latency = median(latencies)
            std_latency = stdev(latencies)

            print(f"\n--- Single Record Latency ---")
            print(f"Average: {avg_latency:.3f} ms")
            print(f"Median:  {median_latency:.3f} ms")
            print(f"Min:     {min_latency:.3f} ms")
            print(f"Max:     {max_latency:.3f} ms")
            print(f"StdDev:  {std_latency:.3f} ms")

            # Assert target: <10ms average latency
            assert avg_latency < 10.0, f"Average latency {avg_latency:.3f}ms exceeds 10ms target"

        finally:
            await buffer_writer.stop()

    @pytest.mark.asyncio
    async def test_batch_write_performance(self, test_db):
        """Test batch write performance"""
        buffer_writer = BufferWriter(
            db_manager=test_db,
            max_size=10000,
            flush_interval=10.0,
            flush_threshold=1000  # Flush after 1000 records
        )

        await buffer_writer.start()

        try:
            # Simulate high-frequency data collection
            # 100 tags * 1 Hz * 10 seconds = 1000 records
            num_tags = 100
            num_samples = 10
            total_records = num_tags * num_samples

            start_time = time.perf_counter()

            for sample in range(num_samples):
                timestamp = time.time() + sample

                for tag_idx in range(num_tags):
                    buffer_writer.add_plc_log(
                        tag_name=f'tag_{tag_idx}',
                        value=1000.0 + tag_idx + sample,
                        timestamp=timestamp,
                        source_id='perf_test',
                        data_quality_flag='raw'
                    )

            # Force final flush
            await buffer_writer.flush()

            end_time = time.perf_counter()
            total_time_ms = (end_time - start_time) * 1000
            avg_per_record = total_time_ms / total_records

            print(f"\n--- Batch Write Performance ---")
            print(f"Total records: {total_records}")
            print(f"Total time:    {total_time_ms:.3f} ms")
            print(f"Avg per record: {avg_per_record:.3f} ms")
            print(f"Throughput:    {total_records / (total_time_ms / 1000):.1f} records/sec")

            # Assert target: <10ms per record
            assert avg_per_record < 10.0, \
                f"Average per record {avg_per_record:.3f}ms exceeds 10ms target"

        finally:
            await buffer_writer.stop()

    @pytest.mark.asyncio
    async def test_concurrent_writes(self, test_db):
        """Test concurrent write performance (multiple collectors)"""
        buffer_writer = BufferWriter(
            db_manager=test_db,
            max_size=10000,
            flush_interval=1.0,
            flush_threshold=500
        )

        await buffer_writer.start()

        try:
            async def simulate_collector(collector_id: str, num_records: int):
                """Simulate a data collector"""
                for i in range(num_records):
                    buffer_writer.add_plc_log(
                        tag_name=f'collector_{collector_id}_tag',
                        value=float(i),
                        timestamp=time.time(),
                        source_id=collector_id,
                        data_quality_flag='raw'
                    )
                    await asyncio.sleep(0.001)  # 1ms between records

            # Simulate 5 concurrent collectors
            num_collectors = 5
            records_per_collector = 100

            start_time = time.perf_counter()

            # Run collectors concurrently
            tasks = [
                simulate_collector(f'collector_{i}', records_per_collector)
                for i in range(num_collectors)
            ]
            await asyncio.gather(*tasks)

            # Final flush
            await buffer_writer.flush()

            end_time = time.perf_counter()

            total_records = num_collectors * records_per_collector
            total_time_ms = (end_time - start_time) * 1000
            avg_per_record = total_time_ms / total_records

            print(f"\n--- Concurrent Write Performance ---")
            print(f"Collectors:    {num_collectors}")
            print(f"Total records: {total_records}")
            print(f"Total time:    {total_time_ms:.3f} ms")
            print(f"Avg per record: {avg_per_record:.3f} ms")

            # Verify all records written
            with test_db.get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) as count FROM plc_logs")
                result = cursor.fetchone()
                assert result['count'] == total_records

        finally:
            await buffer_writer.stop()

    @pytest.mark.asyncio
    async def test_quality_pipeline_overhead(self, test_db):
        """Test performance overhead of data quality pipeline"""
        # Test without quality pipeline
        buffer_writer = BufferWriter(
            db_manager=test_db,
            max_size=10000,
            flush_interval=10.0,
            flush_threshold=10000
        )

        await buffer_writer.start()

        try:
            num_records = 1000

            # Baseline: no validation
            start_time = time.perf_counter()

            for i in range(num_records):
                buffer_writer.add_plc_log(
                    tag_name='thrust_total',
                    value=12000.0 + i,
                    timestamp=time.time(),
                    source_id='perf_test',
                    data_quality_flag='raw'
                )

            await buffer_writer.flush()
            baseline_time = time.perf_counter() - start_time

            # With validation
            validator = ThresholdValidator()
            calibrator = CalibrationApplicator()

            start_time = time.perf_counter()

            for i in range(num_records):
                value = 12000.0 + i

                # Threshold validation
                is_valid, reason = validator.validate('thrust_total', value)

                if is_valid:
                    # Calibration
                    value, _ = calibrator.calibrate('thrust_total', value, time.time())

                    # Write
                    buffer_writer.add_plc_log(
                        tag_name='thrust_total',
                        value=value,
                        timestamp=time.time(),
                        source_id='perf_test',
                        data_quality_flag='calibrated'
                    )

            await buffer_writer.flush()
            with_validation_time = time.perf_counter() - start_time

            overhead_ms = (with_validation_time - baseline_time) * 1000
            overhead_per_record = overhead_ms / num_records

            print(f"\n--- Quality Pipeline Overhead ---")
            print(f"Baseline time:      {baseline_time * 1000:.3f} ms")
            print(f"With validation:    {with_validation_time * 1000:.3f} ms")
            print(f"Overhead:           {overhead_ms:.3f} ms")
            print(f"Overhead per record: {overhead_per_record:.3f} ms")

            # Overhead should be minimal (<2ms per record)
            assert overhead_per_record < 2.0, \
                f"Quality pipeline overhead {overhead_per_record:.3f}ms is too high"

        finally:
            await buffer_writer.stop()

    @pytest.mark.asyncio
    async def test_high_frequency_sustained_load(self, test_db):
        """Test sustained high-frequency data collection"""
        buffer_writer = BufferWriter(
            db_manager=test_db,
            max_size=10000,
            flush_interval=1.0,
            flush_threshold=1000
        )

        await buffer_writer.start()

        try:
            # Simulate 1 Hz data collection for 50 tags over 10 seconds
            # Total: 50 tags * 10 samples * 1 Hz = 500 records
            num_tags = 50
            duration_seconds = 10
            samples_per_second = 1

            total_records = 0
            start_time = time.perf_counter()

            for second in range(duration_seconds):
                second_start = time.perf_counter()

                for sample in range(samples_per_second):
                    timestamp = time.time() + (sample / samples_per_second)

                    for tag_idx in range(num_tags):
                        buffer_writer.add_plc_log(
                            tag_name=f'tag_{tag_idx}',
                            value=1000.0 + tag_idx + second,
                            timestamp=timestamp,
                            source_id='perf_test',
                            data_quality_flag='raw'
                        )
                        total_records += 1

                # Sleep to maintain 1 second intervals
                elapsed = time.perf_counter() - second_start
                if elapsed < 1.0:
                    await asyncio.sleep(1.0 - elapsed)

            # Final flush
            await buffer_writer.flush()

            end_time = time.perf_counter()
            total_time = end_time - start_time
            throughput = total_records / total_time

            print(f"\n--- Sustained Load Performance ---")
            print(f"Duration:     {total_time:.2f} seconds")
            print(f"Total records: {total_records}")
            print(f"Throughput:   {throughput:.1f} records/sec")
            print(f"Target rate:  {num_tags * samples_per_second} records/sec")

            # Verify all records written
            with test_db.get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) as count FROM plc_logs")
                result = cursor.fetchone()
                assert result['count'] == total_records

            # Check buffer statistics
            stats = buffer_writer.get_statistics()
            print(f"\nBuffer stats:")
            print(f"  Total added:    {stats['total_added']}")
            print(f"  Total written:  {stats['total_written']}")
            print(f"  Flush count:    {stats['flush_count']}")
            print(f"  Overflow drops: {stats['overflow_drops']}")

            # No records should be dropped
            assert stats['overflow_drops'] == 0, "Buffer overflow occurred"

        finally:
            await buffer_writer.stop()

    @pytest.mark.asyncio
    async def test_database_write_scalability(self, test_db):
        """Test database write performance at different batch sizes"""
        results = {}

        for batch_size in [10, 100, 500, 1000]:
            buffer_writer = BufferWriter(
                db_manager=test_db,
                max_size=10000,
                flush_interval=10.0,
                flush_threshold=batch_size
            )

            await buffer_writer.start()

            try:
                # Write enough records to trigger multiple flushes
                num_records = batch_size * 10

                start_time = time.perf_counter()

                for i in range(num_records):
                    buffer_writer.add_plc_log(
                        tag_name='test_tag',
                        value=float(i),
                        timestamp=time.time(),
                        source_id='perf_test',
                        data_quality_flag='raw'
                    )

                # Final flush
                await buffer_writer.flush()

                end_time = time.perf_counter()
                total_time_ms = (end_time - start_time) * 1000
                avg_per_record = total_time_ms / num_records

                results[batch_size] = {
                    'total_time_ms': total_time_ms,
                    'avg_per_record_ms': avg_per_record,
                    'throughput': num_records / (total_time_ms / 1000)
                }

            finally:
                await buffer_writer.stop()

        print(f"\n--- Database Write Scalability ---")
        print(f"{'Batch Size':<12} {'Total Time':<15} {'Avg/Record':<15} {'Throughput':<15}")
        print(f"{'-' * 60}")

        for batch_size, metrics in sorted(results.items()):
            print(
                f"{batch_size:<12} "
                f"{metrics['total_time_ms']:<15.2f} "
                f"{metrics['avg_per_record_ms']:<15.3f} "
                f"{metrics['throughput']:<15.1f}"
            )

        # All batch sizes should meet <10ms per record target
        for batch_size, metrics in results.items():
            assert metrics['avg_per_record_ms'] < 10.0, \
                f"Batch size {batch_size}: {metrics['avg_per_record_ms']:.3f}ms exceeds target"
