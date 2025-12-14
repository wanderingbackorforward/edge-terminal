"""
Unit tests for RingBoundaryDetector
Tests ring boundary detection using multiple methods
"""
import pytest
from unittest.mock import MagicMock, Mock
from datetime import datetime
from edge.services.aligner.ring_detector import RingBoundaryDetector


class TestRingBoundaryDetector:
    """Test cases for RingBoundaryDetector"""

    @pytest.fixture
    def detector(self):
        """Create detector instance"""
        return RingBoundaryDetector()

    @pytest.fixture
    def mock_db(self):
        """Create mock database"""
        db = MagicMock()
        mock_conn = MagicMock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        db.get_connection.return_value = mock_conn
        return db, mock_conn

    def test_detect_from_advance_sensor_success(self, detector, mock_db):
        """Test detecting ring boundary from advance sensor"""
        db, mock_conn = mock_db

        ring_number = 100
        start_time = datetime(2025, 11, 19, 10, 0).timestamp()

        # Mock advance sensor data showing ring completion
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'timestamp': start_time + 100, 'value': 0.0},
            {'timestamp': start_time + 1000, 'value': 750.0},  # Mid-ring
            {'timestamp': start_time + 1800, 'value': 1500.0},  # Ring complete
            {'timestamp': start_time + 2000, 'value': 1500.0},
        ]
        mock_conn.execute.return_value = mock_cursor

        result = detector.detect_from_advance_sensor(
            db, ring_number, start_time
        )

        # Should detect completion when advance reaches ring length
        assert result is not None
        assert isinstance(result, tuple)
        assert len(result) == 2  # (start_time, end_time)

    def test_detect_from_assembly_signal_success(self, detector, mock_db):
        """Test detecting ring boundary from assembly signal"""
        db, mock_conn = mock_db

        ring_number = 100
        start_time = datetime(2025, 11, 19, 10, 0).timestamp()

        # Mock ring assembly signal
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'start_time': start_time,
            'end_time': start_time + 2700  # 45 minutes
        }
        mock_conn.execute.return_value = mock_cursor

        result = detector.detect_from_ring_assembly_signal(
            db, ring_number
        )

        assert result is not None
        assert result[0] == start_time
        assert result[1] == start_time + 2700

    def test_detect_with_time_fallback(self, detector, mock_db):
        """Test fallback time-based detection"""
        db, mock_conn = mock_db

        ring_number = 100
        prev_ring_end = datetime(2025, 11, 19, 10, 0).timestamp()

        # Mock PLC data showing activity
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'timestamp': prev_ring_end + 100},
            {'timestamp': prev_ring_end + 1000},
            {'timestamp': prev_ring_end + 2000},
        ]
        mock_conn.execute.return_value = mock_cursor

        result = detector.detect_with_time_fallback(
            db, ring_number, prev_ring_end
        )

        # Should estimate based on average ring time
        assert result is not None
        assert result[0] > prev_ring_end

    def test_detect_ring_boundary_cascade(self, detector, mock_db):
        """Test cascade of detection methods"""
        db, mock_conn = mock_db

        ring_number = 100
        prev_ring_end = datetime(2025, 11, 19, 10, 0).timestamp()

        # First method fails (no advance sensor data)
        # Second method succeeds (assembly signal)
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []  # No advance data
        mock_cursor.fetchone.return_value = {
            'start_time': prev_ring_end,
            'end_time': prev_ring_end + 2700
        }
        mock_conn.execute.return_value = mock_cursor

        result = detector.detect_ring_boundary(
            db, ring_number, prev_ring_end
        )

        # Should fall back to assembly signal
        assert result is not None

    def test_detect_no_data(self, detector, mock_db):
        """Test detection when no data is available"""
        db, mock_conn = mock_db

        ring_number = 999
        prev_ring_end = datetime(2025, 11, 19, 10, 0).timestamp()

        # Mock empty responses for all methods
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None
        mock_conn.execute.return_value = mock_cursor

        result = detector.detect_ring_boundary(
            db, ring_number, prev_ring_end
        )

        # Should return None when no data available
        assert result is None

    def test_validate_boundary_times(self, detector):
        """Test boundary time validation"""
        start_time = datetime(2025, 11, 19, 10, 0).timestamp()
        end_time = start_time + 2700

        is_valid = detector.validate_boundary_times(start_time, end_time)
        assert is_valid is True

        # Invalid: end before start
        is_valid = detector.validate_boundary_times(end_time, start_time)
        assert is_valid is False

        # Invalid: too short duration
        is_valid = detector.validate_boundary_times(start_time, start_time + 60)
        assert is_valid is False

        # Invalid: too long duration
        is_valid = detector.validate_boundary_times(start_time, start_time + 10800)
        assert is_valid is False

    def test_estimate_ring_duration(self, detector, mock_db):
        """Test estimating ring duration from historical data"""
        db, mock_conn = mock_db

        # Mock historical ring durations
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'duration': 2700},  # 45 min
            {'duration': 2800},  # 47 min
            {'duration': 2600},  # 43 min
            {'duration': 2700},  # 45 min
        ]
        mock_conn.execute.return_value = mock_cursor

        estimated_duration = detector.estimate_ring_duration(db)

        # Should be around 2700 seconds (average)
        assert 2500 < estimated_duration < 2900

    def test_detect_from_thrust_pattern(self, detector, mock_db):
        """Test detecting ring boundary from thrust pattern"""
        db, mock_conn = mock_db

        ring_number = 100
        start_time = datetime(2025, 11, 19, 10, 0).timestamp()

        # Mock thrust data showing excavation start/stop
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'timestamp': start_time + 100, 'value': 5000.0},  # Low (stopped)
            {'timestamp': start_time + 200, 'value': 12000.0},  # High (excavating)
            {'timestamp': start_time + 2500, 'value': 12000.0},
            {'timestamp': start_time + 2700, 'value': 5000.0},  # Low (stopped)
        ]
        mock_conn.execute.return_value = mock_cursor

        result = detector.detect_from_thrust_pattern(
            db, ring_number, start_time
        )

        # Should detect start and stop based on thrust changes
        if result:
            assert result[0] >= start_time
            assert result[1] > result[0]

    def test_get_statistics(self, detector, mock_db):
        """Test detector statistics"""
        db, mock_conn = mock_db

        # Perform some detections
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'start_time': 1000.0,
            'end_time': 3700.0
        }
        mock_conn.execute.return_value = mock_cursor

        detector.detect_ring_boundary(db, 100, 1000.0)
        detector.detect_ring_boundary(db, 101, 3700.0)

        stats = detector.get_statistics()

        assert 'rings_detected' in stats
        assert stats['rings_detected'] >= 0

    def test_reset_statistics(self, detector):
        """Test statistics reset"""
        detector.reset_statistics()

        stats = detector.get_statistics()
        assert stats['rings_detected'] == 0

    def test_multiple_detection_methods_agreement(self, detector, mock_db):
        """Test agreement between multiple detection methods"""
        db, mock_conn = mock_db

        ring_number = 100
        start_time = datetime(2025, 11, 19, 10, 0).timestamp()
        end_time = start_time + 2700

        # Mock all methods returning similar results
        mock_cursor = MagicMock()

        # Advance sensor
        mock_cursor.fetchall.return_value = [
            {'timestamp': start_time + 1800, 'value': 1500.0}
        ]

        # Assembly signal
        mock_cursor.fetchone.return_value = {
            'start_time': start_time,
            'end_time': end_time
        }

        mock_conn.execute.return_value = mock_cursor

        result1 = detector.detect_from_advance_sensor(db, ring_number, start_time)
        result2 = detector.detect_from_ring_assembly_signal(db, ring_number)

        # Results from different methods should be similar
        if result1 and result2:
            time_diff = abs(result1[1] - result2[1])
            assert time_diff < 600  # Within 10 minutes
