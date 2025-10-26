# DAG Nodes Explanation

This document explains all the tasks (nodes) in the Airflow DAG and their purpose in the ML pipeline.

## 📋 DAG Overview

**DAG Name:** `dag`
**Schedule:** Monthly (1st of each month at 00:00)
**Period:** 2023-01-01 to 2024-12-01 (24 months)
**Catchup:** Enabled (will backfill all historical runs)

---

## 🏷️ Label Store Pipeline

This pipeline processes loan data to create labels for ML model training.

### `dep_check_source_label_data`

- **Type:** DummyOperator
- **Purpose:** Dependency checkpoint to ensure source data is ready
- **Input:** None (checkpoint only)
- **Output:** None
- **Notes:** Placeholder for future data validation logic

### `run_bronze_label_store`

- **Type:** BashOperator
- **Script:** `bronze_label_store.py`
- **Purpose:** Ingest raw loan management system (LMS) data
- **Input:** `data/lms_loan_daily.csv`
- **Output:** `datamart/bronze/lms/bronze_loan_daily_YYYY_MM_DD.csv`
- **Processing:**
  - Reads raw loan daily snapshot data
  - Filters by snapshot date
  - Saves to bronze layer with minimal transformation

### `silver_label_store`

- **Type:** BashOperator
- **Script:** `silver_label_store.py`
- **Purpose:** Clean and validate loan data
- **Input:** `datamart/bronze/lms/bronze_loan_daily_YYYY_MM_DD.csv`
- **Output:** `datamart/silver/loan_daily/silver_loan_daily_YYYY_MM_DD.parquet`
- **Processing:**
  - Data cleaning (handle nulls, outliers)
  - Data type standardization
  - Business rule validation
  - Convert to Parquet format

### `gold_label_store`

- **Type:** BashOperator
- **Script:** `gold_label_store.py`
- **Purpose:** Generate ML labels (target variable)
- **Input:** `datamart/silver/loan_daily/silver_loan_daily_YYYY_MM_DD.parquet`
- **Output:** `datamart/gold/label_store/gold_labels_YYYY_MM_DD.parquet`
- **Processing:**
  - Calculate Days Past Due (DPD) threshold: 30 days
  - Filter Months on Books (MOB) minimum: 6 months
  - Generate binary label: 1 = Default, 0 = No Default
  - Creates ML-ready label dataset

### `label_store_completed`

- **Type:** DummyOperator
- **Purpose:** Marker indicating label store pipeline completed
- **Input:** None
- **Output:** None
- **Notes:** Used for downstream task dependencies

---

## 🎯 Feature Store Pipeline

This pipeline processes user feature data (attributes, financials, clickstream) to create features for ML models.

### Bronze Layer - Data Ingestion

#### `dep_check_source_data_bronze_1`

- **Type:** DummyOperator
- **Purpose:** Checkpoint for attributes data availability
- **Notes:** Placeholder for future data validation

#### `bronze_table_1`

- **Type:** BashOperator
- **Script:** `bronze_table_1.py`
- **Purpose:** Ingest user attributes data
- **Input:** `data/features_attributes.csv`
- **Output:** `datamart/bronze/features/attributes/bronze_features_attributes_YYYY_MM_DD.csv`
- **Processing:**
  - Reads user demographic and attribute data
  - No date filtering (snapshot-independent data)
  - Saves raw data to bronze layer

#### `dep_check_source_data_bronze_2`

- **Type:** DummyOperator
- **Purpose:** Checkpoint for financials data availability
- **Notes:** Placeholder for future data validation

#### `bronze_table_2`

- **Type:** BashOperator
- **Script:** `bronze_table_2.py`
- **Purpose:** Ingest user financial data
- **Input:** `data/features_financials.csv`
- **Output:** `datamart/bronze/features/financials/bronze_features_financials_YYYY_MM_DD.csv`
- **Processing:**
  - Reads user financial information
  - Includes engineered finance ratios (from Assignment 1)
  - No date filtering (snapshot-independent data)
  - Saves raw data to bronze layer

#### `dep_check_source_data_bronze_3`

- **Type:** DummyOperator
- **Purpose:** Checkpoint for clickstream data availability
- **Notes:** Placeholder for future data validation

#### `bronze_table_3`

- **Type:** BashOperator
- **Script:** `bronze_table_3.py`
- **Purpose:** Ingest user clickstream/interaction data
- **Input:** `data/feature_clickstream.csv`
- **Output:** `datamart/bronze/features/clickstream/bronze_feature_clickstream_YYYY_MM_DD.csv`
- **Processing:**
  - Reads user behavioral/clickstream data
  - No date filtering (snapshot-independent data)
  - Saves raw data to bronze layer

### Silver Layer - Data Cleaning & Transformation

#### `silver_table_1`

- **Type:** BashOperator
- **Script:** `silver_table_1.py`
- **Purpose:** Clean and transform attributes + financials data
- **Input:**
  - `datamart/bronze/features/attributes/bronze_features_attributes_YYYY_MM_DD.csv`
  - `datamart/bronze/features/financials/bronze_features_financials_YYYY_MM_DD.csv`
- **Output:**
  - `datamart/silver/attributes/silver_attributes_YYYY_MM_DD.parquet`
  - `datamart/silver/financials/silver_financials_YYYY_MM_DD.parquet`
- **Processing:**
  - Handle missing values
  - Standardize data types
  - Validate finance ratios (Debt_to_Salary, Total_EMI_per_month, etc.)
  - Remove duplicates
  - Convert to Parquet format

#### `silver_table_2`

- **Type:** BashOperator
- **Script:** `silver_table_2.py`
- **Purpose:** Clean and transform clickstream data
- **Input:** `datamart/bronze/features/clickstream/bronze_feature_clickstream_YYYY_MM_DD.csv`
- **Output:** `datamart/silver/clickstream/silver_clickstream_YYYY_MM_DD.parquet`
- **Processing:**
  - Clean behavioral data
  - Aggregate user interactions
  - Handle missing/invalid events
  - Convert to Parquet format

### Gold Layer - Feature Store Assembly

#### `gold_feature_store`

- **Type:** BashOperator
- **Script:** `gold_feature_store.py`
- **Purpose:** Combine all features into ML-ready feature store
- **Input:**
  - `datamart/silver/loan_daily/silver_loan_daily_YYYY_MM_DD.parquet`
  - `datamart/silver/attributes/silver_attributes_YYYY_MM_DD.parquet`
  - `datamart/silver/financials/silver_financials_YYYY_MM_DD.parquet`
  - `datamart/silver/clickstream/silver_clickstream_YYYY_MM_DD.parquet`
- **Output:** `datamart/gold/feature_store/gold_features_YYYY_MM_DD.parquet`
- **Processing:**
  - Join all feature tables by user_id
  - Create final feature set for ML training
  - Ensure no data leakage (temporal, target, train-test)
  - Generate ML-compatible schema

#### `feature_store_completed`

- **Type:** DummyOperator
- **Purpose:** Marker indicating feature store pipeline completed
- **Notes:** Triggers downstream ML tasks

---

## 🤖 Model Inference Pipeline

**Status:** ✅ Implemented
**Purpose:** Use trained models to generate predictions

### `check_models_for_inference`

- **Type:** ShortCircuitOperator
- **Purpose:** Conditional check to ensure models exist before running inference
- **Function:** `check_models_exist_for_inference()`
- **Logic:**
  - Checks for existence of `/opt/airflow/scripts/model_store/model_1/model.pkl`
  - Checks for existence of `/opt/airflow/scripts/model_store/model_2/model.pkl`
  - Returns `True` only if both models exist
  - Returns `False` otherwise, skipping downstream inference tasks
- **Notes:**
  - Runs in parallel with training pipeline
  - On first run (2024-12-01), skips because models don't exist yet
  - `seed_inference_backfill` handles initial predictions after training
  - Subsequent runs use existing models immediately

### `model_inference_start`

- **Type:** DummyOperator
- **Purpose:** Start marker for inference pipeline
- **Dependencies:** Waits for `feature_store_completed` → `check_models_for_inference`

### `model_1_inference`

- **Type:** BashOperator
- **Script:** `model_1_inference.py`
- **Purpose:** Run inference with Model 1
- **Input:**
  - `datamart/gold/feature_store/gold_features_YYYY_MM_DD.parquet`
  - `model_store/model_1/model.pkl`
- **Output:** `datamart/gold/predictions/model_1_predictions_YYYY_MM_DD.parquet`
- **Processing:**
  - Load trained Model 1
  - Load feature store for snapshot date
  - Generate predictions for loans at MOB=0
  - Save predictions with user_id, prediction, probability

### `model_2_inference`

- **Type:** BashOperator
- **Script:** `model_2_inference.py`
- **Purpose:** Run inference with Model 2
- **Input:**
  - `datamart/gold/feature_store/gold_features_YYYY_MM_DD.parquet`
  - `model_store/model_2/model.pkl`
- **Output:** `datamart/gold/predictions/model_2_predictions_YYYY_MM_DD.parquet`
- **Processing:**
  - Load trained Model 2
  - Load feature store for snapshot date
  - Generate predictions for loans at MOB=0
  - Save predictions with user_id, prediction, probability

### `model_inference_completed`

- **Type:** DummyOperator
- **Purpose:** End marker for inference pipeline
- **Notes:** Triggers monitoring pipeline

---

## 📊 Model Monitoring Pipeline

**Status:** ✅ Implemented
**Purpose:** Monitor model performance and stability over time

### `check_inference_for_monitoring`

- **Type:** ShortCircuitOperator
- **Purpose:** Conditional check to ensure required predictions exist before monitoring
- **Function:** `check_inference_completed_for_monitoring()`
- **Logic:**
  - Checks if models exist (inference must be running)
  - Checks if predictions from **6 months ago** exist
  - Returns `True` only if both conditions are met
  - Returns `False` otherwise, skipping monitoring tasks
- **Temporal Requirement:**
  - Monitoring joins predictions (from MOB=0) with labels (from MOB=6)
  - Labels on snapshot_date are for loans at MOB=6
  - These loans were at MOB=0 exactly 6 months earlier
  - Therefore, monitoring requires predictions from 6 months before snapshot_date
- **Notes:**
  - Expected to skip for first 6 months after inference starts
  - Example: For labels on 2024-12-01, needs predictions from 2024-06-01

### `model_monitor_start`

- **Type:** DummyOperator
- **Purpose:** Start marker for monitoring pipeline
- **Dependencies:** Waits for `model_inference_completed` → `check_inference_for_monitoring`

### `model_1_monitor`

- **Type:** BashOperator
- **Script:** `model_1_monitor.py`
- **Purpose:** Monitor Model 1 performance
- **Input:**
  - `datamart/gold/predictions/model_1_predictions_[6_months_ago].parquet`
  - `datamart/gold/label_store/gold_labels_YYYY_MM_DD.parquet`
- **Output:** `datamart/gold/monitoring/model_1_metrics_YYYY_MM_DD.parquet`
- **Metrics Calculated:**
  - ROC-AUC, Accuracy, Precision, Recall, F1-Score
  - Population Stability Index (PSI)
  - Prediction drift statistics
  - Confusion matrix
- **Processing:**
  - Load predictions from 6 months ago (MOB=0)
  - Load current labels (MOB=6)
  - Join by user_id for temporal alignment
  - Calculate performance metrics
  - Save metrics to monitoring store

### `model_2_monitor`

- **Type:** BashOperator
- **Script:** `model_2_monitor.py`
- **Purpose:** Monitor Model 2 performance
- **Input:**
  - `datamart/gold/predictions/model_2_predictions_[6_months_ago].parquet`
  - `datamart/gold/label_store/gold_labels_YYYY_MM_DD.parquet`
- **Output:** `datamart/gold/monitoring/model_2_metrics_YYYY_MM_DD.parquet`
- **Metrics Calculated:** Same as Model 1

### `model_monitor_completed`

- **Type:** DummyOperator
- **Purpose:** End marker for monitoring pipeline
- **Notes:** Triggers visualization pipeline

---

## 📈 Visualization Pipeline

**Status:** ✅ Implemented
**Purpose:** Generate visual reports and charts for model monitoring metrics

### `visualize_monitoring`

- **Type:** BashOperator
- **Script:** `visualize_monitoring.py`
- **Purpose:** Create performance visualization charts and reports
- **Input:**
  - `datamart/gold/monitoring/model_1_metrics_*.parquet` (all available dates)
  - `datamart/gold/monitoring/model_2_metrics_*.parquet` (all available dates)
- **Output:**
  - Performance trend charts (ROC-AUC, F1-Score over time)
  - PSI drift charts
  - Confusion matrices
  - HTML/PNG reports for both models
- **Trigger Rule:** `all_success` - only runs if monitoring succeeds
- **Processing:**
  - Aggregates metrics across all snapshot dates
  - Generates time-series visualizations
  - Creates comparative charts (Model 1 vs Model 2)
  - Saves visualizations to output directory
- **Notes:** Non-blocking; runs after monitoring completes

---

## 🎯 Action Evaluation Pipeline

**Status:** ✅ Implemented
**Purpose:** Evaluate monitoring metrics against thresholds to determine required actions

### `evaluate_monitoring_actions`

- **Type:** BashOperator
- **Script:** `evaluate_monitoring_action.py`
- **Purpose:** Assess model performance and recommend actions using 3-tier governance framework
- **Input:**
  - `datamart/gold/monitoring/model_1_metrics_*.parquet`
  - `datamart/gold/monitoring/model_2_metrics_*.parquet`
  - `scripts/monitoring_thresholds.json` (threshold configuration)
  - `scripts/model_store/model_X/metadata.json` (baseline metrics)
- **Output:**
  - `scripts/outputs/actions/model_X_action_YYYY_MM_DD.json` (machine-readable decision)
  - `scripts/outputs/actions/model_X_action_YYYY_MM_DD.txt` (human-readable report)
- **Trigger Rule:** `all_success` - only runs if visualization succeeds

### Dual Threshold Philosophy

The action evaluation uses **two threshold levels** for each metric:

- **Business Threshold:** Minimum acceptable performance for business operations (ROC-AUC ≥ 0.75, Accuracy ≥ 0.70)
- **Data Science Threshold:** Early warning buffer set higher than business thresholds (ROC-AUC ≥ 0.80, Accuracy ≥ 0.75)
- **Purpose:** Enable proactive intervention before reaching critical levels

### Priority Levels

Metrics are prioritized based on business impact:

- **P0:** Critical business metrics (ROC-AUC) - directly impacts credit decisions
- **P1:** Important business metrics (Accuracy) - affects operational efficiency
- **P2:** Data Science operational metrics (F1-Score) - technical health indicators
- **P3:** Data Science diagnostic metrics (Precision, Recall) - detailed analysis

### Action Determination Logic

Three action levels based on P0 and P1 metric performance:

#### 1. **monitor** (Green)

- **Trigger:** All P0 and P1 metrics above data science thresholds
- **Action Required:** Continue normal monthly monitoring cycle
- **Notification:** Monthly email report to ML team (informational)
- **Example:** ROC-AUC ≥ 0.80, Accuracy ≥ 0.75

#### 2. **active_monitoring** (Yellow)

- **Trigger:** Any P0 or P1 metric below data science threshold but above business threshold
- **Action Required:**
  - Increase monitoring frequency (weekly instead of monthly)
  - Investigate root cause (data drift, feature quality, population shift)
  - Prepare retraining plan as contingency
  - Set up additional alerting for further degradation
- **Notification:** Slack alert + Email to ML team
- **Example:** 0.75 ≤ ROC-AUC < 0.80 or 0.70 ≤ Accuracy < 0.75

#### 3. **retrain** (Red)

- **Trigger:** Any P0 or P1 metric below business threshold
- **Action Required:**
  - Initiate emergency retraining workflow immediately
  - Investigate root cause (data quality, model drift, label issues)
  - Notify all stakeholders (Risk team, Product team)
  - Schedule retraining to complete within 1 week
  - Prepare rollback plan
- **Notification:** PagerDuty alert + Slack + Email (ML team + Risk team)
- **Example:** ROC-AUC < 0.75 or Accuracy < 0.70

### Processing

- Run separately for Model 1 and Model 2
- Executed sequentially via: `python3 evaluate_monitoring_action.py --model-id model_1 && python3 evaluate_monitoring_action.py --model-id model_2`
- Compares current metrics against thresholds
- Compares current metrics against OOT baseline (for degradation detection)
- Generates detailed report with recommended next steps

**Notes:** Could trigger automated retraining in future iterations; currently outputs action decision for manual review

---

## 🔄 Model AutoML Pipeline

**Status:** ✅ Implemented
**Purpose:** Automatically train and retrain models with temporal validation

### `check_training_data`

- **Type:** ShortCircuitOperator
- **Purpose:** Conditional check to ensure sufficient data exists before training
- **Function:** `check_sufficient_data_for_training()`
- **Logic:**
  - Returns `True` only if `execution_date >= 2024-12-01`
  - Returns `False` otherwise, skipping training tasks
- **Data Requirements:**
  - **Minimum 23 months of data needed:**
    - 12 months: Training window
    - 2 months: Validation window
    - 2 months: Test window
    - 1 month: Out-of-Time (OOT) window
    - 6 months: MOB=6 requirement for labels
    - Total: 12 + 2 + 2 + 1 + 6 = 23 months
  - Starting from 2023-01-01, earliest training date is 2024-12-01
- **Modes:**
  - **Dynamic (Relative):** Windows calculated backwards from snapshot_date
  - **Fixed (Absolute):** Hardcoded dates (still requires data through 2024-12-01)
- **Retraining:**
  - After initial training, allows monthly retraining with rolling windows
  - Adjust DAG schedule or add custom logic to control retraining frequency
- **Notes:**
  - First training occurs on 2024-12-01
  - Subsequent runs enable continuous model improvement

### `model_automl_start`

- **Type:** DummyOperator
- **Purpose:** Start marker for AutoML pipeline
- **Dependencies:** Waits for both `feature_store_completed` AND `label_store_completed` → `check_training_data`

### `model_1_automl`

- **Type:** BashOperator
- **Script:** `model_1_automl_v2.py`
- **Config:** `model_config.json`
- **Purpose:** Train/retrain Model 1 (e.g., Logistic Regression)
- **Input:**
  - `datamart/gold/feature_store/gold_features_*.parquet` (multiple dates)
  - `datamart/gold/label_store/gold_labels_*.parquet` (multiple dates)
  - `model_config.json` (temporal windows, hyperparameters)
- **Output:**
  - `model_store/model_1/model.pkl` (trained model)
  - `model_store/model_1/preprocessing.pkl` (preprocessing pipeline)
  - `model_store/model_1/features.json` (feature list)
  - `model_store/model_1/metadata.json` (model metadata, metrics)
- **Processing:**
  - Load temporal windows from config (training, validation, test, OOT)
  - Load and join feature store + label store for each window
  - Train model on training window
  - Evaluate on validation window (hyperparameter tuning)
  - Test on test window (performance assessment)
  - Validate on OOT window (temporal stability)
  - Save model artifacts if performance acceptable
- **Validation Strategy:**
  - **Training:** Historical data for model fitting
  - **Validation:** Held-out data for hyperparameter selection
  - **Test:** Independent data for unbiased evaluation
  - **OOT:** Future data for temporal validation

### `model_2_automl`

- **Type:** BashOperator
- **Script:** `model_2_automl_v2.py`
- **Config:** `model_config.json`
- **Purpose:** Train/retrain Model 2 (e.g., Random Forest)
- **Input:** Same as Model 1
- **Output:**
  - `model_store/model_2/model.pkl`
  - `model_store/model_2/preprocessing.pkl`
  - `model_store/model_2/features.json`
  - `model_store/model_2/metadata.json`
- **Processing:** Same as Model 1, but with different algorithm
- **Notes:** Runs in parallel with Model 1 training

### `model_automl_completed`

- **Type:** DummyOperator
- **Purpose:** End marker for AutoML pipeline
- **Notes:** Triggers seed inference backfill

### `seed_inference_backfill`

- **Type:** BashOperator
- **Script:** `seed_inference_backfill.py`
- **Purpose:** Generate predictions for past 8 months after initial model training
- **Input:**
  - Newly trained models (`model_store/model_1/`, `model_store/model_2/`)
  - Historical feature store data (8 months worth)
  - `--backfill-months 8` parameter
- **Output:**
  - `datamart/gold/predictions/model_1_predictions_*.parquet` (8 files)
  - `datamart/gold/predictions/model_2_predictions_*.parquet` (8 files)
- **Processing:**
  - Only runs after initial training (2024-12-01)
  - Backfills predictions from 2024-04-01 to 2024-11-01
  - Ensures monitoring has predictions from 6 months ago for subsequent runs
  - Enables monitoring to start on next DAG run (2025-01-01)
- **Why 8 months:**
  - Training occurs on 2024-12-01
  - Need predictions from 2024-06-01 for monitoring on 2024-12-01 (6 months ago)
  - Backfill extra months to cover buffer period
  - 8 months ensures sufficient prediction history
- **Notes:**
  - Critical for bootstrapping monitoring pipeline
  - Without this, monitoring would be delayed until enough inference runs accumulate

---

## 🔗 Pipeline Dependencies

### Parallel Execution Groups

1. **Bronze Feature Tables** (run in parallel):
   - `bronze_table_1` (attributes)
   - `bronze_table_2` (financials)
   - `bronze_table_3` (clickstream)

2. **Model Inference** (run in parallel):
   - `model_1_inference`
   - `model_2_inference`

3. **Model Monitoring** (run in parallel):
   - `model_1_monitor`
   - `model_2_monitor`

4. **Model Training** (run in parallel):
   - `model_1_automl`
   - `model_2_automl`

5. **Independent Pipeline Branches** (run in parallel):
   - **Inference Branch:** `feature_store_completed` → `check_models_for_inference` → inference tasks
   - **Training Branch:** `[feature_store_completed + label_store_completed]` → `check_training_data` → training tasks

### Sequential Dependencies

1. **Label Store Pipeline:**
   - `dep_check_source_label_data` → `bronze_label_store` → `silver_label_store` → `gold_label_store` → `label_store_completed`

2. **Feature Store Pipeline:**
   - Three parallel bronze ingestion chains, converging at `gold_feature_store`:
     - Chain 1: `dep_check_source_data_bronze_1` → `bronze_table_1` → `silver_table_1` → `gold_feature_store`
     - Chain 2: `dep_check_source_data_bronze_2` → `bronze_table_2` → `silver_table_1` → `gold_feature_store`
     - Chain 3: `dep_check_source_data_bronze_3` → `bronze_table_3` → `silver_table_2` → `gold_feature_store`
   - Then: `gold_feature_store` → `feature_store_completed`

3. **Inference Pipeline:**
   - `feature_store_completed` → `check_models_for_inference` → `model_inference_start`
   - `model_inference_start` → [`model_1_inference`, `model_2_inference`] → `model_inference_completed`

4. **Monitoring Pipeline:**
   - `model_inference_completed` → `check_inference_for_monitoring` → `model_monitor_start`
   - `model_monitor_start` → [`model_1_monitor`, `model_2_monitor`] → `model_monitor_completed`

5. **Visualization & Action Pipeline:**
   - `model_monitor_completed` → `visualize_monitoring` → `evaluate_monitoring_actions`

6. **Training Pipeline:**
   - `[feature_store_completed + label_store_completed]` → `check_training_data` → `model_automl_start`
   - `model_automl_start` → [`model_1_automl`, `model_2_automl`] → `model_automl_completed`
   - `model_automl_completed` → `seed_inference_backfill`

### Conditional Execution (ShortCircuitOperators)

- **`check_models_for_inference`:**
  - Skips inference if models don't exist
  - Expected on first run (2024-12-01) before training completes

- **`check_inference_for_monitoring`:**
  - Skips monitoring if predictions from 6 months ago don't exist
  - Expected for first 6 months after inference starts

- **`check_training_data`:**
  - Skips training if `execution_date < 2024-12-01`
  - Ensures minimum 23 months of data available

### Critical Path

The critical path for full pipeline execution (once all conditions are met):

```
Label Store → Training → Seed Backfill
Feature Store → Inference → Monitoring → Visualization → Action Evaluation
```

### First Run Behavior (2024-12-01)

1. Label Store + Feature Store execute successfully
2. Training executes (condition met: execution_date >= 2024-12-01)
3. Inference **SKIPS** (models don't exist yet)
4. Monitoring **SKIPS** (no predictions exist)
5. Seed backfill creates historical predictions after training
6. Next run (2025-01-01): Inference starts working, Monitoring still waits

### Steady State Behavior (2025-07-01+)

1. All data pipelines execute
2. Inference runs using existing models
3. Monitoring runs (has predictions from 6 months ago)
4. Visualization and action evaluation run
5. Training runs monthly (rolling windows)

---

## 📁 Data Flow Summary

```
Raw Data (data/)
    ├── lms_loan_daily.csv
    ├── features_attributes.csv
    ├── features_financials.csv
    └── feature_clickstream.csv
    ↓
Bronze Layer (datamart/bronze/) - Raw ingestion
    ├── lms/bronze_loan_daily_*.csv
    └── features/
        ├── attributes/bronze_features_attributes_*.csv
        ├── financials/bronze_features_financials_*.csv
        └── clickstream/bronze_feature_clickstream_*.csv
    ↓
Silver Layer (datamart/silver/) - Cleaned & validated
    ├── loan_daily/silver_loan_daily_*.parquet
    ├── attributes/silver_attributes_*.parquet
    ├── financials/silver_financials_*.parquet
    └── clickstream/silver_clickstream_*.parquet
    ↓
Gold Layer (datamart/gold/) - ML-ready
    ├── label_store/gold_labels_*.parquet - Target labels for training
    ├── feature_store/gold_features_*.parquet - Features for ML models
    ├── predictions/ - Model inference outputs
    │   ├── model_1_predictions_*.parquet
    │   └── model_2_predictions_*.parquet
    └── monitoring/ - Performance metrics
        ├── model_1_metrics_*.parquet
        └── model_2_metrics_*.parquet
    ↓
Model Store (model_store/) - Trained model artifacts
    ├── model_1/
    │   ├── model.pkl - Trained model
    │   ├── preprocessing.pkl - Preprocessing pipeline
    │   ├── features.json - Feature list
    │   └── metadata.json - Model metadata & metrics
    └── model_2/
        ├── model.pkl
        ├── preprocessing.pkl
        ├── features.json
        └── metadata.json
    ↓
Outputs (scripts/outputs/) - Visualizations & reports
    ├── monitoring_dashboard.html
    ├── model_1_performance.png
    ├── model_2_performance.png
    ├── psi_trends.png
    └── action_evaluation_log.txt
```

---

## 🎯 Current Implementation Status

| Pipeline Section | Status | Components | Key Features |
|-----------------|--------|------------|--------------|
| Label Store (Bronze → Gold) | ✅ Implemented | 3 scripts | DPD-based labeling, MOB=6 filtering |
| Feature Store (Bronze → Gold) | ✅ Implemented | 6 scripts | Multi-source feature integration |
| Model Inference | ✅ Implemented | 3 scripts + 1 conditional | ShortCircuit logic, parallel execution |
| Model Monitoring | ✅ Implemented | 3 scripts + 1 conditional | Temporal joins (6-month lag), PSI tracking |
| Visualization | ✅ Implemented | 1 script | Performance trends, drift charts |
| Action Evaluation | ✅ Implemented | 1 script | Threshold-based alerting |
| Model AutoML | ✅ Implemented | 3 scripts + 1 conditional + 1 backfill | 4-window validation, seed backfill |

### Summary Statistics

- **Total Tasks:** 28 (13 operators, 15 script runners)
- **ShortCircuitOperators:** 3 (conditional execution)
- **BashOperators:** 15 (script execution)
- **DummyOperators:** 10 (checkpoints & markers)
- **Python Scripts:** 18 (data processing, ML training/inference)

### Temporal Features

- **Dynamic Windows:** Training windows calculated relative to snapshot_date
- **6-Month Label Lag:** MOB=6 requirement for loan maturity
- **6-Month Monitoring Lag:** Temporal alignment of predictions with labels
- **8-Month Backfill:** Bootstrap prediction history for monitoring
- **23-Month Minimum Data:** Required for initial training (12+2+2+1+6)

### Execution Modes

- **Catchup Mode:** Enabled (backfills all 24 months from 2023-01-01 to 2024-12-01)
- **First Training:** 2024-12-01 (when 23 months of data available)
- **First Monitoring:** 2025-07-01 (when 6 months of predictions exist)
- **Parallel Execution:** Bronze ingestion, inference, monitoring, training

**Status:** All pipeline components fully implemented and operational.
