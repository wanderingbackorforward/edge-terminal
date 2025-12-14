"""
T048: Ring Data Aggregation and Alignment
Implements the core align_data() function for spatio-temporal alignment
Based on pseudocode from plan.md lines 807-935
"""
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime
import yaml
import logging

logger = logging.getLogger(__name__)


def align_data(
    ring_number: int,
    db: Any,  # SQLite database manager
    config_path: str = "edge/config/alignment.yaml"
) -> Dict[str, Any]:
    """
    Core alignment function: aggregate high-frequency data for a ring
    and associate time-lagged monitoring data.

    This function implements the spatio-temporal alignment algorithm that:
    1. Determines ring excavation time window
    2. Aggregates high-frequency PLC data (1Hz) → statistics
    3. Aggregates high-frequency attitude data (1Hz) → statistics
    4. Calculates derived engineering indicators
    5. Associates time-lagged monitoring data (settlement with 6-8 hour lag)
    6. Returns complete feature vector for the ring

    Args:
        ring_number: Tunnel ring identifier (sequential integer)
        db: Database manager instance with query/execute methods
        config_path: Path to alignment configuration YAML

    Returns:
        feature_vector: Dict with aggregated features and target values

    Raises:
        ValueError: If ring not found or data insufficient
    """
    # Load configuration
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Step 1: Get ring time window
    ring_window = db.query(
        "SELECT start_time, end_time FROM ring_summary WHERE ring_number = ?",
        (ring_number,)
    ).fetchone()

    if not ring_window:
        raise ValueError(f"Ring {ring_number} not found in ring_summary")

    start_time = ring_window['start_time']
    end_time = ring_window['end_time']

    logger.info(
        f"Aligning data for ring {ring_number}: "
        f"[{datetime.fromtimestamp(start_time)} - {datetime.fromtimestamp(end_time)}]"
    )

    # Step 2: Query high-frequency PLC data within ring window
    plc_data = db.query(
        """SELECT tag_name, value
           FROM plc_logs
           WHERE timestamp >= ? AND timestamp <= ?
           AND data_quality_flag IN ('raw', 'interpolated', 'calibrated')
           AND ring_number = ?""",
        (start_time, end_time, ring_number)
    ).fetchall()

    # Step 3: Aggregate PLC data into statistics
    plc_features = aggregate_plc_data(plc_data, config)

    # Step 4: Query attitude data and aggregate
    attitude_data = db.query(
        """SELECT pitch, roll, yaw, horizontal_deviation, vertical_deviation
           FROM attitude_logs
           WHERE timestamp >= ? AND timestamp <= ?
           AND ring_number = ?""",
        (start_time, end_time, ring_number)
    ).fetchall()

    attitude_features = aggregate_attitude_data(attitude_data, config)

    # Step 5: Calculate derived engineering indicators
    derived_features = calculate_derived_indicators(
        plc_features,
        attitude_features,
        config['ring_geometry']
    )

    # Step 6: Query time-lagged monitoring data (settlement with 6-8 hour lag)
    lag_config = config['time_lag_windows']['surface_settlement']
    lag_window_start = end_time + (lag_config['min_hours'] * 3600)
    lag_window_end = end_time + (lag_config['max_hours'] * 3600)

    settlement_data = db.query(
        """SELECT AVG(value) as avg_settlement
           FROM monitoring_logs
           WHERE sensor_type = 'surface_settlement'
           AND timestamp >= ? AND timestamp <= ?
           AND ring_number = ?""",
        (lag_window_start, lag_window_end, ring_number)
    ).fetchone()

    target = {
        "settlement_value": settlement_data['avg_settlement'] if settlement_data else None
    }

    # Step 7: Combine all features
    feature_vector = {
        "ring_number": ring_number,
        "start_time": start_time,
        "end_time": end_time,
        **plc_features,
        **attitude_features,
        **derived_features,
        **target
    }

    # Step 8: Assess data completeness
    completeness = assess_data_completeness(
        plc_data=plc_data,
        attitude_data=attitude_data,
        settlement=target['settlement_value'],
        config=config['data_completeness']
    )
    feature_vector['data_completeness_flag'] = completeness

    # Step 9: Update ring_summary table
    update_ring_summary(db, ring_number, feature_vector)

    logger.info(
        f"Ring {ring_number} alignment complete: "
        f"completeness={completeness}, settlement={target['settlement_value']}"
    )

    return feature_vector


def aggregate_plc_data(plc_data: List[Dict], config: Dict) -> Dict[str, Optional[float]]:
    """
    Aggregate high-frequency PLC readings into statistical features.

    Args:
        plc_data: List of PLC readings with tag_name and value
        config: Alignment configuration

    Returns:
        Dictionary of aggregated features (mean, max, min, std per tag)
    """
    features: Dict[str, Optional[float]] = {}

    # Key PLC tags to aggregate
    key_tags = [
        "thrust_total",
        "torque_cutterhead",
        "chamber_pressure",
        "advance_rate",
        "grout_pressure",
        "grout_volume"
    ]

    # Group by tag name
    tag_groups: Dict[str, List[float]] = {}
    for reading in plc_data:
        tag_name = reading['tag_name']
        if tag_name in key_tags:
            if tag_name not in tag_groups:
                tag_groups[tag_name] = []
            tag_groups[tag_name].append(reading['value'])

    # Calculate statistics for each tag
    agg_funcs = config['feature_engineering']['aggregation_functions']

    for tag_name in key_tags:
        values = tag_groups.get(tag_name, [])

        if len(values) > 0:
            np_values = np.array(values)
            if 'mean' in agg_funcs:
                features[f'mean_{tag_name}'] = float(np.mean(np_values))
            if 'max' in agg_funcs:
                features[f'max_{tag_name}'] = float(np.max(np_values))
            if 'min' in agg_funcs:
                features[f'min_{tag_name}'] = float(np.min(np_values))
            if 'std' in agg_funcs:
                features[f'std_{tag_name}'] = float(np.std(np_values))
        else:
            # No data for this tag
            for func in agg_funcs:
                features[f'{func}_{tag_name}'] = None

    return features


def aggregate_attitude_data(attitude_data: List[Dict], config: Dict) -> Dict[str, Optional[float]]:
    """
    Aggregate high-frequency attitude readings into statistical features.

    Args:
        attitude_data: List of attitude readings
        config: Alignment configuration

    Returns:
        Dictionary of aggregated attitude features
    """
    features: Dict[str, Optional[float]] = {}

    fields = ['pitch', 'roll', 'yaw', 'horizontal_deviation', 'vertical_deviation']
    agg_funcs = config['feature_engineering']['aggregation_functions']

    for field in fields:
        values = [reading[field] for reading in attitude_data if reading[field] is not None]

        if len(values) > 0:
            np_values = np.array(values)
            if 'mean' in agg_funcs:
                features[f'mean_{field}'] = float(np.mean(np_values))
            if 'max' in agg_funcs:
                features[f'max_{field}'] = float(np.max(np_values))
        else:
            if 'mean' in agg_funcs:
                features[f'mean_{field}'] = None
            if 'max' in agg_funcs:
                features[f'max_{field}'] = None

    return features


def calculate_derived_indicators(
    plc_features: Dict,
    attitude_features: Dict,
    ring_geometry: Dict
) -> Dict[str, Optional[float]]:
    """
    Calculate physics-based derived indicators.

    Implements engineering formulas:
    - Specific Energy: E_s = (T * ω) / (A * v)
    - Ground Loss Rate: V_loss = V_theoretical - V_grout
    - Volume Loss Ratio: VL% = V_loss / V_theoretical * 100

    Args:
        plc_features: Aggregated PLC features
        attitude_features: Aggregated attitude features
        ring_geometry: Ring dimensions (diameter, width)

    Returns:
        Dictionary of derived indicators
    """
    derived: Dict[str, Optional[float]] = {}

    # Specific energy: E_s = (T * ω) / (A * v)
    # where T=torque (kN·m), ω=rotational speed (rad/s), A=area (m²), v=velocity (m/s)
    torque = plc_features.get('mean_torque_cutterhead', 0) or 0  # kN·m
    advance_rate = plc_features.get('mean_advance_rate', 1) or 1  # mm/min

    # Calculate excavation area
    diameter = ring_geometry['diameter']  # m
    excavation_area = np.pi * (diameter ** 2) / 4  # m²

    # Convert units
    # Assume cutterhead RPM available or use typical value
    rpm = 2.0  # Typical value, should come from PLC if available
    omega = rpm * 2 * np.pi / 60  # rad/s
    velocity = (advance_rate / 1000) / 60  # m/s

    if velocity > 0:
        specific_energy = (torque * 1000 * omega) / (excavation_area * velocity)  # J/m³
        derived['specific_energy'] = specific_energy / 1e6  # MJ/m³
    else:
        derived['specific_energy'] = None

    # Ground loss rate: V_loss = V_theoretical - V_grout
    ring_width = ring_geometry['width']  # m
    theoretical_volume = excavation_area * ring_width  # m³
    grout_volume = plc_features.get('grout_volume', 0) or 0  # m³

    ground_loss = theoretical_volume - grout_volume
    derived['ground_loss_rate'] = ground_loss

    # Volume loss ratio: VL% = V_loss / V_theoretical * 100
    if theoretical_volume > 0:
        derived['volume_loss_ratio'] = (ground_loss / theoretical_volume) * 100
    else:
        derived['volume_loss_ratio'] = None

    return derived


def assess_data_completeness(
    plc_data: List[Dict],
    attitude_data: List[Dict],
    settlement: Optional[float],
    config: Dict
) -> str:
    """
    Assess data completeness for the ring.

    Args:
        plc_data: PLC readings
        attitude_data: Attitude readings
        settlement: Settlement value
        config: Completeness thresholds

    Returns:
        Completeness flag: 'complete', 'partial', or 'incomplete'
    """
    plc_count = len(plc_data)
    attitude_count = len(attitude_data)

    has_min_plc = plc_count >= config['min_plc_readings']
    has_min_attitude = attitude_count >= config['min_attitude_readings']
    has_settlement = settlement is not None if config['required_settlement'] else True

    if has_min_plc and has_min_attitude and has_settlement:
        return 'complete'
    elif has_min_plc or has_min_attitude:
        return 'partial'
    else:
        return 'incomplete'


def update_ring_summary(db: Any, ring_number: int, feature_vector: Dict) -> None:
    """
    Update ring_summary table with aggregated features.

    Args:
        db: Database manager
        ring_number: Ring number
        feature_vector: Aggregated features
    """
    db.execute(
        """UPDATE ring_summary SET
           mean_thrust = ?, max_thrust = ?, min_thrust = ?, std_thrust = ?,
           mean_torque = ?, max_torque = ?, min_torque = ?, std_torque = ?,
           mean_chamber_pressure = ?, max_chamber_pressure = ?, std_chamber_pressure = ?,
           mean_advance_rate = ?, max_advance_rate = ?,
           mean_grout_pressure = ?, grout_volume = ?,
           mean_pitch = ?, mean_roll = ?, mean_yaw = ?,
           max_pitch = ?, max_roll = ?,
           horizontal_deviation_max = ?, vertical_deviation_max = ?,
           specific_energy = ?, ground_loss_rate = ?, volume_loss_ratio = ?,
           settlement_value = ?,
           data_completeness_flag = ?,
           updated_at = ?
           WHERE ring_number = ?""",
        (
            feature_vector.get('mean_thrust_total'),
            feature_vector.get('max_thrust_total'),
            feature_vector.get('min_thrust_total'),
            feature_vector.get('std_thrust_total'),
            feature_vector.get('mean_torque_cutterhead'),
            feature_vector.get('max_torque_cutterhead'),
            feature_vector.get('min_torque_cutterhead'),
            feature_vector.get('std_torque_cutterhead'),
            feature_vector.get('mean_chamber_pressure'),
            feature_vector.get('max_chamber_pressure'),
            feature_vector.get('std_chamber_pressure'),
            feature_vector.get('mean_advance_rate'),
            feature_vector.get('max_advance_rate'),
            feature_vector.get('mean_grout_pressure'),
            feature_vector.get('grout_volume'),
            feature_vector.get('mean_pitch'),
            feature_vector.get('mean_roll'),
            feature_vector.get('mean_yaw'),
            feature_vector.get('max_pitch'),
            feature_vector.get('max_roll'),
            feature_vector.get('max_horizontal_deviation'),
            feature_vector.get('max_vertical_deviation'),
            feature_vector.get('specific_energy'),
            feature_vector.get('ground_loss_rate'),
            feature_vector.get('volume_loss_ratio'),
            feature_vector.get('settlement_value'),
            feature_vector.get('data_completeness_flag'),
            datetime.utcnow().timestamp(),
            ring_number
        )
    )
    db.commit()
