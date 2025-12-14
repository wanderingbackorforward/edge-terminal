"""
T043: Ring Boundary Detector
Detects ring construction start/end times from sensor signals
Uses advance sensor signals with time-based fallback
"""
import logging
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta
import yaml

logger = logging.getLogger(__name__)


class RingBoundaryDetector:
    """
    Detects ring construction boundaries from sensor data.

    Detection Methods:
    1. Advance sensor signal (primary method)
    2. Ring assembly completion signal
    3. Time-based fallback (typical construction duration)
    4. Manual ring boundary input

    Features:
    - Multi-signal fusion for robust detection
    - Configurable detection thresholds
    - Fallback strategies for sensor failures
    - Boundary validation and correction
    """

    def __init__(self, config_path: str = "edge/config/alignment.yaml"):
        """
        Initialize ring boundary detector.

        Args:
            config_path: Path to alignment configuration
        """
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        self.ring_config = config.get('ring_boundary_detection', {})
        self.geometry = config.get('ring_geometry', {})

        # Detection parameters
        self.detection_method = self.ring_config.get('method', 'auto')
        self.fallback_duration = self.ring_config.get('fallback_duration', 45)  # minutes
        self.advance_threshold = self.ring_config.get('advance_threshold', 1400)  # mm

        # Ring geometry
        self.ring_width = self.geometry.get('width', 1.5)  # meters

        self.stats = {
            'total_detected': 0,
            'method_used': {},
            'validation_failures': 0
        }

    def detect_from_advance_sensor(
        self,
        db,
        start_search_time: float,
        end_search_time: float,
        ring_number: int
    ) -> Optional[Tuple[float, float]]:
        """
        Detect ring boundary from advance sensor signal.

        The advance sensor measures cumulative shield advance distance.
        A ring boundary is detected when advance increases by ~ring_width.

        Args:
            db: Database manager instance
            start_search_time: Start of search window (Unix timestamp)
            end_search_time: End of search window
            ring_number: Ring number being detected

        Returns:
            Tuple of (start_time, end_time) or None if not detected
        """
        try:
            with db.get_connection() as conn:
                # Query advance sensor data
                cursor = conn.execute(
                    """
                    SELECT timestamp, value
                    FROM plc_logs
                    WHERE tag_name = 'advance_distance'
                      AND timestamp >= ?
                      AND timestamp <= ?
                    ORDER BY timestamp
                    """,
                    (start_search_time, end_search_time)
                )

                readings = cursor.fetchall()

                if len(readings) < 2:
                    logger.warning("Insufficient advance sensor data for ring detection")
                    return None

                # Find advance increments matching ring width
                ring_width_mm = self.ring_width * 1000  # Convert to mm
                tolerance = 200  # mm tolerance

                start_time = None
                start_value = None

                for i, (timestamp, value) in enumerate(readings):
                    if start_time is None:
                        # Potential ring start
                        start_time = timestamp
                        start_value = value
                        continue

                    # Check if advance matches ring width
                    advance_delta = value - start_value

                    if abs(advance_delta - ring_width_mm) < tolerance:
                        # Ring boundary detected
                        end_time = timestamp

                        logger.info(
                            f"Ring {ring_number} detected via advance sensor: "
                            f"advance={advance_delta:.1f}mm, "
                            f"duration={(end_time - start_time)/60:.1f}min"
                        )

                        self._record_detection('advance_sensor')
                        return (start_time, end_time)

                    # If advance exceeds expected, reset search
                    if advance_delta > ring_width_mm + tolerance:
                        start_time = timestamp
                        start_value = value

                logger.warning(f"No ring boundary found in advance sensor data")
                return None

        except Exception as e:
            logger.error(f"Error detecting from advance sensor: {e}")
            return None

    def detect_from_ring_assembly_signal(
        self,
        db,
        start_search_time: float,
        end_search_time: float,
        ring_number: int
    ) -> Optional[Tuple[float, float]]:
        """
        Detect ring boundary from ring assembly completion signal.

        Some TBMs have discrete signals indicating ring assembly start/complete.

        Args:
            db: Database manager
            start_search_time: Search window start
            end_search_time: Search window end
            ring_number: Ring number

        Returns:
            Tuple of (start_time, end_time) or None
        """
        try:
            with db.get_connection() as conn:
                # Look for ring assembly start signal
                cursor = conn.execute(
                    """
                    SELECT timestamp, value
                    FROM plc_logs
                    WHERE tag_name = 'ring_assembly_active'
                      AND timestamp >= ?
                      AND timestamp <= ?
                    ORDER BY timestamp
                    """,
                    (start_search_time, end_search_time)
                )

                readings = cursor.fetchall()

                # Find rising edge (0 -> 1) and falling edge (1 -> 0)
                start_time = None
                for i in range(len(readings) - 1):
                    curr_timestamp, curr_value = readings[i]
                    next_timestamp, next_value = readings[i + 1]

                    # Rising edge: ring assembly started
                    if curr_value == 0 and next_value == 1:
                        start_time = next_timestamp

                    # Falling edge: ring assembly completed
                    if curr_value == 1 and next_value == 0 and start_time:
                        end_time = next_timestamp

                        logger.info(
                            f"Ring {ring_number} detected via assembly signal: "
                            f"duration={(end_time - start_time)/60:.1f}min"
                        )

                        self._record_detection('assembly_signal')
                        return (start_time, end_time)

                logger.debug("No ring assembly signal found")
                return None

        except Exception as e:
            logger.error(f"Error detecting from assembly signal: {e}")
            return None

    def detect_with_time_fallback(
        self,
        last_ring_end_time: float,
        ring_number: int
    ) -> Tuple[float, float]:
        """
        Fallback method: Use typical ring construction duration.

        When sensors fail, estimate ring boundaries based on average duration.

        Args:
            last_ring_end_time: End time of previous ring
            ring_number: Current ring number

        Returns:
            Tuple of (start_time, end_time)
        """
        # Use fallback duration from config
        duration_seconds = self.fallback_duration * 60

        start_time = last_ring_end_time
        end_time = start_time + duration_seconds

        logger.warning(
            f"Ring {ring_number} using time-based fallback: "
            f"duration={self.fallback_duration}min"
        )

        self._record_detection('time_fallback')
        return (start_time, end_time)

    def detect_ring_boundary(
        self,
        db,
        ring_number: int,
        start_search_time: Optional[float] = None,
        end_search_time: Optional[float] = None,
        last_ring_end_time: Optional[float] = None
    ) -> Tuple[float, float]:
        """
        Detect ring boundary using configured method with fallbacks.

        Detection priority:
        1. Advance sensor (most reliable)
        2. Ring assembly signal
        3. Time-based fallback

        Args:
            db: Database manager
            ring_number: Ring number to detect
            start_search_time: Search window start (optional)
            end_search_time: Search window end (optional)
            last_ring_end_time: Previous ring end time for fallback

        Returns:
            Tuple of (start_time, end_time)

        Raises:
            ValueError: If detection fails and no fallback available
        """
        # Set default search window if not provided
        if not start_search_time or not end_search_time:
            if last_ring_end_time:
                # Search 2 hours after last ring
                start_search_time = last_ring_end_time
                end_search_time = last_ring_end_time + (2 * 3600)
            else:
                raise ValueError(
                    "Must provide either search window or last_ring_end_time"
                )

        result = None

        # Try advance sensor (primary method)
        if self.detection_method in ['auto', 'advance']:
            result = self.detect_from_advance_sensor(
                db, start_search_time, end_search_time, ring_number
            )

        # Try assembly signal
        if not result and self.detection_method in ['auto', 'assembly']:
            result = self.detect_from_ring_assembly_signal(
                db, start_search_time, end_search_time, ring_number
            )

        # Fallback to time-based
        if not result:
            if last_ring_end_time is None:
                raise ValueError(
                    "Ring boundary detection failed and no fallback available"
                )
            result = self.detect_with_time_fallback(last_ring_end_time, ring_number)

        # Validate detected boundary
        if not self._validate_boundary(result[0], result[1], ring_number):
            logger.warning(f"Ring {ring_number} boundary validation failed")
            self.stats['validation_failures'] += 1

        return result

    def _validate_boundary(
        self,
        start_time: float,
        end_time: float,
        ring_number: int
    ) -> bool:
        """
        Validate detected ring boundary.

        Checks:
        - Duration is reasonable (10-120 minutes typical)
        - Times are in correct order
        - Not in the future

        Args:
            start_time: Ring start time
            end_time: Ring end time
            ring_number: Ring number

        Returns:
            True if valid, False otherwise
        """
        # Check time ordering
        if end_time <= start_time:
            logger.error(f"Ring {ring_number}: end_time <= start_time")
            return False

        # Check not in future
        now = datetime.utcnow().timestamp()
        if start_time > now or end_time > now:
            logger.error(f"Ring {ring_number}: boundary in the future")
            return False

        # Check duration is reasonable
        duration_minutes = (end_time - start_time) / 60
        if duration_minutes < 10:
            logger.warning(
                f"Ring {ring_number}: very short duration ({duration_minutes:.1f}min)"
            )
            return False

        if duration_minutes > 120:
            logger.warning(
                f"Ring {ring_number}: very long duration ({duration_minutes:.1f}min)"
            )
            return False

        return True

    def _record_detection(self, method: str) -> None:
        """Record detection method used"""
        self.stats['total_detected'] += 1
        if method not in self.stats['method_used']:
            self.stats['method_used'][method] = 0
        self.stats['method_used'][method] += 1

    def get_statistics(self) -> Dict[str, Any]:
        """Get detection statistics"""
        return {
            'total_detected': self.stats['total_detected'],
            'methods_used': self.stats['method_used'],
            'validation_failures': self.stats['validation_failures']
        }


# Example usage
if __name__ == "__main__":
    import sys
    sys.path.append('/home/monss/tunnel-su-1/shield-tunneling-icp')

    from edge.database.manager import DatabaseManager

    # Initialize
    db = DatabaseManager("data/edge.db")
    detector = RingBoundaryDetector()

    # Example: Detect ring 100
    ring_number = 100
    last_ring_end = datetime(2025, 11, 19, 10, 0).timestamp()

    try:
        start_time, end_time = detector.detect_ring_boundary(
            db=db,
            ring_number=ring_number,
            last_ring_end_time=last_ring_end
        )

        duration_min = (end_time - start_time) / 60

        print(f"Ring {ring_number} detected:")
        print(f"  Start: {datetime.fromtimestamp(start_time)}")
        print(f"  End: {datetime.fromtimestamp(end_time)}")
        print(f"  Duration: {duration_min:.1f} minutes")
        print(f"\nStatistics: {detector.get_statistics()}")

    except Exception as e:
        print(f"Error: {e}")
