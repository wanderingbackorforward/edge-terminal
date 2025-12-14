"""
Unit tests for CalibrationApplicator
Tests sensor calibration application
"""
import pytest
from edge.services.cleaner.calibration import CalibrationApplicator


class TestCalibrationApplicator:
    """Test cases for CalibrationApplicator"""

    @pytest.fixture
    def applicator(self):
        """Create calibration applicator instance"""
        return CalibrationApplicator()

    def test_linear_calibration(self, applicator):
        """Test linear calibration (y = scale * x + offset)"""
        # Mock configuration for testing
        applicator.calibrations = {
            'sensor_A': {
                'type': 'linear',
                'offset': -2.5,
                'scale': 1.02
            }
        }

        raw_value = 100.0
        calibrated_value, was_calibrated = applicator.calibrate(
            'sensor_A', raw_value, timestamp=None
        )

        # Expected: (100 + (-2.5)) * 1.02 = 97.5 * 1.02 = 99.45
        expected = (raw_value + (-2.5)) * 1.02
        assert abs(calibrated_value - expected) < 0.01
        assert was_calibrated is True

    def test_polynomial_calibration(self, applicator):
        """Test polynomial calibration"""
        applicator.calibrations = {
            'sensor_B': {
                'type': 'polynomial',
                'coefficients': [1.0, 2.0, 0.5]  # 1 + 2x + 0.5x^2
            }
        }

        raw_value = 10.0
        calibrated_value, was_calibrated = applicator.calibrate(
            'sensor_B', raw_value, timestamp=None
        )

        # Expected: 1 + 2*10 + 0.5*10^2 = 1 + 20 + 50 = 71
        expected = 1.0 + 2.0 * 10.0 + 0.5 * (10.0 ** 2)
        assert abs(calibrated_value - expected) < 0.01
        assert was_calibrated is True

    def test_lookup_table_calibration(self, applicator):
        """Test lookup table calibration with interpolation"""
        applicator.calibrations = {
            'sensor_C': {
                'type': 'lookup_table',
                'table': [
                    {'raw': 0.0, 'calibrated': 0.0},
                    {'raw': 10.0, 'calibrated': 12.0},
                    {'raw': 20.0, 'calibrated': 25.0}
                ]
            }
        }

        # Test exact match
        calibrated_value, was_calibrated = applicator.calibrate(
            'sensor_C', 10.0, timestamp=None
        )
        assert abs(calibrated_value - 12.0) < 0.01
        assert was_calibrated is True

        # Test interpolation (value between 10 and 20)
        calibrated_value, was_calibrated = applicator.calibrate(
            'sensor_C', 15.0, timestamp=None
        )
        # Linear interpolation: 12 + (15-10)/(20-10) * (25-12) = 12 + 0.5 * 13 = 18.5
        expected = 12.0 + (15.0 - 10.0) / (20.0 - 10.0) * (25.0 - 12.0)
        assert abs(calibrated_value - expected) < 0.01

    def test_no_calibration_configured(self, applicator):
        """Test sensor with no calibration"""
        raw_value = 100.0
        calibrated_value, was_calibrated = applicator.calibrate(
            'unconfigured_sensor', raw_value, timestamp=None
        )

        # Should return original value
        assert calibrated_value == raw_value
        assert was_calibrated is False

    def test_time_based_calibration(self, applicator):
        """Test calibration that changes over time"""
        applicator.calibrations = {
            'sensor_D': {
                'type': 'linear',
                'offset': -2.5,
                'scale': 1.02,
                'valid_from': 1000.0,
                'valid_until': 2000.0
            }
        }

        raw_value = 100.0

        # Within valid time range
        calibrated_value, was_calibrated = applicator.calibrate(
            'sensor_D', raw_value, timestamp=1500.0
        )
        assert was_calibrated is True

        # Before valid time range
        calibrated_value, was_calibrated = applicator.calibrate(
            'sensor_D', raw_value, timestamp=500.0
        )
        assert was_calibrated is False
        assert calibrated_value == raw_value

        # After valid time range
        calibrated_value, was_calibrated = applicator.calibrate(
            'sensor_D', raw_value, timestamp=2500.0
        )
        assert was_calibrated is False
        assert calibrated_value == raw_value

    def test_batch_calibration(self, applicator):
        """Test calibrating multiple sensors at once"""
        applicator.calibrations = {
            'sensor_A': {
                'type': 'linear',
                'offset': -1.0,
                'scale': 1.0
            },
            'sensor_B': {
                'type': 'linear',
                'offset': 0.0,
                'scale': 2.0
            }
        }

        data = {
            'sensor_A': 100.0,
            'sensor_B': 50.0,
            'sensor_C': 75.0  # No calibration
        }

        calibrated_data = applicator.batch_calibrate(data)

        assert 'sensor_A' in calibrated_data
        assert 'sensor_B' in calibrated_data
        assert 'sensor_C' in calibrated_data

        # sensor_A: (100 - 1) * 1.0 = 99
        assert abs(calibrated_data['sensor_A'] - 99.0) < 0.01

        # sensor_B: (50 + 0) * 2.0 = 100
        assert abs(calibrated_data['sensor_B'] - 100.0) < 0.01

        # sensor_C: unchanged
        assert calibrated_data['sensor_C'] == 75.0

    def test_invalid_calibration_type(self, applicator):
        """Test handling of invalid calibration type"""
        applicator.calibrations = {
            'sensor_E': {
                'type': 'invalid_type',
                'offset': 1.0
            }
        }

        raw_value = 100.0
        calibrated_value, was_calibrated = applicator.calibrate(
            'sensor_E', raw_value, timestamp=None
        )

        # Should return original value on error
        assert calibrated_value == raw_value
        assert was_calibrated is False

    def test_lookup_table_extrapolation(self, applicator):
        """Test lookup table behavior outside range"""
        applicator.calibrations = {
            'sensor_F': {
                'type': 'lookup_table',
                'table': [
                    {'raw': 10.0, 'calibrated': 12.0},
                    {'raw': 20.0, 'calibrated': 25.0}
                ]
            }
        }

        # Below range
        calibrated_value, was_calibrated = applicator.calibrate(
            'sensor_F', 5.0, timestamp=None
        )
        # Should return first value or extrapolate
        assert was_calibrated is True

        # Above range
        calibrated_value, was_calibrated = applicator.calibrate(
            'sensor_F', 30.0, timestamp=None
        )
        # Should return last value or extrapolate
        assert was_calibrated is True

    def test_statistics_tracking(self, applicator):
        """Test calibration statistics"""
        applicator.calibrations = {
            'sensor_A': {
                'type': 'linear',
                'offset': -1.0,
                'scale': 1.0
            }
        }

        # Apply some calibrations
        applicator.calibrate('sensor_A', 100.0, None)
        applicator.calibrate('sensor_A', 200.0, None)
        applicator.calibrate('sensor_B', 150.0, None)  # No calibration

        stats = applicator.get_statistics()

        assert stats['total_calibrations'] == 3
        assert stats['calibrated_count'] == 2
        assert stats['uncalibrated_count'] == 1

    def test_reset_statistics(self, applicator):
        """Test statistics reset"""
        applicator.calibrations = {
            'sensor_A': {
                'type': 'linear',
                'offset': -1.0,
                'scale': 1.0
            }
        }

        applicator.calibrate('sensor_A', 100.0, None)
        applicator.reset_statistics()

        stats = applicator.get_statistics()
        assert stats['total_calibrations'] == 0

    def test_calibration_with_nan(self, applicator):
        """Test handling of NaN values"""
        import math

        applicator.calibrations = {
            'sensor_A': {
                'type': 'linear',
                'offset': -1.0,
                'scale': 1.0
            }
        }

        calibrated_value, was_calibrated = applicator.calibrate(
            'sensor_A', math.nan, timestamp=None
        )

        # Should handle NaN gracefully
        assert math.isnan(calibrated_value) or calibrated_value is None
        assert was_calibrated is False

    def test_calibration_with_inf(self, applicator):
        """Test handling of infinity values"""
        import math

        applicator.calibrations = {
            'sensor_A': {
                'type': 'linear',
                'offset': -1.0,
                'scale': 1.0
            }
        }

        calibrated_value, was_calibrated = applicator.calibrate(
            'sensor_A', math.inf, timestamp=None
        )

        # Should handle inf gracefully
        assert math.isinf(calibrated_value) or calibrated_value is None
        assert was_calibrated is False
