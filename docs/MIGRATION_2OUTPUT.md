# Migration Guide: 2-Output Model Format Change

**Date**: January 21, 2025
**Affects**: All 2-output ONNX models
**Breaking Change**: Yes (for models deployed without explicit format version)

---

## Background

Phase 3 introduced support for two different 2-output model formats:

- **v1_lower_bound (legacy)**: `[settlement, lower_bound]` - Model outputs settlement prediction and lower confidence interval bound
- **v2_confidence (new)**: `[settlement, confidence]` - Model outputs settlement prediction and confidence score (0.0-1.0)

To support both formats simultaneously, models now require an `output_format_version` field in `model_metadata` table.

---

## Who Needs to Migrate?

**You need to take action if:**

1. You have **existing 2-output models** deployed before January 21, 2025
2. You are **training new 2-output models** that output confidence scores
3. You see **warning logs** like: `"Model X has 2 outputs but no output_format_version in metadata"`

**You can skip this if:**

- All your models have 1, 3, 4, 6, 8, 9, or 12 outputs (not 2-output)
- You only deploy new models after running the migration script

---

## Step 1: Run Database Migration

The migration script adds the `output_format_version` column and marks all existing models as `v1_lower_bound` for backward compatibility:

```bash
# Run migration (adds column + marks existing models as v1)
sqlite3 data/edge.db < database/migrations/edge/008_output_format_version.sql

# Verify migration completed successfully
echo $?  # Should output: 0

# Check existing models are marked as v1
sqlite3 data/edge.db "SELECT model_name, model_version, output_format_version FROM model_metadata;"
```

**Expected output**: All existing models should show `v1_lower_bound`.

**Important Notes**:
- SQLite does not support `ALTER COLUMN ... SET DEFAULT`, so the default value is **not set at the database level**
- New models automatically get `v2_confidence` through:
  1. SQLAlchemy ORM: `ModelMetadata.output_format_version` has `default='v2_confidence'`
  2. API parameter: `PredictionManager.deploy_model(..., output_format_version='v2_confidence')`
- This means **only models deployed via the ORM API** will get the default; direct SQL `INSERT` would create NULL values (not recommended)

**Verification**:
```bash
# Check no models have NULL output_format_version (should return 0)
sqlite3 data/edge.db "SELECT COUNT(*) FROM model_metadata WHERE output_format_version IS NULL;"
```

---

## Step 2: Identify Your Model's Actual Format

### Method 1: Check Model Training Code

Look at your ONNX export code:

```python
# v1 format (lower_bound)
outputs = [settlement_pred, lower_bound]

# v2 format (confidence)
outputs = [settlement_pred, confidence_score]
```

### Method 2: Inspect ONNX Model Output

```python
import onnxruntime as ort
import numpy as np

session = ort.InferenceSession("your_model.onnx")
dummy_input = np.random.randn(1, 50).astype(np.float32)
outputs = session.run(None, {"input": dummy_input})

print(f"Output 0 (settlement): {outputs[0][0, 0]}")
print(f"Output 1 (???): {outputs[1][0, 0]}")

# If output 1 is in range [0.0, 1.0] → likely confidence
# If output 1 is in range similar to settlement (e.g., 5-15mm) → likely lower_bound
```

### Method 3: Check Prediction Results

```python
from edge.services.inference import PredictionManager

manager = PredictionManager(...)
result = manager.predict(ring_number=100)

# For v1 models
print(result.settlement_lower_bound)  # Should have value (e.g., 6.8mm)
print(result.prediction_confidence)    # Will be default 0.85

# For v2 models
print(result.settlement_lower_bound)  # Will be fallback ±20%
print(result.prediction_confidence)    # Should have model value (e.g., 0.92)
```

---

## Step 3: Update Model Metadata

### Option A: Update Existing Models in Database

If you confirmed a model uses **v2_confidence** format:

```sql
-- Update specific model
UPDATE model_metadata
SET output_format_version = 'v2_confidence'
WHERE model_name = 'your_model_name' AND model_version = '1.0.0';

-- Update all models with "conf" in name (if you have naming convention)
UPDATE model_metadata
SET output_format_version = 'v2_confidence'
WHERE model_name LIKE '%_conf_%';

-- Verify update
SELECT model_name, model_version, output_format_version
FROM model_metadata
WHERE output_format_version = 'v2_confidence';
```

### Option B: Specify Format When Deploying New Models

```python
from edge.services.inference import PredictionManager

manager = PredictionManager(...)

# Deploy v2 model (with confidence)
manager.deploy_model(
    model_file_path="models/settlement_lgb_v2.onnx",
    model_name="settlement_lgb_soft_clay_v2",
    model_version="2.0.0",
    model_type="lightgbm",
    geological_zone="soft_clay",
    output_format_version="v2_confidence",  # <-- Explicit format
    feature_list=[...],
    activate=True
)

# Deploy v1 model (with lower_bound, rare case)
manager.deploy_model(
    model_file_path="models/settlement_legacy.onnx",
    model_name="settlement_legacy",
    model_version="1.0.0",
    model_type="lightgbm",
    output_format_version="v1_lower_bound",  # <-- Explicit format
    ...
)
```

---

## Step 4: Monitor Warnings

After migration, check logs for untagged models:

```bash
# Check for format warnings
tail -f logs/edge.log | grep "no output_format_version"

# Example warning:
# WARNING: Model settlement_lgb_soft_clay has 2 outputs but no output_format_version in metadata.
# Defaulting to legacy 'v1_lower_bound' format [settlement, lower_bound].
# If this model outputs confidence scores, please update model_metadata ...
```

If you see warnings for models that should use `v2_confidence`, update them per Step 3.

---

## Step 5: Verify Correct Behavior

### Test v1 Models (lower_bound format)

```python
result = manager.predict(ring_number=100)

# Verify lower bound comes from model (not fallback ±20%)
assert result.settlement_lower_bound != result.predicted_settlement * 0.8
print(f"Lower bound: {result.settlement_lower_bound:.2f}mm")  # Should be model value

# Confidence will be default
assert result.prediction_confidence == 0.85
```

### Test v2 Models (confidence format)

```python
result = manager.predict(ring_number=100)

# Verify confidence comes from model (not default 0.85)
assert result.prediction_confidence != 0.85
print(f"Confidence: {result.prediction_confidence:.2%}")  # Should be model value (e.g., 92%)

# CI will be fallback ±20% (or from 3+ output models)
print(f"CI: [{result.settlement_lower_bound:.2f}, {result.settlement_upper_bound:.2f}]mm")
```

---

## Common Issues

### Issue 1: Model outputs look wrong after migration

**Symptom**: Confidence shows 680% or lower_bound shows 0.92mm

**Cause**: Wrong format_version assigned

**Solution**:
```sql
-- Check what format is set
SELECT model_name, output_format_version FROM model_metadata WHERE model_name = 'your_model';

-- Flip to correct format
UPDATE model_metadata
SET output_format_version = CASE
    WHEN output_format_version = 'v1_lower_bound' THEN 'v2_confidence'
    WHEN output_format_version = 'v2_confidence' THEN 'v1_lower_bound'
END
WHERE model_name = 'your_model';
```

### Issue 2: No warnings but model still wrong

**Cause**: Migration set format but it's incorrect for that specific model

**Solution**: Manually verify and update per Step 3

### Issue 3: Want to retrain v1 models to v2

**Steps**:
1. Update model training code to output confidence instead of lower_bound
2. Re-export to ONNX with 2 outputs: `[settlement, confidence]`
3. Deploy with `output_format_version="v2_confidence"`
4. Test predictions to verify confidence is in [0.0, 1.0] range

---

## Rollback Plan

If you need to revert the migration:

```sql
-- Remove output_format_version column
ALTER TABLE model_metadata DROP COLUMN output_format_version;

-- Revert model_loader.py to always use confidence format
-- (Requires code change - contact dev team)
```

**Warning**: Rollback will break v1_lower_bound models again. Only rollback if ALL your 2-output models use confidence format.

---

## FAQ

**Q: What happens if I don't migrate?**
A: All 2-output models will default to `v1_lower_bound` format. If your model outputs confidence, it will be misinterpreted as a lower_bound value.

**Q: Can I have both v1 and v2 models deployed simultaneously?**
A: Yes! That's the whole point of this migration. Each model's format is stored in its metadata.

**Q: Which format should I use for new models?**
A: Use `v2_confidence` for new models. Confidence scores are more useful than partial CI. If you need CI, use 3-output format `[settlement, lower, upper]` or 4-output `[settlement, confidence, lower, upper]`.

**Q: Does this affect models with other output counts (1, 3, 4, 6, 8, 9, 12)?**
A: No. The `output_format_version` field is only checked for 2-output models.

**Q: How do I know the migration was successful?**
A: Run `SELECT COUNT(*) FROM model_metadata WHERE output_format_version IS NULL;` - should return 0.

---

## Support

If you encounter issues:

1. Check logs: `tail -f logs/edge.log | grep -i format`
2. Verify database: `sqlite3 data/edge.db "SELECT * FROM model_metadata;"`
3. Test predictions and check if values make sense
4. Consult `docs/prediction_quickstart.md` for expected output formats

For questions, contact the ML platform team or open an issue in the project repository.
