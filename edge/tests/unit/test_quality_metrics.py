"""
Unit tests for QualityMetricsTracker
Tests quality metrics tracking and reporting
"""
import pytest
from edge.services.cleaner.quality_metrics import QualityMetricsTracker


class TestQualityMetricsTracker:
    """Test cases for QualityMetricsTracker"""

    @pytest.fixture
    def tracker(self):
        """Create metrics tracker instance"""
        return QualityMetricsTracker()

    def test_record_validation_passed(self, tracker):
        """Test recording successful validation"""
        tracker.record_validation('thrust_total', True, None)

        stats = tracker.get_tag_statistics('thrust_total')
        assert stats['total_validations'] == 1
        assert stats['validation_passed'] == 1
        assert stats['validation_failed'] == 0

    def test_record_validation_failed(self, tracker):
        """Test recording failed validation"""
        tracker.record_validation('thrust_total', False, 'Value out of range')

        stats = tracker.get_tag_statistics('thrust_total')
        assert stats['total_validations'] == 1
        assert stats['validation_passed'] == 0
        assert stats['validation_failed'] == 1
        assert 'Value out of range' in stats['failure_reasons']

    def test_record_interpolation(self, tracker):
        """Test recording interpolation"""
        tracker.record_interpolation('chamber_pressure', True)
        tracker.record_interpolation('chamber_pressure', False)

        stats = tracker.get_tag_statistics('chamber_pressure')
        assert stats['interpolations'] == 1
        assert stats['total_values'] == 2

    def test_record_calibration(self, tracker):
        """Test recording calibration"""
        tracker.record_calibration('sensor_A', True)
        tracker.record_calibration('sensor_A', False)
        tracker.record_calibration('sensor_A', True)

        stats = tracker.get_tag_statistics('sensor_A')
        assert stats['calibrations'] == 2
        assert stats['total_values'] == 3

    def test_record_reasonableness_check(self, tracker):
        """Test recording reasonableness check"""
        tracker.record_reasonableness('thrust_total', True, None)
        tracker.record_reasonableness('thrust_total', False, 'Ratio out of bounds')

        stats = tracker.get_tag_statistics('thrust_total')
        assert stats['reasonableness_passed'] == 1
        assert stats['reasonableness_failed'] == 1

    def test_assess_record_quality_high(self, tracker):
        """Test assessing high quality record"""
        quality = tracker.assess_record_quality(
            validation_passed=True,
            was_interpolated=False,
            reasonableness_passed=True,
            was_calibrated=True
        )

        assert quality == 'high'

    def test_assess_record_quality_medium(self, tracker):
        """Test assessing medium quality record (interpolated)"""
        quality = tracker.assess_record_quality(
            validation_passed=True,
            was_interpolated=True,
            reasonableness_passed=True,
            was_calibrated=True
        )

        assert quality == 'medium'

    def test_assess_record_quality_low(self, tracker):
        """Test assessing low quality record (failed validation)"""
        quality = tracker.assess_record_quality(
            validation_passed=False,
            was_interpolated=False,
            reasonableness_passed=True,
            was_calibrated=True
        )

        assert quality == 'low'

    def test_assess_record_quality_low_reasonableness(self, tracker):
        """Test assessing low quality record (failed reasonableness)"""
        quality = tracker.assess_record_quality(
            validation_passed=True,
            was_interpolated=False,
            reasonableness_passed=False,
            was_calibrated=True
        )

        assert quality == 'low'

    def test_get_quality_summary(self, tracker):
        """Test getting overall quality summary"""
        # Record various quality events
        tracker.record_validation('thrust_total', True, None)
        tracker.record_validation('thrust_total', False, 'Out of range')
        tracker.record_interpolation('pressure', True)
        tracker.record_calibration('sensor_A', True)

        summary = tracker.get_quality_summary()

        assert 'total_tags' in summary
        assert 'total_validations' in summary
        assert 'validation_pass_rate' in summary
        assert summary['total_tags'] >= 2

    def test_get_tag_statistics_nonexistent(self, tracker):
        """Test getting statistics for non-existent tag"""
        stats = tracker.get_tag_statistics('nonexistent_tag')

        # Should return empty/zero statistics
        assert stats['total_validations'] == 0

    def test_get_all_tag_statistics(self, tracker):
        """Test getting statistics for all tags"""
        tracker.record_validation('tag1', True, None)
        tracker.record_validation('tag2', True, None)

        all_stats = tracker.get_all_tag_statistics()

        assert 'tag1' in all_stats
        assert 'tag2' in all_stats
        assert len(all_stats) >= 2

    def test_failure_reasons_accumulation(self, tracker):
        """Test accumulation of failure reasons"""
        tracker.record_validation('thrust_total', False, 'Too high')
        tracker.record_validation('thrust_total', False, 'Too low')
        tracker.record_validation('thrust_total', False, 'Too high')

        stats = tracker.get_tag_statistics('thrust_total')

        # Should have unique failure reasons
        assert 'Too high' in stats['failure_reasons']
        assert 'Too low' in stats['failure_reasons']

    def test_validation_pass_rate(self, tracker):
        """Test validation pass rate calculation"""
        # 7 passes, 3 fails = 70% pass rate
        for i in range(7):
            tracker.record_validation('sensor', True, None)
        for i in range(3):
            tracker.record_validation('sensor', False, 'Error')

        stats = tracker.get_tag_statistics('sensor')

        expected_rate = 7.0 / 10.0
        assert abs(stats['validation_pass_rate'] - expected_rate) < 0.01

    def test_interpolation_rate(self, tracker):
        """Test interpolation rate calculation"""
        # 3 interpolated out of 10 = 30% interpolation rate
        for i in range(3):
            tracker.record_interpolation('pressure', True)
        for i in range(7):
            tracker.record_interpolation('pressure', False)

        stats = tracker.get_tag_statistics('pressure')

        expected_rate = 3.0 / 10.0
        assert abs(stats['interpolation_rate'] - expected_rate) < 0.01

    def test_reset_statistics(self, tracker):
        """Test statistics reset"""
        tracker.record_validation('tag1', True, None)
        tracker.record_interpolation('tag2', True)

        tracker.reset_statistics()

        summary = tracker.get_quality_summary()
        assert summary['total_tags'] == 0
        assert summary['total_validations'] == 0

    def test_reset_tag_statistics(self, tracker):
        """Test resetting statistics for specific tag"""
        tracker.record_validation('tag1', True, None)
        tracker.record_validation('tag2', True, None)

        tracker.reset_tag_statistics('tag1')

        stats1 = tracker.get_tag_statistics('tag1')
        stats2 = tracker.get_tag_statistics('tag2')

        assert stats1['total_validations'] == 0
        assert stats2['total_validations'] == 1

    def test_concurrent_tag_tracking(self, tracker):
        """Test tracking multiple tags concurrently"""
        tags = ['tag1', 'tag2', 'tag3', 'tag4', 'tag5']

        for tag in tags:
            tracker.record_validation(tag, True, None)
            tracker.record_interpolation(tag, False)
            tracker.record_calibration(tag, True)

        summary = tracker.get_quality_summary()
        assert summary['total_tags'] == len(tags)

    def test_quality_distribution(self, tracker):
        """Test quality score distribution"""
        # Record mix of quality levels
        for i in range(10):
            tracker.record_validation('sensor', True, None)
            tracker.record_interpolation('sensor', i % 3 == 0)  # Some interpolated
            tracker.record_reasonableness('sensor', i % 5 != 0, 'Error' if i % 5 == 0 else None)
            tracker.record_calibration('sensor', True)

        stats = tracker.get_tag_statistics('sensor')

        # Should have recorded all events
        assert stats['total_validations'] == 10
        assert stats['total_values'] >= 10

    def test_get_worst_quality_tags(self, tracker):
        """Test identifying worst quality tags"""
        # Good tag
        for i in range(10):
            tracker.record_validation('good_tag', True, None)

        # Bad tag
        for i in range(10):
            tracker.record_validation('bad_tag', False, 'Error')

        # Should be able to identify worst tags
        all_stats = tracker.get_all_tag_statistics()

        good_stats = all_stats['good_tag']
        bad_stats = all_stats['bad_tag']

        assert good_stats['validation_pass_rate'] > bad_stats['validation_pass_rate']

    def test_export_metrics_report(self, tracker):
        """Test exporting comprehensive metrics report"""
        # Record various metrics
        tracker.record_validation('tag1', True, None)
        tracker.record_validation('tag1', False, 'Error1')
        tracker.record_interpolation('tag1', True)
        tracker.record_calibration('tag1', True)
        tracker.record_reasonableness('tag1', True, None)

        report = tracker.export_report()

        assert 'summary' in report
        assert 'tags' in report
        assert 'tag1' in report['tags']

    def test_time_window_statistics(self, tracker):
        """Test statistics over time window"""
        import time

        # Record with timestamps
        for i in range(5):
            tracker.record_validation('sensor', True, None)
            time.sleep(0.01)  # Small delay

        # Should have time-based statistics
        stats = tracker.get_tag_statistics('sensor')
        assert stats['total_validations'] == 5
