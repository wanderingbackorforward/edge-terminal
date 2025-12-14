"""
T131: Integration tests for combined warning aggregation
Tests WarningEngine end-to-end for multiple simultaneous warnings
"""
import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from edge.services.warning.warning_engine import WarningEngine
from edge.models.warning_threshold import WarningThreshold


@pytest.fixture
def mock_db_session():
    session = Mock()
    session.query = Mock()
    session.add = Mock()
    session.commit = Mock()
    return session


@pytest.fixture
def test_thresholds():
    """Create multiple threshold configurations"""
    thresholds = {
        "settlement_value_all": WarningThreshold(
            threshold_id="settlement",
            indicator_name="settlement_value",
            geological_zone="all",
            warning_upper=30.0,
            alarm_upper=40.0,
            enabled=True
        ),
        "mean_thrust_all": WarningThreshold(
            threshold_id="thrust",
            indicator_name="mean_thrust",
            geological_zone="all",
            warning_upper=30000.0,
            alarm_upper=35000.0,
            indicator_unit="kN",
            enabled=True
        ),
        "mean_torque_all": WarningThreshold(
            threshold_id="torque",
            indicator_name="mean_torque",
            geological_zone="all",
            warning_upper=1800.0,
            alarm_upper=2000.0,
            indicator_unit="kN·m",
            enabled=True
        ),
    }
    return thresholds


@pytest.fixture
def warning_engine(mock_db_session, test_thresholds):
    engine = WarningEngine(mock_db_session, test_thresholds)
    return engine


class TestCombinedWarnings:
    """Integration tests for combined warning aggregation"""

    @pytest.mark.integration
    def test_single_warning_no_combination(self, warning_engine):
        """Test that single warning doesn't create combined warning"""
        indicators = {"settlement_value": 35.0}  # WARNING only

        warnings = warning_engine.evaluate_ring(
            ring_number=100,
            indicators=indicators,
            geological_zone="all"
        )

        # Should have 1 warning, no combined warning
        combined_warnings = [w for w in warnings if w.warning_type == "combined"]
        assert len(combined_warnings) == 0

    @pytest.mark.integration
    def test_multiple_alarms_create_combined(self, warning_engine):
        """Test that multiple ALARM warnings create combined warning"""
        indicators = {
            "settlement_value": 45.0,     # ALARM (> 40)
            "mean_thrust": 36000.0,       # ALARM (> 35000)
        }

        warnings = warning_engine.evaluate_ring(
            ring_number=100,
            indicators=indicators,
            geological_zone="all"
        )

        # Should have 2 individual ALARMs + 1 combined ALARM
        combined_warnings = [w for w in warnings if w.warning_type == "combined"]
        assert len(combined_warnings) == 1
        assert combined_warnings[0].warning_level == "ALARM"

    @pytest.mark.integration
    def test_settlement_plus_tunneling_params(self, warning_engine):
        """Test combined warning for settlement + tunneling parameter violations"""
        indicators = {
            "settlement_value": 35.0,     # WARNING
            "mean_thrust": 32000.0,       # WARNING
            "mean_torque": 1900.0,        # WARNING
        }

        warnings = warning_engine.evaluate_ring(
            ring_number=100,
            indicators=indicators,
            geological_zone="all"
        )

        # Should create combined ALARM (settlement + tunneling params)
        combined_warnings = [w for w in warnings if w.warning_type == "combined"]
        assert len(combined_warnings) >= 1

    @pytest.mark.integration
    def test_three_warnings_create_combined(self, warning_engine):
        """Test that 3+ WARNING level warnings create combined warning"""
        indicators = {
            "settlement_value": 35.0,     # WARNING
            "mean_thrust": 32000.0,       # WARNING
            "mean_torque": 1900.0,        # WARNING
        }

        warnings = warning_engine.evaluate_ring(
            ring_number=100,
            indicators=indicators,
            geological_zone="all"
        )

        combined_warnings = [w for w in warnings if w.warning_type == "combined"]
        assert len(combined_warnings) >= 1
        
        if combined_warnings:
            combined_indicators = combined_warnings[0].get_combined_indicators()
            assert len(combined_indicators) >= 3

    @pytest.mark.integration
    def test_combined_warning_has_all_indicators(self, warning_engine):
        """Test that combined warning includes all source indicators"""
        indicators = {
            "settlement_value": 45.0,     # ALARM
            "mean_thrust": 36000.0,       # ALARM
        }

        warnings = warning_engine.evaluate_ring(
            ring_number=100,
            indicators=indicators,
            geological_zone="all"
        )

        combined_warnings = [w for w in warnings if w.warning_type == "combined"]
        if combined_warnings:
            combined_indicators = combined_warnings[0].get_combined_indicators()
            assert "settlement_value" in combined_indicators
            assert "mean_thrust" in combined_indicators

    @pytest.mark.integration
    @pytest.mark.requires_db
    def test_end_to_end_warning_generation(self, warning_engine, mock_db_session):
        """Test complete warning generation pipeline"""
        # Setup mock for rate detection (no historical data)
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.order_by = Mock(return_value=mock_query)
        mock_query.limit = Mock(return_value=mock_query)
        mock_query.all = Mock(return_value=[])
        mock_query.first = Mock(return_value=None)
        mock_db_session.query = Mock(return_value=mock_query)

        indicators = {
            "settlement_value": 45.0,     # ALARM
            "mean_thrust": 32000.0,       # WARNING
            "mean_torque": 1900.0,        # WARNING
        }

        warnings = warning_engine.evaluate_ring(
            ring_number=100,
            indicators=indicators,
            geological_zone="all"
        )

        # Should have threshold warnings
        threshold_warnings = [w for w in warnings if w.warning_type == "threshold"]
        assert len(threshold_warnings) >= 3

        # Check database persistence was called
        assert mock_db_session.add.called
        assert mock_db_session.commit.called
