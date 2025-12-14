"""
T037: Engineering Threshold Validator
Validates sensor readings against engineering limits
Rejects values outside reasonable operating ranges
"""
import logging
from typing import Optional, Dict, Any
import yaml

logger = logging.getLogger(__name__)


class ThresholdValidator:
    """
    Validates sensor readings against configured engineering thresholds.

    Checks:
    - Minimum value bounds
    - Maximum value bounds
    - Physical reasonableness
    """

    def __init__(self, config_path: str = "edge/config/thresholds.yaml"):
        """
        Initialize validator with threshold configuration.

        Args:
            config_path: Path to thresholds YAML file
        """
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        self.thresholds = config['thresholds']
        self.stats = {
            'total_validated': 0,
            'passed': 0,
            'rejected': 0,
            'by_tag': {}
        }

    def validate(
        self,
        tag_name: str,
        value: Any
    ) -> tuple[bool, Optional[str]]:
        """
        Validate a sensor reading against thresholds.

        Args:
            tag_name: Tag identifier (e.g., 'thrust_total', 'chamber_pressure')
            value: Reading value

        Returns:
            Tuple of (is_valid, rejection_reason)
            - (True, None) if value passes validation
            - (False, reason) if value fails validation
        """
        self.stats['total_validated'] += 1

        if tag_name not in self.stats['by_tag']:
            self.stats['by_tag'][tag_name] = {'passed': 0, 'rejected': 0}

        # Check if threshold exists for this tag
        if tag_name not in self.thresholds:
            logger.debug(f"No threshold configured for {tag_name}, accepting value")
            self.stats['passed'] += 1
            self.stats['by_tag'][tag_name]['passed'] += 1
            return True, None

        threshold = self.thresholds[tag_name]

        # Check for None/null values
        if value is None:
            reason = "Null value"
            self._record_rejection(tag_name, value, reason)
            return False, reason

        # Convert to float for comparison
        try:
            numeric_value = float(value)
        except (ValueError, TypeError):
            reason = f"Non-numeric value: {value}"
            self._record_rejection(tag_name, value, reason)
            return False, reason

        # Check minimum bound
        if 'min' in threshold:
            if numeric_value < threshold['min']:
                reason = f"Below minimum: {numeric_value} < {threshold['min']} {threshold.get('unit', '')}"
                self._record_rejection(tag_name, value, reason)
                return False, reason

        # Check maximum bound
        if 'max' in threshold:
            if numeric_value > threshold['max']:
                reason = f"Above maximum: {numeric_value} > {threshold['max']} {threshold.get('unit', '')}"
                self._record_rejection(tag_name, value, reason)
                return False, reason

        # Value passed validation
        self.stats['passed'] += 1
        self.stats['by_tag'][tag_name]['passed'] += 1
        return True, None

    def _record_rejection(self, tag_name: str, value: Any, reason: str) -> None:
        """Record a rejected value for statistics"""
        self.stats['rejected'] += 1
        self.stats['by_tag'][tag_name]['rejected'] += 1
        logger.warning(f"Threshold validation failed for {tag_name}: {reason}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get validation statistics.

        Returns:
            Dictionary with validation counts and rejection rates
        """
        total = self.stats['total_validated']
        if total == 0:
            rejection_rate = 0.0
        else:
            rejection_rate = (self.stats['rejected'] / total) * 100

        return {
            'total_validated': total,
            'passed': self.stats['passed'],
            'rejected': self.stats['rejected'],
            'rejection_rate_percent': round(rejection_rate, 2),
            'by_tag': self.stats['by_tag']
        }

    def reset_statistics(self) -> None:
        """Reset validation statistics"""
        self.stats = {
            'total_validated': 0,
            'passed': 0,
            'rejected': 0,
            'by_tag': {}
        }


# Example usage
if __name__ == "__main__":
    validator = ThresholdValidator()

    # Test cases
    test_cases = [
        ("thrust_total", 8500),      # Valid
        ("thrust_total", -100),       # Invalid: below min
        ("thrust_total", 60000),      # Invalid: above max
        ("chamber_pressure", 2.5),    # Valid
        ("chamber_pressure", 15),     # Invalid: above max
        ("unknown_tag", 100),         # Valid: no threshold
    ]

    for tag, value in test_cases:
        is_valid, reason = validator.validate(tag, value)
        status = "✓ PASS" if is_valid else "✗ FAIL"
        print(f"{status}: {tag}={value} {f'({reason})' if reason else ''}")

    print("\nStatistics:", validator.get_statistics())
