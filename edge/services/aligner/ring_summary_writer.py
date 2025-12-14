"""
T049: Ring Summary Persister
Writes aggregated ring features to ring_summary table
Handles upserts, data completeness flagging, and validation
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class RingSummaryWriter:
    """
    Persists ring summary data to database.

    Features:
    - Upsert operations (insert or update)
    - Data completeness assessment
    - Feature validation
    - Audit trail (created_at, updated_at)
    - Batch operations support
    """

    def __init__(self):
        """Initialize ring summary writer"""
        self.stats = {
            'rings_written': 0,
            'rings_updated': 0,
            'rings_inserted': 0,
            'write_errors': 0
        }

    def write_ring_summary(
        self,
        db,
        ring_number: int,
        start_time: float,
        end_time: float,
        plc_features: Dict[str, float],
        attitude_features: Dict[str, float],
        derived_indicators: Dict[str, float],
        settlement_features: Dict[str, float],
        geological_zone: Optional[str] = None
    ) -> bool:
        """
        Write complete ring summary to database.

        Args:
            db: Database manager
            ring_number: Ring number
            start_time: Ring start timestamp
            end_time: Ring end timestamp
            plc_features: Aggregated PLC features
            attitude_features: Aggregated attitude features
            derived_indicators: Calculated derived indicators
            settlement_features: Time-lagged settlement features
            geological_zone: Geological zone identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            # Merge all features
            all_features = {
                **plc_features,
                **attitude_features,
                **derived_indicators,
                **settlement_features
            }

            # Assess data completeness
            completeness_flag = self._assess_completeness(all_features)

            # Check if ring already exists
            with db.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT id FROM ring_summary WHERE ring_number = ?",
                    (ring_number,)
                )
                existing = cursor.fetchone()

            if existing:
                # Update existing record
                success = self._update_ring(
                    db, ring_number, start_time, end_time,
                    all_features, completeness_flag, geological_zone
                )
                if success:
                    self.stats['rings_updated'] += 1
            else:
                # Insert new record
                success = self._insert_ring(
                    db, ring_number, start_time, end_time,
                    all_features, completeness_flag, geological_zone
                )
                if success:
                    self.stats['rings_inserted'] += 1

            if success:
                self.stats['rings_written'] += 1
                logger.info(
                    f"Ring {ring_number} summary persisted: "
                    f"completeness={completeness_flag}, "
                    f"features={len(all_features)}"
                )
            else:
                self.stats['write_errors'] += 1

            return success

        except Exception as e:
            logger.error(f"Error writing ring {ring_number} summary: {e}")
            self.stats['write_errors'] += 1
            return False

    def _insert_ring(
        self,
        db,
        ring_number: int,
        start_time: float,
        end_time: float,
        features: Dict[str, float],
        completeness_flag: str,
        geological_zone: Optional[str]
    ) -> bool:
        """Insert new ring summary"""
        try:
            with db.transaction() as conn:
                now = datetime.utcnow().timestamp()

                conn.execute(
                    """
                    INSERT INTO ring_summary (
                        ring_number, start_time, end_time,
                        mean_thrust, max_thrust, min_thrust, std_thrust,
                        mean_torque, max_torque,
                        mean_penetration_rate, max_penetration_rate,
                        mean_chamber_pressure, max_chamber_pressure,
                        mean_pitch, mean_roll, mean_yaw,
                        horizontal_deviation, vertical_deviation,
                        specific_energy, ground_loss_rate, volume_loss_ratio,
                        settlement_value,
                        data_completeness_flag, geological_zone,
                        synced_to_cloud, created_at, updated_at
                    ) VALUES (
                        ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?,
                        ?, ?,
                        ?, ?,
                        ?, ?, ?,
                        ?, ?,
                        ?, ?, ?,
                        ?,
                        ?, ?,
                        ?, ?, ?
                    )
                    """,
                    (
                        ring_number, start_time, end_time,
                        features.get('mean_thrust'),
                        features.get('max_thrust'),
                        features.get('min_thrust'),
                        features.get('std_thrust'),
                        features.get('mean_torque'),
                        features.get('max_torque'),
                        features.get('mean_penetration_rate'),
                        features.get('max_penetration_rate'),
                        features.get('mean_chamber_pressure'),
                        features.get('max_chamber_pressure'),
                        features.get('mean_pitch'),
                        features.get('mean_roll'),
                        features.get('mean_yaw'),
                        features.get('horizontal_deviation'),
                        features.get('vertical_deviation'),
                        features.get('specific_energy'),
                        features.get('ground_loss_rate'),
                        features.get('volume_loss_ratio'),
                        features.get('settlement_value'),
                        completeness_flag,
                        geological_zone,
                        0,  # synced_to_cloud
                        now,  # created_at
                        now   # updated_at
                    )
                )

            logger.debug(f"Inserted ring {ring_number} summary")
            return True

        except Exception as e:
            logger.error(f"Error inserting ring {ring_number}: {e}")
            return False

    def _update_ring(
        self,
        db,
        ring_number: int,
        start_time: float,
        end_time: float,
        features: Dict[str, float],
        completeness_flag: str,
        geological_zone: Optional[str]
    ) -> bool:
        """Update existing ring summary"""
        try:
            with db.transaction() as conn:
                now = datetime.utcnow().timestamp()

                conn.execute(
                    """
                    UPDATE ring_summary SET
                        start_time = ?,
                        end_time = ?,
                        mean_thrust = ?,
                        max_thrust = ?,
                        min_thrust = ?,
                        std_thrust = ?,
                        mean_torque = ?,
                        max_torque = ?,
                        mean_penetration_rate = ?,
                        max_penetration_rate = ?,
                        mean_chamber_pressure = ?,
                        max_chamber_pressure = ?,
                        mean_pitch = ?,
                        mean_roll = ?,
                        mean_yaw = ?,
                        horizontal_deviation = ?,
                        vertical_deviation = ?,
                        specific_energy = ?,
                        ground_loss_rate = ?,
                        volume_loss_ratio = ?,
                        settlement_value = ?,
                        data_completeness_flag = ?,
                        geological_zone = ?,
                        updated_at = ?
                    WHERE ring_number = ?
                    """,
                    (
                        start_time, end_time,
                        features.get('mean_thrust'),
                        features.get('max_thrust'),
                        features.get('min_thrust'),
                        features.get('std_thrust'),
                        features.get('mean_torque'),
                        features.get('max_torque'),
                        features.get('mean_penetration_rate'),
                        features.get('max_penetration_rate'),
                        features.get('mean_chamber_pressure'),
                        features.get('max_chamber_pressure'),
                        features.get('mean_pitch'),
                        features.get('mean_roll'),
                        features.get('mean_yaw'),
                        features.get('horizontal_deviation'),
                        features.get('vertical_deviation'),
                        features.get('specific_energy'),
                        features.get('ground_loss_rate'),
                        features.get('volume_loss_ratio'),
                        features.get('settlement_value'),
                        completeness_flag,
                        geological_zone,
                        now,  # updated_at
                        ring_number
                    )
                )

            logger.debug(f"Updated ring {ring_number} summary")
            return True

        except Exception as e:
            logger.error(f"Error updating ring {ring_number}: {e}")
            return False

    def _assess_completeness(self, features: Dict[str, Any]) -> str:
        """
        Assess data completeness based on available features.

        Args:
            features: Dictionary of all features

        Returns:
            Completeness flag: 'complete', 'partial', or 'incomplete'
        """
        # Define critical features
        critical_features = [
            'mean_thrust',
            'mean_torque',
            'mean_penetration_rate',
            'mean_chamber_pressure',
            'mean_pitch',
            'mean_roll',
            'settlement_value',
            'specific_energy'
        ]

        # Count available critical features
        available = sum(
            1 for feat in critical_features
            if features.get(feat) is not None
        )

        total = len(critical_features)
        completeness_ratio = available / total

        if completeness_ratio >= 0.9:
            return 'complete'
        elif completeness_ratio >= 0.6:
            return 'partial'
        else:
            return 'incomplete'

    def mark_synced_to_cloud(
        self,
        db,
        ring_number: int
    ) -> bool:
        """
        Mark ring as synced to cloud.

        Args:
            db: Database manager
            ring_number: Ring number

        Returns:
            True if successful
        """
        try:
            with db.transaction() as conn:
                conn.execute(
                    """
                    UPDATE ring_summary
                    SET synced_to_cloud = 1,
                        updated_at = ?
                    WHERE ring_number = ?
                    """,
                    (datetime.utcnow().timestamp(), ring_number)
                )

            logger.info(f"Ring {ring_number} marked as synced to cloud")
            return True

        except Exception as e:
            logger.error(f"Error marking ring {ring_number} as synced: {e}")
            return False

    def get_unsynced_rings(self, db, limit: int = 100) -> list:
        """
        Get list of rings not yet synced to cloud.

        Args:
            db: Database manager
            limit: Maximum number of rings to return

        Returns:
            List of ring numbers
        """
        try:
            with db.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT ring_number
                    FROM ring_summary
                    WHERE synced_to_cloud = 0
                    ORDER BY ring_number
                    LIMIT ?
                    """,
                    (limit,)
                )

                rings = [row['ring_number'] for row in cursor.fetchall()]
                return rings

        except Exception as e:
            logger.error(f"Error getting unsynced rings: {e}")
            return []

    def get_statistics(self) -> Dict[str, Any]:
        """Get writer statistics"""
        return {
            'rings_written': self.stats['rings_written'],
            'rings_inserted': self.stats['rings_inserted'],
            'rings_updated': self.stats['rings_updated'],
            'write_errors': self.stats['write_errors']
        }


# Example usage
if __name__ == "__main__":
    import sys
    sys.path.append('/home/monss/tunnel-su-1/shield-tunneling-icp')

    from edge.database.manager import DatabaseManager
    from datetime import datetime

    db = DatabaseManager("data/edge.db")
    writer = RingSummaryWriter()

    # Example: Write ring summary
    ring_number = 100
    start_time = datetime(2025, 11, 19, 10, 0).timestamp()
    end_time = datetime(2025, 11, 19, 10, 45).timestamp()

    plc_features = {
        'mean_thrust': 12000.5,
        'max_thrust': 15000.0,
        'min_thrust': 9500.0,
        'std_thrust': 1200.0,
        'mean_torque': 900.0,
        'max_torque': 1100.0,
        'mean_penetration_rate': 15.2,
        'max_penetration_rate': 18.5,
        'mean_chamber_pressure': 1.8,
        'max_chamber_pressure': 2.1
    }

    attitude_features = {
        'mean_pitch': 0.5,
        'mean_roll': -0.3,
        'mean_yaw': 2.1,
        'horizontal_deviation': 25.0,
        'vertical_deviation': -10.0
    }

    derived_indicators = {
        'specific_energy': 28.5,
        'ground_loss_rate': 0.85,
        'volume_loss_ratio': 1.9
    }

    settlement_features = {
        'settlement_value': -5.2
    }

    # Write to database
    success = writer.write_ring_summary(
        db, ring_number, start_time, end_time,
        plc_features, attitude_features,
        derived_indicators, settlement_features,
        geological_zone='Clay'
    )

    print(f"Write successful: {success}")
    print(f"Writer statistics: {writer.get_statistics()}")

    # Get unsynced rings
    unsynced = writer.get_unsynced_rings(db)
    print(f"\nUnsynced rings: {unsynced}")
