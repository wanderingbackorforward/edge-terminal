"""
Warning Engine Orchestrator
Coordinates threshold, rate, and predictive warning checks
Implements Feature 003 - Real-Time Warning System
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from edge.models.warning_threshold import WarningThreshold
from edge.models.warning_event import WarningEvent
from edge.services.warning.threshold_checker import ThresholdChecker
from edge.services.warning.rate_detector import RateDetector
from edge.services.warning.predictive_checker import PredictiveChecker

logger = logging.getLogger(__name__)


class WarningEngine:
    """
    Orchestrates multi-dimensional warning system

    Implements:
    - FR-001 to FR-007: Multi-dimensional warning strategy
    - FR-020 to FR-025: Edge-first autonomous operation
    - FR-033: Hysteresis logic for oscillating indicators

    Coordinates three warning mechanisms:
    1. Threshold-based: Absolute value violations
    2. Rate-based: Abnormal rate of change
    3. Predictive: Forecasted violations

    Performance target: <10ms warning generation latency
    """

    def __init__(
        self,
        db_session: Session,
        threshold_configs: Optional[Dict[str, WarningThreshold]] = None
    ):
        """
        Initialize warning engine with database session and threshold configs

        Args:
            db_session: Database session for querying data and persisting warnings
            threshold_configs: Dict mapping indicator_name_zone → WarningThreshold
                              If None, loads from database
        """
        self.db = db_session

        # Load threshold configurations
        if threshold_configs is None:
            threshold_configs = self._load_threshold_configs()

        self.thresholds = threshold_configs

        # Initialize warning checkers
        self.threshold_checker = ThresholdChecker(threshold_configs)
        self.rate_detector = RateDetector(db_session, threshold_configs)
        self.predictive_checker = PredictiveChecker(db_session, threshold_configs)

        # Hysteresis tracking: indicator_key → last_warning_level
        self.hysteresis_state: Dict[str, Dict[str, Any]] = {}

        logger.info(
            f"WarningEngine initialized with {len(threshold_configs)} threshold configs"
        )

    def evaluate_ring(
        self,
        ring_number: int,
        indicators: Dict[str, float],
        geological_zone: str = "all",
        timestamp: Optional[float] = None
    ) -> List[WarningEvent]:
        """
        Evaluate all warning mechanisms for a ring

        This is the main entry point for warning generation.

        Args:
            ring_number: Current ring number
            indicators: Dict mapping indicator_name → current_value
                       Example: {"cumulative_settlement": 25.3, "chamber_pressure": 2.8}
            geological_zone: Geological zone for zone-specific thresholds
            timestamp: Event timestamp (defaults to now)

        Returns:
            List of WarningEvent objects (may be empty if no warnings)

        Implements FR-001 to FR-007, FR-033
        """
        if timestamp is None:
            timestamp = datetime.utcnow().timestamp()

        all_warnings = []

        # Phase 1: Threshold-based checks (FR-001, FR-002)
        threshold_warnings = self._check_thresholds(
            ring_number, indicators, geological_zone, timestamp
        )
        all_warnings.extend(threshold_warnings)

        # Phase 2: Rate-based checks (FR-003, FR-004)
        rate_warnings = self._check_rates(
            ring_number, indicators, geological_zone, timestamp
        )
        all_warnings.extend(rate_warnings)

        # Phase 3: Predictive checks (FR-006)
        predictive_warnings = self._check_predictions(
            ring_number, geological_zone, timestamp
        )
        all_warnings.extend(predictive_warnings)

        # Phase 4: Apply hysteresis logic (FR-033)
        filtered_warnings = self._apply_hysteresis(all_warnings, indicators, geological_zone)

        # Phase 5: Aggregate combined warnings (FR-005, FR-007)
        final_warnings = self._aggregate_combined_warnings(filtered_warnings)

        # Phase 6: Persist to database (FR-024, FR-026)
        persisted_warnings = self._persist_warnings(final_warnings)

        if persisted_warnings:
            logger.info(
                f"Ring {ring_number}: Generated {len(persisted_warnings)} warnings "
                f"({len(threshold_warnings)} threshold, {len(rate_warnings)} rate, "
                f"{len(predictive_warnings)} predictive)"
            )

            # Phase 7: Publish to MQTT for real-time notifications (FR-010, FR-011, FR-012)
            self._publish_warnings_to_mqtt(persisted_warnings)

        return persisted_warnings

    def _check_thresholds(
        self,
        ring_number: int,
        indicators: Dict[str, float],
        geological_zone: str,
        timestamp: float
    ) -> List[WarningEvent]:
        """Check all indicators against absolute thresholds"""
        warnings = []

        for indicator_name, value in indicators.items():
            warning = self.threshold_checker.check(
                ring_number, indicator_name, value, geological_zone, timestamp
            )
            if warning:
                warnings.append(warning)

        return warnings

    def _check_rates(
        self,
        ring_number: int,
        indicators: Dict[str, float],
        geological_zone: str,
        timestamp: float
    ) -> List[WarningEvent]:
        """Check all indicators for abnormal rate of change"""
        warnings = []

        for indicator_name, value in indicators.items():
            warning = self.rate_detector.check(
                ring_number, indicator_name, value, geological_zone, timestamp
            )
            if warning:
                warnings.append(warning)

        return warnings

    def _check_predictions(
        self,
        ring_number: int,
        geological_zone: str,
        timestamp: float
    ) -> List[WarningEvent]:
        """Check predictions for potential future violations"""
        warnings = self.predictive_checker.check(
            ring_number, geological_zone, timestamp
        )
        return warnings

    def _apply_hysteresis(
        self,
        warnings: List[WarningEvent],
        current_indicators: Dict[str, float],
        geological_zone: str
    ) -> List[WarningEvent]:
        """
        Apply hysteresis logic to prevent oscillating alerts

        Implements FR-033: 5% threshold buffer

        Hysteresis rules:
        1. If no warning was previously active for this indicator, allow new warning
        2. If warning level increased (ATTENTION→WARNING→ALARM), allow escalation
        3. If warning level stayed same, check if value moved >5% from threshold
        4. If warning level decreased, allow de-escalation

        Args:
            warnings: List of warning events to filter
            current_indicators: Current indicator values for cleanup validation
            geological_zone: Current geological zone for zone-specific threshold lookup

        Returns:
            Filtered list of warnings with hysteresis applied
        """
        filtered = []

        for warning in warnings:
            # Key by indicator name + zone to track state per zone
            # This ensures zone-specific thresholds are properly tracked
            indicator_key = f"{warning.indicator_name}_{geological_zone}"

            current_value = self._get_hysteresis_value(warning)
            # Get previous warning state
            prev_state = self.hysteresis_state.get(indicator_key)

            if prev_state is None:
                # No previous warning - allow
                filtered.append(warning)
                self._update_hysteresis_state(
                    warning, indicator_key, current_value, geological_zone
                )
                continue

            prev_level = prev_state.get("level")
            prev_threshold = prev_state.get("threshold")
            prev_value = prev_state.get("value")

            # Compare warning levels
            level_order = {"ATTENTION": 1, "WARNING": 2, "ALARM": 3}
            current_level_rank = level_order.get(warning.warning_level, 0)
            prev_level_rank = level_order.get(prev_level, 0)

            if current_level_rank > prev_level_rank:
                # Escalation - always allow
                filtered.append(warning)
                self._update_hysteresis_state(
                    warning, indicator_key, current_value, geological_zone
                )
                logger.debug(
                    f"Hysteresis: Escalation from {prev_level} to {warning.warning_level} "
                    f"for {warning.indicator_name}"
                )
            elif current_level_rank < prev_level_rank:
                # De-escalation - allow (warning is resolving)
                filtered.append(warning)
                self._update_hysteresis_state(
                    warning, indicator_key, current_value, geological_zone
                )
                logger.debug(
                    f"Hysteresis: De-escalation from {prev_level} to {warning.warning_level} "
                    f"for {warning.indicator_name}"
                )
            else:
                # Same level - check if value changed significantly
                if prev_threshold and warning.threshold_value and current_value is not None and prev_value is not None:
                    threshold_change = abs(
                        (current_value - prev_value) / prev_threshold
                    )

                    if threshold_change >= 0.05:  # 5% hysteresis buffer
                        filtered.append(warning)
                        self._update_hysteresis_state(
                            warning, indicator_key, current_value, geological_zone
                        )
                        logger.debug(
                            f"Hysteresis: Allowing same-level warning for {warning.indicator_name} "
                            f"(value changed {threshold_change:.1%})"
                        )
                    else:
                        logger.debug(
                            f"Hysteresis: Suppressing oscillating warning for {warning.indicator_name} "
                            f"(value changed only {threshold_change:.1%})"
                        )
                else:
                    # No threshold info - allow by default
                    filtered.append(warning)
                    self._update_hysteresis_state(
                        warning, indicator_key, current_value, geological_zone
                    )

        # Clean up hysteresis state for indicators that returned to normal
        self._cleanup_hysteresis_state(warnings, current_indicators, geological_zone)

        return filtered

    def _update_hysteresis_state(
        self,
        warning: WarningEvent,
        indicator_key: str,
        value: Optional[float],
        geological_zone: str
    ):
        """Update hysteresis tracking state"""
        self.hysteresis_state[indicator_key] = {
            "level": warning.warning_level,
            "value": value,
            "threshold": warning.threshold_value,
            "timestamp": warning.timestamp,
            "indicator_name": warning.indicator_name,
            "zone": geological_zone,
        }

    def _get_hysteresis_value(self, warning: WarningEvent) -> Optional[float]:
        """
        Get numeric value used for hysteresis comparison.

        Predictive warnings don't set indicator_value, so fall back to predicted_value.
        """
        if warning.indicator_value is not None:
            return warning.indicator_value
        if warning.predicted_value is not None:
            return warning.predicted_value
        return None

    def _cleanup_hysteresis_state(
        self,
        warnings: List[WarningEvent],
        current_indicators: Dict[str, float],
        geological_zone: str
    ):
        """
        Remove hysteresis state only for indicators that truly returned to normal range

        Uses current_indicators to verify indicator values are within thresholds
        before clearing state. This prevents incorrect cleanup when:
        - Checkers fail to run
        - Thresholds are temporarily disabled
        - Database queries fail

        Args:
            warnings: Current warning events
            current_indicators: Current indicator values for validation
            geological_zone: Current geological zone for zone-specific threshold lookup
        """
        # Get set of indicator keys currently violating thresholds (indicator_name_zone)
        warned_indicator_keys = {
            f"{w.indicator_name}_{geological_zone}" for w in warnings
        }

        keys_to_remove = []
        for indicator_key in list(self.hysteresis_state.keys()):
            # Keep state if indicator is still violating (in warnings list)
            if indicator_key in warned_indicator_keys:
                logger.debug(
                    f"Hysteresis: Keeping state for {indicator_key} (still violating)"
                )
                continue

            state_meta = self.hysteresis_state[indicator_key]

            indicator_name = state_meta.get("indicator_name")
            state_zone = state_meta.get("zone")

            # Backward compatibility for legacy keys without metadata
            if indicator_name is None or state_zone is None:
                if "_" in indicator_key:
                    parts = indicator_key.rsplit("_", 1)
                    if len(parts) == 2:
                        indicator_name = indicator_name or parts[0]
                        state_zone = state_zone or parts[1]
                if indicator_name is None:
                    indicator_name = indicator_key
                if state_zone is None:
                    state_zone = geological_zone

            # Skip cleanup if this state belongs to a different zone
            if state_zone != geological_zone:
                logger.debug(
                    f"Hysteresis: Skipping cleanup for {indicator_key} (belongs to zone {state_zone})"
                )
                continue

            # Also keep state if indicator is not in current_indicators
            # (we can't verify it's normal without current data)
            if indicator_name not in current_indicators:
                logger.debug(
                    f"Hysteresis: Keeping state for {indicator_key} (no current data for {indicator_name})"
                )
                continue

            # Check if indicator value is actually within normal range
            current_value = current_indicators[indicator_name]
            threshold_config = self._get_threshold_config_for_cleanup(
                indicator_name, state_zone
            )

            if threshold_config and threshold_config.enabled:
                # Evaluate current value against thresholds
                warning_level = threshold_config.evaluate_threshold(current_value)

                # Only clear state if value is truly normal (no threshold violation)
                if warning_level is None:
                    keys_to_remove.append(indicator_key)
                    logger.debug(
                        f"Hysteresis: Clearing state for {indicator_key} "
                        f"(value {current_value:.2f}{threshold_config.indicator_unit or ''} "
                        f"returned to normal range)"
                    )
                else:
                    # Value still violates threshold but no warning was generated
                    # (possibly due to checker failure) - keep state
                    logger.warning(
                        f"Hysteresis: Keeping state for {indicator_key} "
                        f"(value {current_value:.2f} still violates {warning_level} threshold "
                        f"but no warning generated - possible checker issue)"
                    )
            else:
                # No threshold config or disabled - clear state
                # (indicator not being monitored anymore)
                keys_to_remove.append(indicator_key)
                logger.debug(
                    f"Hysteresis: Clearing state for {indicator_key} "
                    f"(threshold disabled or not configured for zone {state_zone})"
                )

        for key in keys_to_remove:
            del self.hysteresis_state[key]

    def _get_threshold_config_for_cleanup(
        self, indicator_name: str, geological_zone: str
    ) -> Optional[WarningThreshold]:
        """
        Get threshold config for cleanup validation

        Tries zone-specific config first, then falls back to 'all' zone.

        Args:
            indicator_name: Name of the indicator
            geological_zone: Current geological zone

        Returns:
            WarningThreshold config or None if not found
        """
        # Try zone-specific config first
        key = f"{indicator_name}_{geological_zone}"
        if key in self.thresholds:
            return self.thresholds[key]

        # Fall back to 'all' zone
        key = f"{indicator_name}_all"
        if key in self.thresholds:
            return self.thresholds[key]

        # Try direct match (backward compatibility)
        if indicator_name in self.thresholds:
            return self.thresholds[indicator_name]

        # Try to find any config for this indicator (any zone)
        for key, config in self.thresholds.items():
            if config.indicator_name == indicator_name:
                return config

        return None

    def _aggregate_combined_warnings(
        self, warnings: List[WarningEvent]
    ) -> List[WarningEvent]:
        """
        Aggregate multiple simultaneous warnings into combined alerts

        Implements FR-005, FR-007

        Combined warning criteria:
        - Multiple indicators violating thresholds simultaneously
        - High tunneling parameters (thrust/torque) + settlement rate increase

        Returns:
            Original warnings plus any new combined warnings
        """
        if len(warnings) < 2:
            return warnings

        # Group warnings by ring number
        warnings_by_ring: Dict[int, List[WarningEvent]] = {}
        for warning in warnings:
            ring = warning.ring_number
            if ring not in warnings_by_ring:
                warnings_by_ring[ring] = []
            warnings_by_ring[ring].append(warning)

        combined_warnings = []

        for ring_number, ring_warnings in warnings_by_ring.items():
            if len(ring_warnings) < 2:
                continue

            # Check for critical combinations
            combined = self._check_critical_combination(ring_warnings)
            if combined:
                combined_warnings.append(combined)

        return warnings + combined_warnings

    def _check_critical_combination(
        self, ring_warnings: List[WarningEvent]
    ) -> Optional[WarningEvent]:
        """
        Check if warnings represent a critical combination

        Critical combinations:
        1. Settlement + high thrust/torque
        2. Multiple ALARM level warnings
        3. 3+ simultaneous WARNING level warnings
        """
        indicator_names = [w.indicator_name for w in ring_warnings]
        warning_levels = [w.warning_level for w in ring_warnings]

        # Count alarms
        alarm_count = warning_levels.count("ALARM")
        warning_count = warning_levels.count("WARNING")

        # Criteria 1: Multiple alarms
        if alarm_count >= 2:
            return self._create_combined_warning(
                ring_warnings, "ALARM", "Multiple simultaneous alarms"
            )

        # Criteria 2: Settlement + tunneling parameter violations
        has_settlement = any("settlement" in name for name in indicator_names)
        has_tunneling_param = any(
            param in indicator_names
            for param in ["thrust_total", "torque_cutterhead", "chamber_pressure"]
        )

        if has_settlement and has_tunneling_param and (alarm_count >= 1 or warning_count >= 2):
            return self._create_combined_warning(
                ring_warnings,
                "ALARM",
                "Settlement violation with abnormal tunneling parameters"
            )

        # Criteria 3: Multiple warnings
        if warning_count >= 3:
            return self._create_combined_warning(
                ring_warnings, "WARNING", "Multiple simultaneous warnings"
            )

        return None

    def _create_combined_warning(
        self,
        source_warnings: List[WarningEvent],
        combined_level: str,
        description: str
    ) -> WarningEvent:
        """Create a combined warning event from multiple source warnings"""
        import uuid

        # Use first warning as template
        first = source_warnings[0]

        combined = WarningEvent(
            warning_id=str(uuid.uuid4()),
            warning_type="combined",
            warning_level=combined_level,
            ring_number=first.ring_number,
            timestamp=first.timestamp,
            indicator_name="combined",
            indicator_value=None,
            indicator_unit=None,
            status="active",
        )

        # Set combined indicators
        combined_indicators = [w.indicator_name for w in source_warnings]
        combined.set_combined_indicators(combined_indicators)

        # Use highest severity notification channels
        highest_severity = max(
            source_warnings,
            key=lambda w: {"ATTENTION": 1, "WARNING": 2, "ALARM": 3}.get(
                w.warning_level, 0
            ),
        )
        combined.set_notification_channels(
            highest_severity.get_notification_channels() or []
        )

        logger.warning(
            f"Combined warning created for ring {first.ring_number}: {description} "
            f"(indicators: {', '.join(combined_indicators)})"
        )

        return combined

    def _persist_warnings(self, warnings: List[WarningEvent]) -> List[WarningEvent]:
        """
        Persist warnings to database

        Implements FR-024, FR-026
        """
        persisted = []

        for warning in warnings:
            try:
                self.db.add(warning)
                self.db.commit()
                persisted.append(warning)
            except Exception as e:
                logger.error(
                    f"Failed to persist warning {warning.warning_id}: {e}",
                    exc_info=True
                )
                self.db.rollback()

        return persisted

    def _publish_warnings_to_mqtt(self, warnings: List[WarningEvent]):
        """
        Publish warnings to MQTT broker for real-time dashboard updates

        Implements FR-010, FR-011, FR-012

        Uses fire-and-forget approach to avoid blocking warning generation
        if MQTT broker is unavailable.
        """
        try:
            from edge.services.notification.mqtt_publisher import get_mqtt_publisher
            import asyncio
            import threading

            mqtt = get_mqtt_publisher()

            # Fire-and-forget: don't block if MQTT fails
            def publish_async():
                """Background thread to publish warnings"""
                try:
                    asyncio.run(mqtt.publish_warnings_batch(warnings))
                except Exception as e:
                    logger.error(f"Failed to publish {len(warnings)} warnings to MQTT: {e}")

            # Start background thread for MQTT publishing
            thread = threading.Thread(target=publish_async, daemon=True)
            thread.start()

            logger.debug(f"Started MQTT publishing thread for {len(warnings)} warnings")

        except Exception as e:
            # Don't fail warning generation if MQTT setup fails
            logger.error(f"Failed to initialize MQTT publishing: {e}", exc_info=True)

    def _load_threshold_configs(self) -> Dict[str, WarningThreshold]:
        """Load threshold configurations from database"""
        configs = {}

        try:
            thresholds = (
                self.db.query(WarningThreshold)
                .filter(WarningThreshold.enabled == True)
                .all()
            )

            for threshold in thresholds:
                key = f"{threshold.indicator_name}_{threshold.geological_zone}"
                configs[key] = threshold

            logger.info(f"Loaded {len(configs)} threshold configurations from database")
        except Exception as e:
            logger.error(f"Failed to load threshold configs: {e}", exc_info=True)

        return configs

    def reload_thresholds(self):
        """
        Reload threshold configurations from database

        Allows runtime reconfiguration without restart
        """
        self.thresholds = self._load_threshold_configs()
        self.threshold_checker = ThresholdChecker(self.thresholds)
        self.rate_detector = RateDetector(self.db, self.thresholds)
        self.predictive_checker = PredictiveChecker(self.db, self.thresholds)
        logger.info("Threshold configurations reloaded")
