"""
T127: Unit tests for threshold-based warning logic
Tests ThresholdChecker for absolute value violations
"""
import pytest
from datetime import datetime

from edge.services.warning.threshold_checker import ThresholdChecker
from edge.models.warning_threshold import WarningThreshold
from edge.models.warning_event import WarningEvent


@pytest.fixture
def settlement_threshold():
    """Settlement threshold configuration"""
    threshold = WarningThreshold(
        threshold_id="test-settlement",
        indicator_name="settlement_value",
        geological_zone="all",
        indicator_unit="mm",
        attention_upper=20.0,
        warning_upper=30.0,
        alarm_upper=40.0,
        enabled=True,
        description="Settlement monitoring"
    )
    return threshold


@pytest.fixture
def pressure_threshold():
    """Chamber pressure threshold with range"""
    threshold = WarningThreshold(
        threshold_id="test-pressure",
        indicator_name="mean_chamber_pressure",
        geological_zone="all",
        indicator_unit="bar",
        attention_lower=1.8,
        attention_upper=3.2,
        warning_lower=1.6,
        warning_upper=3.5,
        alarm_lower=1.4,
        alarm_upper=4.0,
        enabled=True,
        description="Chamber pressure range"
    )
    return threshold


@pytest.fixture
def threshold_checker(settlement_threshold, pressure_threshold):
    """ThresholdChecker with test configurations"""
    thresholds = {
        "settlement_value_all": settlement_threshold,
        "mean_chamber_pressure_all": pressure_threshold,
    }
    return ThresholdChecker(thresholds)


class TestThresholdChecker:
    """Unit tests for ThresholdChecker"""

    @pytest.mark.unit
    def test_no_violation_normal_value(self, threshold_checker):
        """Test that normal values don't trigger warnings"""
        warning = threshold_checker.check(
            ring_number=100,
            indicator_name="settlement_value",
            indicator_value=15.0,  # Below ATTENTION (20mm)
            geological_zone="all"
        )
        assert warning is None

    @pytest.mark.unit
    def test_attention_level_triggered(self, threshold_checker):
        """Test ATTENTION level warning"""
        warning = threshold_checker.check(
            ring_number=100,
            indicator_name="settlement_value",
            indicator_value=25.0,  # Between ATTENTION (20) and WARNING (30)
            geological_zone="all"
        )
        assert warning is not None
        assert warning.warning_level == "ATTENTION"
        assert warning.indicator_name == "settlement_value"
        assert warning.indicator_value == 25.0
        assert warning.threshold_value == 20.0
        assert warning.ring_number == 100

    @pytest.mark.unit
    def test_warning_level_triggered(self, threshold_checker):
        """Test WARNING level warning"""
        warning = threshold_checker.check(
            ring_number=100,
            indicator_name="settlement_value",
            indicator_value=35.0,  # Between WARNING (30) and ALARM (40)
            geological_zone="all"
        )
        assert warning is not None
        assert warning.warning_level == "WARNING"
        assert warning.threshold_value == 30.0

    @pytest.mark.unit
    def test_alarm_level_triggered(self, threshold_checker):
        """Test ALARM level warning"""
        warning = threshold_checker.check(
            ring_number=100,
            indicator_name="settlement_value",
            indicator_value=45.0,  # Above ALARM (40)
            geological_zone="all"
        )
        assert warning is not None
        assert warning.warning_level == "ALARM"
        assert warning.threshold_value == 40.0

    @pytest.mark.unit
    def test_exact_threshold_boundary(self, threshold_checker):
        """Test behavior at exact threshold boundary"""
        # Exactly at ATTENTION threshold
        warning = threshold_checker.check(
            ring_number=100,
            indicator_name="settlement_value",
            indicator_value=20.0,
            geological_zone="all"
        )
        assert warning is not None
        assert warning.warning_level == "ATTENTION"

    @pytest.mark.unit
    def test_range_based_threshold_lower_violation(self, threshold_checker):
        """Test lower bound violation for range-based threshold"""
        warning = threshold_checker.check(
            ring_number=100,
            indicator_name="mean_chamber_pressure",
            indicator_value=1.5,  # Below WARNING lower (1.6)
            geological_zone="all"
        )
        assert warning is not None
        assert warning.warning_level == "WARNING"
        assert warning.threshold_type == "lower"
        assert warning.threshold_value == 1.6

    @pytest.mark.unit
    def test_range_based_threshold_upper_violation(self, threshold_checker):
        """Test upper bound violation for range-based threshold"""
        warning = threshold_checker.check(
            ring_number=100,
            indicator_name="mean_chamber_pressure",
            indicator_value=3.8,  # Above WARNING upper (3.5)
            geological_zone="all"
        )
        assert warning is not None
        assert warning.warning_level == "WARNING"
        assert warning.threshold_type == "upper"
        assert warning.threshold_value == 3.5

    @pytest.mark.unit
    def test_range_based_threshold_within_range(self, threshold_checker):
        """Test value within acceptable range"""
        warning = threshold_checker.check(
            ring_number=100,
            indicator_name="mean_chamber_pressure",
            indicator_value=2.5,  # Within all ranges
            geological_zone="all"
        )
        assert warning is None

    @pytest.mark.unit
    def test_batch_checking(self, threshold_checker):
        """Test batch checking of multiple indicators"""
        indicators = {
            "settlement_value": 35.0,  # WARNING
            "mean_chamber_pressure": 1.3  # ALARM (below 1.4)
        }

        warnings = threshold_checker.check_batch(
            ring_number=100,
            indicators=indicators,
            geological_zone="all"
        )

        assert len(warnings) == 2

        # Find warnings by indicator
        settlement_warning = next(
            w for w in warnings if w.indicator_name == "settlement_value"
        )
        pressure_warning = next(
            w for w in warnings if w.indicator_name == "mean_chamber_pressure"
        )

        assert settlement_warning.warning_level == "WARNING"
        assert pressure_warning.warning_level == "ALARM"

    @pytest.mark.unit
    def test_unknown_indicator(self, threshold_checker):
        """Test behavior with unknown indicator"""
        warning = threshold_checker.check(
            ring_number=100,
            indicator_name="unknown_indicator",
            indicator_value=100.0,
            geological_zone="all"
        )
        assert warning is None

    @pytest.mark.unit
    def test_zone_specific_threshold(self, settlement_threshold):
        """Test zone-specific threshold takes precedence"""
        # Create zone-specific threshold
        zone_a_threshold = WarningThreshold(
            threshold_id="test-settlement-zone-a",
            indicator_name="settlement_value",
            geological_zone="zone_a",
            indicator_unit="mm",
            attention_upper=15.0,  # Stricter than 'all'
            warning_upper=25.0,
            alarm_upper=35.0,
            enabled=True
        )

        checker = ThresholdChecker({
            "settlement_value_all": settlement_threshold,
            "settlement_value_zone_a": zone_a_threshold
        })

        # Check with zone_a (should use stricter threshold)
        warning = checker.check(
            ring_number=100,
            indicator_name="settlement_value",
            indicator_value=18.0,  # Normal for 'all', ATTENTION for 'zone_a'
            geological_zone="zone_a"
        )
        assert warning is not None
        assert warning.warning_level == "ATTENTION"
        assert warning.threshold_value == 15.0

    @pytest.mark.unit
    def test_disabled_threshold(self, settlement_threshold):
        """Test that disabled thresholds don't trigger warnings"""
        settlement_threshold.enabled = False

        checker = ThresholdChecker({
            "settlement_value_all": settlement_threshold
        })

        warning = checker.check(
            ring_number=100,
            indicator_name="settlement_value",
            indicator_value=45.0,  # Would be ALARM if enabled
            geological_zone="all"
        )
        assert warning is None

    @pytest.mark.unit
    def test_warning_event_fields(self, threshold_checker):
        """Test that warning event has all required fields"""
        timestamp = datetime.utcnow().timestamp()

        warning = threshold_checker.check(
            ring_number=100,
            indicator_name="settlement_value",
            indicator_value=35.0,
            geological_zone="all",
            timestamp=timestamp
        )

        assert warning is not None
        assert warning.warning_id is not None
        assert warning.warning_type == "threshold"
        assert warning.warning_level == "WARNING"
        assert warning.ring_number == 100
        assert warning.timestamp == timestamp
        assert warning.indicator_name == "settlement_value"
        assert warning.indicator_value == 35.0
        assert warning.indicator_unit == "mm"
        assert warning.threshold_value == 30.0
        assert warning.threshold_type == "upper"
        assert warning.status == "active"

    @pytest.mark.unit
    def test_notification_channels_set(self, threshold_checker):
        """Test that notification channels are set based on warning level"""
        warning = threshold_checker.check(
            ring_number=100,
            indicator_name="settlement_value",
            indicator_value=45.0,  # ALARM
            geological_zone="all"
        )

        assert warning is not None
        channels = warning.get_notification_channels()
        assert channels is not None
        assert len(channels) > 0

    @pytest.mark.unit
    def test_multiple_rings_independent(self, threshold_checker):
        """Test that warnings for different rings are independent"""
        warning1 = threshold_checker.check(
            ring_number=100,
            indicator_name="settlement_value",
            indicator_value=35.0,
            geological_zone="all"
        )

        warning2 = threshold_checker.check(
            ring_number=101,
            indicator_name="settlement_value",
            indicator_value=35.0,
            geological_zone="all"
        )

        assert warning1 is not None
        assert warning2 is not None
        assert warning1.ring_number == 100
        assert warning2.ring_number == 101
        assert warning1.warning_id != warning2.warning_id

    @pytest.mark.unit
    def test_escalation_thresholds(self, threshold_checker):
        """Test that higher severity values trigger higher levels"""
        # Test escalation from ATTENTION → WARNING → ALARM
        values_and_levels = [
            (15.0, None),         # Normal
            (20.0, "ATTENTION"),  # Exactly at ATTENTION
            (30.0, "WARNING"),    # Exactly at WARNING
            (40.0, "ALARM"),      # Exactly at ALARM
            (50.0, "ALARM"),      # Above ALARM
        ]

        for value, expected_level in values_and_levels:
            warning = threshold_checker.check(
                ring_number=100,
                indicator_name="settlement_value",
                indicator_value=value,
                geological_zone="all"
            )

            if expected_level is None:
                assert warning is None, f"Value {value} should not trigger warning"
            else:
                assert warning is not None, f"Value {value} should trigger warning"
                assert warning.warning_level == expected_level, \
                    f"Value {value} should trigger {expected_level}"
