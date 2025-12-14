"""
T021: Unit tests for data interpolator
Tests gap detection and linear interpolation
"""
import pytest
from edge.services.cleaner.interpolator import DataInterpolator


class TestDataInterpolator:
    """Test cases for DataInterpolator"""

    @pytest.fixture
    def interpolator(self):
        """Create interpolator instance"""
        return DataInterpolator(max_gap_seconds=5.0, expected_interval=1.0)

    def test_no_gaps(self, interpolator):
        """Test data with no gaps"""
        timestamps = [1000.0, 1001.0, 1002.0, 1003.0]
        values = [10.0, 11.0, 12.0, 13.0]

        result_timestamps, result_values, result_flags = interpolator.process(
            timestamps, values
        )

        # Should return original data unchanged
        assert len(result_timestamps) == 4
        assert result_flags == ['raw', 'raw', 'raw', 'raw']

    def test_small_gap_interpolation(self, interpolator):
        """Test interpolation of small gap"""
        timestamps = [1000.0, 1001.0, 1004.0, 1005.0]  # 3-second gap
        values = [10.0, 11.0, 14.0, 15.0]

        result_timestamps, result_values, result_flags = interpolator.process(
            timestamps, values
        )

        # Should interpolate missing values
        assert len(result_timestamps) > 4
        assert 'interpolated' in result_flags
        assert result_flags[0] == 'raw'
        assert result_flags[1] == 'raw'

    def test_large_gap_no_interpolation(self, interpolator):
        """Test that large gaps are not interpolated"""
        timestamps = [1000.0, 1001.0, 1010.0, 1011.0]  # 9-second gap
        values = [10.0, 11.0, 20.0, 21.0]

        result_timestamps, result_values, result_flags = interpolator.process(
            timestamps, values
        )

        # Should not interpolate gap > max_gap_seconds
        # Check statistics
        stats = interpolator.get_statistics()
        assert stats['gaps_too_large'] >= 1

    def test_gap_detection(self, interpolator):
        """Test gap detection"""
        timestamps = [1000.0, 1001.0, 1005.0, 1006.0]

        gaps = interpolator.detect_gaps(timestamps)

        assert len(gaps) > 0
        assert gaps[0] == (1, 2)  # Gap between index 1 and 2

    def test_interpolated_values(self, interpolator):
        """Test accuracy of interpolated values"""
        timestamps = [1000.0, 1003.0]  # 3-second gap
        values = [10.0, 13.0]

        result_timestamps, result_values, result_flags = interpolator.process(
            timestamps, values
        )

        # Check that middle value is approximately correct
        # Should have values at 1000, 1001, 1002, 1003
        assert len(result_timestamps) == 4
        assert abs(result_values[1] - 11.0) < 0.1  # Linear interpolation
        assert abs(result_values[2] - 12.0) < 0.1

    def test_empty_input(self, interpolator):
        """Test with empty input"""
        timestamps = []
        values = []

        result_timestamps, result_values, result_flags = interpolator.process(
            timestamps, values
        )

        assert len(result_timestamps) == 0
        assert len(result_values) == 0
        assert len(result_flags) == 0

    def test_single_value(self, interpolator):
        """Test with single value"""
        timestamps = [1000.0]
        values = [10.0]

        result_timestamps, result_values, result_flags = interpolator.process(
            timestamps, values
        )

        assert len(result_timestamps) == 1
        assert result_flags == ['raw']

    def test_statistics_tracking(self, interpolator):
        """Test statistics tracking"""
        timestamps = [1000.0, 1001.0, 1004.0, 1005.0]
        values = [10.0, 11.0, 14.0, 15.0]

        interpolator.process(timestamps, values)

        stats = interpolator.get_statistics()

        assert stats['gaps_detected'] >= 1
        assert stats['values_interpolated'] >= 1

    def test_reset_statistics(self, interpolator):
        """Test statistics reset"""
        timestamps = [1000.0, 1004.0]
        values = [10.0, 14.0]

        interpolator.process(timestamps, values)
        interpolator.reset_statistics()

        stats = interpolator.get_statistics()
        assert stats['gaps_detected'] == 0
        assert stats['values_interpolated'] == 0

    def test_quality_flags(self, interpolator):
        """Test quality flag assignment"""
        timestamps = [1000.0, 1003.0, 1004.0]
        values = [10.0, 13.0, 14.0]

        _, _, flags = interpolator.process(timestamps, values)

        assert flags[0] == 'raw'  # First value
        assert 'interpolated' in flags  # Some interpolated values
        assert flags[-1] == 'raw'  # Last value
