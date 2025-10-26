# Task 1 Implementation Plan

## DAG DummyOperator Strategy

### ✅ DummyOperators to KEEP (Workflow Markers)

These operators serve as **checkpoints and markers** for workflow visualization and dependency management. They don't perform actual work but help organize the DAG structure:

**Why Keep Them:**

- Visual clarity in Airflow UI graph view
- Clean dependency management between pipeline stages
- No computational cost (instant completion)
- Industry best practice for complex DAGs

**List of DummyOperators to Keep:**

1. `dep_check_source_label_data` - Checkpoint before label data ingestion
2. `label_store_completed` - End marker for label store pipeline
3. `dep_check_source_data_bronze_1/2/3` - Checkpoints before feature bronze ingestion
4. `feature_store_completed` - End marker for feature store pipeline
5. `model_inference_start` - Start marker for inference pipeline
6. `model_inference_completed` - End marker for inference pipeline
7. `model_monitor_start` - Start marker for monitoring pipeline
8. `model_monitor_completed` - End marker for monitoring pipeline
9. `model_automl_start` - Start marker for AutoML pipeline
10. `model_automl_completed` - End marker for AutoML pipeline

### ⚠️ DummyOperators to REPLACE (Actual Work Tasks)

These operators currently do nothing but **MUST** be replaced with BashOperators calling actual Python scripts to perform ML work:

**Why Replace Them:**

- They represent actual computational tasks (training, inference, monitoring)
- Required for Task 1 deliverables
- Need to produce artifacts (models, predictions, metrics)

**List of DummyOperators to Replace:**

#### Model Training (Section 3-4)

- `model_1_automl` → Replace with BashOperator calling `model_1_automl.py`
  - **Purpose:** Train Model 1 (e.g., Logistic Regression)
  - **Input:** Gold feature store + label store
  - **Output:** `model_store/model_1/` (model artifacts, metrics)

- `model_2_automl` → Replace with BashOperator calling `model_2_automl.py`
  - **Purpose:** Train Model 2 (e.g., Gradient Boosted Trees)
  - **Input:** Gold feature store + label store
  - **Output:** `model_store/model_2/` (model artifacts, metrics)

#### Model Inference (Section 5)

- `model_1_inference` → Replace with BashOperator calling `model_1_inference.py`
  - **Purpose:** Generate predictions using Model 1
  - **Input:** Gold feature store + trained model_1
  - **Output:** `datamart/gold/predictions/model_1_predictions_YYYY_MM_DD.parquet`

- `model_2_inference` → Replace with BashOperator calling `model_2_inference.py`
  - **Purpose:** Generate predictions using Model 2
  - **Input:** Gold feature store + trained model_2
  - **Output:** `datamart/gold/predictions/model_2_predictions_YYYY_MM_DD.parquet`

#### Model Monitoring (Section 6)

- `model_1_monitor` → Replace with BashOperator calling `model_1_monitor.py`
  - **Purpose:** Calculate performance metrics for Model 1
  - **Input:** Predictions + labels (ground truth)
  - **Output:** `datamart/gold/monitoring/model_1_metrics_YYYY_MM_DD.parquet`

- `model_2_monitor` → Replace with BashOperator calling `model_2_monitor.py`
  - **Purpose:** Calculate performance metrics for Model 2
  - **Input:** Predictions + labels (ground truth)
  - **Output:** `datamart/gold/monitoring/model_2_metrics_YYYY_MM_DD.parquet`

---

## 1. Establish Data Foundations

- **Inventory Existing Assets:** Review `utils/data_processing_silver_table.py` to confirm the new finance ratio fields flow into downstream gold tables and note any schema changes required for ML features.
- **Feature Availability Check:** Run (or dry-run) the existing bronze → silver → gold ETL to ensure clean feature and label sets exist, documenting table locations and partition columns.
- **Snapshot Strategy:** Decide the prediction window granularity (e.g., monthly) so that training, inference, and monitoring all align on the same time index.

## 2. Airflow Orchestration Setup

- **Reuse Lab 5 Stack:** Adapt the `lab_5/docker-compose.yaml` and DAG structure so an Airflow deployment in Docker orchestrates the end-to-end ML pipeline.
- **DAG Design:** Create separate tasks for data refresh, model training/evaluation, model selection/persistence, inference generation, monitoring, and visualization exports. Wire dependencies to support both full runs and incremental backfills.
- **Configuration Management:** Externalize key parameters (date ranges, feature paths, model hyperparameters) via Airflow Variables or environment files for repeatability.

## 3. Model Training & Evaluation (Max 2 Models)

- **Model Candidates:** Implement two lightweight classifiers (e.g., Logistic Regression and Gradient Boosted Trees) using PySpark ML or scikit-learn, depending on feature volume.
- **Training Data Prep:** Source the engineered gold feature table, apply train/validation splits respecting temporal leakage rules, and handle class imbalance if present.
- **Evaluation Metrics:** Compute at least Accuracy plus one stability-aware metric (e.g., ROC-AUC or F1). Capture metrics per model and persist them for downstream use.

## 4. Model Selection & Model Store

- **Selection Logic:** Choose the best model based on the primary evaluation metric with ties broken by secondary metrics or model simplicity.
- **Model Registry:** Serialize the winning model artefacts (model binary, preprocessing metadata, metrics summary) into a structured `Assignment_2/model_store/<model_id>/` directory.
- **Lineage Tracking:** Record training metadata (data snapshot, feature schema hash, training timestamp) for governance and reproducibility.

## 5. Inference & Prediction Gold Table

- **Batch Inference Task:** Load the stored best model, score the designated prediction window(s), and write prediction outputs (probability, label, model_id, inference_dt) into a gold table (e.g., `datamart/gold/predictions/`).
- **Monitoring Hooks:** Persist supporting columns (e.g., prediction confidence) that will feed monitoring calculations.
- **Operational Validation:** Add lightweight checks to ensure scoring succeeds even if new data rows have unexpected nulls or schema drift.

## 6. Performance & Stability Monitoring

- **Metric Design:** Define temporal monitoring metrics (e.g., rolling ROC-AUC using ground truth once available, Population Stability Index, prediction drift statistics).
- **Monitoring Pipeline:** Build an Airflow task that aggregates predictions + actuals into monitoring metrics per time bucket and writes results to a gold table `datamart/gold/monitoring/`.
- **Alerting Placeholder:** Document how alerts would trigger (e.g., threshold breaches) even if automated notifications are out of scope for the assignment.

## 7. Visualisation Deliverables

- **Visualization Script/Notebook:** Implement a Python script or notebook that reads the monitoring gold table and produces plots (trajectory of metrics, drift charts). Export figures (PNG/HTML) for inclusion in the deck.
- **Airflow Integration:** Optionally schedule a DAG task to regenerate visual artefacts after each monitoring run, storing outputs under `Assignment_2/outputs/visuals/`.

## 8. Governance & SOP Documentation

- **Refresh Policy:** Draft an SOP outlining triggers for model retraining (e.g., degraded monitoring metrics, data drift, scheduled cadence).
- **Deployment Options:** Evaluate deployment paths (batch scoring via Airflow vs. real-time microservice) and document pros/cons aligned with assignment expectations.
- **Operational Checklist:** Summarize roles, approval steps, and artefacts required before promoting a new model.

## 9. Validation & Delivery

- **Smoke Tests:** Implement quick unit/integration tests for critical utilities (e.g., feature extraction, metric computations) to ensure pipeline reliability.
- **Runbook:** Execute a dry run of the full DAG (possibly for a limited date range) to verify all artefacts populate correctly.
- **Final Assets:** Prepare to submit the Airflow DAGs, model store snapshot, gold tables, monitoring outputs, visualisations, and SOP documentation alongside a brief write-up connecting each deliverable to Task 1 requirements.

## Current state

- [x] automl training is up
- [x] inference is up
- [x] monitoring is up
