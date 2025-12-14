"""
T130: Unit tests for hysteresis logic
Tests WarningEngine._apply_hysteresis() to prevent oscillating warnings
"""
import pytest
from datetime import datetime
from unittest.mock import Mock

from edge.services.warning.warning_engine import WarningEngine
from edge.models.warning_event import WarningEvent
from edge.models.warning_threshold import WarningThreshold


@pytest.fixture
def mock_db_session():
    return Mock()


@pytest.fixture
def settlement_threshold():
    threshold = WarningThreshold(
        threshold_id="test-settlement",
        indicator_name="settlement_value",
        geological_zone="all",
        indicator_unit="mm",
        warning_upper=30.0,
        hysteresis_percentage=0.05,  # 5% buffer
        enabled=True
    )
    return threshold


@pytest.fixture
def warning_engine(mock_db_session, settlement_threshold):
    thresholds = {"settlement_value_all": settlement_threshold}
    engine = WarningEngine(mock_db_session, thresholds)
    return engine


def create_warning(ring_number, indicator_name, value, level, threshold_value, geological_zone="all"):
    """Helper to create warning event"""
    warning = WarningEvent(
        warning_id=f"test-{ring_number}",
        warning_type="threshold",
        warning_level=level,
        ring_number=ring_number,
        timestamp=datetime.utcnow().timestamp(),
        indicator_name=indicator_name,
        indicator_value=value,
        indicator_unit="mm",
        threshold_value=threshold_value,
        threshold_type="upper",
        status="active"
    )
    return warning


class TestHysteresis:
    """Unit tests for hysteresis logic"""

    @pytest.mark.unit
    def test_first_warning_allowed(self, warning_engine):
        """Test that first warning is always allowed"""
        warnings = [create_warning(100, "settlement_value", 31.0, "WARNING", 30.0)]
        current_indicators = {"settlement_value": 31.0}

        filtered = warning_engine._apply_hysteresis(warnings, current_indicators, "all")

        assert len(filtered) == 1
        assert "settlement_value_all" in warning_engine.hysteresis_state

    @pytest.mark.unit
    def test_escalation_allowed(self, warning_engine):
        """Test that escalation (ATTENTION → WARNING) is always allowed"""
        # First warning: ATTENTION
        warning1 = create_warning(100, "settlement_value", 25.0, "ATTENTION", 20.0)
        warning_engine._apply_hysteresis([warning1], {"settlement_value": 25.0}, "all")

        # Second warning: WARNING (escalation)
        warning2 = create_warning(101, "settlement_value", 31.0, "WARNING", 30.0)
        filtered = warning_engine._apply_hysteresis([warning2], {"settlement_value": 31.0}, "all")

        assert len(filtered) == 1
        assert filtered[0].warning_level == "WARNING"

    @pytest.mark.unit
    def test_deescalation_allowed(self, warning_engine):
        """Test that de-escalation (WARNING → ATTENTION) is allowed"""
        # First warning: WARNING
        warning1 = create_warning(100, "settlement_value", 31.0, "WARNING", 30.0)
        warning_engine._apply_hysteresis([warning1], {"settlement_value": 31.0}, "all")

        # Second warning: ATTENTION (de-escalation)
        warning2 = create_warning(101, "settlement_value", 25.0, "ATTENTION", 20.0)
        filtered = warning_engine._apply_hysteresis([warning2], {"settlement_value": 25.0}, "all")

        assert len(filtered) == 1
        assert filtered[0].warning_level == "ATTENTION"

    @pytest.mark.unit
    def test_small_change_suppressed(self, warning_engine):
        """Test that small changes (<5%) are suppressed"""
        # First warning: 31.0mm
        warning1 = create_warning(100, "settlement_value", 31.0, "WARNING", 30.0)
        warning_engine._apply_hysteresis([warning1], {"settlement_value": 31.0}, "all")

        # Second warning: 31.5mm (change = 0.5mm, which is 1.67% of threshold 30mm < 5%)
        warning2 = create_warning(101, "settlement_value", 31.5, "WARNING", 30.0)
        filtered = warning_engine._apply_hysteresis([warning2], {"settlement_value": 31.5}, "all")

        assert len(filtered) == 0  # Suppressed

    @pytest.mark.unit
    def test_large_change_allowed(self, warning_engine):
        """Test that large changes (>=5%) are allowed"""
        # First warning: 31.0mm
        warning1 = create_warning(100, "settlement_value", 31.0, "WARNING", 30.0)
        warning_engine._apply_hysteresis([warning1], {"settlement_value": 31.0}, "all")

        # Second warning: 33.0mm (change = 2.0mm, which is 6.67% of threshold 30mm >= 5%)
        warning2 = create_warning(101, "settlement_value", 33.0, "WARNING", 30.0)
        filtered = warning_engine._apply_hysteresis([warning2], {"settlement_value": 33.0}, "all")

        assert len(filtered) == 1  # Allowed

    @pytest.mark.unit
    def test_cleanup_when_value_returns_normal(self, warning_engine, settlement_threshold):
        """Test that hysteresis state is cleared when value returns to normal"""
        # First warning
        warning1 = create_warning(100, "settlement_value", 31.0, "WARNING", 30.0)
        warning_engine._apply_hysteresis([warning1], {"settlement_value": 31.0}, "all")

        assert "settlement_value_all" in warning_engine.hysteresis_state

        # Value returns to normal (no warnings)
        warning_engine._apply_hysteresis([], {"settlement_value": 25.0}, "all")

        # State should be cleared
        assert "settlement_value_all" not in warning_engine.hysteresis_state

    @pytest.mark.unit
    def test_cleanup_preserves_state_when_still_violating(self, warning_engine):
        """Test that state is preserved when indicator still violating"""
        # First warning
        warning1 = create_warning(100, "settlement_value", 31.0, "WARNING", 30.0)
        warning_engine._apply_hysteresis([warning1], {"settlement_value": 31.0}, "all")

        # Value still violating but warning suppressed by hysteresis
        warning2 = create_warning(101, "settlement_value", 31.2, "WARNING", 30.0)
        warning_engine._apply_hysteresis([warning2], {"settlement_value": 31.2}, "all")

        # State should still exist
        assert "settlement_value_all" in warning_engine.hysteresis_state

    @pytest.mark.unit
    def test_zone_specific_hysteresis_state(self, warning_engine):
        """Test that hysteresis state is tracked per zone"""
        # Warning in zone_a
        warning1 = create_warning(100, "settlement_value", 31.0, "WARNING", 30.0, "zone_a")
        warning_engine._apply_hysteresis([warning1], {"settlement_value": 31.0}, "zone_a")

        # Warning in zone_b
        warning2 = create_warning(101, "settlement_value", 31.0, "WARNING", 30.0, "zone_b")
        filtered = warning_engine._apply_hysteresis([warning2], {"settlement_value": 31.0}, "zone_b")

        # Should have separate state keys
        assert "settlement_value_zone_a" in warning_engine.hysteresis_state
        assert "settlement_value_zone_b" in warning_engine.hysteresis_state
        assert len(filtered) == 1  # zone_b warning not suppressed

    @pytest.mark.unit
    def test_multiple_indicators_independent(self, warning_engine):
        """Test that different indicators have independent hysteresis state"""
        # Warning for settlement
        warning1 = create_warning(100, "settlement_value", 31.0, "WARNING", 30.0)
        warning_engine._apply_hysteresis([warning1], {"settlement_value": 31.0}, "all")

        # Warning for pressure (different indicator)
        warning2 = create_warning(100, "mean_chamber_pressure", 3.8, "WARNING", 3.5)
        filtered = warning_engine._apply_hysteresis([warning2], {"mean_chamber_pressure": 3.8}, "all")

        # Pressure warning should not be suppressed (different indicator)
        assert len(filtered) == 1
