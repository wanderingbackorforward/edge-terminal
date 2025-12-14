"""
T132: Performance tests for warning generation latency
Target: <10ms from data arrival to warning generation
"""
import pytest
import time
from unittest.mock import Mock

from edge.services.warning.warning_engine import WarningEngine
from edge.models.warning_threshold import WarningThreshold


@pytest.fixture
def perf_thresholds():
    """Threshold configurations for performance testing"""
    thresholds = {}
    for indicator in ["settlement_value", "mean_thrust", "mean_torque", "mean_chamber_pressure"]:
        thresholds[f"{indicator}_all"] = WarningThreshold(
            threshold_id=f"perf-{indicator}",
            indicator_name=indicator,
            geological_zone="all",
            warning_upper=30.0,
            alarm_upper=40.0,
            enabled=True
        )
    return thresholds


@pytest.fixture
def perf_engine(perf_thresholds):
    mock_session = Mock()
    mock_session.add = Mock()
    mock_session.commit = Mock()
    
    # Mock for rate/predictive queries (return empty to skip)
    mock_query = Mock()
    mock_query.filter = Mock(return_value=mock_query)
    mock_query.order_by = Mock(return_value=mock_query)
    mock_query.limit = Mock(return_value=mock_query)
    mock_query.all = Mock(return_value=[])
    mock_query.first = Mock(return_value=None)
    mock_session.query = Mock(return_value=mock_query)
    
    return WarningEngine(mock_session, perf_thresholds)


class TestWarningLatency:
    """Performance tests for warning latency"""

    @pytest.mark.performance
    def test_single_threshold_check_latency(self, perf_engine):
        """Test latency for single threshold check"""
        indicators = {"settlement_value": 35.0}

        start = time.perf_counter()
        warnings = perf_engine.evaluate_ring(
            ring_number=100,
            indicators=indicators,
            geological_zone="all"
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 10.0, f"Threshold check took {elapsed_ms:.2f}ms (target: <10ms)"
        assert len(warnings) > 0

    @pytest.mark.performance
    def test_multiple_indicators_latency(self, perf_engine):
        """Test latency for multiple indicators (typical scenario)"""
        indicators = {
            "settlement_value": 35.0,
            "mean_thrust": 32000.0,
            "mean_torque": 1900.0,
            "mean_chamber_pressure": 3.8,
        }

        start = time.perf_counter()
        warnings = perf_engine.evaluate_ring(
            ring_number=100,
            indicators=indicators,
            geological_zone="all"
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 10.0, f"Multi-indicator check took {elapsed_ms:.2f}ms (target: <10ms)"

    @pytest.mark.performance
    @pytest.mark.slow
    def test_100_consecutive_evaluations(self, perf_engine):
        """Test sustained performance over 100 rings"""
        indicators = {"settlement_value": 35.0}
        latencies = []

        for ring in range(100, 200):
            start = time.perf_counter()
            perf_engine.evaluate_ring(ring, indicators, "all")
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]

        print(f"\nPerformance stats over 100 evaluations:")
        print(f"  Average: {avg_latency:.2f}ms")
        print(f"  P95: {p95_latency:.2f}ms")
        print(f"  Max: {max_latency:.2f}ms")

        assert avg_latency < 10.0, f"Average latency {avg_latency:.2f}ms exceeds target"
        assert p95_latency < 15.0, f"P95 latency {p95_latency:.2f}ms too high"

    @pytest.mark.performance
    def test_hysteresis_overhead(self, perf_engine):
        """Test that hysteresis doesn't add significant overhead"""
        indicators = {"settlement_value": 31.0}

        # First evaluation (populate hysteresis state)
        perf_engine.evaluate_ring(100, indicators, "all")

        # Subsequent evaluations (with hysteresis check)
        latencies = []
        for ring in range(101, 111):
            indicators["settlement_value"] += 0.1  # Small incremental change
            start = time.perf_counter()
            perf_engine.evaluate_ring(ring, indicators, "all")
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

        avg_with_hysteresis = sum(latencies) / len(latencies)
        assert avg_with_hysteresis < 10.0, \
            f"Hysteresis overhead too high: {avg_with_hysteresis:.2f}ms"

    @pytest.mark.performance
    def test_combined_warning_overhead(self, perf_engine):
        """Test overhead of combined warning aggregation"""
        # Multiple simultaneous warnings
        indicators = {
            "settlement_value": 45.0,
            "mean_thrust": 36000.0,
            "mean_torque": 2100.0,
            "mean_chamber_pressure": 4.2,
        }

        start = time.perf_counter()
        warnings = perf_engine.evaluate_ring(100, indicators, "all")
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Even with combined warning generation, should stay under target
        assert elapsed_ms < 15.0, \
            f"Combined warning generation took {elapsed_ms:.2f}ms (target: <15ms)"

        combined = [w for w in warnings if w.warning_type == "combined"]
        assert len(combined) > 0  # Verify combined warning was created
