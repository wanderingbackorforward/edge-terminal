"""
T023: Integration test for end-to-end data pipeline
Tests complete flow: collection -> cleaning -> aggregation -> persistence
"""
import pytest
import tempfile
import os
from datetime import datetime
from edge.database.manager import DatabaseManager
from edge.services.cleaner.threshold_validator import ThresholdValidator
from edge.services.cleaner.interpolator import DataInterpolator
from edge.services.aligner.plc_aggregator import PLCAggregator
from edge.services.aligner.ring_summary_writer import RingSummaryWriter


class TestDataPipeline:
    """Integration tests for complete data pipeline"""

    @pytest.fixture
    def test_db(self):
        """Create temporary test database"""
        # Create temp database file
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        db = DatabaseManager(db_path)

        # Create tables
        with db.transaction() as conn:
            # Create plc_logs table
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

            # Create ring_summary table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ring_summary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ring_number INTEGER UNIQUE NOT NULL,
                    start_time REAL NOT NULL,
                    end_time REAL NOT NULL,
                    mean_thrust REAL,
                    max_thrust REAL,
                    min_thrust REAL,
                    std_thrust REAL,
                    mean_torque REAL,
                    max_torque REAL,
                    mean_penetration_rate REAL,
                    max_penetration_rate REAL,
                    mean_chamber_pressure REAL,
                    max_chamber_pressure REAL,
                    mean_pitch REAL,
                    mean_roll REAL,
                    mean_yaw REAL,
                    horizontal_deviation REAL,
                    vertical_deviation REAL,
                    specific_energy REAL,
                    ground_loss_rate REAL,
                    volume_loss_ratio REAL,
                    settlement_value REAL,
                    data_completeness_flag TEXT DEFAULT 'incomplete',
                    geological_zone TEXT,
                    synced_to_cloud INTEGER DEFAULT 0,
                    created_at REAL,
                    updated_at REAL
                )
            """)

        yield db

        # Cleanup
        try:
            os.unlink(db_path)
        except:
            pass

    def test_end_to_end_pipeline(self, test_db):
        """Test complete data pipeline flow"""
        # 1. Insert raw PLC data
        ring_number = 100
        start_time = datetime(2025, 11, 19, 10, 0).timestamp()
        end_time = datetime(2025, 11, 19, 10, 45).timestamp()

        with test_db.transaction() as conn:
            # Insert sample PLC data
            for i in range(100):
                timestamp = start_time + (i * 27)  # ~45 min / 100 samples
                conn.execute(
                    """
                    INSERT INTO plc_logs
                    (timestamp, ring_number, tag_name, value, source_id, data_quality_flag)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (timestamp, ring_number, 'thrust_total', 12000 + i * 50, 'test_source', 'raw')
                )

            # Insert torque data
            for i in range(100):
                timestamp = start_time + (i * 27)
                conn.execute(
                    """
                    INSERT INTO plc_logs
                    (timestamp, ring_number, tag_name, value, source_id, data_quality_flag)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (timestamp, ring_number, 'torque', 900 + i * 2, 'test_source', 'raw')
                )

        # 2. Aggregate data
        aggregator = PLCAggregator()
        plc_features = aggregator.aggregate_ring_data(
            test_db, ring_number, start_time, end_time
        )

        # Verify aggregation
        assert 'mean_thrust_total' in plc_features
        assert 'mean_torque' in plc_features
        assert plc_features['mean_thrust_total'] > 0

        # 3. Write to ring_summary
        writer = RingSummaryWriter()

        success = writer.write_ring_summary(
            test_db, ring_number, start_time, end_time,
            plc_features=plc_features,
            attitude_features={},
            derived_indicators={},
            settlement_features={},
            geological_zone='Test'
        )

        assert success is True

        # 4. Verify data was written
        with test_db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM ring_summary WHERE ring_number = ?",
                (ring_number,)
            )
            result = cursor.fetchone()

            assert result is not None
            assert result['ring_number'] == ring_number
            assert result['mean_thrust'] is not None

    def test_data_quality_pipeline(self, test_db):
        """Test data quality validation and filtering"""
        # Insert mixed quality data
        ring_number = 101
        start_time = datetime(2025, 11, 19, 11, 0).timestamp()
        end_time = datetime(2025, 11, 19, 11, 45).timestamp()

        with test_db.transaction() as conn:
            # Good data
            conn.execute(
                """
                INSERT INTO plc_logs
                (timestamp, ring_number, tag_name, value, source_id, data_quality_flag)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (start_time, ring_number, 'thrust_total', 12000, 'test', 'raw')
            )

            # Rejected data (should be filtered out)
            conn.execute(
                """
                INSERT INTO plc_logs
                (timestamp, ring_number, tag_name, value, source_id, data_quality_flag)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (start_time + 10, ring_number, 'thrust_total', 99999, 'test', 'rejected')
            )

            # More good data
            conn.execute(
                """
                INSERT INTO plc_logs
                (timestamp, ring_number, tag_name, value, source_id, data_quality_flag)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (start_time + 20, ring_number, 'thrust_total', 13000, 'test', 'raw')
            )

        # Aggregate
        aggregator = PLCAggregator()
        features = aggregator.aggregate_ring_data(
            test_db, ring_number, start_time, end_time
        )

        # Mean should be (12000 + 13000) / 2 = 12500, not including rejected value
        assert features['mean_thrust_total'] == 12500.0

    def test_multiple_rings(self, test_db):
        """Test processing multiple rings"""
        writer = RingSummaryWriter()

        for ring_num in [100, 101, 102]:
            start_time = datetime(2025, 11, 19, 10 + ring_num - 100, 0).timestamp()
            end_time = start_time + 2700  # 45 minutes

            # Write ring summary
            writer.write_ring_summary(
                test_db, ring_num, start_time, end_time,
                plc_features={'mean_thrust_total': 12000.0 + ring_num * 100},
                attitude_features={},
                derived_indicators={},
                settlement_features={}
            )

        # Verify all rings written
        with test_db.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM ring_summary")
            result = cursor.fetchone()
            assert result['count'] == 3

    def test_update_existing_ring(self, test_db):
        """Test updating an existing ring"""
        ring_number = 100
        start_time = datetime(2025, 11, 19, 10, 0).timestamp()
        end_time = start_time + 2700

        writer = RingSummaryWriter()

        # Initial write
        writer.write_ring_summary(
            test_db, ring_number, start_time, end_time,
            plc_features={'mean_thrust_total': 12000.0},
            attitude_features={},
            derived_indicators={},
            settlement_features={}
        )

        # Update with new data
        writer.write_ring_summary(
            test_db, ring_number, start_time, end_time,
            plc_features={'mean_thrust_total': 15000.0},  # Updated value
            attitude_features={},
            derived_indicators={},
            settlement_features={}
        )

        # Verify update
        with test_db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT mean_thrust FROM ring_summary WHERE ring_number = ?",
                (ring_number,)
            )
            result = cursor.fetchone()
            assert result['mean_thrust'] == 15000.0

        # Should have updated, not inserted
        stats = writer.get_statistics()
        assert stats['rings_updated'] == 1
        assert stats['rings_inserted'] == 1  # First write
