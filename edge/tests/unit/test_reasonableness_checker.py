"""
Unit tests for ReasonablenessChecker
Tests physics-based validation of sensor relationships
"""
import pytest
from edge.services.cleaner.reasonableness_checker import ReasonablenessChecker


class TestReasonablenessChecker:
    """Test cases for ReasonablenessChecker"""

    @pytest.fixture
    def checker(self):
        """Create checker instance"""
        return ReasonablenessChecker()

    def test_check_thrust_penetration_ratio_valid(self, checker):
        """Test valid thrust/penetration ratio"""
        is_valid, reason = checker.check_thrust_penetration_ratio(
            thrust=12000.0,  # kN
            penetration_rate=50.0  # mm/min
        )

        assert is_valid is True
        assert reason is None

    def test_check_thrust_penetration_ratio_too_high(self, checker):
        """Test thrust/penetration ratio too high (excessive thrust)"""
        is_valid, reason = checker.check_thrust_penetration_ratio(
            thrust=30000.0,  # Very high thrust
            penetration_rate=10.0  # Low penetration
        )

        assert is_valid is False
        assert "ratio" in reason.lower()

    def test_check_thrust_penetration_ratio_too_low(self, checker):
        """Test thrust/penetration ratio too low (insufficient thrust)"""
        is_valid, reason = checker.check_thrust_penetration_ratio(
            thrust=5000.0,  # Low thrust
            penetration_rate=100.0  # High penetration (unrealistic)
        )

        assert is_valid is False
        assert "ratio" in reason.lower()

    def test_check_chamber_pressure_depth_valid(self, checker):
        """Test valid chamber pressure for depth"""
        is_valid, reason = checker.check_chamber_pressure_depth(
            chamber_pressure=2.5,  # bar
            depth=20.0  # meters
        )

        assert is_valid is True
        assert reason is None

    def test_check_chamber_pressure_depth_too_low(self, checker):
        """Test chamber pressure too low for depth"""
        is_valid, reason = checker.check_chamber_pressure_depth(
            chamber_pressure=0.5,  # Too low
            depth=20.0
        )

        assert is_valid is False
        assert "pressure" in reason.lower()

    def test_check_chamber_pressure_depth_too_high(self, checker):
        """Test chamber pressure too high for depth"""
        is_valid, reason = checker.check_chamber_pressure_depth(
            chamber_pressure=8.0,  # Too high
            depth=20.0
        )

        assert is_valid is False
        assert "pressure" in reason.lower()

    def test_check_torque_speed_relationship_valid(self, checker):
        """Test valid torque-speed relationship"""
        is_valid, reason = checker.check_torque_speed_relationship(
            torque=900.0,  # kNm
            speed=3.0,  # rpm
            power=300.0  # kW
        )

        assert is_valid is True
        assert reason is None

    def test_check_torque_speed_power_mismatch(self, checker):
        """Test power doesn't match torque*speed"""
        is_valid, reason = checker.check_torque_speed_relationship(
            torque=900.0,
            speed=3.0,
            power=100.0  # Should be ~283 kW, this is too low
        )

        assert is_valid is False
        assert "power" in reason.lower()

    def test_check_slurry_balance_valid(self, checker):
        """Test valid slurry flow balance"""
        is_valid, reason = checker.check_slurry_balance(
            flow_in=150.0,  # m3/h
            flow_out=148.0  # m3/h (2% loss is acceptable)
        )

        assert is_valid is True
        assert reason is None

    def test_check_slurry_balance_excessive_loss(self, checker):
        """Test excessive slurry flow loss"""
        is_valid, reason = checker.check_slurry_balance(
            flow_in=150.0,
            flow_out=130.0  # 13% loss is too high
        )

        assert is_valid is False
        assert "imbalance" in reason.lower()

    def test_check_slurry_balance_negative_loss(self, checker):
        """Test negative slurry loss (impossible)"""
        is_valid, reason = checker.check_slurry_balance(
            flow_in=150.0,
            flow_out=160.0  # More out than in (impossible)
        )

        assert is_valid is False
        assert "imbalance" in reason.lower()

    def test_check_grout_volume_valid(self, checker):
        """Test valid grout volume for ring"""
        is_valid, reason = checker.check_grout_volume(
            grout_volume=15.0,  # m3
            ring_length=1.5,  # m
            shield_diameter=6.0  # m
        )

        assert is_valid is True
        assert reason is None

    def test_check_grout_volume_too_low(self, checker):
        """Test grout volume too low"""
        is_valid, reason = checker.check_grout_volume(
            grout_volume=5.0,  # Too low
            ring_length=1.5,
            shield_diameter=6.0
        )

        assert is_valid is False
        assert "volume" in reason.lower()

    def test_check_grout_volume_too_high(self, checker):
        """Test grout volume too high"""
        is_valid, reason = checker.check_grout_volume(
            grout_volume=50.0,  # Excessively high
            ring_length=1.5,
            shield_diameter=6.0
        )

        assert is_valid is False
        assert "volume" in reason.lower()

    def test_check_settlement_gradient_valid(self, checker):
        """Test valid settlement gradient"""
        is_valid, reason = checker.check_settlement_gradient(
            settlement_values=[0.0, -2.0, -5.0, -8.0, -10.0],
            distances=[0, 5, 10, 15, 20]  # meters
        )

        assert is_valid is True
        assert reason is None

    def test_check_settlement_gradient_too_steep(self, checker):
        """Test settlement gradient too steep"""
        is_valid, reason = checker.check_settlement_gradient(
            settlement_values=[0.0, -2.0, -20.0, -8.0, -10.0],  # Sudden drop
            distances=[0, 5, 10, 15, 20]
        )

        assert is_valid is False
        assert "gradient" in reason.lower()

    def test_batch_check_valid(self, checker):
        """Test batch checking of all rules"""
        data = {
            'thrust_total': 12000.0,
            'penetration_rate': 50.0,
            'chamber_pressure': 2.5,
            'excavation_depth': 20.0,
            'torque': 900.0,
            'cutterhead_speed': 3.0,
            'cutterhead_power': 300.0
        }

        results = checker.batch_check(data)

        assert 'thrust_penetration' in results
        assert results['thrust_penetration']['valid'] is True

    def test_batch_check_with_failures(self, checker):
        """Test batch checking with some failures"""
        data = {
            'thrust_total': 30000.0,  # Too high
            'penetration_rate': 10.0,
            'chamber_pressure': 0.5,  # Too low for depth
            'excavation_depth': 20.0
        }

        results = checker.batch_check(data)

        # Should have at least one failure
        failures = [r for r in results.values() if not r['valid']]
        assert len(failures) > 0

    def test_get_statistics(self, checker):
        """Test statistics tracking"""
        # Perform some checks
        checker.check_thrust_penetration_ratio(12000.0, 50.0)
        checker.check_thrust_penetration_ratio(30000.0, 10.0)  # Fail
        checker.check_chamber_pressure_depth(2.5, 20.0)

        stats = checker.get_statistics()

        assert stats['total_checks'] == 3
        assert stats['passed_checks'] == 2
        assert stats['failed_checks'] == 1

    def test_reset_statistics(self, checker):
        """Test statistics reset"""
        checker.check_thrust_penetration_ratio(12000.0, 50.0)
        checker.reset_statistics()

        stats = checker.get_statistics()
        assert stats['total_checks'] == 0

    def test_check_with_missing_data(self, checker):
        """Test handling of None values"""
        is_valid, reason = checker.check_thrust_penetration_ratio(
            thrust=None,
            penetration_rate=50.0
        )

        # Should handle gracefully (return True with warning or skip)
        assert isinstance(is_valid, bool)

    def test_check_with_zero_values(self, checker):
        """Test handling of zero values"""
        is_valid, reason = checker.check_thrust_penetration_ratio(
            thrust=0.0,
            penetration_rate=0.0
        )

        # Zero penetration rate should be invalid or cause division error
        assert isinstance(is_valid, bool)

    def test_multiple_sensor_correlation(self, checker):
        """Test checking correlation between multiple sensors"""
        # This tests a more complex scenario
        data = {
            'thrust_total': 15000.0,
            'penetration_rate': 60.0,
            'chamber_pressure': 3.0,
            'excavation_depth': 25.0,
            'torque': 1000.0,
            'cutterhead_speed': 3.5,
            'cutterhead_power': 350.0,
            'slurry_flow_in': 180.0,
            'slurry_flow_out': 176.0
        }

        results = checker.batch_check(data)

        # All checks should pass for reasonable values
        all_valid = all(r['valid'] for r in results.values())
        assert all_valid is True
