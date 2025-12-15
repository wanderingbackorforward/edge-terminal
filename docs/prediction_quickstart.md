# Prediction Module Quick Start Guide

This guide shows you how to use the Edge ML Prediction Module to make settlement predictions.

---

## Prerequisites

- Edge database with ring_summary data
- ONNX model file (e.g., `settlement_lgb_v1.onnx`)
- Python dependencies:
  ```bash
  pip install onnxruntime numpy sqlalchemy
  ```

---

## 1. Initialize the Prediction System

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from edge.services.inference import PredictionManager

# Create database session
engine = create_engine("sqlite:///data/edge.db")
Session = sessionmaker(bind=engine)
db = Session()

# Initialize prediction manager
manager = PredictionManager(
    db_session=db,
    models_dir="edge/models_onnx",
    enable_auto_monitoring=True,
    monitoring_interval=50  # Evaluate every 50 predictions
)

# Load active models from database
manager.initialize()
print(f"Loaded models: {manager.model_loader.list_loaded_models()}")
```

---

## 2. Deploy a New Model

```python
# Deploy ONNX model
success = manager.deploy_model(
    model_file_path="models/settlement_lgb_v1.0.onnx",
    model_name="settlement_lgb_soft_clay",
    model_version="1.0.0",
    model_type="lightgbm",
    geological_zone="soft_clay",
    validation_metrics={
        "r2": 0.96,
        "rmse": 2.1,
        "mae": 1.6
    },
    feature_list=[
        # Raw features (must match model training order)
        "mean_thrust", "max_thrust", "std_thrust",
        "mean_torque", "max_torque", "std_torque",
        "mean_chamber_pressure", "std_chamber_pressure",
        "mean_advance_rate", "max_advance_rate",
        "mean_grout_pressure", "grout_volume",
        "mean_pitch", "mean_roll", "mean_yaw",
        "horizontal_deviation_max", "vertical_deviation_max",

        # Derived features
        "specific_energy", "ground_loss_rate", "volume_loss_ratio",
        "thrust_torque_ratio", "advance_pressure_ratio",

        # Geological features
        "overburden_depth", "groundwater_level", "proximity_to_structures",
        "soil_type_soft_clay", "soil_type_sand_silt", "soil_type_hard_rock",
        "soil_type_mixed", "soil_type_transition",

        # Time-windowed features (10-ring window)
        "mean_thrust_ma10", "mean_thrust_std10", "mean_thrust_trend",
        "mean_torque_ma10", "mean_torque_std10", "mean_torque_trend",
        "mean_chamber_pressure_ma10", "mean_chamber_pressure_std10", "mean_chamber_pressure_trend",
        "mean_advance_rate_ma10", "mean_advance_rate_std10", "mean_advance_rate_trend",
        "cumulative_thrust_change"
    ],
    activate=True  # Immediately activate for predictions
)

if success:
    print("Model deployed successfully!")
else:
    print("Model deployment failed")
```

---

## 3. Make Predictions

### Single Prediction

```python
# Predict settlement for ring 100
result = manager.predict(
    ring_number=100,
    geological_data={
        "soil_type": "soft_clay",
        "overburden_depth": 15.0,  # meters
        "groundwater_level": -3.0,  # meters (negative = below surface)
        "proximity_to_structures": 50.0  # meters
    }
)

# Display results
print(f"\n=== Prediction for Ring {result.ring_number} ===")
print(f"Model: {result.model_name} v{result.model_version}")
print(f"Predicted Settlement: {result.predicted_settlement:.2f} mm")
print(f"95% Confidence Interval: [{result.settlement_lower_bound:.2f}, {result.settlement_upper_bound:.2f}] mm")
print(f"Prediction Confidence: {result.prediction_confidence:.1%}")
print(f"Inference Time: {result.inference_time_ms:.1f} ms")
print(f"Feature Completeness: {result.feature_completeness:.1%}")
print(f"Quality Flag: {result.quality_flag}")
```

**Example Output**:

```
=== Prediction for Ring 100 ===
Model: settlement_lgb_soft_clay v1.0.0
Predicted Settlement: 8.50 mm
95% Confidence Interval: [6.80, 10.20] mm
Prediction Confidence: 92.0%
Inference Time: 3.2 ms
Feature Completeness: 95.0%
Quality Flag: normal
```

**Understanding Confidence vs. Confidence Intervals**:

- **Prediction Confidence** (0.92 = 92%): The model's certainty in its prediction. High confidence means the model has seen similar data during training. Extracted from 2, 4, 8, or 12 output models.

- **Confidence Interval** (6.80-10.20 mm): The range where the true value is expected to lie with 95% probability. Wide intervals indicate higher uncertainty in the prediction magnitude. Extracted from 3, 4, 6, 8, 9, or 12 output models.

**Fallback Behavior**:

If your model doesn't provide confidence or CI:
- Missing confidence → defaults to 0.85 (85%)
- Missing CI → automatically generates ±20% bounds (e.g., 8.5mm → [6.8, 10.2])
- Partial CI (e.g., only lower bound) → preserves provided bound, generates the other

### Batch Predictions

```python
# Predict for multiple rings
results = manager.predict_batch(
    ring_numbers=[101, 102, 103, 104, 105],
    geological_data_map={
        101: {"soil_type": "soft_clay", "overburden_depth": 15.0, ...},
        102: {"soil_type": "soft_clay", "overburden_depth": 15.5, ...},
        103: {"soil_type": "sand_silt", "overburden_depth": 16.0, ...},
        104: {"soil_type": "sand_silt", "overburden_depth": 16.5, ...},
        105: {"soil_type": "transition", "overburden_depth": 17.0, ...},
    }
)

for r in results:
    print(f"Ring {r.ring_number}: {r.predicted_settlement:.2f}mm [{r.quality_flag}]")
```

### Multi-Target Predictions

If your ONNX model supports multi-target outputs (displacement and groundwater in addition to settlement):

```python
# Deploy a multi-target model
# The model must have 9 outputs:
#   - settlement, settlement_lower, settlement_upper
#   - displacement, displacement_lower, displacement_upper
#   - groundwater, groundwater_lower, groundwater_upper

manager.deploy_model(
    model_file_path="models/multi_target_lgb_v1.onnx",
    model_name="multi_target_soft_clay",
    model_version="1.0.0",
    model_type="lightgbm",
    geological_zone="soft_clay",
    validation_metrics={"r2": 0.95, "rmse": 2.3},
    feature_list=[...],  # Same features as single-target
    activate=True
)

# Make prediction
result = manager.predict(ring_number=100, geological_data={...})

# Access all targets
print(f"\n=== Multi-Target Prediction for Ring {result.ring_number} ===")

# Settlement (primary target)
print(f"Settlement: {result.predicted_settlement:.2f}mm")
print(f"  95% CI: [{result.settlement_lower_bound:.2f}, {result.settlement_upper_bound:.2f}]")

# Displacement (secondary target)
if result.predicted_displacement is not None:
    print(f"Displacement: {result.predicted_displacement:.2f}mm")
    print(f"  95% CI: [{result.displacement_lower_bound:.2f}, {result.displacement_upper_bound:.2f}]")

# Groundwater change (tertiary target)
if result.predicted_groundwater_change is not None:
    print(f"Groundwater Change: {result.predicted_groundwater_change:.2f}m")
    print(f"  95% CI: [{result.groundwater_lower_bound:.2f}, {result.groundwater_upper_bound:.2f}]")
```

**ONNX Model Output Format**:

The system supports 8 different ONNX output formats. Choose the format that matches your model's capabilities:

| Outputs | Format | Description | Use Case | Version |
|---------|--------|-------------|----------|---------|
| **1** | `[settlement]` | Point estimate only | Simple regression models | - |
| **2a** | `[settlement, lower_bound]` | Point estimate + lower CI bound | Legacy partial CI models | v1_lower_bound |
| **2b** | `[settlement, confidence]` | Point estimate + confidence score (0.0-1.0) | Models with prediction confidence | v2_confidence (default) |
| **3** | `[settlement, lower, upper]` | Point estimate + 95% CI | Models with uncertainty quantification | - |
| **4** | `[settlement, confidence, lower, upper]` | Point estimate + confidence + CI | Advanced single-target models | - |
| **6** | `[settlement, lower, upper, displacement, disp_lower, disp_upper]` | 2-target with CI | Settlement + displacement prediction | - |
| **8** | `[settlement, conf, lower, upper, displacement, disp_conf, disp_lower, disp_upper]` | 2-target with confidence + CI | Advanced 2-target models | - |
| **9** | `[settlement, lower, upper, displacement, disp_lower, disp_upper, groundwater, gw_lower, gw_upper]` | 3-target with CI | Full multi-target prediction | - |
| **12** | `[settlement, conf, lower, upper, displacement, disp_conf, disp_lower, disp_upper, groundwater, gw_conf, gw_lower, gw_upper]` | 3-target with confidence + CI | Advanced 3-target models | - |

**Notes**:
- All outputs should have shape `(1, 1)` (batch size 1, single value)
- **2-output models** require specifying `output_format_version` during deployment (see below)
- Confidence scores should be in range [0.0, 1.0] (e.g., 0.92 = 92% confidence)
- CI bounds should use the same units as predictions (mm for settlement/displacement, m for groundwater)
- If your model doesn't provide CI bounds, the system will automatically generate ±20% fallback bounds
- If your model doesn't provide confidence, the system will default to 0.85 (85% confidence)

**For 2-Output Models**:

```python
# Deploy v2 model (with confidence) - default for new models
manager.deploy_model(
    model_file_path="models/settlement_v2.onnx",
    model_name="settlement_soft_clay_v2",
    output_format_version="v2_confidence",  # <-- Explicit (optional, this is default)
    ...
)

# Deploy v1 model (with lower_bound) - for legacy compatibility
manager.deploy_model(
    model_file_path="models/settlement_legacy.onnx",
    model_name="settlement_soft_clay_legacy",
    output_format_version="v1_lower_bound",  # <-- Required for legacy format
    ...
)
```

For existing 2-output models, see [**MIGRATION_2OUTPUT.md**](MIGRATION_2OUTPUT.md) for upgrade guide.

---

## 4. Update with Actual Measurements

After 6-24 hours, when actual settlement measurements are available:

```python
# Update prediction with actual value
manager.update_with_actual(
    ring_number=100,
    actual_settlement=9.2,  # mm (measured value)
    actual_displacement=3.1  # mm (optional, if available)
)

# Retrieve updated prediction
from edge.models.prediction_result import PredictionResult
updated = db.query(PredictionResult).filter(
    PredictionResult.ring_number == 100
).first()

print(f"\n=== Prediction vs Actual ===")
print(f"Predicted: {updated.predicted_settlement:.2f} mm")
print(f"Actual: {updated.actual_settlement:.2f} mm")
print(f"Prediction Error: {updated.prediction_error:.2f} mm")
print(f"Absolute Error: {updated.absolute_error:.2f} mm")
```

---

## 5. Monitor Model Performance

### Get Performance Report

```python
# Get comprehensive performance report
report = manager.get_performance_report("settlement_lgb_soft_clay")

print(f"\n=== Model Performance Report ===")
print(f"Model: {report['model_name']} v{report['model_version']}")
print(f"Status: {report['deployment_status']}")
print(f"\nLatest Evaluation:")
print(f"  R² Score: {report['latest_evaluation']['r2_score']:.3f}")
print(f"  RMSE: {report['latest_evaluation']['rmse']:.2f} mm")
print(f"  MAE: {report['latest_evaluation']['mae']:.2f} mm")
print(f"  Confidence Coverage: {report['latest_evaluation']['confidence_coverage']:.1%}")
print(f"\nDrift Status:")
print(f"  Drift Detected: {report['drift_status']['drift_detected']}")
print(f"  Severity: {report['drift_status']['drift_severity']}")
print(f"  RMSE Increase: {report['drift_status']['rmse_increase_percent']:.1f}%")
print(f"\nRetraining:")
print(f"  Triggered: {report['retraining']['triggered']}")
print(f"  Reason: {report['retraining']['reason']}")
```

### Check Drift Alerts

```python
# Get recent drift alerts (last 7 days)
alerts = manager.get_drift_alerts(days=7)

if alerts:
    print("\n=== Drift Alerts ===")
    for alert in alerts:
        print(f"{alert['model_name']}: {alert['drift_severity']} drift")
        print(f"  RMSE increase: {alert['rmse_increase_percent']:.1f}%")
        print(f"  Retraining: {alert['retraining_reason']}")
else:
    print("No drift alerts")
```

---

## 6. Model Rollback (If Needed)

If a new model version performs poorly:

```python
# Rollback to previous version
success = manager.rollback_model(
    model_name="settlement_lgb_soft_clay",
    previous_version="1.0.0"
)

if success:
    print("Model rolled back successfully")
```

---

## 7. Get System Status

```python
# Get overall system status
status = manager.get_status()

print(f"\n=== System Status ===")
print(f"Status: {status['status']}")
print(f"Loaded Models: {len(status['loaded_models'])}")
for model in status['loaded_models']:
    print(f"  - {model}")
print(f"Active Models: {status['active_models_count']}")
print(f"Total Predictions: {status['total_predictions']}")
print(f"Predictions Since Last Eval: {status['predictions_since_last_eval']}")

print(f"\n=== Model Performance Stats ===")
for model, stats in status['model_performance_stats'].items():
    print(f"{model}:")
    print(f"  Mean Latency: {stats['mean_ms']:.1f} ms")
    print(f"  P99 Latency: {stats['p99_ms']:.1f} ms")
    print(f"  Total Inferences: {stats['num_inferences']}")
```

---

## Complete Example Script

```python
#!/usr/bin/env python3
"""
Complete prediction workflow example
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from edge.services.inference import PredictionManager

def main():
    # 1. Setup
    engine = create_engine("sqlite:///data/edge.db")
    Session = sessionmaker(bind=engine)
    db = Session()

    manager = PredictionManager(
        db_session=db,
        models_dir="edge/models_onnx",
        enable_auto_monitoring=True
    )
    manager.initialize()

    # 2. Make predictions
    geological_data = {
        "soil_type": "soft_clay",
        "overburden_depth": 15.0,
        "groundwater_level": -3.0,
        "proximity_to_structures": 50.0
    }

    for ring_num in range(100, 110):
        result = manager.predict(
            ring_number=ring_num,
            geological_data=geological_data
        )
        print(f"Ring {ring_num}: {result.predicted_settlement:.2f}mm "
              f"[{result.settlement_lower_bound:.2f}, {result.settlement_upper_bound:.2f}]")

    # 3. Check status
    status = manager.get_status()
    print(f"\nTotal predictions: {status['total_predictions']}")

    # 4. Cleanup
    manager.shutdown()
    db.close()

if __name__ == "__main__":
    main()
```

---

## 8. Performance Benchmarking

The system includes a benchmark script to verify that models meet performance targets:
- Model loading: <5 seconds
- Inference latency: <10ms p99

```bash
# Run benchmark with your ONNX model
python scripts/benchmark_prediction.py \
    --model edge/models_onnx/settlement_lgb_v1.onnx \
    --features 50 \
    --inference-iterations 1000 \
    --report benchmark_report.md

# Output:
# ==========================================================
# Model Loading Benchmark
# ==========================================================
# Model: settlement_lgb_v1.onnx (8.5 MB)
# Iterations: 5
#   Iteration 1: 2.234s
#   Iteration 2: 2.198s
#   ...
# Results:
#   Mean:   2.216s
#   ✅ PASS: Mean load time 2.216s < 5.0s target
#
# ==========================================================
# Inference Latency Benchmark
# ==========================================================
# Iterations: 1000
# Feature count: 50
# Running inference...
#   Completed 100/1000 iterations
#   ...
# Results:
#   Mean:   3.2 ms
#   Median: 3.1 ms
#   P95:    5.8 ms
#   P99:    7.9 ms
#   ✅ PASS: P99 latency 7.9ms < 10.0ms target
#
# Report saved to: benchmark_report.md
```

**Benchmark Options**:
- `--model`: Path to ONNX model file (required)
- `--features`: Number of input features (default: 50)
- `--load-iterations`: Model loading iterations (default: 5)
- `--inference-iterations`: Inference iterations (default: 1000)
- `--concurrent`: Concurrent requests to simulate (default: 10)
- `--report`: Output file for markdown report (optional)

---

## Common Issues and Solutions

### Issue: Model not found

```python
# Check if model is active
from edge.models.model_metadata import ModelMetadata
models = db.query(ModelMetadata).filter(
    ModelMetadata.deployment_status == "active"
).all()
for m in models:
    print(f"{m.model_name} ({m.geological_zone})")
```

### Issue: Insufficient historical rings (cold start)

The system will automatically use cold start mode with quality flag `cold_start`.
Predictions will still be made using neutral windowed features.

### Issue: Missing geological data

The system will automatically use fallback geological features with quality flag `geological_data_incomplete`.
Predictions will still be made but may be less accurate.

### Issue: High inference latency

```python
# Check model performance stats
stats = manager.model_loader.get_performance_stats("settlement_lgb_soft_clay")
print(f"P99 latency: {stats['p99_ms']:.1f} ms")

# If too high (>10ms), consider:
# 1. Model optimization (fewer trees, shallower depth)
# 2. Fewer features
# 3. Model quantization
```

---

## Next Steps

- **Phase 4**: Integrate with warning system for anomaly detection
- **Phase 5**: Visualize predictions in real-time dashboard
- **Cloud Training**: Set up automated model retraining pipeline

For more details, see [PHASE3_SUMMARY.md](../PHASE3_SUMMARY.md)
