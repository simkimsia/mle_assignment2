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

**Status:** 🚧 Not yet implemented (DummyOperators only)
**Purpose:** Use trained models to generate predictions

### `model_inference_start`
- **Type:** DummyOperator
- **Purpose:** Start marker for inference pipeline
- **Dependencies:** Waits for `feature_store_completed`

### `model_1_inference`
- **Type:** DummyOperator (to be implemented)
- **Future Purpose:** Run inference with Model 1
- **Future Input:** `datamart/gold/feature_store/` + `model_store/model_1/`
- **Future Output:** `datamart/gold/predictions/model_1_predictions_YYYY_MM_DD.parquet`

### `model_2_inference`
- **Type:** DummyOperator (to be implemented)
- **Future Purpose:** Run inference with Model 2
- **Future Input:** `datamart/gold/feature_store/` + `model_store/model_2/`
- **Future Output:** `datamart/gold/predictions/model_2_predictions_YYYY_MM_DD.parquet`

### `model_inference_completed`
- **Type:** DummyOperator
- **Purpose:** End marker for inference pipeline
- **Notes:** Triggers monitoring pipeline

---

## 📊 Model Monitoring Pipeline

**Status:** 🚧 Not yet implemented (DummyOperators only)
**Purpose:** Monitor model performance and stability over time

### `model_monitor_start`
- **Type:** DummyOperator
- **Purpose:** Start marker for monitoring pipeline
- **Dependencies:** Waits for `model_inference_completed`

### `model_1_monitor`
- **Type:** DummyOperator (to be implemented)
- **Future Purpose:** Monitor Model 1 performance
- **Future Input:**
  - `datamart/gold/predictions/model_1_predictions_YYYY_MM_DD.parquet`
  - `datamart/gold/label_store/gold_labels_YYYY_MM_DD.parquet`
- **Future Output:** `datamart/gold/monitoring/model_1_metrics_YYYY_MM_DD.parquet`
- **Future Metrics:**
  - ROC-AUC, Accuracy, F1-Score
  - Population Stability Index (PSI)
  - Prediction drift statistics

### `model_2_monitor`
- **Type:** DummyOperator (to be implemented)
- **Future Purpose:** Monitor Model 2 performance
- **Future Input:**
  - `datamart/gold/predictions/model_2_predictions_YYYY_MM_DD.parquet`
  - `datamart/gold/label_store/gold_labels_YYYY_MM_DD.parquet`
- **Future Output:** `datamart/gold/monitoring/model_2_metrics_YYYY_MM_DD.parquet`

### `model_monitor_completed`
- **Type:** DummyOperator
- **Purpose:** End marker for monitoring pipeline

---

## 🔄 Model AutoML Pipeline

**Status:** 🚧 Not yet implemented (DummyOperators only)
**Purpose:** Automatically retrain and evaluate models

### `model_automl_start`
- **Type:** DummyOperator
- **Purpose:** Start marker for AutoML pipeline
- **Dependencies:** Waits for both `feature_store_completed` AND `label_store_completed`

### `model_1_automl`
- **Type:** DummyOperator (to be implemented)
- **Future Purpose:** Train/retrain Model 1
- **Future Input:**
  - `datamart/gold/feature_store/`
  - `datamart/gold/label_store/`
- **Future Output:**
  - `model_store/model_1/model_YYYY_MM_DD.pkl`
  - `model_store/model_1/metrics_YYYY_MM_DD.json`
- **Future Processing:**
  - Train model on historical data
  - Evaluate on validation set
  - Save model artifacts if performance improves

### `model_2_automl`
- **Type:** DummyOperator (to be implemented)
- **Future Purpose:** Train/retrain Model 2
- **Future Input:**
  - `datamart/gold/feature_store/`
  - `datamart/gold/label_store/`
- **Future Output:**
  - `model_store/model_2/model_YYYY_MM_DD.pkl`
  - `model_store/model_2/metrics_YYYY_MM_DD.json`

### `model_automl_completed`
- **Type:** DummyOperator
- **Purpose:** End marker for AutoML pipeline

---

## 🔗 Pipeline Dependencies

### Parallel Execution Groups:
1. **Bronze Feature Tables** (can run in parallel):
   - `bronze_table_1` (attributes)
   - `bronze_table_2` (financials)
   - `bronze_table_3` (clickstream)

2. **Model Inference** (can run in parallel):
   - `model_1_inference`
   - `model_2_inference`

3. **Model Monitoring** (can run in parallel):
   - `model_1_monitor`
   - `model_2_monitor`

4. **Model Training** (can run in parallel):
   - `model_1_automl`
   - `model_2_automl`

### Sequential Dependencies:
- Label Store: `bronze` → `silver` → `gold` (must run in sequence)
- Feature Store: `bronze` → `silver` → `gold` (must run in sequence)
- ML Pipeline: `inference` → `monitoring` (must run in sequence)

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
    ↓
Silver Layer (datamart/silver/) - Cleaned & validated
    ↓
Gold Layer (datamart/gold/) - ML-ready
    ├── label_store/ - Target labels for training
    ├── feature_store/ - Features for ML models
    ├── predictions/ - Model inference outputs (future)
    └── monitoring/ - Performance metrics (future)
    ↓
Model Store (model_store/) - Trained models (future)
```

---

## 🎯 Current Implementation Status

| Pipeline Section | Status | Scripts |
|-----------------|--------|---------|
| Label Store (Bronze → Gold) | ✅ Implemented | 3 scripts |
| Feature Store (Bronze → Gold) | ✅ Implemented | 6 scripts |
| Model Inference | ⏸️ Dummy operators | TBD |
| Model Monitoring | ⏸️ Dummy operators | TBD |
| Model AutoML | ⏸️ Dummy operators | TBD |

**Next Steps:** Implement ML pipeline components (Sections 3-6 of task1_plan.md)
