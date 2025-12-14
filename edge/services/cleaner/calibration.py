"""
T040: Calibration Offset Applicator
Applies calibration offsets to sensor readings
Supports linear, polynomial, and lookup table calibrations
"""
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import yaml

logger = logging.getLogger(__name__)


class CalibrationApplicator:
    """
    Applies calibration corrections to sensor readings.

    Features:
    - Linear offset and scale calibration
    - Polynomial calibration curves
    - Time-based calibration validity
    - Per-sensor calibration tracking
    - Calibration history management
    """

    def __init__(self, config_path: str = "edge/config/calibration.yaml"):
        """
        Initialize calibration applicator.

        Args:
            config_path: Path to calibration configuration YAML file
        """
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            self.calibrations = config.get('calibrations', {})
        except FileNotFoundError:
            logger.warning(f"Calibration config not found: {config_path}")
            self.calibrations = {}

        self.stats = {
            'total_applied': 0,
            'by_tag': {},
            'uncalibrated_tags': set()
        }

    def apply_linear_calibration(
        self,
        raw_value: float,
        offset: float = 0.0,
        scale: float = 1.0
    ) -> float:
        """
        Apply linear calibration: calibrated = (raw + offset) * scale

        Args:
            raw_value: Raw sensor reading
            offset: Additive offset
            scale: Multiplicative scale factor

        Returns:
            Calibrated value
        """
        return (raw_value + offset) * scale

    def apply_polynomial_calibration(
        self,
        raw_value: float,
        coefficients: List[float]
    ) -> float:
        """
        Apply polynomial calibration: calibrated = c0 + c1*x + c2*x^2 + ...

        Args:
            raw_value: Raw sensor reading
            coefficients: Polynomial coefficients [c0, c1, c2, ...]

        Returns:
            Calibrated value
        """
        result = 0.0
        for i, coeff in enumerate(coefficients):
            result += coeff * (raw_value ** i)
        return result

    def apply_lookup_table_calibration(
        self,
        raw_value: float,
        lookup_table: List[Dict[str, float]]
    ) -> float:
        """
        Apply lookup table calibration with linear interpolation.

        Args:
            raw_value: Raw sensor reading
            lookup_table: List of {'raw': x, 'calibrated': y} points

        Returns:
            Calibrated value (interpolated if between points)
        """
        if not lookup_table:
            return raw_value

        # Sort by raw value
        sorted_table = sorted(lookup_table, key=lambda x: x['raw'])

        # Check bounds
        if raw_value <= sorted_table[0]['raw']:
            return sorted_table[0]['calibrated']
        if raw_value >= sorted_table[-1]['raw']:
            return sorted_table[-1]['calibrated']

        # Linear interpolation between points
        for i in range(len(sorted_table) - 1):
            x1 = sorted_table[i]['raw']
            y1 = sorted_table[i]['calibrated']
            x2 = sorted_table[i + 1]['raw']
            y2 = sorted_table[i + 1]['calibrated']

            if x1 <= raw_value <= x2:
                # Linear interpolation
                if x2 - x1 == 0:
                    return y1
                slope = (y2 - y1) / (x2 - x1)
                return y1 + slope * (raw_value - x1)

        return raw_value

    def calibrate(
        self,
        tag_name: str,
        raw_value: float,
        timestamp: Optional[float] = None
    ) -> Tuple[float, bool]:
        """
        Apply calibration for a specific tag.

        Args:
            tag_name: Sensor tag identifier
            raw_value: Raw sensor reading
            timestamp: Unix timestamp (for time-based calibration validity)

        Returns:
            Tuple of (calibrated_value, was_calibrated)
            - calibrated_value: The calibrated reading
            - was_calibrated: True if calibration was applied, False if not
        """
        self.stats['total_applied'] += 1

        if tag_name not in self.stats['by_tag']:
            self.stats['by_tag'][tag_name] = {
                'total': 0,
                'calibrated': 0,
                'uncalibrated': 0
            }

        self.stats['by_tag'][tag_name]['total'] += 1

        # Check if calibration exists for this tag
        if tag_name not in self.calibrations:
            self.stats['uncalibrated_tags'].add(tag_name)
            self.stats['by_tag'][tag_name]['uncalibrated'] += 1
            logger.debug(f"No calibration configured for {tag_name}")
            return raw_value, False

        calib_config = self.calibrations[tag_name]

        # Check if calibration is enabled
        if not calib_config.get('enabled', True):
            self.stats['by_tag'][tag_name]['uncalibrated'] += 1
            return raw_value, False

        # Check time-based validity (if specified)
        if timestamp is not None:
            valid_from = calib_config.get('valid_from')
            valid_until = calib_config.get('valid_until')

            if valid_from and timestamp < valid_from:
                logger.warning(
                    f"Calibration for {tag_name} not yet valid "
                    f"(valid from {datetime.fromtimestamp(valid_from)})"
                )
                self.stats['by_tag'][tag_name]['uncalibrated'] += 1
                return raw_value, False

            if valid_until and timestamp > valid_until:
                logger.warning(
                    f"Calibration for {tag_name} expired "
                    f"(valid until {datetime.fromtimestamp(valid_until)})"
                )
                self.stats['by_tag'][tag_name]['uncalibrated'] += 1
                return raw_value, False

        # Apply calibration based on type
        calib_type = calib_config.get('type', 'linear')

        try:
            if calib_type == 'linear':
                offset = calib_config.get('offset', 0.0)
                scale = calib_config.get('scale', 1.0)
                calibrated_value = self.apply_linear_calibration(
                    raw_value, offset, scale
                )

            elif calib_type == 'polynomial':
                coefficients = calib_config.get('coefficients', [0.0, 1.0])
                calibrated_value = self.apply_polynomial_calibration(
                    raw_value, coefficients
                )

            elif calib_type == 'lookup':
                lookup_table = calib_config.get('lookup_table', [])
                calibrated_value = self.apply_lookup_table_calibration(
                    raw_value, lookup_table
                )

            else:
                logger.warning(f"Unknown calibration type: {calib_type}")
                self.stats['by_tag'][tag_name]['uncalibrated'] += 1
                return raw_value, False

            self.stats['by_tag'][tag_name]['calibrated'] += 1

            logger.debug(
                f"Calibrated {tag_name}: {raw_value:.3f} → {calibrated_value:.3f} "
                f"(type={calib_type})"
            )

            return calibrated_value, True

        except Exception as e:
            logger.error(f"Calibration failed for {tag_name}: {e}")
            self.stats['by_tag'][tag_name]['uncalibrated'] += 1
            return raw_value, False

    def calibrate_batch(
        self,
        data: Dict[str, float],
        timestamp: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Apply calibration to a batch of sensor readings.

        Args:
            data: Dictionary of tag_name -> raw_value
            timestamp: Unix timestamp for all readings

        Returns:
            Dictionary with:
            - 'calibrated': Dict of tag_name -> calibrated_value
            - 'flags': Dict of tag_name -> 'calibrated' or 'raw'
        """
        calibrated_data = {}
        flags = {}

        for tag_name, raw_value in data.items():
            calibrated_value, was_calibrated = self.calibrate(
                tag_name, raw_value, timestamp
            )
            calibrated_data[tag_name] = calibrated_value
            flags[tag_name] = 'calibrated' if was_calibrated else 'raw'

        return {
            'calibrated': calibrated_data,
            'flags': flags
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get calibration statistics.

        Returns:
            Dictionary with calibration counts and rates
        """
        total = self.stats['total_applied']
        if total == 0:
            calibration_rate = 0.0
        else:
            total_calibrated = sum(
                tag_stats['calibrated']
                for tag_stats in self.stats['by_tag'].values()
            )
            calibration_rate = (total_calibrated / total) * 100

        return {
            'total_processed': total,
            'calibration_rate_percent': round(calibration_rate, 2),
            'uncalibrated_tags': list(self.stats['uncalibrated_tags']),
            'by_tag': self.stats['by_tag']
        }

    def reset_statistics(self) -> None:
        """Reset calibration statistics"""
        self.stats = {
            'total_applied': 0,
            'by_tag': {},
            'uncalibrated_tags': set()
        }


# Type alias for cleaner imports
Tuple = tuple


# Example usage
if __name__ == "__main__":
    applicator = CalibrationApplicator()

    print("Test 1: Linear Calibration")
    # Simulated pressure sensor with -0.05 bar offset and 1.02 scale
    raw_pressure = 2.50
    calibrated, was_calibrated = applicator.calibrate('chamber_pressure', raw_pressure)
    print(f"  Raw: {raw_pressure:.3f} bar → Calibrated: {calibrated:.3f} bar")
    print(f"  Was calibrated: {was_calibrated}\n")

    print("Test 2: Polynomial Calibration")
    # Simulated temperature sensor with quadratic correction
    raw_temp = 25.0
    calibrated, was_calibrated = applicator.calibrate('slurry_temperature', raw_temp)
    print(f"  Raw: {raw_temp:.3f} °C → Calibrated: {calibrated:.3f} °C")
    print(f"  Was calibrated: {was_calibrated}\n")

    print("Test 3: Batch Calibration")
    data = {
        'chamber_pressure': 2.50,
        'slurry_temperature': 25.0,
        'thrust_total': 12000,
        'unknown_sensor': 100
    }
    result = applicator.calibrate_batch(data)
    print("  Calibrated values:")
    for tag, value in result['calibrated'].items():
        flag = result['flags'][tag]
        print(f"    {tag}: {value:.3f} [{flag}]")

    print("\nStatistics:", applicator.get_statistics())
