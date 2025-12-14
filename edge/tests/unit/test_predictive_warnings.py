"""
T129: Unit tests for predictive early warnings
Tests PredictiveChecker for forecasted threshold violations
"""
import pytest
from datetime import datetime
from unittest.mock import Mock

from edge.services.warning.predictive_checker import PredictiveChecker
from edge.models.warning_threshold import WarningThreshold
from edge.models.prediction_result import PredictionResult


@pytest.fixture
def predictive_threshold():
    """Predictive threshold configuration"""
    threshold = WarningThreshold(
        threshold_id="test-predictive",
        indicator_name="settlement_value",
        geological_zone="all",
        indicator_unit="mm",
        warning_upper=30.0,
        alarm_upper=40.0,
        predictive_enabled=True,
        predictive_threshold_percentage=0.9,  # Warn at 90% of threshold
        predictive_horizon_hours=24,
        enabled=True
    )
    return threshold


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    return Mock()


@pytest.fixture
def predictive_checker(mock_db_session, predictive_threshold):
    """PredictiveChecker with test configuration"""
    thresholds = {"settlement_value_all": predictive_threshold}
    return PredictiveChecker(mock_db_session, thresholds)


def create_prediction_result(ring_number, predicted_settlement, upper_bound=None, confidence=0.85):
    """Helper to create PredictionResult mock"""
    pred = Mock(spec=PredictionResult)
    pred.ring_number = ring_number
    pred.predicted_settlement = predicted_settlement
    pred.settlement_upper_bound = upper_bound if upper_bound is not None else predicted_settlement + 5.0
    pred.prediction_confidence = confidence
    pred.predicted_displacement = None
    pred.displacement_upper_bound = None
    return pred


class TestPredictiveChecker:
    """Unit tests for PredictiveChecker"""

    @pytest.mark.unit
    def test_no_prediction_available(self, predictive_checker, mock_db_session):
        """Test when no prediction exists for ring"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = None
        mock_db_session.query.return_value = mock_query

        warnings = predictive_checker.check(
            ring_number=100,
            geological_zone="all"
        )

        assert warnings == []

    @pytest.mark.unit
    def test_prediction_within_safe_range(self, predictive_checker, mock_db_session):
        """Test that safe predictions don't trigger warnings"""
        # Prediction: 20mm (safe, below WARNING 30mm)
        prediction = create_prediction_result(100, predicted_settlement=20.0, upper_bound=22.0)

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = prediction
        mock_db_session.query.return_value = mock_query

        warnings = predictive_checker.check(
            ring_number=100,
            geological_zone="all"
        )

        assert warnings == []

    @pytest.mark.unit
    def test_prediction_approaching_threshold(self, predictive_checker, mock_db_session):
        """Test warning when prediction approaches threshold (90%)"""
        # Prediction: 27mm (90% of WARNING threshold 30mm)
        prediction = create_prediction_result(100, predicted_settlement=27.0, upper_bound=29.0)

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = prediction
        mock_db_session.query.return_value = mock_query

        warnings = predictive_checker.check(
            ring_number=100,
            geological_zone="all"
        )

        assert len(warnings) == 1
        warning = warnings[0]
        assert warning.warning_type == "predictive"
        assert warning.indicator_name == "settlement_value"
        assert warning.predicted_value == 27.0
        assert warning.indicator_value is None  # No actual value yet

    @pytest.mark.unit
    def test_prediction_exceeds_threshold(self, predictive_checker, mock_db_session):
        """Test warning when prediction exceeds threshold"""
        # Prediction: 35mm (exceeds WARNING 30mm)
        prediction = create_prediction_result(100, predicted_settlement=35.0, upper_bound=38.0)

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = prediction
        mock_db_session.query.return_value = mock_query

        warnings = predictive_checker.check(
            ring_number=100,
            geological_zone="all"
        )

        assert len(warnings) == 1
        warning = warnings[0]
        assert warning.warning_level in ["WARNING", "ALARM"]
        assert warning.predicted_value == 35.0

    @pytest.mark.unit
    def test_confidence_interval_upper_bound(self, predictive_checker, mock_db_session):
        """Test warning based on confidence interval upper bound"""
        # Prediction: 25mm (safe), but upper bound: 32mm (exceeds WARNING 30mm)
        prediction = create_prediction_result(100, predicted_settlement=25.0, upper_bound=32.0)

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = prediction
        mock_db_session.query.return_value = mock_query

        warnings = predictive_checker.check(
            ring_number=100,
            geological_zone="all"
        )

        # Should trigger warning (possibly downgraded level since it's CI, not point estimate)
        assert len(warnings) >= 1

    @pytest.mark.unit
    def test_prediction_confidence_included(self, predictive_checker, mock_db_session):
        """Test that prediction confidence is included in warning"""
        prediction = create_prediction_result(100, predicted_settlement=35.0, confidence=0.92)

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = prediction
        mock_db_session.query.return_value = mock_query

        warnings = predictive_checker.check(
            ring_number=100,
            geological_zone="all"
        )

        if warnings:
            assert warnings[0].prediction_confidence == 0.92

    @pytest.mark.unit
    def test_predictive_disabled(self, predictive_checker, predictive_threshold, mock_db_session):
        """Test that disabled predictive checks don't trigger warnings"""
        predictive_threshold.predictive_enabled = False

        prediction = create_prediction_result(100, predicted_settlement=50.0)  # Extreme value

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = prediction
        mock_db_session.query.return_value = mock_query

        warnings = predictive_checker.check(
            ring_number=100,
            geological_zone="all"
        )

        assert warnings == []

    @pytest.mark.unit
    def test_displacement_prediction(self, predictive_checker, mock_db_session):
        """Test predictive warnings for displacement"""
        # Add displacement threshold
        disp_threshold = WarningThreshold(
            threshold_id="test-disp-predictive",
            indicator_name="displacement_value",
            geological_zone="all",
            warning_upper=50.0,
            predictive_enabled=True,
            predictive_threshold_percentage=0.9,
            enabled=True
        )

        checker = PredictiveChecker(mock_db_session, {
            "displacement_value_all": disp_threshold
        })

        prediction = create_prediction_result(100, predicted_settlement=0)
        prediction.predicted_displacement = 48.0  # 96% of WARNING 50mm
        prediction.displacement_upper_bound = 52.0

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = prediction
        mock_db_session.query.return_value = mock_query

        warnings = checker.check(
            ring_number=100,
            geological_zone="all"
        )

        # Should trigger predictive warning for displacement
        assert len(warnings) >= 1
        disp_warnings = [w for w in warnings if w.indicator_name == "displacement_value"]
        assert len(disp_warnings) > 0
