"""
T039: Reasonableness Checker
Physics-based validation of sensor readings
Checks for violations of physical laws and engineering principles
"""
import logging
from typing import Dict, Any, Optional, List, Tuple
import yaml

logger = logging.getLogger(__name__)


class ReasonablenessChecker:
    """
    Validates sensor readings against physics-based rules.

    Features:
    - Cross-parameter validation (e.g., thrust vs penetration rate)
    - Engineering ratio checks (e.g., torque/thrust ratio)
    - Physical constraint validation
    - Multi-tag relationship validation
    """

    def __init__(self, config_path: str = "edge/config/reasonableness_rules.yaml"):
        """
        Initialize reasonableness checker.

        Args:
            config_path: Path to reasonableness rules YAML file
        """
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            self.rules = config.get('rules', {})
        except FileNotFoundError:
            logger.warning(f"Reasonableness rules config not found: {config_path}")
            self.rules = self._get_default_rules()

        self.stats = {
            'total_checks': 0,
            'passed': 0,
            'failed': 0,
            'by_rule': {}
        }

    def _get_default_rules(self) -> Dict[str, Any]:
        """
        Get default physics-based validation rules.

        Returns:
            Dictionary of validation rules
        """
        return {
            'thrust_penetration_ratio': {
                'description': 'Thrust should increase with penetration rate',
                'min_ratio': 100,  # kN per mm/min
                'max_ratio': 2000,
                'enabled': True
            },
            'torque_thrust_ratio': {
                'description': 'Torque/Thrust ratio check',
                'min_ratio': 0.01,  # kNm/kN
                'max_ratio': 0.15,
                'enabled': True
            },
            'chamber_pressure_depth': {
                'description': 'Chamber pressure should increase with depth',
                'min_bar_per_meter': 0.08,  # Minimum 0.08 bar/m
                'max_bar_per_meter': 0.15,  # Maximum 0.15 bar/m
                'enabled': True
            },
            'power_consumption': {
                'description': 'Power should correlate with thrust and torque',
                'enabled': True
            },
            'grout_pressure_volume': {
                'description': 'Grout volume should correspond to pressure',
                'enabled': True
            }
        }

    def check_thrust_penetration_ratio(
        self,
        thrust: float,
        penetration_rate: float
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if thrust/penetration rate ratio is reasonable.

        Args:
            thrust: Total thrust force (kN)
            penetration_rate: Shield penetration rate (mm/min)

        Returns:
            Tuple of (is_valid, reason)
        """
        rule = self.rules.get('thrust_penetration_ratio', {})
        if not rule.get('enabled', False):
            return True, None

        self.stats['total_checks'] += 1
        rule_name = 'thrust_penetration_ratio'

        if rule_name not in self.stats['by_rule']:
            self.stats['by_rule'][rule_name] = {'passed': 0, 'failed': 0}

        # Avoid division by zero
        if penetration_rate <= 0.01:
            logger.debug("Penetration rate too low for ratio check")
            self.stats['passed'] += 1
            self.stats['by_rule'][rule_name]['passed'] += 1
            return True, None

        ratio = thrust / penetration_rate

        min_ratio = rule.get('min_ratio', 100)
        max_ratio = rule.get('max_ratio', 2000)

        if ratio < min_ratio:
            reason = f"Thrust/penetration ratio too low: {ratio:.1f} < {min_ratio}"
            self._record_failure(rule_name, reason)
            return False, reason

        if ratio > max_ratio:
            reason = f"Thrust/penetration ratio too high: {ratio:.1f} > {max_ratio}"
            self._record_failure(rule_name, reason)
            return False, reason

        self.stats['passed'] += 1
        self.stats['by_rule'][rule_name]['passed'] += 1
        return True, None

    def check_torque_thrust_ratio(
        self,
        torque: float,
        thrust: float
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if torque/thrust ratio is within reasonable bounds.

        Args:
            torque: Cutterhead torque (kNm)
            thrust: Total thrust (kN)

        Returns:
            Tuple of (is_valid, reason)
        """
        rule = self.rules.get('torque_thrust_ratio', {})
        if not rule.get('enabled', False):
            return True, None

        self.stats['total_checks'] += 1
        rule_name = 'torque_thrust_ratio'

        if rule_name not in self.stats['by_rule']:
            self.stats['by_rule'][rule_name] = {'passed': 0, 'failed': 0}

        if thrust <= 0:
            reason = "Invalid thrust value for ratio check"
            self._record_failure(rule_name, reason)
            return False, reason

        ratio = torque / thrust

        min_ratio = rule.get('min_ratio', 0.01)
        max_ratio = rule.get('max_ratio', 0.15)

        if ratio < min_ratio:
            reason = f"Torque/thrust ratio too low: {ratio:.3f} < {min_ratio}"
            self._record_failure(rule_name, reason)
            return False, reason

        if ratio > max_ratio:
            reason = f"Torque/thrust ratio too high: {ratio:.3f} > {max_ratio}"
            self._record_failure(rule_name, reason)
            return False, reason

        self.stats['passed'] += 1
        self.stats['by_rule'][rule_name]['passed'] += 1
        return True, None

    def check_chamber_pressure_depth(
        self,
        chamber_pressure: float,
        depth: float
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if chamber pressure is appropriate for excavation depth.

        Args:
            chamber_pressure: Earth pressure balance chamber pressure (bar)
            depth: Excavation depth below ground surface (m)

        Returns:
            Tuple of (is_valid, reason)
        """
        rule = self.rules.get('chamber_pressure_depth', {})
        if not rule.get('enabled', False):
            return True, None

        self.stats['total_checks'] += 1
        rule_name = 'chamber_pressure_depth'

        if rule_name not in self.stats['by_rule']:
            self.stats['by_rule'][rule_name] = {'passed': 0, 'failed': 0}

        if depth <= 0:
            reason = "Invalid depth value for pressure check"
            self._record_failure(rule_name, reason)
            return False, reason

        # Typical earth pressure: ~0.1 bar per meter depth
        min_bar_per_m = rule.get('min_bar_per_meter', 0.08)
        max_bar_per_m = rule.get('max_bar_per_meter', 0.15)

        expected_min_pressure = depth * min_bar_per_m
        expected_max_pressure = depth * max_bar_per_m

        if chamber_pressure < expected_min_pressure:
            reason = (f"Chamber pressure too low for depth: "
                     f"{chamber_pressure:.2f} bar < {expected_min_pressure:.2f} bar "
                     f"at {depth:.1f}m depth")
            self._record_failure(rule_name, reason)
            return False, reason

        if chamber_pressure > expected_max_pressure:
            reason = (f"Chamber pressure too high for depth: "
                     f"{chamber_pressure:.2f} bar > {expected_max_pressure:.2f} bar "
                     f"at {depth:.1f}m depth")
            self._record_failure(rule_name, reason)
            return False, reason

        self.stats['passed'] += 1
        self.stats['by_rule'][rule_name]['passed'] += 1
        return True, None

    def check_power_consumption(
        self,
        power: float,
        thrust: float,
        torque: float,
        penetration_rate: float
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if power consumption is reasonable given operating parameters.

        Args:
            power: Total power consumption (kW)
            thrust: Total thrust (kN)
            torque: Cutterhead torque (kNm)
            penetration_rate: Penetration rate (mm/min)

        Returns:
            Tuple of (is_valid, reason)
        """
        rule = self.rules.get('power_consumption', {})
        if not rule.get('enabled', False):
            return True, None

        self.stats['total_checks'] += 1
        rule_name = 'power_consumption'

        if rule_name not in self.stats['by_rule']:
            self.stats['by_rule'][rule_name] = {'passed': 0, 'failed': 0}

        # Rough estimate: Power should be proportional to work done
        # Work = Force × Distance = Thrust × Penetration
        # Also consider rotational work from torque

        # Convert penetration rate mm/min to m/s
        penetration_m_s = penetration_rate / 60000.0

        # Estimated power from thrust (kW)
        thrust_power = thrust * penetration_m_s

        # Estimated rotational power (assuming typical cutterhead RPM ~2)
        # Power (kW) = Torque (kNm) × Angular velocity (rad/s)
        # RPM = 2, omega = 2 * 2π/60 ≈ 0.21 rad/s
        rotational_power = torque * 0.21

        # Total estimated power
        estimated_power = thrust_power + rotational_power

        # Allow 50-200% efficiency range (accounts for hydraulics, losses, etc.)
        min_expected = estimated_power * 0.5
        max_expected = estimated_power * 2.0

        if power < min_expected * 0.8:  # 20% tolerance
            reason = (f"Power consumption unexpectedly low: "
                     f"{power:.1f} kW (expected {min_expected:.1f}-{max_expected:.1f} kW)")
            logger.warning(reason)
            # Don't fail, just warn (power estimation is rough)

        if power > max_expected * 1.2:  # 20% tolerance
            reason = (f"Power consumption unexpectedly high: "
                     f"{power:.1f} kW (expected {min_expected:.1f}-{max_expected:.1f} kW)")
            self._record_failure(rule_name, reason)
            return False, reason

        self.stats['passed'] += 1
        self.stats['by_rule'][rule_name]['passed'] += 1
        return True, None

    def check_multi_parameter(
        self,
        data: Dict[str, float]
    ) -> Tuple[bool, List[str]]:
        """
        Perform all applicable multi-parameter checks.

        Args:
            data: Dictionary of tag_name -> value

        Returns:
            Tuple of (all_valid, list_of_reasons)
        """
        all_valid = True
        reasons = []

        # Check thrust/penetration ratio
        if 'thrust_total' in data and 'penetration_rate' in data:
            valid, reason = self.check_thrust_penetration_ratio(
                data['thrust_total'],
                data['penetration_rate']
            )
            if not valid:
                all_valid = False
                reasons.append(reason)

        # Check torque/thrust ratio
        if 'cutterhead_torque' in data and 'thrust_total' in data:
            valid, reason = self.check_torque_thrust_ratio(
                data['cutterhead_torque'],
                data['thrust_total']
            )
            if not valid:
                all_valid = False
                reasons.append(reason)

        # Check chamber pressure vs depth
        if 'chamber_pressure' in data and 'excavation_depth' in data:
            valid, reason = self.check_chamber_pressure_depth(
                data['chamber_pressure'],
                data['excavation_depth']
            )
            if not valid:
                all_valid = False
                reasons.append(reason)

        # Check power consumption
        if all(k in data for k in ['power_total', 'thrust_total',
                                     'cutterhead_torque', 'penetration_rate']):
            valid, reason = self.check_power_consumption(
                data['power_total'],
                data['thrust_total'],
                data['cutterhead_torque'],
                data['penetration_rate']
            )
            if not valid:
                all_valid = False
                reasons.append(reason)

        return all_valid, reasons

    def _record_failure(self, rule_name: str, reason: str) -> None:
        """Record a failed validation check"""
        self.stats['failed'] += 1
        self.stats['by_rule'][rule_name]['failed'] += 1
        logger.warning(f"Reasonableness check failed [{rule_name}]: {reason}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get validation statistics.

        Returns:
            Dictionary with check counts and failure rates
        """
        total = self.stats['total_checks']
        if total == 0:
            failure_rate = 0.0
        else:
            failure_rate = (self.stats['failed'] / total) * 100

        return {
            'total_checks': total,
            'passed': self.stats['passed'],
            'failed': self.stats['failed'],
            'failure_rate_percent': round(failure_rate, 2),
            'by_rule': self.stats['by_rule']
        }

    def reset_statistics(self) -> None:
        """Reset validation statistics"""
        self.stats = {
            'total_checks': 0,
            'passed': 0,
            'failed': 0,
            'by_rule': {}
        }


# Example usage
if __name__ == "__main__":
    checker = ReasonablenessChecker()

    # Test case 1: Valid thrust/penetration ratio
    print("Test 1: Thrust/Penetration Ratio")
    valid, reason = checker.check_thrust_penetration_ratio(
        thrust=12000,  # kN
        penetration_rate=15  # mm/min
    )
    print(f"  {'✓ PASS' if valid else '✗ FAIL'}: {reason or 'Valid ratio (800 kN per mm/min)'}\n")

    # Test case 2: Invalid thrust/penetration ratio (too low)
    print("Test 2: Low Thrust for High Penetration")
    valid, reason = checker.check_thrust_penetration_ratio(
        thrust=1000,  # kN (too low)
        penetration_rate=50  # mm/min (high)
    )
    print(f"  {'✓ PASS' if valid else '✗ FAIL'}: {reason or 'Valid'}\n")

    # Test case 3: Valid torque/thrust ratio
    print("Test 3: Torque/Thrust Ratio")
    valid, reason = checker.check_torque_thrust_ratio(
        torque=800,  # kNm
        thrust=10000  # kN
    )
    print(f"  {'✓ PASS' if valid else '✗ FAIL'}: {reason or 'Valid ratio (0.08)'}\n")

    # Test case 4: Valid chamber pressure for depth
    print("Test 4: Chamber Pressure at 15m Depth")
    valid, reason = checker.check_chamber_pressure_depth(
        chamber_pressure=1.5,  # bar
        depth=15  # meters
    )
    print(f"  {'✓ PASS' if valid else '✗ FAIL'}: {reason or 'Valid pressure'}\n")

    # Test case 5: Multi-parameter check
    print("Test 5: Multi-Parameter Check")
    data = {
        'thrust_total': 12000,
        'penetration_rate': 15,
        'cutterhead_torque': 900,
        'chamber_pressure': 1.5,
        'excavation_depth': 15,
        'power_total': 800
    }
    all_valid, reasons = checker.check_multi_parameter(data)
    status = '✓ ALL PASS' if all_valid else '✗ SOME FAILED'
    print(f"  {status}")
    for r in reasons:
        print(f"    - {r}")

    print("\nStatistics:", checker.get_statistics())
