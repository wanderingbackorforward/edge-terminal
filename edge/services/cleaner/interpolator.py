"""
T038: Missing Value Detector and Interpolator
Detects gaps in time-series data and interpolates missing values
Uses linear interpolation for gaps < 5 seconds
"""
import logging
from typing import List, Optional, Tuple
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)


class DataInterpolator:
    """
    Detects and fills missing values in time-series data.

    Features:
    - Gap detection based on expected sampling interval
    - Linear interpolation for small gaps (<5 seconds)
    - Flagging of interpolated values
    - Statistics on interpolation operations
    """

    def __init__(
        self,
        max_gap_seconds: float = 5.0,
        expected_interval: float = 1.0  # seconds, expected sampling rate
    ):
        """
        Initialize interpolator.

        Args:
            max_gap_seconds: Maximum gap duration to fill (seconds)
            expected_interval: Expected sampling interval (seconds)
        """
        self.max_gap_seconds = max_gap_seconds
        self.expected_interval = expected_interval
        self.stats = {
            'gaps_detected': 0,
            'values_interpolated': 0,
            'gaps_too_large': 0
        }

    def detect_gaps(
        self,
        timestamps: List[float],
        tolerance: float = 0.5
    ) -> List[Tuple[int, int]]:
        """
        Detect gaps in time-series based on expected sampling interval.

        Args:
            timestamps: List of Unix timestamps (sorted)
            tolerance: Tolerance factor for gap detection (seconds)

        Returns:
            List of gap indices as (start_idx, end_idx) tuples
        """
        gaps = []

        for i in range(len(timestamps) - 1):
            time_diff = timestamps[i + 1] - timestamps[i]

            # Detect gap if time difference exceeds expected interval + tolerance
            if time_diff > (self.expected_interval + tolerance):
                gaps.append((i, i + 1))
                self.stats['gaps_detected'] += 1

                logger.debug(
                    f"Gap detected at index {i}-{i+1}: "
                    f"{time_diff:.2f}s (expected {self.expected_interval}s)"
                )

        return gaps

    def interpolate_linear(
        self,
        timestamps: List[float],
        values: List[float],
        gaps: List[Tuple[int, int]]
    ) -> Tuple[List[float], List[float], List[str]]:
        """
        Fill gaps using linear interpolation.

        Args:
            timestamps: List of timestamps
            values: List of values (may contain None for missing)
            gaps: List of gap indices

        Returns:
            Tuple of (new_timestamps, new_values, quality_flags)
        """
        result_timestamps = list(timestamps)
        result_values = list(values)
        result_flags = ['raw'] * len(values)

        for gap_start_idx, gap_end_idx in gaps:
            t_start = timestamps[gap_start_idx]
            t_end = timestamps[gap_end_idx]
            gap_duration = t_end - t_start

            # Check if gap is within interpolation limit
            if gap_duration > self.max_gap_seconds:
                self.stats['gaps_too_large'] += 1
                logger.warning(
                    f"Gap too large to interpolate: {gap_duration:.2f}s > {self.max_gap_seconds}s"
                )
                # Insert None placeholder and flag as missing
                result_flags[gap_end_idx] = 'missing'
                continue

            # Get boundary values
            v_start = values[gap_start_idx]
            v_end = values[gap_end_idx]

            if v_start is None or v_end is None:
                logger.warning("Cannot interpolate: boundary values are None")
                continue

            # Calculate number of points to interpolate
            num_points = int(gap_duration / self.expected_interval)

            if num_points < 1:
                continue

            # Generate interpolated timestamps and values
            t_interp = np.linspace(t_start, t_end, num_points + 2)[1:-1]
            v_interp = np.linspace(v_start, v_end, num_points + 2)[1:-1]

            # Insert interpolated points
            insert_idx = gap_end_idx
            for t, v in zip(t_interp, v_interp):
                result_timestamps.insert(insert_idx, float(t))
                result_values.insert(insert_idx, float(v))
                result_flags.insert(insert_idx, 'interpolated')
                insert_idx += 1

            self.stats['values_interpolated'] += len(t_interp)

            logger.info(
                f"Interpolated {len(t_interp)} values for gap "
                f"of {gap_duration:.2f}s"
            )

        return result_timestamps, result_values, result_flags

    def process(
        self,
        timestamps: List[float],
        values: List[float]
    ) -> Tuple[List[float], List[float], List[str]]:
        """
        Detect gaps and interpolate missing values.

        Args:
            timestamps: List of Unix timestamps (must be sorted)
            values: List of sensor values

        Returns:
            Tuple of (timestamps, values, quality_flags)
            - Timestamps may have new entries for interpolated points
            - Values filled with interpolated data
            - Quality flags: 'raw', 'interpolated', or 'missing'
        """
        if len(timestamps) != len(values):
            raise ValueError("Timestamps and values must have same length")

        if len(timestamps) < 2:
            # Not enough data for gap detection
            return timestamps, values, ['raw'] * len(values)

        # Detect gaps
        gaps = self.detect_gaps(timestamps)

        if not gaps:
            # No gaps detected, return original data
            return timestamps, values, ['raw'] * len(values)

        # Interpolate
        return self.interpolate_linear(timestamps, values, gaps)

    def get_statistics(self) -> dict:
        """Get interpolation statistics"""
        return {
            'gaps_detected': self.stats['gaps_detected'],
            'values_interpolated': self.stats['values_interpolated'],
            'gaps_too_large': self.stats['gaps_too_large']
        }

    def reset_statistics(self) -> None:
        """Reset statistics"""
        self.stats = {
            'gaps_detected': 0,
            'values_interpolated': 0,
            'gaps_too_large': 0
        }


# Example usage
if __name__ == "__main__":
    interpolator = DataInterpolator(max_gap_seconds=5.0, expected_interval=1.0)

    # Simulated time-series with gaps
    timestamps = [
        1000.0,  # 0
        1001.0,  # 1
        1002.0,  # 2
        # Gap of 3 seconds (2 missing points)
        1005.0,  # 3
        1006.0,  # 4
        # Gap of 10 seconds (too large)
        1016.0,  # 5
        1017.0,  # 6
    ]

    values = [
        10.0,
        12.0,
        14.0,
        20.0,
        22.0,
        30.0,
        32.0,
    ]

    result_timestamps, result_values, result_flags = interpolator.process(
        timestamps, values
    )

    print("Original data points:", len(timestamps))
    print("Result data points:", len(result_timestamps))
    print("\nInterpolation statistics:", interpolator.get_statistics())

    print("\nResult:")
    for t, v, flag in zip(result_timestamps, result_values, result_flags):
        marker = "●" if flag == 'raw' else ("○" if flag == 'interpolated' else "✗")
        print(f"{marker} t={t:.1f}, v={v:.2f}, flag={flag}")
