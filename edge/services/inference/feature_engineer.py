"""
Feature Engineering Pipeline
Derives ML features from ring_summary data and geological context
Implements FR-008 to FR-014 from spec
"""
import numpy as np
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class FeatureVector:
    """Container for engineered features ready for ML inference"""
    ring_number: int
    features: Dict[str, float]
    feature_completeness: float  # 0.0-1.0
    quality_flag: str  # normal, geological_data_incomplete, cold_start
    geological_zone: Optional[str] = None


class FeatureEngineer:
    """
    Automated feature engineering from ring_summary data

    Features Generated:
    - Raw features: Aggregated PLC and attitude data (from ring_summary)
    - Derived features: Specific energy, ground loss, volume loss
    - Time-windowed features: Moving averages and trends from previous N rings
    - Geological features: Encoded soil type, overburden, groundwater
    """

    def __init__(self, version: str = "1.0.0", window_size: int = 10):
        self.version = version
        self.window_size = window_size  # Number of historical rings for trends

        # Feature definitions (required for validation)
        self.required_raw_features = [
            "mean_thrust", "max_thrust", "std_thrust",
            "mean_torque", "max_torque", "std_torque",
            "mean_chamber_pressure", "std_chamber_pressure",
            "mean_advance_rate", "max_advance_rate",
            "mean_grout_pressure", "grout_volume",
            "mean_pitch", "mean_roll", "mean_yaw",
            "horizontal_deviation_max", "vertical_deviation_max",
        ]

        self.derived_feature_names = [
            "specific_energy",
            "ground_loss_rate",
            "volume_loss_ratio",
            "thrust_torque_ratio",
            "advance_pressure_ratio",
        ]

        self.geological_feature_names = [
            "overburden_depth",
            "groundwater_level",
            # One-hot encoded soil types (populated dynamically)
        ]

    def engineer_features(
        self,
        ring_data: Dict[str, Any],
        historical_rings: List[Dict[str, Any]] = None,
        geological_data: Optional[Dict[str, Any]] = None
    ) -> FeatureVector:
        """
        Main feature engineering pipeline

        Args:
            ring_data: Current ring summary data (from ring_summary table)
            historical_rings: Previous N rings for time-windowed features
            geological_data: Geological context (soil_type, overburden, groundwater)

        Returns:
            FeatureVector with all engineered features
        """
        features = {}
        quality_flag = "normal"

        # Step 1: Extract raw features
        raw_features = self._extract_raw_features(ring_data)
        features.update(raw_features)

        # Step 2: Calculate derived indicators
        derived_features = self._calculate_derived_features(ring_data)
        features.update(derived_features)

        # Step 3: Add geological features
        if geological_data:
            geo_features = self._encode_geological_features(geological_data)
            features.update(geo_features)
        else:
            # Use fallback strategy
            logger.warning(f"Ring {ring_data['ring_number']}: Geological data missing, using fallback")
            geo_features = self._get_fallback_geological_features()
            features.update(geo_features)
            quality_flag = "geological_data_incomplete"

        # Step 4: Add time-windowed features (trends, moving averages)
        if historical_rings and len(historical_rings) >= 3:
            windowed_features = self._calculate_windowed_features(historical_rings)
            features.update(windowed_features)
        else:
            # Cold start: insufficient historical data
            logger.info(f"Ring {ring_data['ring_number']}: Insufficient history ({len(historical_rings or [])} rings), cold start mode")
            windowed_features = self._get_cold_start_features()
            features.update(windowed_features)
            if quality_flag == "normal":
                quality_flag = "cold_start"

        # Step 5: Normalize numeric features
        features = self._normalize_features(features)

        # Step 6: Calculate feature completeness
        completeness = self._calculate_completeness(features)

        return FeatureVector(
            ring_number=ring_data["ring_number"],
            features=features,
            feature_completeness=completeness,
            quality_flag=quality_flag,
            geological_zone=geological_data.get("soil_type") if geological_data else None
        )

    def _extract_raw_features(self, ring_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract raw aggregated features from ring_summary"""
        features = {}
        for feature_name in self.required_raw_features:
            value = ring_data.get(feature_name)
            features[feature_name] = float(value) if value is not None else np.nan
        return features

    def _calculate_derived_features(self, ring_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate physics-based derived indicators
        Implements FR-008
        """
        derived = {}

        # Specific Energy (kJ/m³): Energy per excavated volume
        # Formula: (Torque * 2π * RPM) / (Advance_rate * Cutterhead_area)
        mean_torque = ring_data.get("mean_torque")
        mean_advance_rate = ring_data.get("mean_advance_rate")

        if mean_torque and mean_advance_rate and mean_advance_rate > 0:
            # Assume 6.5m diameter cutterhead, RPM ~1.5 (typical)
            cutterhead_diameter = 6.5  # meters
            cutterhead_area = np.pi * (cutterhead_diameter / 2) ** 2
            rpm = 1.5  # revolutions per minute (typical)

            # Convert to kJ/m³
            specific_energy = (mean_torque * 2 * np.pi * rpm * 60) / (mean_advance_rate * cutterhead_area * 1000)
            derived["specific_energy"] = specific_energy
        else:
            derived["specific_energy"] = np.nan

        # Ground Loss Rate (m³): Theoretical volume - grout volume
        grout_volume = ring_data.get("grout_volume", 0)
        ring_length = 1.5  # meters (typical shield ring length)

        if ring_data.get("mean_advance_rate"):
            theoretical_volume = cutterhead_area * ring_length if 'cutterhead_area' in locals() else 50.0  # Fallback
            ground_loss = theoretical_volume - grout_volume
            derived["ground_loss_rate"] = ground_loss

            # Volume Loss Ratio (%): (ground_loss / theoretical_volume) * 100
            if theoretical_volume > 0:
                derived["volume_loss_ratio"] = (ground_loss / theoretical_volume) * 100
            else:
                derived["volume_loss_ratio"] = np.nan
        else:
            derived["ground_loss_rate"] = np.nan
            derived["volume_loss_ratio"] = np.nan

        # Thrust-Torque Ratio: Indicator of cutting efficiency
        mean_thrust = ring_data.get("mean_thrust")
        if mean_thrust and mean_torque and mean_torque > 0:
            derived["thrust_torque_ratio"] = mean_thrust / mean_torque
        else:
            derived["thrust_torque_ratio"] = np.nan

        # Advance-Pressure Ratio: Face stability indicator
        mean_chamber_pressure = ring_data.get("mean_chamber_pressure")
        if mean_advance_rate and mean_chamber_pressure and mean_chamber_pressure > 0:
            derived["advance_pressure_ratio"] = mean_advance_rate / mean_chamber_pressure
        else:
            derived["advance_pressure_ratio"] = np.nan

        return derived

    def _encode_geological_features(self, geological_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Encode geological parameters as features
        Implements FR-009, FR-010
        """
        features = {}

        # Numeric geological features
        features["overburden_depth"] = float(geological_data.get("overburden_depth", 0))
        features["groundwater_level"] = float(geological_data.get("groundwater_level", 0))
        features["proximity_to_structures"] = float(geological_data.get("proximity_to_structures", 999))

        # One-hot encode soil type
        soil_type = geological_data.get("soil_type", "unknown")
        soil_types = ["soft_clay", "sand_silt", "hard_rock", "mixed", "transition"]

        for st in soil_types:
            features[f"soil_type_{st}"] = 1.0 if soil_type == st else 0.0

        return features

    def _get_fallback_geological_features(self) -> Dict[str, float]:
        """
        Fallback geological features when data is missing
        Implements FR-014
        """
        features = {}

        # Use neutral/average values
        features["overburden_depth"] = 15.0  # Average depth
        features["groundwater_level"] = -3.0  # Average level
        features["proximity_to_structures"] = 999.0  # Far from structures

        # Unknown soil type (all zeros for one-hot)
        soil_types = ["soft_clay", "sand_silt", "hard_rock", "mixed", "transition"]
        for st in soil_types:
            features[f"soil_type_{st}"] = 0.0

        return features

    def _calculate_windowed_features(self, historical_rings: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Calculate time-windowed aggregate features
        Implements FR-012
        """
        features = {}

        # Use last N rings for window
        window = historical_rings[-self.window_size:]

        # Calculate moving averages for key parameters
        for param in ["mean_thrust", "mean_torque", "mean_chamber_pressure", "mean_advance_rate"]:
            values = [r.get(param) for r in window if r.get(param) is not None]
            if values:
                features[f"{param}_ma{self.window_size}"] = np.mean(values)
                features[f"{param}_std{self.window_size}"] = np.std(values)

                # Calculate trend (slope over window)
                if len(values) >= 3:
                    x = np.arange(len(values))
                    slope = np.polyfit(x, values, 1)[0]
                    features[f"{param}_trend"] = slope
                else:
                    features[f"{param}_trend"] = 0.0
            else:
                features[f"{param}_ma{self.window_size}"] = np.nan
                features[f"{param}_std{self.window_size}"] = np.nan
                features[f"{param}_trend"] = 0.0

        # Cumulative thrust trend over window
        thrust_values = [r.get("mean_thrust") for r in window if r.get("mean_thrust") is not None]
        if len(thrust_values) >= 2:
            features["cumulative_thrust_change"] = thrust_values[-1] - thrust_values[0]
        else:
            features["cumulative_thrust_change"] = 0.0

        return features

    def _get_cold_start_features(self) -> Dict[str, float]:
        """
        Default windowed features for cold start (insufficient history)
        Implements edge case from spec
        """
        features = {}

        # Set all windowed features to neutral values (zeros or means)
        for param in ["mean_thrust", "mean_torque", "mean_chamber_pressure", "mean_advance_rate"]:
            features[f"{param}_ma{self.window_size}"] = 0.0
            features[f"{param}_std{self.window_size}"] = 0.0
            features[f"{param}_trend"] = 0.0

        features["cumulative_thrust_change"] = 0.0

        return features

    def _normalize_features(self, features: Dict[str, float]) -> Dict[str, float]:
        """
        Normalize numeric features
        Implements FR-011

        Note: In production, use fitted scalers from training.
        This is a simplified version using reasonable ranges.
        """
        # Define feature ranges (from domain knowledge)
        # In production, these would come from training data scalers
        feature_ranges = {
            "mean_thrust": (8000, 18000),  # kN
            "mean_torque": (500, 1500),     # kNm
            "mean_chamber_pressure": (100, 400),  # kPa
            "mean_advance_rate": (10, 60),  # mm/min
            "overburden_depth": (5, 30),    # m
            "specific_energy": (0, 100),    # kJ/m³
        }

        # Min-max normalization for specified features
        normalized = {}
        for key, value in features.items():
            if np.isnan(value):
                normalized[key] = value  # Keep NaN
            elif any(key.startswith(base) for base in feature_ranges):
                # Find matching range
                base_key = next((k for k in feature_ranges if key.startswith(k)), None)
                if base_key:
                    min_val, max_val = feature_ranges[base_key]
                    normalized[key] = (value - min_val) / (max_val - min_val) if max_val > min_val else value
                else:
                    normalized[key] = value
            else:
                # Keep as-is (one-hot encoded, already 0/1)
                normalized[key] = value

        return normalized

    def _calculate_completeness(self, features: Dict[str, float]) -> float:
        """
        Calculate feature completeness ratio
        """
        total_features = len(features)
        if total_features == 0:
            return 0.0

        complete_features = sum(1 for v in features.values() if not np.isnan(v))
        return complete_features / total_features

    def validate_derived_features(self, ring_data: Dict[str, Any], manual_calculations: Dict[str, float]) -> bool:
        """
        Validate derived features match manual calculations within 2% tolerance
        Implements FR-013
        """
        derived = self._calculate_derived_features(ring_data)

        for feature_name, manual_value in manual_calculations.items():
            if feature_name in derived:
                calculated_value = derived[feature_name]
                if not np.isnan(calculated_value) and not np.isnan(manual_value):
                    tolerance = 0.02  # 2%
                    relative_error = abs(calculated_value - manual_value) / abs(manual_value) if manual_value != 0 else 0

                    if relative_error > tolerance:
                        logger.error(
                            f"Feature validation failed for {feature_name}: "
                            f"calculated={calculated_value:.3f}, manual={manual_value:.3f}, "
                            f"error={relative_error*100:.1f}%"
                        )
                        return False

        return True
