"""
T046: Derived Engineering Indicator Calculator
Calculates derived indicators from aggregated data
Includes specific energy, ground loss rate, volume loss ratio, etc.
"""
import logging
from typing import Dict, Any, Optional
import math

logger = logging.getLogger(__name__)


class DerivedIndicatorCalculator:
    """
    Calculates derived engineering indicators for tunneling analysis.

    Indicators:
    - Specific energy (MJ/m³)
    - Ground loss rate (m³)
    - Volume loss ratio (%)
    - Penetration efficiency
    - Torque/thrust ratio
    - Power efficiency
    """

    def __init__(
        self,
        tunnel_diameter: float = 6.2,  # meters
        ring_width: float = 1.5  # meters
    ):
        """
        Initialize calculator.

        Args:
            tunnel_diameter: Tunnel excavation diameter (m)
            ring_width: Ring width/advance per ring (m)
        """
        self.tunnel_diameter = tunnel_diameter
        self.ring_width = ring_width

        # Calculate excavation volume per ring
        self.excavation_volume = self._calculate_excavation_volume()

        self.stats = {
            'rings_processed': 0
        }

    def _calculate_excavation_volume(self) -> float:
        """
        Calculate theoretical excavation volume per ring.

        Returns:
            Volume in cubic meters
        """
        radius = self.tunnel_diameter / 2
        area = math.pi * (radius ** 2)
        volume = area * self.ring_width
        return volume

    def calculate_specific_energy(
        self,
        mean_cutterhead_power: float,
        mean_penetration_rate: float,
        duration_minutes: float
    ) -> Optional[float]:
        """
        Calculate specific energy (energy per unit volume excavated).

        SE = Total Energy / Excavated Volume (MJ/m³)

        Args:
            mean_cutterhead_power: Average cutterhead power (kW)
            mean_penetration_rate: Average penetration rate (mm/min)
            duration_minutes: Ring construction duration (minutes)

        Returns:
            Specific energy (MJ/m³) or None on error
        """
        try:
            if mean_penetration_rate <= 0:
                logger.warning("Invalid penetration rate for specific energy calculation")
                return None

            # Total energy consumed (kWh -> MJ)
            total_energy_kwh = mean_cutterhead_power * (duration_minutes / 60)
            total_energy_mj = total_energy_kwh * 3.6  # 1 kWh = 3.6 MJ

            # Excavated volume
            excavated_volume = self.excavation_volume

            # Specific energy
            specific_energy = total_energy_mj / excavated_volume

            return round(specific_energy, 2)

        except Exception as e:
            logger.error(f"Error calculating specific energy: {e}")
            return None

    def calculate_ground_loss_rate(
        self,
        mean_grout_volume: float,
        tail_void_volume: Optional[float] = None
    ) -> Optional[float]:
        """
        Calculate ground loss rate.

        Ground loss = Volume of ground lost to settlement
                    ≈ Grout volume - Tail void volume

        Args:
            mean_grout_volume: Grouting volume injected (m³)
            tail_void_volume: Theoretical tail void volume (m³)
                            If None, calculated from geometry

        Returns:
            Ground loss rate (m³) or None
        """
        try:
            if tail_void_volume is None:
                # Estimate tail void from geometry
                # Typical shield has ~50mm overcut
                overcut_diameter = self.tunnel_diameter + 0.1  # 50mm radius overcut
                shield_diameter = self.tunnel_diameter - 0.05  # Shield slightly smaller

                overcut_area = math.pi * ((overcut_diameter/2)**2 - (shield_diameter/2)**2)
                tail_void_volume = overcut_area * self.ring_width

            # Ground loss = excess grout volume
            ground_loss = mean_grout_volume - tail_void_volume

            return round(ground_loss, 3)

        except Exception as e:
            logger.error(f"Error calculating ground loss rate: {e}")
            return None

    def calculate_volume_loss_ratio(
        self,
        ground_loss_rate: float
    ) -> Optional[float]:
        """
        Calculate volume loss ratio (percentage).

        VL% = (Ground Loss / Excavated Volume) * 100

        Args:
            ground_loss_rate: Ground loss volume (m³)

        Returns:
            Volume loss ratio (%) or None
        """
        try:
            if ground_loss_rate < 0:
                logger.warning("Negative ground loss detected, setting to 0")
                ground_loss_rate = 0

            volume_loss_ratio = (ground_loss_rate / self.excavation_volume) * 100

            return round(volume_loss_ratio, 2)

        except Exception as e:
            logger.error(f"Error calculating volume loss ratio: {e}")
            return None

    def calculate_penetration_efficiency(
        self,
        mean_penetration_rate: float,
        mean_thrust: float,
        mean_cutterhead_power: float
    ) -> Optional[float]:
        """
        Calculate penetration efficiency.

        Efficiency = Penetration Rate / (Thrust × Power)

        Higher value indicates more efficient excavation.

        Args:
            mean_penetration_rate: Penetration rate (mm/min)
            mean_thrust: Thrust force (kN)
            mean_cutterhead_power: Cutterhead power (kW)

        Returns:
            Efficiency index or None
        """
        try:
            if mean_thrust <= 0 or mean_cutterhead_power <= 0:
                return None

            # Normalize to consistent units
            penetration_m_min = mean_penetration_rate / 1000  # mm/min -> m/min

            # Efficiency metric (dimensionless index)
            efficiency = penetration_m_min / (mean_thrust * mean_cutterhead_power) * 1e6

            return round(efficiency, 4)

        except Exception as e:
            logger.error(f"Error calculating penetration efficiency: {e}")
            return None

    def calculate_torque_thrust_ratio(
        self,
        mean_torque: float,
        mean_thrust: float
    ) -> Optional[float]:
        """
        Calculate torque/thrust ratio.

        Ratio = Torque (kNm) / Thrust (kN)

        Typical values: 0.01 - 0.15 depending on geology.

        Args:
            mean_torque: Cutterhead torque (kNm)
            mean_thrust: Total thrust (kN)

        Returns:
            Torque/thrust ratio or None
        """
        try:
            if mean_thrust <= 0:
                return None

            ratio = mean_torque / mean_thrust

            return round(ratio, 4)

        except Exception as e:
            logger.error(f"Error calculating torque/thrust ratio: {e}")
            return None

    def calculate_power_efficiency(
        self,
        mean_total_power: float,
        mean_cutterhead_power: float
    ) -> Optional[float]:
        """
        Calculate power efficiency (cutterhead power / total power).

        Indicates how much total power goes to actual excavation.

        Args:
            mean_total_power: Total system power (kW)
            mean_cutterhead_power: Cutterhead power (kW)

        Returns:
            Efficiency ratio (0-1) or None
        """
        try:
            if mean_total_power <= 0:
                return None

            efficiency = mean_cutterhead_power / mean_total_power

            return round(efficiency, 3)

        except Exception as e:
            logger.error(f"Error calculating power efficiency: {e}")
            return None

    def calculate_all_indicators(
        self,
        plc_features: Dict[str, float],
        duration_minutes: float
    ) -> Dict[str, Optional[float]]:
        """
        Calculate all derived indicators from aggregated features.

        Args:
            plc_features: Dictionary with aggregated PLC features
            duration_minutes: Ring construction duration

        Returns:
            Dictionary with all derived indicators
        """
        indicators = {}

        # Specific energy
        if all(k in plc_features for k in ['mean_cutterhead_power', 'mean_penetration_rate']):
            indicators['specific_energy'] = self.calculate_specific_energy(
                plc_features['mean_cutterhead_power'],
                plc_features['mean_penetration_rate'],
                duration_minutes
            )

        # Ground loss rate
        if 'mean_grout_volume' in plc_features:
            ground_loss = self.calculate_ground_loss_rate(
                plc_features['mean_grout_volume']
            )
            indicators['ground_loss_rate'] = ground_loss

            # Volume loss ratio (depends on ground loss)
            if ground_loss is not None:
                indicators['volume_loss_ratio'] = self.calculate_volume_loss_ratio(
                    ground_loss
                )

        # Penetration efficiency
        if all(k in plc_features for k in ['mean_penetration_rate', 'mean_thrust',
                                             'mean_cutterhead_power']):
            indicators['penetration_efficiency'] = self.calculate_penetration_efficiency(
                plc_features['mean_penetration_rate'],
                plc_features['mean_thrust'],
                plc_features['mean_cutterhead_power']
            )

        # Torque/thrust ratio
        if all(k in plc_features for k in ['mean_torque', 'mean_thrust']):
            indicators['torque_thrust_ratio'] = self.calculate_torque_thrust_ratio(
                plc_features['mean_torque'],
                plc_features['mean_thrust']
            )

        # Power efficiency
        if all(k in plc_features for k in ['mean_total_power', 'mean_cutterhead_power']):
            indicators['power_efficiency'] = self.calculate_power_efficiency(
                plc_features['mean_total_power'],
                plc_features['mean_cutterhead_power']
            )

        self.stats['rings_processed'] += 1

        logger.info(f"Calculated {len(indicators)} derived indicators")

        return indicators

    def get_statistics(self) -> Dict[str, Any]:
        """Get calculator statistics"""
        return {
            'rings_processed': self.stats['rings_processed'],
            'tunnel_diameter': self.tunnel_diameter,
            'ring_width': self.ring_width,
            'excavation_volume': round(self.excavation_volume, 3)
        }


# Example usage
if __name__ == "__main__":
    calculator = DerivedIndicatorCalculator(
        tunnel_diameter=6.2,
        ring_width=1.5
    )

    # Example PLC features from aggregator
    plc_features = {
        'mean_cutterhead_power': 800,  # kW
        'mean_penetration_rate': 15,  # mm/min
        'mean_thrust': 12000,  # kN
        'mean_torque': 900,  # kNm
        'mean_total_power': 1200,  # kW
        'mean_grout_volume': 5.5,  # m³
    }

    duration_minutes = 45  # Ring construction duration

    # Calculate all indicators
    indicators = calculator.calculate_all_indicators(plc_features, duration_minutes)

    print("Derived Engineering Indicators:")
    print("=" * 50)
    for name, value in indicators.items():
        if value is not None:
            print(f"{name:.<30} {value:.3f}")
        else:
            print(f"{name:.<30} N/A")

    print("\nCalculator statistics:")
    print(calculator.get_statistics())
