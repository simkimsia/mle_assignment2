# End-to-End ML Pipeline for Loan Default Prediction

GitHub 👨🏻‍💻: https://github.com/simkimsia/mle_assignment2

Loom 🎥:

An Apache Airflow-orchestrated machine learning pipeline for loan default prediction, featuring automated data processing, model training, inference, and monitoring.

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- At least 4GB RAM available for Docker
- Ports 8080 available on your machine

### Launch the Pipeline

1. **Start all services:**

   ```bash
   docker-compose up -d
   ```

2. **Wait for Airflow to initialize** (approximately 30-60 seconds):

   ```bash
   docker-compose logs -f airflow-init
   ```

   Wait until you see "Admin user created" or similar completion message, then press `Ctrl+C`.

3. **Access Airflow Web UI:**
   - URL: <http://localhost:8080>
   - Username: `admin`
   - Password: `admin`

4. **Enable the DAG:**
   - Navigate to the DAGs page
   - Find the DAG named `dag`
   - Toggle the switch to enable it
   - The DAG will automatically start processing historical runs (catchup enabled)

5. **Monitor the Pipeline:**
   - Click on the DAG name to view the graph
   - Watch tasks execute from 2023-01-01 to 2024-12-01
   - Green = Success, Red = Failed, Yellow = Running, Pink = Skipped

### Stop the Pipeline

```bash
docker-compose down
```

To remove all data and start fresh:

```bash
docker-compose down -v
./cleanup.sh  # Removes generated data files
```

---

## Architecture Overview

This project implements a complete MLOps pipeline using the **medallion architecture** (Bronze → Silver → Gold) with Apache Airflow orchestration.

### Pipeline Flow

```
Raw Data (CSV)
    ↓
Bronze Layer (Raw Ingestion)
    ↓
Silver Layer (Cleaned & Validated)
    ↓
Gold Layer (ML-Ready Features & Labels)
    ↓
Model Training (AutoML) ──→ Model Store
    ↓                            ↓
Inference ←──────────────────────┘
    ↓
Monitoring (Performance Metrics)
    ↓
Visualization & Action Evaluation
```

### Key Features

- **Automated Data Processing**: Bronze → Silver → Gold transformation pipeline
- **Dual Model Training**: Two competing ML models (Logistic Regression, Gradient Boosting)
- **Temporal Validation**: 4-window validation (Train/Val/Test/OOT) to prevent data leakage
- **Conditional Execution**: Smart task skipping based on data availability
- **Performance Monitoring**: Automated metric tracking with threshold-based alerting
- **Visualization**: Automated chart generation for model performance trends
- **Action Evaluation**: Threshold-based recommendation system (MONITOR/RETRAIN/INVESTIGATE)

---

## Project Structure

```
.
├── dags/                          # Airflow DAG definitions
│   └── dag.py                     # Main ML pipeline orchestration
│
├── scripts/                       # All Python processing scripts
│   ├── bronze_*.py                # Raw data ingestion (Bronze layer)
│   ├── silver_*.py                # Data cleaning (Silver layer)
│   ├── gold_*.py                  # Feature/label generation (Gold layer)
│   ├── model_*_automl_v2.py       # Model training scripts
│   ├── model_*_inference.py       # Batch inference scripts
│   ├── model_*_monitor.py         # Performance monitoring scripts
│   ├── visualize_monitoring.py    # Chart generation
│   ├── evaluate_monitoring_action.py  # Threshold-based action evaluation
│   ├── seed_inference_backfill.py # Historical prediction backfill
│   ├── model_config.json          # Training configuration
│   ├── monitoring_thresholds.json # Alert threshold configuration
│   └── utils/                     # Shared utility functions
│
├── data/                          # Source data files
│   ├── lms_loan_daily.csv         # Loan management system data
│   ├── features_attributes.csv    # User demographic features
│   ├── features_financials.csv    # Financial ratio features
│   └── feature_clickstream.csv    # Behavioral features
│
├── model_store/                   # Trained model artifacts
│   ├── model_1/                   # Logistic Regression artifacts
│   │   ├── model.pkl              # Trained model binary
│   │   ├── preprocessing.pkl      # Feature transformers
│   │   ├── metadata.json          # Training metrics & config
│   │   └── features.json          # Feature list
│   └── model_2/                   # Gradient Boosting artifacts
│       └── (same structure as model_1)
│
├── outputs/                       # Pipeline outputs
│   ├── visuals/                   # Performance charts (PNG/HTML)
│   └── actions/                   # Action evaluation reports
│
├── docker-compose.yaml            # Docker services configuration
├── Dockerfile                     # Airflow container definition
├── requirements.txt               # Python dependencies
│
└── Documentation (see below)
```

---

## Documentation Files

This project includes comprehensive documentation. Here's what each markdown file covers:

### 1. [DAG_NODES_EXPLAINED.md](./DAG_NODES_EXPLAINED.md)

**Purpose**: Complete technical reference for all Airflow DAG tasks

**What you'll find**:

- Detailed explanation of all 28 DAG tasks
- Input/output specifications for each script
- Data flow diagrams (Bronze → Silver → Gold)
- Pipeline dependencies and execution order
- Conditional execution logic (ShortCircuitOperators)
- Temporal alignment requirements (MOB=0 predictions vs MOB=6 labels)
- First run behavior vs steady state behavior

**When to use**:

- Understanding what each task does
- Debugging pipeline failures
- Adding new tasks or modifying dependencies
- Understanding the 6-month monitoring lag requirement

### 2. [MODEL_GOVERNANCE_SOP.md](./MODEL_GOVERNANCE_SOP.md)

**Purpose**: Standard Operating Procedures for model lifecycle management

**What you'll find**:

- Model refresh policy (when to retrain models)
- Deployment options (batch vs real-time vs hybrid)
- Monitoring thresholds and alerting framework
- Rollback procedures
- Pre/post-deployment checklists
- Roles and responsibilities
- Compliance and audit requirements

**When to use**:

- Deciding when to retrain models
- Setting up monitoring alerts
- Planning deployment strategies
- Preparing for model deployment
- Understanding governance requirements
- Troubleshooting model performance issues

### 3. [MODEL_TRAINING_CONFIG.md](./MODEL_TRAINING_CONFIG.md)

**Purpose**: Guide to temporal window configuration for model training

**What you'll find**:

- Absolute vs Relative temporal window modes
- How dynamic date calculation works (backward from snapshot_date)
- Minimum data requirements (18 months for training)
- DAG training logic and ShortCircuitOperator checks
- Configuration examples for initial training vs retraining
- Complete troubleshooting guide

**When to use**:

- Configuring model training windows
- Switching between fixed dates and rolling windows
- Understanding why training is skipped
- Debugging "insufficient data" errors
- Setting up monthly/quarterly retraining schedules

### 4. [USEFUL_COMMANDS.md](./USEFUL_COMMANDS.md)

**Purpose**: Quick reference for common operational tasks

**What you'll find**:

- Airflow DAG management commands
- Parquet file inspection commands
- Data availability checks
- Manual inference/monitoring execution
- Docker Compose commands for debugging

**When to use**:

- Inspecting generated data files
- Running manual model inference or monitoring
- Clearing Airflow task history
- Debugging data pipeline issues
- Checking row counts and data schemas

### 5. [task1_plan.md](./task1_plan.md)

**Purpose**: Original implementation plan and design decisions

**What you'll find**:

- Implementation strategy breakdown
- DummyOperator vs BashOperator decisions
- Step-by-step implementation checklist
- Current completion status

**When to use**:

- Understanding the original design rationale
- Tracking implementation progress
- Planning future enhancements

---

## Key Concepts

### Medallion Architecture

**Bronze Layer**: Raw data ingestion with minimal transformation

- Files: `bronze_*.py`
- Output: `scripts/datamart/bronze/`
- Purpose: Create an audit trail of raw data

**Silver Layer**: Cleaned and validated data

- Files: `silver_*.py`
- Output: `scripts/datamart/silver/`
- Purpose: Apply business rules, handle nulls, standardize types

**Gold Layer**: ML-ready feature and label stores

- Files: `gold_*.py`
- Output: `scripts/datamart/gold/`
- Purpose: Aggregated, denormalized tables optimized for ML

### Temporal Validation

The pipeline uses a **4-window temporal split** to prevent data leakage:

1. **Training** (12 months): Model fitting
2. **Validation** (3 months): Hyperparameter tuning
3. **Test** (2 months): Performance evaluation
4. **Out-of-Time (OOT)** (1 month): Future data validation

Total: 18 months of data required before training starts

**Why this matters**: OOT testing simulates real production conditions by evaluating on completely unseen future data.

### MOB=6 Label Requirement

**MOB** = Month on Book (time since loan origination)

- Loans are evaluated at **MOB=6** (6 months after disbursement)
- Predictions are made at **MOB=0** (loan origination)
- Monitoring joins predictions from 6 months ago with current labels

**Example**:

- Predict on 2024-06-01 (MOB=0)
- Evaluate performance on 2024-12-01 (same loans now at MOB=6)

### Conditional Execution

The DAG includes **3 ShortCircuitOperators** that skip tasks when prerequisites aren't met:

1. **check_models_for_inference**: Skips inference if models don't exist
2. **check_inference_for_monitoring**: Skips monitoring if predictions from 6 months ago don't exist
3. **check_training_data**: Skips training if execution_date < 2024-12-01 (insufficient data)

This prevents task failures and enables graceful degradation.

---

## DAG Execution Timeline

The DAG runs monthly from **2023-01-01 to 2024-12-01** with catchup enabled.

### Execution Phases

| Date Range | Data Pipeline | Training | Inference | Monitoring | Why |
|------------|---------------|----------|-----------|------------|-----|
| 2023-01-01 to 2024-11-01 | ✅ Runs | ⏭️ Skipped | ⏭️ Skipped | ⏭️ Skipped | Insufficient data (<18 months) |
| 2024-12-01 | ✅ Runs | ✅ Trains | ⏭️ Skipped | ⏭️ Skipped | First training! Models created |
| After training completes | ✅ Runs | ✅ Retrains | ✅ Runs | ✅ Runs* | Full pipeline operational |

*Monitoring requires predictions from 6 months ago, so it may skip for the first 6 months after inference starts.

### Seed Backfill

After the first training (2024-12-01), the pipeline runs a **seed backfill** task that:

- Generates predictions for the past 8 months (2024-04-01 to 2024-11-01)
- Enables monitoring to start immediately on subsequent runs
- Bootstraps the prediction history needed for temporal analysis

---

## Configuration Files

### model_config.json

Controls temporal window calculation for training:

```json
{
  "temporal_window_mode": "relative",  // or "absolute"
  "relative_windows": {
    "train": {"months_back": 12},
    "validation": {"months_after_train_end": 3},
    "test": {"months_after_validation_end": 2},
    "oot": {"months_after_test_end": 1}
  }
}
```

**Modes**:

- **Absolute**: Fixed dates (best for initial training)
- **Relative**: Rolling windows (best for retraining)

See [MODEL_TRAINING_CONFIG.md](./MODEL_TRAINING_CONFIG.md) for details.

### monitoring_thresholds.json

Defines alert thresholds for model monitoring:

```json
{
  "P0_business_critical": {
    "roc_auc": {"business_threshold": 0.75, "ds_threshold": 0.80}
  },
  "P1_business_important": {
    "accuracy": {"business_threshold": 0.70, "ds_threshold": 0.75}
  },
  "P2_ds_operational": {
    "f1_score": {"ds_threshold": 0.60}
  }
}
```

**Priority Levels**:

- **P0**: Critical (ROC-AUC) - triggers immediate retraining
- **P1**: Important (Accuracy) - triggers investigation
- **P2**: Operational (F1-Score) - monitoring only

See [MODEL_GOVERNANCE_SOP.md](./MODEL_GOVERNANCE_SOP.md) for the complete alerting framework.

---

## Common Operations

### View Pipeline Progress

```bash
# View Airflow logs
docker-compose logs -f airflow-scheduler

# View webserver logs
docker-compose logs -f airflow-webserver
```

### Manual Task Execution

```bash
# Run inference manually
docker-compose exec airflow-scheduler python /opt/airflow/scripts/model_1_inference.py --snapshotdate 2024-12-01

# Run monitoring manually
docker-compose exec airflow-scheduler python /opt/airflow/scripts/model_1_monitor.py --snapshotdate 2024-12-01

# Generate visualizations
docker-compose exec airflow-scheduler python /opt/airflow/scripts/visualize_monitoring.py

# Evaluate monitoring actions
docker-compose exec airflow-scheduler python /opt/airflow/scripts/evaluate_monitoring_action.py --model-id model_1
```

### Clear DAG History

```bash
# Clear all task instances
docker-compose exec airflow-scheduler airflow tasks clear dag \
    --start-date 2023-01-01 \
    --end-date 2024-12-01 \
    --yes
```

Or use the Airflow UI: Browse → DAG Runs → Delete

### Inspect Generated Data

```bash
# List feature store files
ls -la scripts/datamart/gold/feature_store/

# List predictions
ls -la scripts/datamart/gold/predictions/

# List monitoring metrics
ls -la scripts/datamart/gold/monitoring/

# View visualizations
open outputs/visuals/
```

See [USEFUL_COMMANDS.md](./USEFUL_COMMANDS.md) for more commands.

---

## Troubleshooting

### Issue: Tasks are being skipped

**Check the DAG logs** to see which ShortCircuitOperator triggered the skip:

```bash
docker-compose logs airflow-scheduler | grep -i "skip"
```

**Common causes**:

1. **Inference skipped**: Models don't exist yet (wait for training on 2024-12-01)
2. **Monitoring skipped**: No predictions from 6 months ago (expected for first 6 months)
3. **Training skipped**: Execution date < 2024-12-01 (insufficient data)

See [MODEL_TRAINING_CONFIG.md](./MODEL_TRAINING_CONFIG.md) for detailed troubleshooting.

### Issue: Docker container won't start

```bash
# Check container status
docker-compose ps

# View error logs
docker-compose logs airflow-init

# Common fix: restart services
docker-compose down
docker-compose up -d
```

### Issue: Port 8080 already in use

```bash
# Find process using port 8080
lsof -i :8080

# Kill the process or change the port in docker-compose.yaml:
# ports:
#   - "8081:8080"  # Use 8081 instead
```

### Issue: Can't access Airflow UI

1. Wait 60 seconds for initialization to complete
2. Check if containers are running: `docker-compose ps`
3. Verify port mapping: `docker-compose port airflow-webserver 8080`
4. Try accessing: <http://127.0.0.1:8080> instead of localhost

---

## Performance Metrics

The pipeline tracks the following metrics for each model:

### Classification Metrics

- **ROC-AUC**: Area under ROC curve (primary metric)
- **Accuracy**: Overall correctness
- **Precision**: Of predicted defaults, % actually defaulted
- **Recall**: Of actual defaults, % caught by model
- **F1-Score**: Harmonic mean of precision and recall

### Stability Metrics

- **Mean Prediction**: Average predicted probability
- **Std Prediction**: Standard deviation of predictions
- **Prediction Drift**: Change from baseline distribution

### Business Metrics

- **OOT Performance**: Out-of-time validation results
- **Degradation Rate**: Performance drop vs baseline

All metrics are tracked monthly and visualized in `outputs/visuals/`.

---

## Model Artifacts

Each trained model generates the following artifacts:

```
model_store/model_1/
├── model.pkl              # Serialized model binary
├── preprocessing.pkl      # Feature transformers (imputer, scaler)
├── metadata.json          # Training config, metrics, timestamps
├── features.json          # Feature list with data types
└── feature_importance.csv # Feature importance scores (if available)
```

**metadata.json** includes:

- Training/validation/test/OOT performance metrics
- Temporal split dates used for training
- Hyperparameters
- Training timestamp
- Feature count and sample counts

---

## Data Flow Details

### Input Data

| File | Records | Description |
|------|---------|-------------|
| `lms_loan_daily.csv` | ~500K+ | Daily loan snapshots with DPD, MOB |
| `features_attributes.csv` | ~50K | User demographics |
| `features_financials.csv` | ~50K | Financial ratios |
| `feature_clickstream.csv` | ~50K | Behavioral data |

### Intermediate Data (Datamart)

```
scripts/datamart/
├── bronze/              # Raw ingestion (CSV)
├── silver/              # Cleaned data (Parquet)
└── gold/                # ML-ready data (Parquet)
    ├── feature_store/   # Features with snapshot dates
    ├── label_store/     # Labels (30dpd_6mob)
    ├── predictions/     # Model predictions
    └── monitoring/      # Performance metrics
```

### Output Data

```
outputs/
├── visuals/             # Charts and dashboards
│   ├── model_1_performance_trends.png
│   ├── model_2_performance_trends.png
│   └── monitoring_dashboard.html
└── actions/             # Action evaluation reports
    ├── model_1_action_2024_12_01.json
    └── model_1_action_2024_12_01.txt
```

---

## Advanced Topics

### Retraining Strategy

**Quarterly Retraining** (recommended):

1. Edit `model_config.json` to use `"temporal_window_mode": "relative"`
2. Models automatically retrain with rolling windows
3. OOT validation ensures new model quality
4. Deploy only if new model shows ≥2% improvement

See [MODEL_GOVERNANCE_SOP.md](./MODEL_GOVERNANCE_SOP.md) for the complete retraining policy.

### Deployment Options

The project currently implements **batch scoring**:

- Monthly inference via Airflow
- Predictions stored in gold table
- Suitable for portfolio monitoring

**Future considerations**:

- Real-time API deployment (FastAPI + Kubernetes)
- Hybrid approach (batch for existing, API for new loans)

See [MODEL_GOVERNANCE_SOP.md](./MODEL_GOVERNANCE_SOP.md) for deployment architecture comparisons.

### Monitoring & Alerting

Three action levels based on threshold breaches:

1. **MONITOR** (Green): All metrics healthy, continue monthly monitoring
2. **ACTIVE MONITORING** (Yellow): Metrics below DS threshold, increase monitoring frequency
3. **RETRAIN** (Red): Metrics below business threshold, immediate retraining required

Thresholds configured in `scripts/monitoring_thresholds.json`.

---

## Technical Stack

- **Orchestration**: Apache Airflow 2.x
- **Data Processing**: PySpark 3.x
- **ML Framework**: Scikit-learn
- **Storage**: Parquet files (Bronze/Silver/Gold layers)
- **Containerization**: Docker & Docker Compose
- **Visualization**: Matplotlib, Seaborn

---

## Project Status

| Component | Status | Notes |
|-----------|--------|-------|
| Data Pipeline (Bronze → Silver → Gold) | ✅ Complete | All 3 layers operational |
| Label Store | ✅ Complete | 30dpd_6mob labeling logic |
| Feature Store | ✅ Complete | Multi-source feature integration |
| Model Training (AutoML) | ✅ Complete | 2 models with 4-window validation |
| Model Inference | ✅ Complete | Batch scoring pipeline |
| Model Monitoring | ✅ Complete | Performance + stability metrics |
| Visualization | ✅ Complete | Automated chart generation |
| Action Evaluation | ✅ Complete | Threshold-based alerting |
| Seed Backfill | ✅ Complete | Historical prediction bootstrap |

**Total**: 28 DAG tasks, 18 Python scripts, fully operational end-to-end pipeline.

---

## Contributing

When modifying the pipeline:

1. **Update documentation**: Keep markdown files in sync with code changes
2. **Test locally**: Run `docker-compose up` and verify DAG execution
3. **Check data lineage**: Ensure temporal alignment is preserved
4. **Update tests**: Add validation for new features
5. **Follow naming conventions**: `{layer}_{table}.py` for data processing, `model_{id}_{action}.py` for ML tasks

---

## License

Educational project for SMU MiTB CS611 MLE course.

---

## Contact & Support

- **Project Documentation**: See markdown files in this directory
- **Airflow Documentation**: <https://airflow.apache.org/docs/>
- **PySpark Documentation**: <https://spark.apache.org/docs/latest/api/python/>

---

## Quick Links

- [DAG Task Explanations](./DAG_NODES_EXPLAINED.md)
- [Model Governance SOP](./MODEL_GOVERNANCE_SOP.md)
- [Training Configuration Guide](./MODEL_TRAINING_CONFIG.md)
- [Useful Commands Reference](./USEFUL_COMMANDS.md)
- [Implementation Plan](./task1_plan.md)
- [Airflow UI](http://localhost:8080) (when running)

---

**Last Updated**: 2025-10-26
