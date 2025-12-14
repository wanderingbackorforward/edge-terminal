"""
T022: Unit tests for PLC aggregator
Tests aggregation of high-frequency PLC data
"""
import pytest
from unittest.mock import MagicMock, Mock
from edge.services.aligner.plc_aggregator import PLCAggregator


class TestPLCAggregator:
    """Test cases for PLCAggregator"""

    @pytest.fixture
    def aggregator(self):
        """Create aggregator instance"""
        return PLCAggregator()

    @pytest.fixture
    def mock_db(self):
        """Create mock database"""
        db = MagicMock()

        # Mock connection context manager
        mock_conn = MagicMock()

        # Mock cursor with sample data
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'tag_name': 'thrust_total', 'value': 12000.0, 'data_quality_flag': 'raw'},
            {'tag_name': 'thrust_total', 'value': 12500.0, 'data_quality_flag': 'raw'},
            {'tag_name': 'thrust_total', 'value': 13000.0, 'data_quality_flag': 'raw'},
            {'tag_name': 'torque', 'value': 900.0, 'data_quality_flag': 'raw'},
            {'tag_name': 'torque', 'value': 950.0, 'data_quality_flag': 'raw'},
        ]

        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        db.get_connection.return_value = mock_conn

        return db

    def test_aggregate_ring_data(self, aggregator, mock_db):
        """Test basic aggregation"""
        ring_number = 100
        start_time = 1000.0
        end_time = 2000.0

        result = aggregator.aggregate_ring_data(
            mock_db, ring_number, start_time, end_time
        )

        # Should have aggregated features
        assert 'mean_thrust_total' in result
        assert 'max_thrust_total' in result
        assert 'min_thrust_total' in result
        assert 'std_thrust_total' in result

    def test_calculate_statistics(self, aggregator):
        """Test statistical calculation"""
        values = [10.0, 12.0, 14.0, 16.0, 18.0]

        stats = aggregator._calculate_statistics('test_tag', values)

        assert 'mean_test_tag' in stats
        assert stats['mean_test_tag'] == 14.0  # Mean of values
        assert stats['max_test_tag'] == 18.0
        assert stats['min_test_tag'] == 10.0
        assert 'std_test_tag' in stats

    def test_empty_data(self, aggregator):
        """Test handling of empty data"""
        mock_db = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_db.get_connection.return_value = mock_conn

        result = aggregator.aggregate_ring_data(mock_db, 100, 1000.0, 2000.0)

        assert result == {}

    def test_data_quality_filtering(self, aggregator):
        """Test filtering of rejected/missing data"""
        mock_db = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Include rejected data
        mock_cursor.fetchall.return_value = [
            {'tag_name': 'thrust', 'value': 12000.0, 'data_quality_flag': 'raw'},
            {'tag_name': 'thrust', 'value': 99999.0, 'data_quality_flag': 'rejected'},
            {'tag_name': 'thrust', 'value': 13000.0, 'data_quality_flag': 'raw'},
        ]

        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_db.get_connection.return_value = mock_conn

        result = aggregator.aggregate_ring_data(mock_db, 100, 1000.0, 2000.0)

        # Rejected value should be filtered out
        # Mean should be (12000 + 13000) / 2 = 12500
        assert result['mean_thrust'] == 12500.0

    def test_statistics_tracking(self, aggregator, mock_db):
        """Test aggregator statistics"""
        aggregator.aggregate_ring_data(mock_db, 100, 1000.0, 2000.0)

        stats = aggregator.get_statistics()

        assert stats['rings_processed'] == 1
        assert stats['total_readings'] > 0
        assert stats['unique_tags'] > 0

    def test_specific_tag_aggregation(self, aggregator, mock_db):
        """Test aggregation of specific tags"""
        tag_mapping = {
            'thrust_total': 'thrust',
            'torque': 'torque'
        }

        result = aggregator.aggregate_specific_tags(
            mock_db, 100, 1000.0, 2000.0, tag_mapping
        )

        # Should have renamed features
        assert 'mean_thrust' in result
        assert 'mean_torque' in result
        assert 'mean_thrust_total' not in result  # Original name

    def test_nan_handling(self, aggregator):
        """Test handling of NaN values"""
        import numpy as np

        values = [10.0, np.nan, 12.0, np.inf, 14.0]

        stats = aggregator._calculate_statistics('test', values)

        # Should filter out NaN/inf and calculate on valid values only
        assert 'mean_test' in stats
        assert stats['mean_test'] == 12.0  # Mean of 10, 12, 14
