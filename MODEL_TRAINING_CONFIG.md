# Model Training Configuration Guide

This document explains the dynamic temporal window configuration system for model training in the ML pipeline.

## Table of Contents
- [Overview](#overview)
- [Configuration Modes](#configuration-modes)
- [How It Works](#how-it-works)
- [DAG Training Logic](#dag-training-logic)
- [Usage Examples](#usage-examples)
- [Production Recommendations](#production-recommendations)
- [Troubleshooting](#troubleshooting)

---

## Overview

The model training system supports two modes for defining temporal training windows:
1. **Absolute Mode**: Fixed, hardcoded date ranges (best for initial training)
2. **Relative Mode**: Dynamic, rolling windows calculated from snapshot_date (best for retraining)

This flexibility allows you to:
- Use predictable, fixed dates during initial development and testing
- Automatically calculate rolling windows for production retraining
- Prevent data leakage with strict temporal splits
- Simulate production deployment with out-of-time (OOT) validation

---

## Configuration Modes

### Absolute Mode (Fixed Dates)

**When to use:**
- Initial model training
- Reproducible experiments
- Debugging and development
- When you need exact control over date ranges

**Configuration:**
```json
{
  "temporal_window_mode": "absolute",
  "temporal_splits": {
    "train": {
      "start_date": "2023-01-01",
      "end_date": "2023-12-01"
    },
    "validation": {
      "start_date": "2024-01-01",
      "end_date": "2024-03-01"
    },
    "test": {
      "start_date": "2024-04-01",
      "end_date": "2024-05-01"
    },
    "oot": {
      "start_date": "2024-06-01",
      "end_date": "2024-06-01"
    }
  }
}
```

**Result:** Same date ranges every time, regardless of snapshot_date.

---

### Relative Mode (Dynamic Rolling Windows)

**When to use:**
- Production retraining schedules
- Monthly/quarterly model updates
- Automated MLOps pipelines
- When you want consistent window sizes with new data

**Configuration:**
```json
{
  "temporal_window_mode": "relative",
  "relative_windows": {
    "train": {
      "months_back": 12,
      "description": "Use last 12 months of data before snapshot for training"
    },
    "validation": {
      "months_after_train_end": 3,
      "description": "3 months after training period ends"
    },
    "test": {
      "months_after_validation_end": 2,
      "description": "2 months after validation period ends"
    },
    "oot": {
      "months_after_test_end": 1,
      "description": "1 month after test period ends"
    }
  }
}
```

**Result:** Date ranges calculated dynamically based on snapshot_date.

---

## How It Works

### Backward Calculation Logic (Relative Mode)

The system calculates temporal windows **backward** from the snapshot_date:

```
snapshot_date = 2024-06-01

Step 1: OOT (most recent data)
  - OOT end   = snapshot_date = 2024-06-01
  - OOT start = 2024-06-01 - (1 month - 1) = 2024-06-01
  → OOT: 2024-06-01 to 2024-06-01

Step 2: Test (before OOT)
  - Test end   = OOT start - 1 month = 2024-05-01
  - Test start = 2024-05-01 - (2 months - 1) = 2024-04-01
  → Test: 2024-04-01 to 2024-05-01

Step 3: Validation (before Test)
  - Val end   = Test start - 1 month = 2024-03-01
  - Val start = 2024-03-01 - (3 months - 1) = 2024-01-01
  → Validation: 2024-01-01 to 2024-03-01

Step 4: Training (before Validation)
  - Train end   = Val start - 1 month = 2023-12-01
  - Train start = 2023-12-01 - (12 months - 1) = 2023-01-01
  → Training: 2023-01-01 to 2023-12-01
```

### Why Backward?

Working backward from snapshot_date ensures:
- OOT period always uses the most recent data
- All splits are calculated relative to the latest available data
- Consistent temporal ordering (train → val → test → OOT)
- No overlap or gaps between periods

---

## DAG Training Logic

The DAG includes three `ShortCircuitOperator` checks to ensure tasks only run when prerequisites are met:

1. **Model Inference Check** - Ensures models exist before running inference
2. **Model Monitoring Check** - Ensures inference completed before monitoring
3. **Model Training Check** - Ensures sufficient data exists before training

### 1. Model Inference Check

**Purpose:** Prevent inference tasks from failing when models don't exist yet.

**Logic:**
```python
# Check if model artifacts exist
model_1_path = '/opt/airflow/scripts/model_store/model_1/model.pkl'
model_2_path = '/opt/airflow/scripts/model_store/model_2/model.pkl'

if both models exist:
    → Proceed with inference
else:
    → Skip inference tasks
```

**Code reference:** `dags/dag.py:14-44`

---

### 2. Model Monitoring Check

**Purpose:** Prevent monitoring from running when inference was skipped.

**Logic:**
```python
# Check if models exist (indicating inference ran)
if models exist:
    → Proceed with monitoring
else:
    → Skip monitoring tasks
```

**Code reference:** `dags/dag.py:47-70`

---

### 3. Model Training Data Check

The DAG includes a `ShortCircuitOperator` that checks if sufficient data exists before running model training.

**Minimum data requirement:**
```
Total months needed = 12 (train) + 3 (val) + 2 (test) + 1 (OOT) = 18 months
```

**Code reference:** `dags/dag.py:73-104`

---

### Complete DAG Behavior Matrix

This table shows which tasks run for each execution date:

| Execution Date | Data Pipeline | Inference | Monitoring | Training | Reason |
|---------------|---------------|-----------|------------|----------|--------|
| 2023-01-01    | ✅ Runs       | ⏭️ Skipped | ⏭️ Skipped | ⏭️ Skipped | No models exist yet; need 18 months data |
| 2023-06-01    | ✅ Runs       | ⏭️ Skipped | ⏭️ Skipped | ⏭️ Skipped | No models exist yet; need 18 months data |
| 2024-05-01    | ✅ Runs       | ⏭️ Skipped | ⏭️ Skipped | ⏭️ Skipped | No models exist yet; need 18 months data |
| 2024-06-01    | ✅ Runs       | ⏭️ Skipped | ⏭️ Skipped | ✅ Trains  | First training! Sufficient data available |
| 2024-07-01    | ✅ Runs       | ✅ Runs    | ✅ Runs    | ✅ Trains  | Models exist; all tasks run |
| 2024-08-01    | ✅ Runs       | ✅ Runs    | ✅ Runs    | ✅ Trains  | Models exist; all tasks run (retraining) |
| 2024-12-01    | ✅ Runs       | ✅ Runs    | ✅ Runs    | ✅ Trains  | Models exist; all tasks run (retraining) |

**Key Insights:**

1. **Data Pipeline** always runs (needed for all downstream tasks)
2. **Inference** skipped until models exist (after 2024-06-01 training)
3. **Monitoring** skipped until inference runs (after 2024-06-01 training)
4. **Training** skipped until sufficient data (≥18 months, i.e., ≥2024-06-01)
5. After 2024-06-01, all tasks run on every execution

**Why Inference Skips on 2024-06-01:**
Training runs in parallel with (not before) inference. The models are created during the 2024-06-01 run but aren't available when the inference check happens. Starting from 2024-07-01, models exist and inference can run.

### Sample Log Output

**Run 1: 2023-03-01 (Early run - skip everything except data pipeline)**
```
# Inference Check
⏭️  Skipping inference - models not yet trained.
   Missing: /opt/airflow/scripts/model_store/model_1/model.pkl
   Missing: /opt/airflow/scripts/model_store/model_2/model.pkl

# Monitoring Check
⏭️  Skipping monitoring - no models/inference to monitor.

# Training Check
⏭️  Skipping model training (execution_date=2023-03-01 < 2024-06-01). Insufficient data.
   Need at least 18 months of data (12 train + 3 val + 2 test + 1 OOT).
```

**Run 18: 2024-06-01 (First training run)**
```
# Inference Check
⏭️  Skipping inference - models not yet trained.

# Monitoring Check
⏭️  Skipping monitoring - no models/inference to monitor.

# Training Check
✅ Sufficient data available (execution_date=2024-06-01). Proceeding with model training.
   Training will use data from calculated temporal windows based on this snapshot_date.

[Training completes successfully, creates model_1/model.pkl and model_2/model.pkl]
```

**Run 19: 2024-07-01 (First full run - all tasks execute)**
```
# Inference Check
✅ Both models exist. Proceeding with inference.
   Model 1: /opt/airflow/scripts/model_store/model_1/model.pkl
   Model 2: /opt/airflow/scripts/model_store/model_2/model.pkl

# Monitoring Check
✅ Models exist and inference should have completed. Proceeding with monitoring.

# Training Check
✅ Sufficient data available (execution_date=2024-07-01). Proceeding with model training.

[All tasks run successfully - data pipeline, inference, monitoring, and retraining]
```

---

## Usage Examples

### Example 1: Initial Training (Absolute Mode)

**File:** `scripts/model_config.json`
```json
{
  "temporal_window_mode": "absolute",
  "temporal_splits": {
    "train": {"start_date": "2023-01-01", "end_date": "2023-12-01"},
    "validation": {"start_date": "2024-01-01", "end_date": "2024-03-01"},
    "test": {"start_date": "2024-04-01", "end_date": "2024-05-01"},
    "oot": {"start_date": "2024-06-01", "end_date": "2024-06-01"}
  }
}
```

**Run command:**
```bash
cd /opt/airflow/scripts
python model_1_automl_v2.py --snapshotdate "2024-06-01" --config model_config.json
```

**Output:**
```
📅 Using ABSOLUTE temporal windows (fixed dates)

============================================================
Loaded Training Configuration
============================================================
Train period:      2023-01-01 to 2023-12-01
Validation period: 2024-01-01 to 2024-03-01
Test period:       2024-04-01 to 2024-05-01
OOT period:        2024-06-01 to 2024-06-01
============================================================
```

---

### Example 2: Monthly Retraining (Relative Mode)

**File:** `scripts/model_config.json`
```json
{
  "temporal_window_mode": "relative",
  "relative_windows": {
    "train": {"months_back": 12},
    "validation": {"months_after_train_end": 3},
    "test": {"months_after_validation_end": 2},
    "oot": {"months_after_test_end": 1}
  }
}
```

**Training Run 1 (June 2024):**
```bash
python model_1_automl_v2.py --snapshotdate "2024-06-01" --config model_config.json
```
- Train: 2023-01-01 to 2023-12-01
- Validation: 2024-01-01 to 2024-03-01
- Test: 2024-04-01 to 2024-05-01
- OOT: 2024-06-01 to 2024-06-01

**Training Run 2 (July 2024 - Rolling Window):**
```bash
python model_1_automl_v2.py --snapshotdate "2024-07-01" --config model_config.json
```
- Train: 2023-02-01 to 2024-01-01 ← Rolled forward 1 month
- Validation: 2024-02-01 to 2024-04-01
- Test: 2024-05-01 to 2024-06-01
- OOT: 2024-07-01 to 2024-07-01 ← Uses latest data

**Training Run 3 (December 2024 - Rolling Window):**
```bash
python model_1_automl_v2.py --snapshotdate "2024-12-01" --config model_config.json
```
- Train: 2023-07-01 to 2024-06-01 ← Rolled forward 6 months
- Validation: 2024-07-01 to 2024-09-01
- Test: 2024-10-01 to 2024-11-01
- OOT: 2024-12-01 to 2024-12-01

---

## Production Recommendations

### Initial Training Phase

1. **Use Absolute Mode**
   ```json
   "temporal_window_mode": "absolute"
   ```
   - Ensures reproducibility
   - Easy to debug
   - Clear documentation of what data was used

2. **Run Once**
   - Wait until data reaches 2024-06-01
   - DAG will automatically skip earlier runs
   - Train and deploy initial model

---

### Retraining Phase

1. **Switch to Relative Mode**
   ```json
   "temporal_window_mode": "relative"
   ```
   - Enables automatic rolling windows
   - No manual date updates needed
   - Consistent window sizes

2. **Configure Retraining Frequency**

   Option A: Keep monthly DAG schedule (all runs after 2024-06-01)
   ```python
   schedule_interval='0 0 1 * *'  # Every month
   ```

   Option B: Retrain quarterly (modify DAG check function)
   ```python
   def check_sufficient_data_for_training(**context):
       execution_date = context['ds']
       min_date = '2024-06-01'

       # Only train in June, September, December, March
       month = int(execution_date[5:7])
       should_train = execution_date >= min_date and month % 3 == 0

       return should_train
   ```

   Option C: Retrain based on model performance degradation
   - Monitor model metrics in production
   - Trigger retraining when ROC-AUC drops below threshold

---

### Error Handling

Both training scripts include robust error handling:

**Empty Label Data:**
```python
# scripts/model_1_automl_v2.py:96-100
if df_labels.count() == 0:
    print(f"Error: No labels found up to {snapshot_date_str}")
    print(f"Insufficient data for model training.")
    return None, None
```

**Empty Joined Data:**
```python
# scripts/model_1_automl_v2.py:111-115
if df_train.count() == 0:
    print(f"Error: No training data after joining features and labels")
    return None, None
```

**Result:** Scripts exit gracefully instead of crashing with NoneType errors.

---

## Troubleshooting

### Issue: Inference tasks are skipped

**Symptom:**
```
⏭️  Skipping inference - models not yet trained.
   Missing: /opt/airflow/scripts/model_store/model_1/model.pkl
```

**Cause:** Models haven't been trained yet (execution_date < 2024-06-01)

**Solution:**
1. This is expected behavior before first training
2. Wait until execution_date >= 2024-06-01 for training to complete
3. After models are trained, inference will run on subsequent executions
4. To check if models exist:
   ```bash
   ls -la /opt/airflow/scripts/model_store/model_1/model.pkl
   ls -la /opt/airflow/scripts/model_store/model_2/model.pkl
   ```

---

### Issue: Monitoring tasks are skipped

**Symptom:**
```
⏭️  Skipping monitoring - no models/inference to monitor.
```

**Cause:** Inference was skipped (because models don't exist)

**Solution:**
Monitoring depends on inference, which depends on models. Follow the inference troubleshooting above.

---

### Issue: Model not training even though data exists

**Check 1:** Verify temporal_window_mode
```bash
cat scripts/model_config.json | grep temporal_window_mode
```

**Check 2:** Verify snapshot_date >= 2024-06-01
```python
# In DAG logs
execution_date = '2024-05-01'  # ← Must be >= 2024-06-01
```

**Check 3:** Check label data availability
```bash
ls -la scripts/datamart/gold/label_store/
```

---

### Issue: "Insufficient data for model training"

**Symptom:**
```
Loaded labels: 0 rows
Error: No labels found up to 2024-06-01
Insufficient data for model training.
```

**Cause:** Label store is empty or data pipeline hasn't completed

**Solution:**
1. Check if label store pipeline completed successfully
2. Verify files exist: `ls scripts/datamart/gold/label_store/`
3. Check DAG logs for label store tasks
4. Ensure label store runs before model training in DAG

---

### Issue: Relative mode produces unexpected dates

**Symptom:**
```
Train period: 2022-12-01 to 2023-11-01  # Expected 2023-01-01 to 2023-12-01
```

**Cause:** Incorrect months_back configuration

**Solution:**
Check the relative_windows configuration matches your needs:
```json
{
  "train": {"months_back": 12},  // 12 months back from snapshot_date
  "validation": {"months_after_train_end": 3},
  "test": {"months_after_validation_end": 2},
  "oot": {"months_after_test_end": 1}
}
```

**Verify calculation:**
- Total coverage: 12 + 3 + 2 + 1 = 18 months
- With snapshot_date = "2024-06-01":
  - OOT ends at 2024-06-01
  - Working backward: 2024-06-01 → 2024-05-01 → 2024-03-01 → 2023-12-01 → 2023-01-01

---

### Issue: Training runs multiple times when it should run once

**Symptom:**
DAG executes model training for every month from 2024-06-01 to 2024-12-01

**Cause:** This is expected behavior with catchup=True

**Explanation:**
```python
# dags/dag.py
catchup=True  # Airflow runs ALL missed executions
```

With monthly schedule and catchup=True:
- Run 1: 2024-06-01 → Trains
- Run 2: 2024-07-01 → Trains (retraining with new data)
- Run 3: 2024-08-01 → Trains (retraining with new data)
- ...

**Solutions:**

Option A: Keep all runs for historical tracking (recommended)
- Each run trains a model with that month's data snapshot
- Creates model history/lineage
- Allows comparing model performance over time

Option B: Run only once
- Set catchup=False (only future runs)
- Or add logic to check_sufficient_data_for_training:
  ```python
  # Only train on first eligible date
  if execution_date == '2024-06-01':
      return True
  return False
  ```

---

## File Locations

| File | Purpose |
|------|---------|
| `scripts/model_config.json` | Main configuration file |
| `scripts/model_1_automl_v2.py` | Model 1 training script (Logistic Regression) |
| `scripts/model_2_automl_v2.py` | Model 2 training script (Gradient Boosting) |
| `dags/dag.py` | Airflow DAG with training logic |
| `scripts/model_store/model_1/metadata.json` | Model 1 training metadata |
| `scripts/model_store/model_2/metadata.json` | Model 2 training metadata |

---

## Key Takeaways

1. **Two modes available:** Absolute (fixed dates) vs Relative (rolling windows)
2. **Easy switching:** Change one line in model_config.json
3. **Backward calculation:** Always works backward from snapshot_date in relative mode
4. **Three-tier protection:** ShortCircuitOperators prevent tasks from failing
   - Inference skips if models don't exist
   - Monitoring skips if inference was skipped
   - Training skips if insufficient data (<18 months)
5. **Graceful degradation:** DAG runs successfully even when tasks are skipped
6. **Error handling:** Graceful exits when data is missing
7. **Production ready:** Switch from absolute → relative for automated retraining
8. **Verified accuracy:** Relative mode with snapshot_date="2024-06-01" produces identical results to hardcoded absolute dates
9. **Complete automation:** After 2024-06-01, all tasks run automatically on every execution

---

## Quick Reference

### Switch to Absolute Mode (Fixed Dates)
```json
"temporal_window_mode": "absolute"
```

### Switch to Relative Mode (Rolling Windows)
```json
"temporal_window_mode": "relative"
```

### Minimum Data Requirement
```
18 months total (12 train + 3 val + 2 test + 1 OOT)
First training possible: 2024-06-01
```

### Training Command
```bash
cd /opt/airflow/scripts
python model_1_automl_v2.py --snapshotdate "YYYY-MM-DD" --config model_config.json
python model_2_automl_v2.py --snapshotdate "YYYY-MM-DD" --config model_config.json
```

---

**Last Updated:** 2025-10-25
**Version:** 2.0 (Dynamic Temporal Windows)
