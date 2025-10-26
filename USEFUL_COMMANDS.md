# Useful Commands

## Airflow - Clear Previous Runs

```bash
docker-compose exec airflow-scheduler airflow tasks clear dag \
    --start-date 2023-01-01 \
    --end-date 2024-12-01 \
    --yes
```

Or go to Airflow UI, select the DAG, and click delete and confirm.

---

## Parquet File Inspection

### List Available Parquet Files by Date

**List all 2024 feature store files:**
```bash
ls -la Assignment_2/scripts/datamart/gold/feature_store/ | grep "2024"
```

**List all 2024 label store files:**
```bash
ls -la Assignment_2/scripts/datamart/gold/label_store/ | grep "2024"
```

**List files for specific months (Apr-Sept):**
```bash
ls -la Assignment_2/scripts/datamart/gold/feature_store/ | grep -E "2024_(0[4-9]|1[0-2])"
```

---

### Check Row Counts in Parquet Files

**Quick count for a single file:**
```bash
cd Assignment_2/scripts
python3 -c "
import pyspark.sql
spark = pyspark.sql.SparkSession.builder.appName('check').master('local[*]').getOrCreate()
spark.sparkContext.setLogLevel('ERROR')
df = spark.read.parquet('datamart/gold/label_store/gold_label_store_2024_07_01.parquet')
print(f'July 2024 labels: {df.count()} rows')
spark.stop()
"
```

**Check multiple months at once:**
```bash
cd Assignment_2/scripts
python3 << 'EOF'
import pyspark.sql
import warnings
warnings.filterwarnings('ignore')

spark = pyspark.sql.SparkSession.builder.appName('check').master('local[*]').getOrCreate()
spark.sparkContext.setLogLevel('ERROR')

print("\n2024 Data Availability:")
print("="*60)
for month in ['04', '05', '06', '07', '08', '09']:
    try:
        feat = spark.read.parquet(f'datamart/gold/feature_store/gold_feature_store_2024_{month}_01.parquet')
        label = spark.read.parquet(f'datamart/gold/label_store/gold_label_store_2024_{month}_01.parquet')
        joined = feat.join(
            label.select('loan_id', 'Customer_ID', 'label'),
            on=['loan_id', 'Customer_ID'],
            how='inner'
        )
        print(f'2024-{month}-01: Feat={feat.count():4d}, Label={label.count():4d}, Joined={joined.count():4d}')
    except Exception as e:
        print(f'2024-{month}-01: ERROR - {str(e)[:50]}')

spark.stop()
EOF
```

---

### Inspect Parquet Schema

**View schema for feature store:**
```bash
cd Assignment_2/scripts
python3 << 'EOF'
import pyspark.sql
spark = pyspark.sql.SparkSession.builder.appName('schema').master('local[*]').getOrCreate()
spark.sparkContext.setLogLevel('ERROR')

df = spark.read.parquet('datamart/gold/feature_store/gold_feature_store_2024_01_01.parquet')
print("\nFeature Store Schema:")
df.printSchema()
print(f"\nTotal columns: {len(df.columns)}")
print(f"Total rows: {df.count()}")

spark.stop()
EOF
```

**View schema for label store:**
```bash
cd Assignment_2/scripts
python3 << 'EOF'
import pyspark.sql
spark = pyspark.sql.SparkSession.builder.appName('schema').master('local[*]').getOrCreate()
spark.sparkContext.setLogLevel('ERROR')

df = spark.read.parquet('datamart/gold/label_store/gold_label_store_2024_01_01.parquet')
print("\nLabel Store Schema:")
df.printSchema()
print(f"\nTotal rows: {df.count()}")

# Show label distribution
print("\nLabel Distribution:")
df.groupBy('label').count().orderBy('label').show()

spark.stop()
EOF
```

---

### View Sample Data

**View first 10 rows of feature store:**
```bash
cd Assignment_2/scripts
python3 << 'EOF'
import pyspark.sql
spark = pyspark.sql.SparkSession.builder.appName('sample').master('local[*]').getOrCreate()
spark.sparkContext.setLogLevel('ERROR')

df = spark.read.parquet('datamart/gold/feature_store/gold_feature_store_2024_01_01.parquet')
print("\nFeature Store Sample (first 10 rows):")
df.show(10, truncate=False)

spark.stop()
EOF
```

---

### Check Date Range Coverage

**Find min/max snapshot dates across all files:**
```bash
cd Assignment_2/scripts
python3 << 'EOF'
import pyspark.sql
import glob

spark = pyspark.sql.SparkSession.builder.appName('date_range').master('local[*]').getOrCreate()
spark.sparkContext.setLogLevel('ERROR')

# Load all feature files
feature_files = sorted(glob.glob('datamart/gold/feature_store/gold_feature_store_*.parquet'))
df_list = [spark.read.parquet(f) for f in feature_files]
df_all = df_list[0]
for df in df_list[1:]:
    df_all = df_all.union(df)

print(f"\nTotal feature records: {df_all.count()}")
print("\nSnapshot date range:")
df_all.select('snapshot_date').distinct().orderBy('snapshot_date').show(100, truncate=False)

spark.stop()
EOF
```

---

### Verify Training Data Availability

**Check what data is available for model training (after feature-label join):**
```bash
cd Assignment_2/scripts
python3 << 'EOF'
import pyspark.sql
import glob
from datetime import datetime

spark = pyspark.sql.SparkSession.builder.appName('training_check').master('local[*]').getOrCreate()
spark.sparkContext.setLogLevel('ERROR')

# Load all features and labels
feature_files = sorted(glob.glob('datamart/gold/feature_store/gold_feature_store_*.parquet'))
label_files = sorted(glob.glob('datamart/gold/label_store/gold_label_store_*.parquet'))

# Union all partitions
df_features = spark.read.parquet('datamart/gold/feature_store/gold_feature_store_*.parquet')
df_labels = spark.read.parquet('datamart/gold/label_store/gold_label_store_*.parquet')

# Join (simulating training data)
df_train = df_features.join(
    df_labels.select('loan_id', 'Customer_ID', 'label', 'label_def'),
    on=['loan_id', 'Customer_ID'],
    how='inner'
)

print(f"\nTraining Data Summary:")
print(f"  Features: {df_features.count()} rows")
print(f"  Labels:   {df_labels.count()} rows")
print(f"  Joined:   {df_train.count()} rows")

print("\nSnapshot date distribution:")
df_train.groupBy('snapshot_date').count().orderBy('snapshot_date').show(100, truncate=False)

print("\nLabel distribution:")
df_train.groupBy('label').count().show()

spark.stop()
EOF
```

## Run model inference

This assumes that `scripts/model_store/` has the right artefacts based on model_id like `model_1`, etc

### For inferencing model 1 and snapshotdate is 2024-12-01

The actual script and the snapshotdate are variable.

`docker compose exec airflow-scheduler python /opt/airflow/scripts/model_1_inference.py --snapshotdate 2024-12-01`

This will output to `scripts/datamart/gold/predictions`

## Run model monitoring

This assumes that `scripts/model_store/` has the right artefacts based on model_id like `model_1`, etc
and that the right predictions have been generated from model inference in `scripts/datamart/gold/predictions`

### For monitoring model 1 and snapshotdate is 2024-12-01

The actual script and the snapshotdate are variable.

`docker compose exec airflow-scheduler python /opt/airflow/scripts/model_1_monitor.py --snapshotdate 2024-12-01`

This will output to `scripts/datamart/gold/monitoring`

## Run visuals - post monitoring

This assumes that the monitoring metrics are generated in `scripts/datamart/gold/monitoring`

Run

`docker compose exec airflow-scheduler python /opt/airflow/scripts/visualize_monitoring.py `

This will act on ALL the models and output to `scripts/outputs/visuals`

## Run evaluate actions - post visuals

This assumes that the monitoring metrics are generated in `scripts/datamart/gold/monitoring`

And that the thresholds are set in `scripts/monitoring_thresholds.json`

### Evaluate action - model 1

`docker compose exec airflow-scheduler python /opt/airflow/scripts/evaluate_monitoring_action.py --model-id model_1`

THis will evaluate the monitoring metrics against the thresholds.

This will act on the selected model and output to `scripts/outputs/actions`