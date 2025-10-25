# Testing the Data Pipeline with Airflow

## 🧪 Testing Steps

### Step 1: Navigate to Assignment_2 Directory
```bash
cd Assignment_2
```

### Step 2: Start Airflow with Docker Compose
```bash
docker-compose up -d
```

This will start 3 services:
- `airflow-init` - Initializes the database and creates admin user
- `airflow-webserver` - Web UI (port 8080)
- `airflow-scheduler` - Runs the DAGs

### Step 3: Check if Services are Running
```bash
docker-compose ps
```

You should see all 3 services running.

### Step 4: Access Airflow Web UI
Open your browser and go to:
```
http://localhost:8080
```

Login credentials:
- **Username:** `admin`
- **Password:** `admin`

### Step 5: Find Your DAG
In the Airflow UI, you should see a DAG named **"dag"** in the list.

### Step 6: Enable the DAG
Click the toggle switch to enable the DAG (it's off by default).

### Step 7: Test a Single Date First
Since your DAG has `catchup=True` and runs from 2023-01-01 to 2024-12-01, it will try to run 24 backfill runs.

**Option A: Trigger Manual Run for Testing**
1. Click on the DAG name "dag"
2. Click the "Play" button (▶️) in the top right
3. Click "Trigger DAG"
4. This will run it for the latest execution date

**Option B: Test with a Specific Date**
1. Click "Trigger DAG w/ config"
2. Set a specific execution date in the config:
   ```json
   {
     "execution_date": "2023-01-01T00:00:00Z"
   }
   ```

### Step 8: Monitor the DAG Run
1. Click on the DAG name to see the Graph View
2. You'll see all tasks and their dependencies
3. Watch the tasks turn:
   - **Gray** = Not started
   - **Light green** = Queued
   - **Green** = Success
   - **Red** = Failed
   - **Yellow** = Running

### Step 9: Check Task Logs (if failures occur)
1. Click on any task box
2. Click "Log" to see detailed output
3. This will show you the Python script execution logs

### Step 10: Verify Output Data
After successful run, check the datamart directories:
```bash
ls -R Assignment_2/scripts/datamart/
```

You should see:
```
datamart/
├── bronze/
│   ├── lms/
│   └── features/
│       ├── attributes/
│       ├── financials/
│       └── clickstream/
├── silver/
│   ├── loan_daily/
│   ├── attributes/
│   ├── financials/
│   └── clickstream/
└── gold/
    ├── label_store/
    └── feature_store/
```

### Step 11: Stop Airflow When Done
```bash
docker-compose down
```

To keep the data but stop services:
```bash
docker-compose stop
```

---

## 🔧 Troubleshooting Tips

**If DAG doesn't appear:**
- Wait 30-60 seconds for scheduler to pick it up
- Check logs: `docker-compose logs airflow-scheduler`

**If tasks fail:**
- Check the task logs in the UI
- Common issues:
  - Missing data files in `data/` directory
  - Python dependencies not installed
  - Path issues (data/ should be accessible)

**To restart fresh:**
```bash
docker-compose down -v  # Removes volumes (resets everything)
docker-compose up -d
```

**View live logs:**
```bash
docker-compose logs -f airflow-scheduler
docker-compose logs -f airflow-webserver
```

---

## 💡 Important Notes

1. **Data Directory:** Make sure `Assignment_2/data/` contains all 4 CSV files
2. **First Run:** The first `catchup` run will process all 24 months sequentially
3. **Performance:** Each month processes independently, so it may take a while
4. **DummyOperators:** Model inference and monitoring tasks are still DummyOperators - they'll show as successful but won't do anything yet

---

## 📝 Testing Status Log

### [Date: YYYY-MM-DD]

**Step 2 Status:**
- [ ] Services started successfully
- [ ] Issues encountered:

**Step 3 Status:**
- [ ] All services running
- [ ] Service status:

**Step 4 Status:**
- [ ] Web UI accessible
- [ ] Login successful

**Step 5 Status:**
- [ ] DAG visible in UI
- [ ] Issues:

**Step 8 Status:**
- [ ] DAG run completed
- [ ] Tasks succeeded:
- [ ] Tasks failed:
- [ ] Error messages:

**Step 10 Status:**
- [ ] Output data verified
- [ ] Directory structure correct
- [ ] Files generated:

**Notes:**

## State

### ✅ **Current Status as of 2025-10-25 Saturday:**

**COMPLETED - Sections 1 & 2:**

#### Section 1: Establish Data Foundations ✅
- ✅ Utils scripts created and tested
- ✅ Bronze → Silver → Gold ETL pipeline working
- ✅ Monthly snapshot strategy implemented (2023-01-01 to 2024-12-01)

#### Section 2: Airflow Orchestration Setup ✅
- ✅ Docker-compose configured with data volume mount
- ✅ DAG created with proper dependencies
- ✅ All data pipeline BashOperators implemented:
  - ✅ `bronze_label_store.py` - LMS data ingestion
  - ✅ `silver_label_store.py` - Loan data cleaning
  - ✅ `gold_label_store.py` - Label generation (dpd=30, mob=6)
  - ✅ `bronze_table_1.py` - Attributes ingestion
  - ✅ `bronze_table_2.py` - Financials ingestion
  - ✅ `bronze_table_3.py` - Clickstream ingestion
  - ✅ `silver_table_1.py` - Attributes + Financials cleaning
  - ✅ `silver_table_2.py` - Clickstream cleaning
  - ✅ `gold_feature_store.py` - Feature store assembly
- ✅ Pipeline tested and working in Airflow

**Pipeline Status:**
- ✅ Label Store: Bronze → Silver → Gold (Working)
- ✅ Feature Store: Bronze → Silver → Gold (Working)
- ⏸️ Model Training: DummyOperators (Not implemented)
- ⏸️ Model Inference: DummyOperators (Not implemented)
- ⏸️ Model Monitoring: DummyOperators (Not implemented)

### ❌ **Not Yet Started - Sections 3-9:**

**Section 3: Model Training & Evaluation**
- Need: `model_1_automl.py` and `model_2_automl.py`
- Replace DummyOperators at lines 166-168 in dag.py

**Section 4: Model Selection & Model Store**
- Integrated into Section 3 scripts
- Model artifacts save to `model_store/model_1/` and `model_store/model_2/`

**Section 5: Inference Pipeline**
- Need: `model_1_inference.py` and `model_2_inference.py`
- Replace DummyOperators at lines 135-137 in dag.py

**Section 6: Monitoring Pipeline**
- Need: `model_1_monitor.py` and `model_2_monitor.py`
- Replace DummyOperators at lines 150-152 in dag.py

**Section 7: Visualization**
- Need: Visualization script/notebook
- Read monitoring gold tables and generate plots

**Section 8: Governance/SOP Documentation**
- Need: SOP document for model refresh policy

**Section 9: Validation & Delivery**
- Need: Final validation and packaging

---

## **Immediate Next Steps:**

**Priority 1: Gather Training Data**
```bash
# Let all 24 months run to completion OR
# Verify sufficient gold tables exist for training
ls -R Assignment_2/scripts/datamart/gold/
```

**Priority 2: Implement ML Scripts (6 scripts needed)**
```
1. model_1_automl.py - Train Model 1 (e.g., Logistic Regression)
2. model_2_automl.py - Train Model 2 (e.g., Gradient Boosted Trees)
3. model_1_inference.py - Generate predictions with Model 1
4. model_2_inference.py - Generate predictions with Model 2
5. model_1_monitor.py - Monitor Model 1 performance
6. model_2_monitor.py - Monitor Model 2 performance
```

**Priority 3: Update DAG**
```
Replace DummyOperators with BashOperators calling the 6 ML scripts
```

**Priority 4: Visualization & Documentation**
```
Create visualization script and SOP documentation
```
