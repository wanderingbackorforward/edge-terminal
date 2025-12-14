"""
T044: PLC Data Aggregator (Modular)
Aggregates high-frequency PLC data into ring-level statistics
Calculates mean, max, min, std for each tag
"""
import logging
from typing import Dict, List, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)


class PLCAggregator:
    """
    Aggregates PLC sensor data for a ring.

    Features:
    - Statistical aggregation (mean, max, min, std, median)
    - Per-tag processing
    - Data quality filtering
    - Missing data handling
    - Performance optimization for large datasets
    """

    def __init__(self):
        """Initialize PLC aggregator"""
        self.stats = {
            'rings_processed': 0,
            'total_readings': 0,
            'tags_processed': set()
        }

    def aggregate_ring_data(
        self,
        db,
        ring_number: int,
        start_time: float,
        end_time: float,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Aggregate PLC data for a specific ring.

        Args:
            db: Database manager
            ring_number: Ring number
            start_time: Ring start timestamp
            end_time: Ring end timestamp
            tags: Optional list of tags to aggregate (None = all tags)

        Returns:
            Dictionary with aggregated statistics per tag
        """
        try:
            with db.get_connection() as conn:
                # Build query
                if tags:
                    placeholders = ','.join(['?' for _ in tags])
                    tag_filter = f"AND tag_name IN ({placeholders})"
                    query_params = [start_time, end_time] + tags
                else:
                    tag_filter = ""
                    query_params = [start_time, end_time]

                # Query PLC data for this ring
                cursor = conn.execute(
                    f"""
                    SELECT tag_name, value, data_quality_flag
                    FROM plc_logs
                    WHERE timestamp >= ?
                      AND timestamp <= ?
                      {tag_filter}
                    ORDER BY tag_name, timestamp
                    """,
                    query_params
                )

                rows = cursor.fetchall()

                if not rows:
                    logger.warning(
                        f"No PLC data found for ring {ring_number} "
                        f"(time window: {start_time} - {end_time})"
                    )
                    return {}

                # Group by tag
                tag_data = {}
                for row in rows:
                    tag_name = row['tag_name']
                    value = row['value']
                    quality_flag = row['data_quality_flag']

                    # Filter out rejected/missing data
                    if quality_flag in ['rejected', 'missing']:
                        continue

                    if tag_name not in tag_data:
                        tag_data[tag_name] = []
                    tag_data[tag_name].append(value)

                # Calculate statistics per tag
                aggregated = {}
                for tag_name, values in tag_data.items():
                    stats = self._calculate_statistics(tag_name, values)
                    aggregated.update(stats)
                    self.stats['tags_processed'].add(tag_name)

                self.stats['rings_processed'] += 1
                self.stats['total_readings'] += len(rows)

                logger.info(
                    f"Aggregated PLC data for ring {ring_number}: "
                    f"{len(tag_data)} tags, {len(rows)} readings"
                )

                return aggregated

        except Exception as e:
            logger.error(f"Error aggregating PLC data for ring {ring_number}: {e}")
            raise

    def _calculate_statistics(
        self,
        tag_name: str,
        values: List[float]
    ) -> Dict[str, float]:
        """
        Calculate statistics for a tag.

        Args:
            tag_name: PLC tag name
            values: List of readings

        Returns:
            Dictionary with mean, max, min, std for this tag
        """
        if not values:
            return {}

        try:
            values_array = np.array(values)

            # Remove NaN/inf values
            values_array = values_array[np.isfinite(values_array)]

            if len(values_array) == 0:
                logger.warning(f"No valid values for tag {tag_name}")
                return {}

            # Calculate statistics
            stats = {
                f'mean_{tag_name}': float(np.mean(values_array)),
                f'max_{tag_name}': float(np.max(values_array)),
                f'min_{tag_name}': float(np.min(values_array)),
                f'std_{tag_name}': float(np.std(values_array))
            }

            # Optional: median (can be expensive for large datasets)
            if len(values_array) <= 10000:  # Only for reasonable sizes
                stats[f'median_{tag_name}'] = float(np.median(values_array))

            return stats

        except Exception as e:
            logger.error(f"Error calculating statistics for {tag_name}: {e}")
            return {}

    def aggregate_specific_tags(
        self,
        db,
        ring_number: int,
        start_time: float,
        end_time: float,
        tag_mapping: Dict[str, str]
    ) -> Dict[str, float]:
        """
        Aggregate specific tags with custom output names.

        Useful for creating standardized feature names.

        Args:
            db: Database manager
            ring_number: Ring number
            start_time: Start timestamp
            end_time: End timestamp
            tag_mapping: Dict mapping tag_name -> output_prefix
                        e.g., {'thrust_total': 'thrust', 'cutterhead_torque': 'torque'}

        Returns:
            Dictionary with aggregated features using custom names
        """
        tags = list(tag_mapping.keys())
        raw_aggregated = self.aggregate_ring_data(
            db, ring_number, start_time, end_time, tags
        )

        # Rename according to mapping
        renamed = {}
        for tag_name, output_prefix in tag_mapping.items():
            for stat_type in ['mean', 'max', 'min', 'std', 'median']:
                old_key = f'{stat_type}_{tag_name}'
                if old_key in raw_aggregated:
                    new_key = f'{stat_type}_{output_prefix}'
                    renamed[new_key] = raw_aggregated[old_key]

        return renamed

    def get_data_completeness(
        self,
        db,
        ring_number: int,
        start_time: float,
        end_time: float,
        expected_frequency: float = 1.0
    ) -> Dict[str, Any]:
        """
        Assess data completeness for the ring.

        Args:
            db: Database manager
            ring_number: Ring number
            start_time: Start timestamp
            end_time: End timestamp
            expected_frequency: Expected sampling rate (Hz)

        Returns:
            Dict with completeness metrics
        """
        duration_seconds = end_time - start_time
        expected_samples = duration_seconds * expected_frequency

        try:
            with db.get_connection() as conn:
                # Count actual samples
                cursor = conn.execute(
                    """
                    SELECT COUNT(*) as total,
                           COUNT(DISTINCT tag_name) as unique_tags
                    FROM plc_logs
                    WHERE timestamp >= ?
                      AND timestamp <= ?
                      AND data_quality_flag NOT IN ('rejected', 'missing')
                    """,
                    (start_time, end_time)
                )

                result = cursor.fetchone()
                actual_samples = result['total']
                unique_tags = result['unique_tags']

                # Calculate completeness percentage
                if unique_tags > 0:
                    samples_per_tag = actual_samples / unique_tags
                    completeness_pct = (samples_per_tag / expected_samples) * 100
                else:
                    completeness_pct = 0.0

                return {
                    'expected_samples_per_tag': expected_samples,
                    'actual_samples_total': actual_samples,
                    'unique_tags': unique_tags,
                    'completeness_percent': min(completeness_pct, 100.0),
                    'data_quality': self._assess_quality(completeness_pct)
                }

        except Exception as e:
            logger.error(f"Error assessing data completeness: {e}")
            return {
                'expected_samples_per_tag': expected_samples,
                'actual_samples_total': 0,
                'unique_tags': 0,
                'completeness_percent': 0.0,
                'data_quality': 'unknown'
            }

    def _assess_quality(self, completeness_pct: float) -> str:
        """
        Assess data quality based on completeness.

        Args:
            completeness_pct: Completeness percentage

        Returns:
            Quality level: 'complete', 'partial', 'incomplete'
        """
        if completeness_pct >= 90:
            return 'complete'
        elif completeness_pct >= 50:
            return 'partial'
        else:
            return 'incomplete'

    def get_statistics(self) -> Dict[str, Any]:
        """Get aggregator statistics"""
        return {
            'rings_processed': self.stats['rings_processed'],
            'total_readings': self.stats['total_readings'],
            'unique_tags': len(self.stats['tags_processed']),
            'tags': list(self.stats['tags_processed'])
        }


# Example usage
if __name__ == "__main__":
    import sys
    sys.path.append('/home/monss/tunnel-su-1/shield-tunneling-icp')

    from edge.database.manager import DatabaseManager
    from datetime import datetime

    db = DatabaseManager("data/edge.db")
    aggregator = PLCAggregator()

    # Example: Aggregate ring 100
    ring_number = 100
    start_time = datetime(2025, 11, 19, 10, 0).timestamp()
    end_time = datetime(2025, 11, 19, 10, 45).timestamp()

    # Method 1: Aggregate all tags
    all_data = aggregator.aggregate_ring_data(
        db, ring_number, start_time, end_time
    )
    print(f"All tags aggregated: {len(all_data)} features")

    # Method 2: Aggregate specific tags with custom names
    tag_mapping = {
        'thrust_total': 'thrust',
        'cutterhead_torque': 'torque',
        'penetration_rate': 'penetration',
        'chamber_pressure': 'pressure'
    }

    specific_data = aggregator.aggregate_specific_tags(
        db, ring_number, start_time, end_time, tag_mapping
    )
    print(f"\nSpecific tags aggregated:")
    for key, value in specific_data.items():
        print(f"  {key}: {value:.2f}")

    # Method 3: Check data completeness
    completeness = aggregator.get_data_completeness(
        db, ring_number, start_time, end_time
    )
    print(f"\nData completeness: {completeness['completeness_percent']:.1f}%")
    print(f"Quality: {completeness['data_quality']}")

    print(f"\nAggregator statistics: {aggregator.get_statistics()}")
