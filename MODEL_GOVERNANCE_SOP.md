# Model Governance and Standard Operating Procedures (SOP)

## Document Information

- **Document Version**: 1.0
- **Last Updated**: 2025-10-25
- **Owner**: ML Engineering Team
- **Review Cycle**: Quarterly

---

## Table of Contents

1. [Overview](#overview)
2. [Model Lifecycle](#model-lifecycle)
3. [Model Refresh Policy](#model-refresh-policy)
4. [Deployment Options](#deployment-options)
5. [Monitoring and Alerting](#monitoring-and-alerting)
6. [Operational Checklist](#operational-checklist)
7. [Roles and Responsibilities](#roles-and-responsibilities)
8. [Model Registry and Versioning](#model-registry-and-versioning)
9. [Rollback Procedures](#rollback-procedures)
10. [Compliance and Audit](#compliance-and-audit)

---

## Overview

This document defines the governance framework and standard operating procedures for managing credit risk ML models in production. It covers model refresh triggers, deployment strategies, monitoring requirements, and operational workflows.

### Scope

- **Models Covered**: Credit default prediction models (Model 1: Logistic Regression, Model 2: Gradient Boosting)
- **Data Pipeline**: Bronze → Silver → Gold feature/label stores
- **Prediction Cadence**: Monthly batch scoring
- **Monitoring Frequency**: Monthly performance evaluation

---

## Model Lifecycle

### 1. Development Phase

**Activities:**

- Feature engineering and selection
- Temporal data splitting (Train/Val/Test/OOT)
- Model training with hyperparameter tuning
- Validation against multiple metrics (ROC-AUC, Accuracy, F1)

**Artifacts:**

- Training scripts (`model_1_automl_v2.py`, `model_2_automl_v2.py`)
- Configuration files (`model_config.json`)
- Temporal split documentation

**Approval Gate:** Model Developer

### 2. Evaluation Phase

**Activities:**

- Out-of-Time (OOT) testing on completely unseen future data
- Model comparison (Model 1 vs Model 2)
- Performance metrics validation
- Business impact assessment

**Artifacts:**

- OOT performance metrics (ROC-AUC, Accuracy, Precision, Recall, F1)
- Confusion matrices
- Feature importance analysis

**Approval Gate:** ML Team Lead + Risk Analytics Team

### 3. Deployment Phase

**Activities:**

- Model artifact packaging
- Model store registration
- Inference pipeline setup
- Monitoring configuration

**Artifacts:**

- Model binaries (`model.pkl`)
- Preprocessing transformers (`preprocessing.pkl`)
- Metadata files (`metadata.json`, `features.json`)
- Deployment documentation

**Approval Gate:** ML Engineering Manager + Risk Management

### 4. Production Phase

**Activities:**

- Monthly batch inference
- Performance monitoring
- Drift detection
- Visualization generation

**Artifacts:**

- Prediction outputs (gold table)
- Monitoring metrics (gold table)
- Performance visualizations
- Summary reports

**Approval Gate:** Automated with alert-based reviews

---

## Model Refresh Policy

### Triggers for Model Retraining

#### 1. Scheduled Retraining (Proactive)

**Frequency:** Quarterly (Every 3 months)

**Rationale:**

- Incorporates latest 3 months of data
- Adapts to seasonal trends
- Preventive maintenance

**Process:**

1. Run training pipeline on latest data using `relative` temporal windows
2. Evaluate OOT performance
3. Compare with current production model
4. Deploy if new model shows ≥2% improvement in ROC-AUC

#### 2. Performance Degradation (Reactive)

**Trigger Conditions:**

| Metric | Threshold | Severity |
|--------|-----------|----------|
| ROC-AUC drops below 0.75 | Critical | Immediate retraining required |
| ROC-AUC drops below 0.80 | Warning | Retraining within 1 month |
| ROC-AUC drops >5% from OOT baseline | Warning | Investigation required |
| Accuracy drops below 70% | Critical | Immediate review |
| F1-Score drops below 0.60 | Warning | Monitor closely |

**Process:**

1. Alert triggered via monitoring pipeline
2. ML Team investigates root cause (data drift, label quality, feature degradation)
3. Emergency retraining initiated if confirmed degradation
4. Accelerated deployment approval process

#### 3. Data Drift Detection (Proactive)

**Trigger Conditions:**

- Mean prediction probability shifts >15% from baseline
- Prediction distribution std deviation changes >20%
- Feature distribution monitoring (manual quarterly review)

**Process:**

1. Analyze drift source (population shift vs model degradation)
2. Decide: Feature recalibration vs full retraining
3. Document findings and corrective actions

#### 4. Regulatory or Business Rule Changes

**Trigger Conditions:**

- New lending policy introduced
- Regulatory requirements updated
- Target definition changes (e.g., 30dpd → 60dpd)

**Process:**

1. Business stakeholder initiates change request
2. Impact assessment on current model
3. Scheduled retraining with updated labels/features
4. Full validation cycle before deployment

### Retraining Configuration

**Temporal Window Mode:**

- **Initial Training**: `absolute` mode with fixed dates (2023-01-01 to 2024-05-01)
- **Production Retraining**: `relative` mode with rolling windows
  - Training: Last 12 months
  - Validation: Next 3 months
  - Test: Next 2 months
  - OOT: Next 1 month

**Configuration File:** `scripts/model_config.json`

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

---

## Deployment Options

### Option 1: Batch Scoring (Current Implementation) ✅

**Architecture:**

- Airflow DAG scheduled monthly (1st of each month)
- Reads features from gold feature store
- Loads model from model store
- Writes predictions to gold predictions table

**Pros:**

- **Simplicity**: Minimal infrastructure (Airflow + Spark)
- **Cost-effective**: No 24/7 API hosting
- **Fault-tolerant**: Built-in Airflow retry mechanisms
- **Auditable**: Full lineage tracking via Parquet files
- **Suitable for use case**: Credit decisions don't require real-time scoring

**Cons:**

- **Latency**: Predictions only available monthly
- **Scalability**: Limited to scheduled batch windows

**Best For:**

- Portfolio monitoring and review
- Monthly credit limit adjustments
- Regulatory reporting

**Implementation:**

```bash
# Airflow DAG task
model_1_inference = BashOperator(
    task_id="model_1_inference",
    bash_command="cd /opt/airflow/scripts && python3 model_1_inference.py --snapshotdate {{ ds }}"
)
```

---

### Option 2: Real-Time API Deployment (Future Consideration)

**Architecture:**

- RESTful API service (Flask/FastAPI)
- Model loaded in-memory for low-latency predictions
- Kubernetes for auto-scaling and high availability
- Redis cache for frequent feature lookups

**Pros:**

- **Low Latency**: <100ms prediction response time
- **On-Demand**: Predictions available anytime
- **Interactive**: Supports loan origination workflows

**Cons:**

- **Infrastructure Cost**: Requires 24/7 hosting (Kubernetes, load balancers)
- **Complexity**: Monitoring, logging, versioning, A/B testing
- **Data Freshness**: Requires real-time feature computation
- **Model Synchronization**: More complex deployment pipeline

**Best For:**

- Online loan applications
- Point-of-sale credit decisions
- Real-time risk assessments

**Sample Implementation:**

```python
# FastAPI endpoint (conceptual)
@app.post("/predict")
async def predict(loan_features: LoanFeatures):
    model = load_model_from_store("model_2")
    features = preprocess(loan_features)
    prediction = model.predict_proba(features)
    return {"default_probability": float(prediction[0][1])}
```

**Deployment Requirements:**

- Model versioning strategy (blue-green deployment)
- SLA definition (99.9% uptime, <100ms p95 latency)
- Load testing (target: 1000 requests/sec)
- Monitoring (Prometheus, Grafana)

---

### Option 3: Hybrid Approach (Recommended for Scale)

**Architecture:**

- **Batch Scoring**: Existing portfolio (monthly refresh)
- **Real-Time API**: New loan applications only

**Pros:**

- **Cost Optimization**: Batch for bulk, API for critical path
- **Gradual Migration**: Start with API for new loans, expand later
- **Risk Mitigation**: Test API on subset before full migration

**Implementation Phases:**

1. **Phase 1** (Current): Batch-only
2. **Phase 2** (6 months): Batch + API for new applications (10% traffic)
3. **Phase 3** (12 months): Expand API to 50% traffic
4. **Phase 4** (18 months): Full migration decision based on metrics

---

## Monitoring and Alerting

### Threshold Framework

The monitoring system uses a **three-tier priority framework** with separate Business and Data Science thresholds:

**Priority Levels:**

- **P0**: Critical business metrics directly impacting credit decisions (ROC-AUC)
- **P1**: Important business metrics affecting operational efficiency (Accuracy)
- **P2**: Data Science operational metrics for technical health (F1-Score)
- **P3**: Data Science diagnostic metrics for detailed analysis (Precision, Recall)

**Threshold Philosophy:**

- **Business Thresholds**: Minimum acceptable performance for business operations
- **Data Science Thresholds**: Early warning buffer (set higher than business thresholds)
- **Purpose**: Enable proactive intervention before reaching critical levels

### Monitoring Metrics and Thresholds

Configuration file: `scripts/monitoring_thresholds.json`

| Metric | Priority | Business Threshold | Data Science Threshold | Owner |
|--------|----------|-------------------|----------------------|-------|
| **ROC-AUC** | P0 | ≥0.75 | ≥0.80 | Business + DS |
| **Accuracy** | P1 | ≥0.70 | ≥0.75 | Business + DS |
| **F1-Score** | P2 | N/A | ≥0.60 | Data Science |
| **Precision** | P3 | N/A | ≥0.60 | Data Science |
| **Recall** | P3 | N/A | ≥0.65 | Data Science |

**Stability Metrics:**

- Mean prediction probability drift: <15% from baseline
- Prediction std deviation drift: <20% from baseline

**Baseline Comparison:**

- OOT vs Production ROC-AUC: max 5% degradation
- OOT vs Production Accuracy: max 5% degradation

### Action Determination Logic

Three action levels based on P0 and P1 metric performance:

#### 1. monitor (Green)

**Trigger:** All P0 and P1 metrics above data science thresholds

**Action Required:** Continue normal monthly monitoring cycle

**Notification:** Monthly email report to ML team (informational)

**Example:** ROC-AUC ≥ 0.80, Accuracy ≥ 0.75

#### 2. active_monitoring (Yellow)

**Trigger:** Any P0 or P1 metric below data science threshold but above business threshold

**Examples:**

- `0.75 ≤ ROC-AUC < 0.80`
- `0.70 ≤ Accuracy < 0.75`

**Action Required:**

1. Increase monitoring frequency (weekly instead of monthly)
2. Investigate root cause (data drift, feature quality, population shift)
3. Prepare retraining plan as contingency
4. Set up additional alerting for further degradation

**Notification:**

- Slack alert to `#ml-monitoring` channel
- Email to ML team
- Frequency: Immediate upon detection

**Sample Alert:**

```
⚠️  WARNING: Active Monitoring Required
Model: model_1
Metric: ROC-AUC (0.7850)
Status: Below DS threshold (0.80) but above business threshold (0.75)
Action: Investigate root cause and prepare for potential retraining
```

#### 3. retrain (Red)

**Trigger:** Any P0 or P1 metric below business threshold

**Examples:**

- `ROC-AUC < 0.75`
- `Accuracy < 0.70`

**Action Required:**

1. Initiate emergency retraining workflow immediately
2. Investigate root cause (data quality, model drift, label issues)
3. Notify all stakeholders (Risk team, Product team)
4. Schedule retraining to complete within 1 week
5. Prepare rollback plan

**Notification:**

- PagerDuty alert to on-call ML engineer
- Slack alert to `#ml-monitoring` channel
- Email to ML team + Risk team
- Frequency: Immediate upon detection

**Sample Alert:**

```
❌ CRITICAL: Model Retraining Required
Model: model_1
Metric: ROC-AUC (0.7300)
Status: Below BUSINESS threshold (0.75)
Action: Immediate retraining required within 1 week
Stakeholders notified: ML team, Risk team
```

### Action Evaluation Pipeline

**Script:** `scripts/evaluate_monitoring_action.py`

**Process:**

1. Load latest monitoring metrics from gold table
2. Load threshold configuration from `monitoring_thresholds.json`
3. Load OOT baseline metrics from model store (for comparison)
4. Evaluate each metric against thresholds
5. Determine overall action based on priority rules
6. Generate detailed action report
7. Save decision to `outputs/actions/model_X_action_YYYY_MM_DD.json`

**Usage:**

```bash
# Evaluate action for model_1
python evaluate_monitoring_action.py --model-id model_1

# Evaluate action for model_2
python evaluate_monitoring_action.py --model-id model_2
```

**Output Files:**

- `outputs/actions/model_X_action_YYYY_MM_DD.json` - Machine-readable decision
- `outputs/actions/model_X_action_YYYY_MM_DD.txt` - Human-readable report

### Monitoring Pipeline

**Location:** `scripts/model_1_monitor.py`, `scripts/model_2_monitor.py`

**Inputs:**

- Predictions from gold predictions table (mob=0)
- Labels from gold label store (mob=6, 6 months later)

**Outputs:**

- Metrics: `datamart/gold/monitoring/model_X_metrics_YYYY_MM_DD.parquet`
- Visualizations: `outputs/visuals/` (via `visualize_monitoring.py`)

**Temporal Alignment:**

- Monitoring on `2024-12-01` uses:
  - Predictions from `2024-06-01` (loans at mob=0)
  - Labels from `2024-12-01` (same loans now at mob=6)

### Threshold Maintenance

**Review Frequency:** Quarterly

**Review Process:**

1. ML Team Lead schedules threshold review meeting
2. Review actual vs threshold performance for past quarter
3. Analyze false positive/negative business impact
4. Consult with Risk team on business requirements
5. Update `monitoring_thresholds.json` if needed
6. Document changes in change log
7. Notify all stakeholders of threshold updates

**Considerations for Threshold Updates:**

- Business risk appetite changes
- Regulatory requirement updates
- Historical model performance trends
- Cost of false positives vs false negatives
- Competitive landscape changes

**Change Management:**

- Threshold changes require ML Team Lead + Risk Analytics approval
- Changes must be communicated 1 week before implementation
- Previous threshold values archived for audit trail

### DAG Integration (Optional)

The action evaluation can be integrated into the Airflow DAG as a post-monitoring task:

```python
# In dags/dag.py - Add after visualization

evaluate_actions = BashOperator(
    task_id="evaluate_monitoring_actions",
    bash_command=(
        "cd /opt/airflow/scripts && "
        "python3 evaluate_monitoring_action.py --model-id model_1 && "
        "python3 evaluate_monitoring_action.py --model-id model_2"
    ),
    trigger_rule="all_done",
)

# Add dependency
visualize_monitoring >> evaluate_actions
```

**Benefits of DAG Integration:**

- Automatic action determination after each monitoring cycle
- Consistent evaluation process
- Audit trail of all decisions
- Can trigger alerts/notifications based on action level

**Current Implementation:**

- Action evaluation runs manually when needed
- Enables ad-hoc analysis and investigation
- Recommended for initial implementation, migrate to automated later

---

## Operational Checklist

### Pre-Deployment Checklist

Before deploying a new model to production:

- [ ] **Training Validation**
  - [ ] OOT ROC-AUC ≥ 0.80 (minimum threshold)
  - [ ] OOT performance comparable to Test performance (max 3% difference)
  - [ ] No significant overfitting (Train vs Val ROC-AUC delta < 5%)
  - [ ] Feature importance aligns with business logic

- [ ] **Data Quality**
  - [ ] Feature store contains all required features
  - [ ] No excessive missing values (>10% nulls in any feature)
  - [ ] Label definition matches training configuration
  - [ ] Temporal alignment validated (mob=0 predictions, mob=6 labels)

- [ ] **Model Artifacts**
  - [ ] `model.pkl` saved and loadable
  - [ ] `preprocessing.pkl` contains correct transformers
  - [ ] `metadata.json` includes full training lineage
  - [ ] `features.json` lists all required features with data types

- [ ] **Testing**
  - [ ] Inference script runs successfully on sample data
  - [ ] Monitoring script produces metrics without errors
  - [ ] Visualization script generates charts
  - [ ] Predictions match expected format (probability, label, loan_id)

- [ ] **Documentation**
  - [ ] Model card created (performance, limitations, intended use)
  - [ ] Deployment date recorded
  - [ ] Change log updated
  - [ ] Stakeholders notified (Risk team, Product team)

- [ ] **Approval**
  - [ ] ML Team Lead sign-off
  - [ ] Risk Analytics Team sign-off
  - [ ] ML Engineering Manager approval

### Post-Deployment Checklist

After deploying a new model:

- [ ] **Verification**
  - [ ] First inference run completed successfully
  - [ ] Prediction counts match expected volume
  - [ ] Predictions written to gold table
  - [ ] Monitoring metrics available (after 6-month maturation)

- [ ] **Monitoring Setup**
  - [ ] Alert rules configured
  - [ ] Visualization dashboard accessible
  - [ ] Baseline metrics documented for comparison

- [ ] **Communication**
  - [ ] Deployment announcement to stakeholders
  - [ ] Updated model performance summary shared
  - [ ] Next monitoring date communicated

- [ ] **Archival**
  - [ ] Previous model artifacts archived (not deleted)
  - [ ] Rollback procedure tested
  - [ ] Performance comparison documented

---

## Roles and Responsibilities

### ML Engineer

**Responsibilities:**

- Develop and maintain training pipelines
- Implement inference and monitoring scripts
- Troubleshoot pipeline failures
- Respond to performance degradation alerts

**Accountable For:**

- Model training execution
- Inference pipeline reliability
- Monitoring accuracy

### ML Team Lead

**Responsibilities:**

- Review model performance before deployment
- Approve model refresh decisions
- Define alert thresholds
- Coordinate with Risk Analytics team

**Accountable For:**

- Model quality standards
- Deployment approval
- SOP compliance

### Risk Analytics Team

**Responsibilities:**

- Validate business impact of model predictions
- Define acceptable performance thresholds
- Review monitoring reports
- Escalate regulatory concerns

**Accountable For:**

- Business metric alignment
- Regulatory compliance
- Stakeholder communication

### ML Engineering Manager

**Responsibilities:**

- Oversee MLOps infrastructure
- Approve deployment to production
- Manage cross-functional coordination
- Budget allocation for infrastructure

**Accountable For:**

- Production stability
- Resource allocation
- Strategic roadmap

---

## Model Registry and Versioning

### Model Store Structure

```
scripts/model_store/
├── model_1/
│   ├── model.pkl                    # Trained model binary
│   ├── preprocessing.pkl            # Feature transformers (imputer, scaler)
│   ├── metadata.json                # Training metadata (dates, metrics, config)
│   ├── features.json                # Feature names and types
│   └── feature_importance.csv       # Feature importance scores
└── model_2/
    ├── model.pkl
    ├── preprocessing.pkl
    ├── metadata.json
    ├── features.json
    └── feature_importance.csv
```

### Metadata Schema

**File:** `metadata.json`

```json
{
  "model_id": "model_1",
  "model_name": "logistic_regression",
  "model_type": "Logistic Regression",
  "training_date": "2025-10-25 13:48:21",
  "snapshot_date": "2024-12-01",
  "label_definition": "30dpd_6mob",

  "temporal_splits": {
    "train": {"start_date": "2023-01-01", "end_date": "2023-12-01"},
    "validation": {"start_date": "2024-01-01", "end_date": "2024-02-01"},
    "test": {"start_date": "2024-03-01", "end_date": "2024-04-01"},
    "oot": {"start_date": "2024-05-01", "end_date": "2024-05-01"}
  },

  "performance_metrics": {
    "train_roc_auc": 0.8291,
    "val_roc_auc": 0.8420,
    "test_roc_auc": 0.8352,
    "oot_roc_auc": 0.8253
  },

  "hyperparameters": {
    "max_iter": 1000,
    "C": 1.0,
    "class_weight": "balanced",
    "random_state": 42
  },

  "feature_count": 83,
  "train_samples": 5958
}
```

### Versioning Strategy

**Current Approach (Overwrite):**

- Each retraining overwrites `model_store/model_1/`
- Previous model artifacts lost unless manually backed up

**Recommended Approach (Versioned Storage):**

```
scripts/model_store/
├── model_1/
│   ├── v20251025_134821/   # Timestamp-based versioning
│   │   ├── model.pkl
│   │   ├── metadata.json
│   │   └── ...
│   ├── v20251125_091442/
│   └── latest -> v20251125_091442/   # Symlink to active version
└── model_2/
    └── ...
```

**Benefits:**

- Easy rollback to previous versions
- A/B testing capability
- Audit trail for compliance
- Gradual rollout (champion/challenger)

---

## Rollback Procedures

### When to Rollback

**Immediate Rollback Triggers:**

- Production ROC-AUC drops below 0.70 (vs OOT ≥ 0.80)
- Inference pipeline crashes repeatedly (>3 failures)
- Data quality issues detected (corrupted features)
- Regulatory non-compliance identified

**Rollback Decision Matrix:**

| Issue Severity | ROC-AUC Drop | Action | Timeline |
|---------------|--------------|--------|----------|
| Critical | >15% from baseline | Immediate rollback | <2 hours |
| High | 10-15% | Rollback + investigation | <1 day |
| Medium | 5-10% | Investigate first, rollback if needed | <3 days |
| Low | <5% | Monitor, no rollback | N/A |

### Rollback Steps

**Preparation (Before Deployment):**

1. Archive current production model artifacts to `model_store_backup/`
2. Document current model version ID and deployment date
3. Verify backup model can load and run inference

**Rollback Execution:**

```bash
# Step 1: Stop inference pipeline
# (Manually pause Airflow DAG or mark task as skipped)

# Step 2: Restore previous model artifacts
cd /opt/airflow/scripts/model_store
cp -r ../model_store_backup/model_1/* model_1/
cp -r ../model_store_backup/model_2/* model_2/

# Step 3: Verify restored model
python3 model_1_inference.py --snapshotdate 2024-12-01 --dry-run

# Step 4: Resume inference pipeline
# (Unpause Airflow DAG)

# Step 5: Run monitoring on next cycle
# Verify rolled-back model performance recovers

# Step 6: Document incident
# Update change log, notify stakeholders
```

**Post-Rollback:**

- Conduct root cause analysis (RCA)
- Document lessons learned
- Update SOPs if process gaps identified
- Schedule retraining with fixes

### Testing Rollback Procedure

**Frequency:** Quarterly (during off-peak, e.g., 2nd week of quarter)

**Process:**

1. Simulate deployment of intentionally degraded model
2. Trigger rollback based on monitoring alerts
3. Time rollback execution (target: <2 hours)
4. Validate service restoration
5. Document improvements to procedure

---

## Compliance and Audit

### Regulatory Requirements

**Applicable Regulations:**

- **Fair Lending Laws**: Model predictions must not discriminate based on protected classes
- **Model Risk Management**: SR 11-7 (Supervisory Guidance on Model Risk Management)
- **Data Privacy**: GDPR/CCPA compliance for customer data

**Compliance Measures:**

- Feature exclusion: Remove race, gender, religion from model features
- Disparate impact testing: Monitor default rate predictions across demographic groups
- Model documentation: Maintain model cards with limitations and intended use
- Data retention: Audit logs retained for 7 years

### Audit Trail

**Required Documentation:**

1. **Training Lineage**
   - Data snapshot dates used for training
   - Feature schema and transformations
   - Hyperparameters and random seeds
   - Training, validation, test, OOT metrics

2. **Deployment Records**
   - Model version deployed
   - Deployment timestamp
   - Approver names and timestamps
   - Rollback events (if any)

3. **Monitoring History**
   - Monthly performance metrics
   - Alert triggers and resolutions
   - Drift detection events
   - Visualization archives

4. **Change Log**
   - Model refresh decisions and rationale
   - Configuration changes
   - SOP updates
   - Incident reports

**Storage:**

- **Location**: `scripts/audit_logs/` (append-only)
- **Format**: JSON with timestamps and digital signatures
- **Retention**: 7 years
- **Access Control**: ML Engineering Manager + Compliance Officer

### Periodic Reviews

**Monthly:**

- Review monitoring metrics
- Check alert history
- Update visualization dashboard

**Quarterly:**

- Model performance review with Risk team
- Feature importance analysis
- Drift detection review
- Rollback procedure testing

**Annually:**

- Full model validation (independent validation team)
- Compliance audit
- SOP review and updates
- Stakeholder feedback collection

---

## Appendix

### A. Glossary

- **OOT (Out-of-Time)**: Test dataset from a future time period, unseen during training
- **ROC-AUC**: Receiver Operating Characteristic - Area Under Curve, measures model discrimination
- **30dpd_6mob**: 30 Days Past Due at Month-on-Book 6
- **mob=0**: Month-on-Book 0, loan origination date
- **mob=6**: Month-on-Book 6, six months after loan origination

### B. Key Metrics Reference

| Metric | Formula | Interpretation | Acceptable Range |
|--------|---------|---------------|------------------|
| ROC-AUC | Area under TPR/FPR curve | Model's ability to rank defaults higher | ≥0.75 (Good: ≥0.80) |
| Accuracy | (TP+TN)/(TP+TN+FP+FN) | Overall correctness | ≥0.70 |
| Precision | TP/(TP+FP) | Of predicted defaults, % correct | ≥0.60 |
| Recall | TP/(TP+FN) | Of actual defaults, % caught | ≥0.65 |
| F1-Score | 2×(Precision×Recall)/(Precision+Recall) | Balance of precision/recall | ≥0.60 |

### C. Contact Information

- **ML Engineering Team**: <ml-engineering@company.com>
- **Risk Analytics Team**: <risk-analytics@company.com>
- **On-Call ML Engineer**: PagerDuty rotation
- **Compliance Officer**: <compliance@company.com>

### D. Document Change History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-25 | ML Engineering Team | Initial SOP creation |

---

**Document Approval:**

| Role | Name | Signature | Date |
|------|------|-----------|------|
| ML Team Lead | ___________________ | ___________________ | ___________ |
| Risk Analytics Lead | ___________________ | ___________________ | ___________ |
| ML Engineering Manager | ___________________ | ___________________ | ___________ |
| Compliance Officer | ___________________ | ___________________ | ___________ |

---

**END OF DOCUMENT**
