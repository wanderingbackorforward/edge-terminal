"""
T047: Time-Lag Settlement Associator
Associates settlement monitoring data with rings using time lag
Accounts for 6-8 hour delay between excavation and settlement
"""
import logging
from typing import Dict, Any, Optional, List
import numpy as np

logger = logging.getLogger(__name__)


class SettlementAssociator:
    """
    Associates time-lagged settlement data with construction rings.

    Features:
    - Configurable time lag windows
    - Multiple sensor aggregation
    - Spatial proximity weighting
    - Statistical aggregation of settlement readings
    """

    def __init__(
        self,
        min_lag_hours: float = 6.0,
        max_lag_hours: float = 8.0
    ):
        """
        Initialize settlement associator.

        Args:
            min_lag_hours: Minimum lag time (hours) after ring completion
            max_lag_hours: Maximum lag time (hours) after ring completion
        """
        self.min_lag_seconds = min_lag_hours * 3600
        self.max_lag_seconds = max_lag_hours * 3600

        self.stats = {
            'rings_processed': 0,
            'total_sensors_read': 0,
            'associations_found': 0,
            'associations_not_found': 0
        }

    def associate_settlement_data(
        self,
        db,
        ring_number: int,
        ring_end_time: float,
        sensor_type: str = 'surface_settlement',
        sensor_locations: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Associate settlement data with a ring using time lag.

        Args:
            db: Database manager
            ring_number: Ring number
            ring_end_time: Ring construction end time
            sensor_type: Type of monitoring sensor
            sensor_locations: Optional list of specific sensor locations to query

        Returns:
            Dictionary with settlement features
        """
        try:
            # Calculate lag window
            lag_start = ring_end_time + self.min_lag_seconds
            lag_end = ring_end_time + self.max_lag_seconds

            logger.debug(
                f"Querying settlement for ring {ring_number}: "
                f"lag window {self.min_lag_seconds/3600:.1f}-{self.max_lag_seconds/3600:.1f}h"
            )

            with db.get_connection() as conn:
                # Build query
                if sensor_locations:
                    placeholders = ','.join(['?' for _ in sensor_locations])
                    location_filter = f"AND sensor_location IN ({placeholders})"
                    query_params = [sensor_type, lag_start, lag_end] + sensor_locations
                else:
                    location_filter = ""
                    query_params = [sensor_type, lag_start, lag_end]

                # Query settlement data in lag window
                cursor = conn.execute(
                    f"""
                    SELECT
                        value, sensor_location, timestamp
                    FROM monitoring_logs
                    WHERE sensor_type = ?
                      AND timestamp >= ?
                      AND timestamp <= ?
                      {location_filter}
                    ORDER BY timestamp
                    """,
                    query_params
                )

                rows = cursor.fetchall()

                if not rows:
                    logger.warning(
                        f"No settlement data found for ring {ring_number} "
                        f"in lag window"
                    )
                    self.stats['associations_not_found'] += 1
                    return {}

                # Extract settlement values
                values = [row['value'] for row in rows if row['value'] is not None]

                if not values:
                    self.stats['associations_not_found'] += 1
                    return {}

                # Aggregate settlement data
                features = self._aggregate_settlement(values)

                # Add metadata
                features['settlement_sensor_count'] = len(set(
                    row['sensor_location'] for row in rows if row['sensor_location']
                ))
                features['settlement_reading_count'] = len(values)

                self.stats['rings_processed'] += 1
                self.stats['total_sensors_read'] += len(rows)
                self.stats['associations_found'] += 1

                logger.info(
                    f"Associated settlement for ring {ring_number}: "
                    f"{len(values)} readings from {features['settlement_sensor_count']} sensors"
                )

                return features

        except Exception as e:
            logger.error(f"Error associating settlement for ring {ring_number}: {e}")
            raise

    def _aggregate_settlement(self, values: List[float]) -> Dict[str, float]:
        """
        Aggregate settlement values.

        Args:
            values: List of settlement readings (mm, negative = settlement)

        Returns:
            Dictionary with aggregated settlement features
        """
        if not values:
            return {}

        try:
            values_array = np.array(values)

            # Remove NaN/inf
            values_array = values_array[np.isfinite(values_array)]

            if len(values_array) == 0:
                return {}

            # Calculate statistics
            features = {
                'settlement_value': float(np.mean(values_array)),  # Primary feature
                'settlement_max': float(np.max(values_array)),
                'settlement_min': float(np.min(values_array)),
                'settlement_std': float(np.std(values_array))
            }

            # Additional metrics
            if len(values_array) > 1:
                features['settlement_median'] = float(np.median(values_array))

            return features

        except Exception as e:
            logger.error(f"Error aggregating settlement: {e}")
            return {}

    def associate_multiple_sensor_types(
        self,
        db,
        ring_number: int,
        ring_end_time: float,
        sensor_configs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Associate multiple types of monitoring sensors.

        Args:
            db: Database manager
            ring_number: Ring number
            ring_end_time: Ring end time
            sensor_configs: List of sensor configurations
                           Each: {'type': str, 'locations': List[str], 'lag_hours': float}

        Returns:
            Dictionary with all sensor features
        """
        all_features = {}

        for config in sensor_configs:
            sensor_type = config['type']
            locations = config.get('locations')
            lag_hours = config.get('lag_hours')

            # Temporarily adjust lag if specified
            if lag_hours:
                original_min = self.min_lag_seconds
                original_max = self.max_lag_seconds
                self.min_lag_seconds = lag_hours * 3600
                self.max_lag_seconds = (lag_hours + 2) * 3600

            try:
                features = self.associate_settlement_data(
                    db, ring_number, ring_end_time,
                    sensor_type=sensor_type,
                    sensor_locations=locations
                )

                # Prefix features with sensor type
                for key, value in features.items():
                    prefixed_key = f"{sensor_type}_{key}"
                    all_features[prefixed_key] = value

            except Exception as e:
                logger.error(f"Error associating {sensor_type}: {e}")

            finally:
                # Restore original lag
                if lag_hours:
                    self.min_lag_seconds = original_min
                    self.max_lag_seconds = original_max

        return all_features

    def get_settlement_time_series(
        self,
        db,
        ring_number: int,
        ring_end_time: float,
        sensor_location: str,
        hours_after: float = 24.0
    ) -> List[Dict[str, Any]]:
        """
        Get settlement time series for a specific sensor.

        Useful for analyzing settlement evolution over time.

        Args:
            db: Database manager
            ring_number: Ring number
            ring_end_time: Ring end time
            sensor_location: Specific sensor location
            hours_after: Hours after ring completion to query

        Returns:
            List of settlement readings with timestamps
        """
        try:
            end_time = ring_end_time + (hours_after * 3600)

            with db.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT timestamp, value
                    FROM monitoring_logs
                    WHERE sensor_type = 'surface_settlement'
                      AND sensor_location = ?
                      AND timestamp >= ?
                      AND timestamp <= ?
                    ORDER BY timestamp
                    """,
                    (sensor_location, ring_end_time, end_time)
                )

                rows = cursor.fetchall()

                time_series = [
                    {
                        'timestamp': row['timestamp'],
                        'hours_after_excavation': (row['timestamp'] - ring_end_time) / 3600,
                        'settlement_mm': row['value']
                    }
                    for row in rows if row['value'] is not None
                ]

                logger.info(
                    f"Retrieved {len(time_series)} settlement readings for "
                    f"sensor {sensor_location}, ring {ring_number}"
                )

                return time_series

        except Exception as e:
            logger.error(f"Error retrieving settlement time series: {e}")
            return []

    def get_statistics(self) -> Dict[str, Any]:
        """Get associator statistics"""
        total_attempts = self.stats['associations_found'] + self.stats['associations_not_found']
        success_rate = (
            (self.stats['associations_found'] / total_attempts * 100)
            if total_attempts > 0 else 0
        )

        return {
            'rings_processed': self.stats['rings_processed'],
            'total_sensors_read': self.stats['total_sensors_read'],
            'associations_found': self.stats['associations_found'],
            'associations_not_found': self.stats['associations_not_found'],
            'success_rate_percent': round(success_rate, 2)
        }


# Example usage
if __name__ == "__main__":
    import sys
    sys.path.append('/home/monss/tunnel-su-1/shield-tunneling-icp')

    from edge.database.manager import DatabaseManager
    from datetime import datetime

    db = DatabaseManager("data/edge.db")
    associator = SettlementAssociator(min_lag_hours=6.0, max_lag_hours=8.0)

    # Example: Associate settlement for ring 100
    ring_number = 100
    ring_end_time = datetime(2025, 11, 19, 10, 45).timestamp()

    # Method 1: Single sensor type
    settlement = associator.associate_settlement_data(
        db, ring_number, ring_end_time,
        sensor_type='surface_settlement'
    )

    print(f"Settlement features for ring {ring_number}:")
    for key, value in settlement.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")

    # Method 2: Multiple sensor types with different lags
    sensor_configs = [
        {
            'type': 'surface_settlement',
            'locations': None,  # All locations
            'lag_hours': 6.0
        },
        {
            'type': 'building_tilt',
            'locations': ['Building_A', 'Building_B'],
            'lag_hours': 12.0  # Longer lag for building response
        }
    ]

    all_monitoring = associator.associate_multiple_sensor_types(
        db, ring_number, ring_end_time, sensor_configs
    )

    print(f"\nAll monitoring features:")
    for key, value in all_monitoring.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")

    print(f"\nAssociator statistics: {associator.get_statistics()}")
