"""
T041: Data Quality Metrics Tracker
Aggregates quality metrics from all cleaning stages
Provides comprehensive data quality assessment
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


class QualityMetricsTracker:
    """
    Tracks and aggregates data quality metrics across all cleaning stages.

    Metrics tracked:
    - Threshold validation failures
    - Interpolation operations
    - Reasonableness check failures
    - Calibration application rates
    - Overall data quality scores
    - Per-tag quality indicators
    """

    def __init__(self):
        """Initialize quality metrics tracker"""
        self.metrics = {
            'session_start': datetime.utcnow().timestamp(),
            'total_records_processed': 0,
            'validation': {
                'total_validated': 0,
                'passed': 0,
                'failed': 0,
                'by_tag': defaultdict(lambda: {'passed': 0, 'failed': 0})
            },
            'interpolation': {
                'gaps_detected': 0,
                'values_interpolated': 0,
                'gaps_too_large': 0
            },
            'reasonableness': {
                'total_checks': 0,
                'passed': 0,
                'failed': 0,
                'by_rule': defaultdict(lambda: {'passed': 0, 'failed': 0})
            },
            'calibration': {
                'total_processed': 0,
                'calibrated': 0,
                'uncalibrated': 0,
                'by_tag': defaultdict(lambda: {'calibrated': 0, 'uncalibrated': 0})
            },
            'overall_quality': {
                'high_quality_records': 0,    # All checks passed
                'medium_quality_records': 0,  # Some interpolation/calibration
                'low_quality_records': 0      # Validation or reasonableness failures
            }
        }

    def record_validation(
        self,
        tag_name: str,
        passed: bool,
        reason: Optional[str] = None
    ) -> None:
        """
        Record a threshold validation result.

        Args:
            tag_name: Sensor tag identifier
            passed: Whether validation passed
            reason: Failure reason (if applicable)
        """
        self.metrics['validation']['total_validated'] += 1

        if passed:
            self.metrics['validation']['passed'] += 1
            self.metrics['validation']['by_tag'][tag_name]['passed'] += 1
        else:
            self.metrics['validation']['failed'] += 1
            self.metrics['validation']['by_tag'][tag_name]['failed'] += 1
            logger.info(f"Validation failure recorded: {tag_name} - {reason}")

    def record_interpolation(
        self,
        gaps_detected: int,
        values_interpolated: int,
        gaps_too_large: int = 0
    ) -> None:
        """
        Record interpolation statistics.

        Args:
            gaps_detected: Number of gaps found
            values_interpolated: Number of values filled
            gaps_too_large: Number of gaps too large to fill
        """
        self.metrics['interpolation']['gaps_detected'] += gaps_detected
        self.metrics['interpolation']['values_interpolated'] += values_interpolated
        self.metrics['interpolation']['gaps_too_large'] += gaps_too_large

    def record_reasonableness_check(
        self,
        rule_name: str,
        passed: bool,
        reason: Optional[str] = None
    ) -> None:
        """
        Record a reasonableness check result.

        Args:
            rule_name: Name of physics rule checked
            passed: Whether check passed
            reason: Failure reason (if applicable)
        """
        self.metrics['reasonableness']['total_checks'] += 1

        if passed:
            self.metrics['reasonableness']['passed'] += 1
            self.metrics['reasonableness']['by_rule'][rule_name]['passed'] += 1
        else:
            self.metrics['reasonableness']['failed'] += 1
            self.metrics['reasonableness']['by_rule'][rule_name]['failed'] += 1
            logger.info(f"Reasonableness failure recorded: {rule_name} - {reason}")

    def record_calibration(
        self,
        tag_name: str,
        was_calibrated: bool
    ) -> None:
        """
        Record calibration application.

        Args:
            tag_name: Sensor tag identifier
            was_calibrated: Whether calibration was applied
        """
        self.metrics['calibration']['total_processed'] += 1

        if was_calibrated:
            self.metrics['calibration']['calibrated'] += 1
            self.metrics['calibration']['by_tag'][tag_name]['calibrated'] += 1
        else:
            self.metrics['calibration']['uncalibrated'] += 1
            self.metrics['calibration']['by_tag'][tag_name]['uncalibrated'] += 1

    def record_overall_quality(
        self,
        quality_level: str
    ) -> None:
        """
        Record overall quality assessment for a data record.

        Args:
            quality_level: 'high', 'medium', or 'low'
        """
        self.metrics['total_records_processed'] += 1

        if quality_level == 'high':
            self.metrics['overall_quality']['high_quality_records'] += 1
        elif quality_level == 'medium':
            self.metrics['overall_quality']['medium_quality_records'] += 1
        elif quality_level == 'low':
            self.metrics['overall_quality']['low_quality_records'] += 1
        else:
            logger.warning(f"Unknown quality level: {quality_level}")

    def assess_record_quality(
        self,
        validation_passed: bool,
        was_interpolated: bool,
        reasonableness_passed: bool,
        was_calibrated: bool
    ) -> str:
        """
        Assess overall quality level of a data record.

        Args:
            validation_passed: Threshold validation result
            was_interpolated: Whether data was interpolated
            reasonableness_passed: Reasonableness check result
            was_calibrated: Whether calibration was applied

        Returns:
            Quality level: 'high', 'medium', or 'low'
        """
        # Low quality: Failed validation or reasonableness checks
        if not validation_passed or not reasonableness_passed:
            return 'low'

        # Medium quality: Passed checks but required interpolation
        if was_interpolated:
            return 'medium'

        # High quality: Passed all checks, no interpolation needed
        return 'high'

    def get_quality_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive quality metrics summary.

        Returns:
            Dictionary with quality statistics and calculated rates
        """
        total_validated = self.metrics['validation']['total_validated']
        validation_pass_rate = (
            (self.metrics['validation']['passed'] / total_validated * 100)
            if total_validated > 0 else 0.0
        )

        total_checks = self.metrics['reasonableness']['total_checks']
        reasonableness_pass_rate = (
            (self.metrics['reasonableness']['passed'] / total_checks * 100)
            if total_checks > 0 else 0.0
        )

        total_calibrated = self.metrics['calibration']['total_processed']
        calibration_rate = (
            (self.metrics['calibration']['calibrated'] / total_calibrated * 100)
            if total_calibrated > 0 else 0.0
        )

        total_records = self.metrics['total_records_processed']
        high_quality_rate = (
            (self.metrics['overall_quality']['high_quality_records'] / total_records * 100)
            if total_records > 0 else 0.0
        )

        gaps_detected = self.metrics['interpolation']['gaps_detected']
        values_interpolated = self.metrics['interpolation']['values_interpolated']
        avg_gap_size = (
            (values_interpolated / gaps_detected)
            if gaps_detected > 0 else 0.0
        )

        return {
            'session_duration_hours': (
                datetime.utcnow().timestamp() - self.metrics['session_start']
            ) / 3600,
            'total_records_processed': total_records,

            'validation': {
                'total': total_validated,
                'passed': self.metrics['validation']['passed'],
                'failed': self.metrics['validation']['failed'],
                'pass_rate_percent': round(validation_pass_rate, 2)
            },

            'interpolation': {
                'gaps_detected': gaps_detected,
                'values_interpolated': values_interpolated,
                'gaps_too_large': self.metrics['interpolation']['gaps_too_large'],
                'avg_gap_size': round(avg_gap_size, 2)
            },

            'reasonableness': {
                'total_checks': total_checks,
                'passed': self.metrics['reasonableness']['passed'],
                'failed': self.metrics['reasonableness']['failed'],
                'pass_rate_percent': round(reasonableness_pass_rate, 2)
            },

            'calibration': {
                'total_processed': total_calibrated,
                'calibrated': self.metrics['calibration']['calibrated'],
                'uncalibrated': self.metrics['calibration']['uncalibrated'],
                'calibration_rate_percent': round(calibration_rate, 2)
            },

            'overall_quality': {
                'high': self.metrics['overall_quality']['high_quality_records'],
                'medium': self.metrics['overall_quality']['medium_quality_records'],
                'low': self.metrics['overall_quality']['low_quality_records'],
                'high_quality_rate_percent': round(high_quality_rate, 2)
            }
        }

    def get_tag_quality_report(self, tag_name: str) -> Dict[str, Any]:
        """
        Get quality metrics for a specific tag.

        Args:
            tag_name: Sensor tag identifier

        Returns:
            Dictionary with tag-specific quality metrics
        """
        validation_stats = self.metrics['validation']['by_tag'].get(tag_name, {})
        calibration_stats = self.metrics['calibration']['by_tag'].get(tag_name, {})

        total_validated = validation_stats.get('passed', 0) + validation_stats.get('failed', 0)
        validation_pass_rate = (
            (validation_stats.get('passed', 0) / total_validated * 100)
            if total_validated > 0 else 0.0
        )

        total_calibrated = calibration_stats.get('calibrated', 0) + calibration_stats.get('uncalibrated', 0)
        calibration_rate = (
            (calibration_stats.get('calibrated', 0) / total_calibrated * 100)
            if total_calibrated > 0 else 0.0
        )

        return {
            'tag_name': tag_name,
            'validation': {
                'total': total_validated,
                'passed': validation_stats.get('passed', 0),
                'failed': validation_stats.get('failed', 0),
                'pass_rate_percent': round(validation_pass_rate, 2)
            },
            'calibration': {
                'total': total_calibrated,
                'calibrated': calibration_stats.get('calibrated', 0),
                'uncalibrated': calibration_stats.get('uncalibrated', 0),
                'calibration_rate_percent': round(calibration_rate, 2)
            }
        }

    def get_problematic_tags(self, min_failure_rate: float = 10.0) -> List[Dict[str, Any]]:
        """
        Identify tags with high failure rates.

        Args:
            min_failure_rate: Minimum failure rate percentage to flag

        Returns:
            List of problematic tags with their failure rates
        """
        problematic = []

        for tag_name, stats in self.metrics['validation']['by_tag'].items():
            total = stats['passed'] + stats['failed']
            if total < 10:  # Skip tags with too few samples
                continue

            failure_rate = (stats['failed'] / total) * 100
            if failure_rate >= min_failure_rate:
                problematic.append({
                    'tag_name': tag_name,
                    'failure_rate_percent': round(failure_rate, 2),
                    'total_samples': total,
                    'failed_samples': stats['failed']
                })

        # Sort by failure rate (descending)
        return sorted(problematic, key=lambda x: x['failure_rate_percent'], reverse=True)

    def export_metrics(self, filepath: str) -> None:
        """
        Export metrics to JSON file.

        Args:
            filepath: Output file path
        """
        summary = self.get_quality_summary()

        # Convert defaultdicts to regular dicts for JSON serialization
        export_data = {
            'summary': summary,
            'detailed_metrics': {
                'validation_by_tag': dict(self.metrics['validation']['by_tag']),
                'reasonableness_by_rule': dict(self.metrics['reasonableness']['by_rule']),
                'calibration_by_tag': dict(self.metrics['calibration']['by_tag'])
            },
            'export_timestamp': datetime.utcnow().isoformat()
        }

        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Quality metrics exported to {filepath}")

    def reset_metrics(self) -> None:
        """Reset all metrics"""
        self.__init__()


# Example usage
if __name__ == "__main__":
    tracker = QualityMetricsTracker()

    # Simulate data processing
    print("Simulating data quality tracking...\n")

    # Record some validation results
    tracker.record_validation('thrust_total', True)
    tracker.record_validation('thrust_total', True)
    tracker.record_validation('thrust_total', False, "Below minimum threshold")
    tracker.record_validation('chamber_pressure', True)
    tracker.record_validation('chamber_pressure', False, "Above maximum")

    # Record interpolation
    tracker.record_interpolation(gaps_detected=3, values_interpolated=8, gaps_too_large=1)

    # Record reasonableness checks
    tracker.record_reasonableness_check('thrust_penetration_ratio', True)
    tracker.record_reasonableness_check('torque_thrust_ratio', True)
    tracker.record_reasonableness_check('chamber_pressure_depth', False, "Pressure too low for depth")

    # Record calibration
    tracker.record_calibration('thrust_total', True)
    tracker.record_calibration('chamber_pressure', True)
    tracker.record_calibration('unknown_sensor', False)

    # Record overall quality assessments
    tracker.record_overall_quality('high')
    tracker.record_overall_quality('high')
    tracker.record_overall_quality('medium')
    tracker.record_overall_quality('low')

    # Print summary
    print("Quality Metrics Summary:")
    print("=" * 60)
    summary = tracker.get_quality_summary()
    print(json.dumps(summary, indent=2))

    print("\n" + "=" * 60)
    print("Tag-specific Report: thrust_total")
    print("=" * 60)
    tag_report = tracker.get_tag_quality_report('thrust_total')
    print(json.dumps(tag_report, indent=2))

    print("\n" + "=" * 60)
    print("Problematic Tags (>10% failure rate):")
    print("=" * 60)
    problematic = tracker.get_problematic_tags(min_failure_rate=10.0)
    for tag_info in problematic:
        print(f"  - {tag_info['tag_name']}: {tag_info['failure_rate_percent']}% "
              f"({tag_info['failed_samples']}/{tag_info['total_samples']} failures)")
