"""
T021: Unit tests for threshold validator
Tests data validation against engineering limits
"""
import pytest
import tempfile
import yaml
from edge.services.cleaner.threshold_validator import ThresholdValidator


class TestThresholdValidator:
    """Test cases for ThresholdValidator"""

    @pytest.fixture
    def validator(self):
        """Create validator with test configuration"""
        # Create temporary config file
        config = {
            'thresholds': {
                'thrust_total': {
                    'min': 0,
                    'max': 50000,
                    'unit': 'kN'
                },
                'chamber_pressure': {
                    'min': 0,
                    'max': 10,
                    'unit': 'bar'
                },
                'penetration_rate': {
                    'min': 0,
                    'max': 100,
                    'unit': 'mm/min'
                }
            }
        }

        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            config_path = f.name

        return ThresholdValidator(config_path)

    def test_valid_value(self, validator):
        """Test validation of valid value"""
        is_valid, reason = validator.validate('thrust_total', 12000)
        assert is_valid is True
        assert reason is None

    def test_value_below_minimum(self, validator):
        """Test validation of value below minimum"""
        is_valid, reason = validator.validate('thrust_total', -100)
        assert is_valid is False
        assert 'Below minimum' in reason

    def test_value_above_maximum(self, validator):
        """Test validation of value above maximum"""
        is_valid, reason = validator.validate('chamber_pressure', 15)
        assert is_valid is False
        assert 'Above maximum' in reason

    def test_null_value(self, validator):
        """Test validation of null value"""
        is_valid, reason = validator.validate('thrust_total', None)
        assert is_valid is False
        assert 'Null value' in reason

    def test_non_numeric_value(self, validator):
        """Test validation of non-numeric value"""
        is_valid, reason = validator.validate('thrust_total', 'invalid')
        assert is_valid is False
        assert 'Non-numeric' in reason

    def test_unconfigured_tag(self, validator):
        """Test validation of tag without threshold config"""
        is_valid, reason = validator.validate('unknown_tag', 100)
        assert is_valid is True
        assert reason is None

    def test_edge_values(self, validator):
        """Test validation at boundary values"""
        # Minimum boundary
        is_valid, _ = validator.validate('thrust_total', 0)
        assert is_valid is True

        # Maximum boundary
        is_valid, _ = validator.validate('thrust_total', 50000)
        assert is_valid is True

    def test_statistics(self, validator):
        """Test statistics tracking"""
        # Perform some validations
        validator.validate('thrust_total', 12000)
        validator.validate('thrust_total', -100)
        validator.validate('chamber_pressure', 5)

        stats = validator.get_statistics()

        assert stats['total_validated'] == 3
        assert stats['passed'] == 2
        assert stats['rejected'] == 1
        assert 'thrust_total' in stats['by_tag']

    def test_reset_statistics(self, validator):
        """Test statistics reset"""
        validator.validate('thrust_total', 12000)
        validator.reset_statistics()

        stats = validator.get_statistics()
        assert stats['total_validated'] == 0
        assert stats['passed'] == 0
        assert stats['rejected'] == 0
