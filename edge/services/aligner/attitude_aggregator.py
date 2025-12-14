"""
T045: Attitude Data Aggregator (Modular)
Aggregates shield guidance/attitude data for ring-level analysis
Processes pitch, roll, yaw, and deviation measurements
"""
import logging
from typing import Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)


class AttitudeAggregator:
    """
    Aggregates attitude/guidance system data for a ring.

    Features:
    - Circular mean for angular data (pitch, roll, yaw)
    - Linear statistics for deviations
    - Trajectory assessment
    - Deviation trend analysis
    """

    def __init__(self):
        """Initialize attitude aggregator"""
        self.stats = {
            'rings_processed': 0,
            'total_readings': 0
        }

    def aggregate_ring_data(
        self,
        db,
        ring_number: int,
        start_time: float,
        end_time: float
    ) -> Dict[str, Any]:
        """
        Aggregate attitude data for a specific ring.

        Args:
            db: Database manager
            ring_number: Ring number
            start_time: Ring start timestamp
            end_time: Ring end timestamp

        Returns:
            Dictionary with aggregated attitude features
        """
        try:
            with db.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT
                        pitch, roll, yaw,
                        horizontal_deviation, vertical_deviation, axis_deviation
                    FROM attitude_logs
                    WHERE timestamp >= ?
                      AND timestamp <= ?
                    ORDER BY timestamp
                    """,
                    (start_time, end_time)
                )

                rows = cursor.fetchall()

                if not rows:
                    logger.warning(
                        f"No attitude data found for ring {ring_number}"
                    )
                    return {}

                # Extract data
                pitch_values = [row['pitch'] for row in rows if row['pitch'] is not None]
                roll_values = [row['roll'] for row in rows if row['roll'] is not None]
                yaw_values = [row['yaw'] for row in rows if row['yaw'] is not None]

                h_dev_values = [row['horizontal_deviation'] for row in rows
                               if row['horizontal_deviation'] is not None]
                v_dev_values = [row['vertical_deviation'] for row in rows
                               if row['vertical_deviation'] is not None]
                axis_dev_values = [row['axis_deviation'] for row in rows
                                  if row['axis_deviation'] is not None]

                # Calculate aggregations
                features = {}

                # Angular data (use circular mean)
                if pitch_values:
                    features.update(self._aggregate_angular('pitch', pitch_values))

                if roll_values:
                    features.update(self._aggregate_angular('roll', roll_values))

                if yaw_values:
                    features.update(self._aggregate_angular('yaw', yaw_values))

                # Deviation data (linear statistics)
                if h_dev_values:
                    features.update(
                        self._aggregate_linear('horizontal_deviation', h_dev_values)
                    )

                if v_dev_values:
                    features.update(
                        self._aggregate_linear('vertical_deviation', v_dev_values)
                    )

                if axis_dev_values:
                    features.update(
                        self._aggregate_linear('axis_deviation', axis_dev_values)
                    )

                self.stats['rings_processed'] += 1
                self.stats['total_readings'] += len(rows)

                logger.info(
                    f"Aggregated attitude data for ring {ring_number}: "
                    f"{len(rows)} readings, {len(features)} features"
                )

                return features

        except Exception as e:
            logger.error(f"Error aggregating attitude data for ring {ring_number}: {e}")
            raise

    def _aggregate_angular(
        self,
        name: str,
        values: list
    ) -> Dict[str, float]:
        """
        Aggregate angular data using circular statistics.

        For angles, we need circular mean to handle wraparound correctly.
        E.g., mean of [359°, 1°] should be 0°, not 180°.

        Args:
            name: Parameter name (pitch, roll, yaw)
            values: List of angle values in degrees

        Returns:
            Dictionary with circular mean and linear std
        """
        if not values:
            return {}

        try:
            values_array = np.array(values)

            # Convert degrees to radians
            radians = np.deg2rad(values_array)

            # Circular mean
            sin_mean = np.mean(np.sin(radians))
            cos_mean = np.mean(np.cos(radians))
            circular_mean = np.arctan2(sin_mean, cos_mean)
            circular_mean_deg = np.rad2deg(circular_mean)

            # For std, use linear approximation (valid for small variations)
            # Full circular std is more complex
            linear_std = float(np.std(values_array))

            return {
                f'mean_{name}': float(circular_mean_deg),
                f'std_{name}': linear_std,
                f'max_{name}': float(np.max(values_array)),
                f'min_{name}': float(np.min(values_array))
            }

        except Exception as e:
            logger.error(f"Error calculating circular statistics for {name}: {e}")
            return {}

    def _aggregate_linear(
        self,
        name: str,
        values: list
    ) -> Dict[str, float]:
        """
        Aggregate linear data (deviations).

        Args:
            name: Parameter name
            values: List of values

        Returns:
            Dictionary with mean, max, min, std
        """
        if not values:
            return {}

        try:
            values_array = np.array(values)

            # Remove NaN/inf
            values_array = values_array[np.isfinite(values_array)]

            if len(values_array) == 0:
                return {}

            return {
                f'mean_{name}': float(np.mean(values_array)),
                f'max_{name}': float(np.max(values_array)),
                f'min_{name}': float(np.min(values_array)),
                f'std_{name}': float(np.std(values_array))
            }

        except Exception as e:
            logger.error(f"Error calculating linear statistics for {name}: {e}")
            return {}

    def calculate_trajectory_quality(
        self,
        db,
        ring_number: int,
        start_time: float,
        end_time: float,
        tolerance_mm: float = 50.0
    ) -> Dict[str, Any]:
        """
        Assess trajectory quality for the ring.

        Checks if shield stayed within tolerance during construction.

        Args:
            db: Database manager
            ring_number: Ring number
            start_time: Start timestamp
            end_time: End timestamp
            tolerance_mm: Allowable deviation (mm)

        Returns:
            Dictionary with trajectory quality metrics
        """
        try:
            with db.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT
                        horizontal_deviation, vertical_deviation, axis_deviation
                    FROM attitude_logs
                    WHERE timestamp >= ?
                      AND timestamp <= ?
                    """,
                    (start_time, end_time)
                )

                rows = cursor.fetchall()

                if not rows:
                    return {
                        'quality': 'unknown',
                        'samples': 0
                    }

                # Check how many samples exceed tolerance
                total_samples = len(rows)
                out_of_tolerance = 0

                for row in rows:
                    h_dev = row['horizontal_deviation'] or 0
                    v_dev = row['vertical_deviation'] or 0
                    axis_dev = row['axis_deviation'] or 0

                    # Total deviation (Euclidean distance)
                    total_dev = np.sqrt(h_dev**2 + v_dev**2 + axis_dev**2)

                    if total_dev > tolerance_mm:
                        out_of_tolerance += 1

                # Calculate metrics
                within_tolerance_pct = ((total_samples - out_of_tolerance) / total_samples) * 100

                # Assess quality
                if within_tolerance_pct >= 95:
                    quality = 'excellent'
                elif within_tolerance_pct >= 90:
                    quality = 'good'
                elif within_tolerance_pct >= 80:
                    quality = 'acceptable'
                else:
                    quality = 'poor'

                return {
                    'quality': quality,
                    'samples': total_samples,
                    'out_of_tolerance': out_of_tolerance,
                    'within_tolerance_percent': round(within_tolerance_pct, 2),
                    'tolerance_mm': tolerance_mm
                }

        except Exception as e:
            logger.error(f"Error calculating trajectory quality: {e}")
            return {
                'quality': 'unknown',
                'samples': 0,
                'error': str(e)
            }

    def calculate_deviation_trend(
        self,
        db,
        ring_number: int,
        start_time: float,
        end_time: float
    ) -> Dict[str, str]:
        """
        Analyze deviation trend during ring construction.

        Determines if deviations are increasing, decreasing, or stable.

        Args:
            db: Database manager
            ring_number: Ring number
            start_time: Start timestamp
            end_time: End timestamp

        Returns:
            Dictionary with trend analysis
        """
        try:
            with db.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT
                        timestamp,
                        horizontal_deviation, vertical_deviation
                    FROM attitude_logs
                    WHERE timestamp >= ?
                      AND timestamp <= ?
                    ORDER BY timestamp
                    """,
                    (start_time, end_time)
                )

                rows = cursor.fetchall()

                if len(rows) < 10:
                    return {
                        'horizontal_trend': 'insufficient_data',
                        'vertical_trend': 'insufficient_data'
                    }

                # Extract data
                h_devs = [row['horizontal_deviation'] for row in rows
                         if row['horizontal_deviation'] is not None]
                v_devs = [row['vertical_deviation'] for row in rows
                         if row['vertical_deviation'] is not None]

                # Calculate trends using simple linear regression slope
                h_trend = self._calculate_trend(h_devs)
                v_trend = self._calculate_trend(v_devs)

                return {
                    'horizontal_trend': h_trend,
                    'vertical_trend': v_trend
                }

        except Exception as e:
            logger.error(f"Error calculating deviation trend: {e}")
            return {
                'horizontal_trend': 'error',
                'vertical_trend': 'error'
            }

    def _calculate_trend(self, values: list) -> str:
        """
        Calculate trend direction from time series.

        Args:
            values: Time series data

        Returns:
            Trend: 'increasing', 'decreasing', 'stable'
        """
        if len(values) < 2:
            return 'insufficient_data'

        try:
            # Simple linear regression
            x = np.arange(len(values))
            y = np.array(values)

            # Calculate slope
            slope = np.polyfit(x, y, 1)[0]

            # Threshold for "stable" (< 0.1 mm per sample)
            if abs(slope) < 0.1:
                return 'stable'
            elif slope > 0:
                return 'increasing'
            else:
                return 'decreasing'

        except Exception as e:
            logger.error(f"Error calculating trend: {e}")
            return 'error'

    def get_statistics(self) -> Dict[str, Any]:
        """Get aggregator statistics"""
        return {
            'rings_processed': self.stats['rings_processed'],
            'total_readings': self.stats['total_readings']
        }


# Example usage
if __name__ == "__main__":
    import sys
    sys.path.append('/home/monss/tunnel-su-1/shield-tunneling-icp')

    from edge.database.manager import DatabaseManager
    from datetime import datetime

    db = DatabaseManager("data/edge.db")
    aggregator = AttitudeAggregator()

    # Example: Aggregate ring 100
    ring_number = 100
    start_time = datetime(2025, 11, 19, 10, 0).timestamp()
    end_time = datetime(2025, 11, 19, 10, 45).timestamp()

    # Aggregate attitude data
    features = aggregator.aggregate_ring_data(
        db, ring_number, start_time, end_time
    )

    print(f"Attitude features for ring {ring_number}:")
    for key, value in features.items():
        print(f"  {key}: {value:.2f}")

    # Check trajectory quality
    quality = aggregator.calculate_trajectory_quality(
        db, ring_number, start_time, end_time, tolerance_mm=50.0
    )
    print(f"\nTrajectory quality: {quality['quality']}")
    print(f"Within tolerance: {quality.get('within_tolerance_percent', 0):.1f}%")

    # Analyze deviation trend
    trend = aggregator.calculate_deviation_trend(
        db, ring_number, start_time, end_time
    )
    print(f"\nDeviation trends:")
    print(f"  Horizontal: {trend['horizontal_trend']}")
    print(f"  Vertical: {trend['vertical_trend']}")

    print(f"\nAggregator statistics: {aggregator.get_statistics()}")
