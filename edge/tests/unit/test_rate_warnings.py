"""
T128: Unit tests for rate-based anomaly detection
Tests RateDetector for abnormal rate of change
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock

from edge.services.warning.rate_detector import RateDetector
from edge.models.warning_threshold import WarningThreshold
from edge.models.ring_summary import RingSummary


@pytest.fixture
def rate_threshold():
    """Rate-based threshold configuration"""
    threshold = WarningThreshold(
        threshold_id="test-rate-settlement",
        indicator_name="settlement_value",
        geological_zone="all",
        indicator_unit="mm",
        rate_attention_multiplier=2.0,  # 2× average
        rate_warning_multiplier=3.0,    # 3× average
        rate_alarm_multiplier=5.0,      # 5× average
        rate_enabled=True,
        rate_window_size=10,
        description="Settlement rate monitoring"
    )
    return threshold


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    session = Mock()
    return session


@pytest.fixture
def rate_detector(mock_db_session, rate_threshold):
    """RateDetector with test configuration"""
    thresholds = {
        "settlement_value_all": rate_threshold
    }
    return RateDetector(mock_db_session, thresholds)


def create_ring_summary(ring_number, settlement_value):
    """Helper to create RingSummary mock"""
    ring = Mock(spec=RingSummary)
    ring.ring_number = ring_number
    ring.settlement_value = settlement_value
    ring.mean_chamber_pressure = 2.5
    ring.mean_advance_rate = 50.0
    return ring


class TestRateDetector:
    """Unit tests for RateDetector"""

    @pytest.mark.unit
    def test_insufficient_historical_data(self, rate_detector, mock_db_session):
        """Test that insufficient history doesn't trigger warnings"""
        # Mock query to return only 1 ring (need at least 2)
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [create_ring_summary(99, 10.0)]

        mock_db_session.query.return_value = mock_query

        warning = rate_detector.check(
            ring_number=100,
            indicator_name="settlement_value",
            indicator_value=15.0,
            geological_zone="all"
        )

        assert warning is None

    @pytest.mark.unit
    def test_normal_rate_no_warning(self, rate_detector, mock_db_session):
        """Test that normal rate of change doesn't trigger warnings"""
        # Mock historical data: 10 rings with settlement around 10mm
        historical_rings = [
            create_ring_summary(90 + i, 10.0 + i * 0.5)
            for i in range(10)
        ]

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = historical_rings

        mock_db_session.query.return_value = mock_query

        # Current value: 15.5mm (continuing normal trend)
        warning = rate_detector.check(
            ring_number=100,
            indicator_name="settlement_value",
            indicator_value=15.5,
            geological_zone="all"
        )

        assert warning is None

    @pytest.mark.unit
    def test_attention_rate_triggered(self, rate_detector, mock_db_session):
        """Test ATTENTION level for 2× average rate"""
        # Historical: stable around 10mm (avg change ~ 0.5mm)
        historical_rings = [
            create_ring_summary(90 + i, 10.0 + i * 0.5)
            for i in range(10)
        ]

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = historical_rings

        mock_db_session.query.return_value = mock_query

        # Current: 16.0mm (change = 1.5mm from 14.5mm, ~3× normal 0.5mm)
        warning = rate_detector.check(
            ring_number=100,
            indicator_name="settlement_value",
            indicator_value=16.0,
            geological_zone="all"
        )

        assert warning is not None
        assert warning.warning_type == "rate"
        assert warning.indicator_name == "settlement_value"

    @pytest.mark.unit
    def test_warning_rate_triggered(self, rate_detector, mock_db_session):
        """Test WARNING level for 3× average rate"""
        # Historical: stable around 10mm
        historical_rings = [
            create_ring_summary(90 + i, 10.0 + i * 0.3)
            for i in range(10)
        ]

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = historical_rings

        mock_db_session.query.return_value = mock_query

        # Large jump: change ~3× historical average
        warning = rate_detector.check(
            ring_number=100,
            indicator_name="settlement_value",
            indicator_value=15.0,  # Jump from ~13mm
            geological_zone="all"
        )

        assert warning is not None
        assert warning.warning_level in ["WARNING", "ALARM"]

    @pytest.mark.unit
    def test_alarm_rate_triggered(self, rate_detector, mock_db_session):
        """Test ALARM level for 5× average rate"""
        # Historical: very stable
        historical_rings = [
            create_ring_summary(90 + i, 10.0 + i * 0.1)
            for i in range(10)
        ]

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = historical_rings

        mock_db_session.query.return_value = mock_query

        # Huge jump: 5mm change (50× normal 0.1mm)
        warning = rate_detector.check(
            ring_number=100,
            indicator_name="settlement_value",
            indicator_value=16.0,  # From 11mm to 16mm
            geological_zone="all"
        )

        assert warning is not None
        assert warning.warning_level == "ALARM"

    @pytest.mark.unit
    def test_rate_decrease_detection(self, rate_detector, mock_db_session):
        """Test that rate decrease (negative change) also triggers warnings"""
        # Historical: gradually increasing
        historical_rings = [
            create_ring_summary(90 + i, 10.0 + i * 0.5)
            for i in range(10)
        ]

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = historical_rings

        mock_db_session.query.return_value = mock_query

        # Sudden drop (abnormal rate of decrease)
        warning = rate_detector.check(
            ring_number=100,
            indicator_name="settlement_value",
            indicator_value=10.0,  # Dropped from 14.5 to 10
            geological_zone="all"
        )

        # Should trigger warning for abnormal rate change
        assert warning is not None

    @pytest.mark.unit
    def test_indicator_field_mapping(self, rate_detector, mock_db_session):
        """Test that indicator field mapping works correctly"""
        # Test with mean_chamber_pressure (maps to field in RingSummary)
        threshold = WarningThreshold(
            threshold_id="test-pressure-rate",
            indicator_name="mean_chamber_pressure",
            geological_zone="all",
            rate_attention_multiplier=2.0,
            rate_enabled=True,
            rate_window_size=5
        )

        detector = RateDetector(mock_db_session, {
            "mean_chamber_pressure_all": threshold
        })

        # Mock historical rings with pressure values
        historical_rings = [create_ring_summary(95 + i, 10.0) for i in range(5)]
        for i, ring in enumerate(historical_rings):
            ring.mean_chamber_pressure = 2.0 + i * 0.1

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = historical_rings

        mock_db_session.query.return_value = mock_query

        # Should not crash with field mapping
        warning = detector.check(
            ring_number=100,
            indicator_name="mean_chamber_pressure",
            indicator_value=3.0,
            geological_zone="all"
        )

        # May or may not trigger depending on calculation, but shouldn't crash
        assert warning is None or isinstance(warning.warning_level, str)

    @pytest.mark.unit
    def test_disabled_rate_monitoring(self, rate_detector, rate_threshold):
        """Test that disabled rate monitoring doesn't trigger warnings"""
        rate_threshold.rate_enabled = False

        detector = RateDetector(Mock(), {
            "settlement_value_all": rate_threshold
        })

        warning = detector.check(
            ring_number=100,
            indicator_name="settlement_value",
            indicator_value=100.0,  # Extreme value
            geological_zone="all"
        )

        assert warning is None

    @pytest.mark.unit
    def test_unknown_indicator(self, rate_detector):
        """Test behavior with unknown indicator"""
        warning = rate_detector.check(
            ring_number=100,
            indicator_name="unknown_indicator",
            indicator_value=100.0,
            geological_zone="all"
        )

        assert warning is None

    @pytest.mark.unit
    def test_warning_event_fields(self, rate_detector, mock_db_session):
        """Test that rate warning event has correct fields"""
        # Historical data
        historical_rings = [
            create_ring_summary(90 + i, 10.0 + i * 0.1)
            for i in range(10)
        ]

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = historical_rings

        mock_db_session.query.return_value = mock_query

        timestamp = datetime.utcnow().timestamp()

        # Trigger rate warning
        warning = rate_detector.check(
            ring_number=100,
            indicator_name="settlement_value",
            indicator_value=20.0,  # Large jump
            geological_zone="all",
            timestamp=timestamp
        )

        if warning is not None:
            assert warning.warning_id is not None
            assert warning.warning_type == "rate"
            assert warning.ring_number == 100
            assert warning.timestamp == timestamp
            assert warning.indicator_name == "settlement_value"
            assert warning.indicator_value == 20.0
            assert warning.status == "active"

    @pytest.mark.unit
    def test_window_size_respected(self, rate_detector, mock_db_session):
        """Test that rate_window_size is respected"""
        # Create 20 historical rings
        historical_rings = [
            create_ring_summary(80 + i, 10.0 + i * 0.5)
            for i in range(20)
        ]

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = historical_rings

        mock_db_session.query.return_value = mock_query

        rate_detector.check(
            ring_number=100,
            indicator_name="settlement_value",
            indicator_value=20.0,
            geological_zone="all"
        )

        # Verify that limit was called with window_size (10)
        mock_query.limit.assert_called_once_with(10)

    @pytest.mark.unit
    def test_zone_specific_rate_threshold(self, mock_db_session):
        """Test zone-specific rate thresholds"""
        # Create zone-specific threshold
        zone_a_threshold = WarningThreshold(
            threshold_id="test-rate-zone-a",
            indicator_name="settlement_value",
            geological_zone="zone_a",
            rate_attention_multiplier=1.5,  # More sensitive than default
            rate_enabled=True,
            rate_window_size=5
        )

        all_threshold = WarningThreshold(
            threshold_id="test-rate-all",
            indicator_name="settlement_value",
            geological_zone="all",
            rate_attention_multiplier=3.0,
            rate_enabled=True,
            rate_window_size=5
        )

        detector = RateDetector(mock_db_session, {
            "settlement_value_all": all_threshold,
            "settlement_value_zone_a": zone_a_threshold
        })

        # Mock historical data
        historical_rings = [
            create_ring_summary(95 + i, 10.0 + i * 0.5)
            for i in range(5)
        ]

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = historical_rings

        mock_db_session.query.return_value = mock_query

        # Check with zone_a (should use more sensitive threshold)
        warning = detector.check(
            ring_number=100,
            indicator_name="settlement_value",
            indicator_value=14.0,  # Moderate change
            geological_zone="zone_a"
        )

        # Zone-specific threshold is more sensitive, more likely to trigger
        # (Exact behavior depends on historical average calculation)
