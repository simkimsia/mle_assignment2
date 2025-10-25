import argparse
import os
import json
from datetime import datetime
import pyspark
import pyspark.sql.functions as F
from pyspark.sql.functions import col
import pandas as pd
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    roc_auc_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report
)
import warnings
warnings.filterwarnings('ignore')

# Model 2 Monitoring Script
# Purpose: Calculate performance metrics for Model 2 predictions
# Input: Predictions + labels (ground truth)
# Output: datamart/gold/monitoring/model_2_metrics_YYYY_MM_DD.parquet


def load_predictions(snapshot_date_str, spark):
    """Load predictions from gold predictions table

    TEMPORAL CORRECTION:
    - Labels are created for loans at mob=6 on the snapshot_date
    - These loans were at mob=0 exactly 6 months earlier
    - So we need predictions from 6 months before the snapshot_date
    """
    from dateutil.relativedelta import relativedelta

    predictions_dir = "datamart/gold/predictions/"

    # Calculate prediction date: 6 months before snapshot date
    # This ensures we get predictions for loans that are now at mob=6
    snapshot_date_obj = datetime.strptime(snapshot_date_str, "%Y-%m-%d")
    prediction_date_obj = snapshot_date_obj - relativedelta(months=6)
    prediction_date_str = prediction_date_obj.strftime("%Y-%m-%d")
    file_date_str = prediction_date_obj.strftime("%Y_%m_%d")

    predictions_file = f"{predictions_dir}model_2_predictions_{file_date_str}.parquet"

    if not os.path.exists(predictions_file):
        print(f"⚠️  Predictions file not found: {predictions_file}")
        print(f"   This is expected for snapshot dates within 6 months of pipeline start.")
        print(f"   Predictions are made at mob=0, labels are at mob=6.")
        print(f"   Need predictions from {prediction_date_str} to match labels from {snapshot_date_str}")
        raise FileNotFoundError(f"Predictions file not found: {predictions_file}")

    print(f"\nLoading predictions from: {predictions_file}")
    print(f"  Prediction date (mob=0): {prediction_date_str}")
    print(f"  Label date (mob=6):      {snapshot_date_str}")
    print(f"  These loans should match after 6-month maturation period")
    df_predictions = spark.read.parquet(predictions_file)

    print(f"Loaded predictions: {df_predictions.count()} rows")
    print(f"Columns: {df_predictions.columns}")

    return df_predictions


def load_labels(snapshot_date_str, spark):
    """Load ground truth labels from gold label store"""

    label_store_dir = "datamart/gold/label_store/"

    # Build path for the specific snapshot date
    date_obj = datetime.strptime(snapshot_date_str, "%Y-%m-%d")
    file_date_str = date_obj.strftime("%Y_%m_%d")
    label_file = f"{label_store_dir}gold_label_store_{file_date_str}.parquet"

    if not os.path.exists(label_file):
        raise FileNotFoundError(f"Label file not found: {label_file}")

    print(f"\nLoading labels from: {label_file}")
    df_labels = spark.read.parquet(label_file)

    print(f"Loaded labels: {df_labels.count()} rows")
    print(f"Columns: {df_labels.columns}")

    return df_labels


def join_predictions_and_labels(df_predictions, df_labels):
    """Join predictions with ground truth labels"""

    print("\n" + "="*60)
    print("Joining Predictions with Labels")
    print("="*60)

    # Join on loan_id and Customer_ID
    df_joined = df_predictions.join(
        df_labels.select("loan_id", "Customer_ID", "label", "label_def"),
        on=["loan_id", "Customer_ID"],
        how="inner"
    )

    print(f"Joined data: {df_joined.count()} rows")

    if df_joined.count() == 0:
        raise ValueError("No matching records found between predictions and labels")

    return df_joined


def calculate_metrics(df_joined):
    """Calculate performance metrics"""

    print("\n" + "="*60)
    print("Calculating Performance Metrics")
    print("="*60)

    # Convert to pandas for sklearn metrics
    pdf = df_joined.select(
        "loan_id",
        "Customer_ID",
        "prediction_proba",
        "prediction_label",
        "label"
    ).toPandas()

    y_true = pdf['label'].values
    y_pred = pdf['prediction_label'].values
    y_proba = pdf['prediction_proba'].values

    # Calculate metrics
    accuracy = accuracy_score(y_true, y_pred)

    # Handle case where only one class is present
    try:
        roc_auc = roc_auc_score(y_true, y_proba)
    except ValueError as e:
        print(f"⚠️  Warning: Could not calculate ROC-AUC: {e}")
        roc_auc = None

    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)

    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)

    # Calculate additional metrics
    total_samples = len(y_true)
    actual_positives = y_true.sum()
    actual_negatives = total_samples - actual_positives
    predicted_positives = y_pred.sum()
    predicted_negatives = total_samples - predicted_positives

    # Prediction distribution statistics
    mean_proba = y_proba.mean()
    std_proba = y_proba.std()
    min_proba = y_proba.min()
    max_proba = y_proba.max()
    median_proba = np.median(y_proba)

    # Print summary
    print(f"\nPerformance Metrics Summary:")
    print(f"{'─'*60}")
    print(f"Overall Metrics:")
    print(f"  Accuracy:   {accuracy:.4f}")
    if roc_auc is not None:
        print(f"  ROC-AUC:    {roc_auc:.4f}")
    print(f"  Precision:  {precision:.4f}")
    print(f"  Recall:     {recall:.4f}")
    print(f"  F1-Score:   {f1:.4f}")

    print(f"\nConfusion Matrix:")
    print(f"                Predicted")
    print(f"               No Default  Default")
    print(f"Actual No Def    {tn:6d}     {fp:6d}")
    print(f"Actual Default   {fn:6d}     {tp:6d}")

    print(f"\nClass Distribution:")
    print(f"  Actual Positives (Default):     {actual_positives:6d} ({100*actual_positives/total_samples:5.2f}%)")
    print(f"  Actual Negatives (No Default):  {actual_negatives:6d} ({100*actual_negatives/total_samples:5.2f}%)")
    print(f"  Predicted Positives (Default):  {predicted_positives:6d} ({100*predicted_positives/total_samples:5.2f}%)")
    print(f"  Predicted Negatives (No Default): {predicted_negatives:6d} ({100*predicted_negatives/total_samples:5.2f}%)")

    print(f"\nPrediction Probability Statistics:")
    print(f"  Mean:   {mean_proba:.4f}")
    print(f"  Median: {median_proba:.4f}")
    print(f"  Std:    {std_proba:.4f}")
    print(f"  Min:    {min_proba:.4f}")
    print(f"  Max:    {max_proba:.4f}")

    # Detailed classification report
    print(f"\nDetailed Classification Report:")
    print(classification_report(y_true, y_pred, target_names=['No Default', 'Default']))

    # Compile metrics into dictionary
    metrics = {
        'model_id': 'model_2',
        'model_type': 'gradient_boosting',
        'accuracy': float(accuracy),
        'roc_auc': float(roc_auc) if roc_auc is not None else None,
        'precision': float(precision),
        'recall': float(recall),
        'f1_score': float(f1),
        'true_negatives': int(tn),
        'false_positives': int(fp),
        'false_negatives': int(fn),
        'true_positives': int(tp),
        'total_samples': int(total_samples),
        'actual_positives': int(actual_positives),
        'actual_negatives': int(actual_negatives),
        'predicted_positives': int(predicted_positives),
        'predicted_negatives': int(predicted_negatives),
        'mean_prediction_proba': float(mean_proba),
        'median_prediction_proba': float(median_proba),
        'std_prediction_proba': float(std_proba),
        'min_prediction_proba': float(min_proba),
        'max_prediction_proba': float(max_proba)
    }

    return metrics


def save_metrics(metrics, snapshot_date_str, spark):
    """Save monitoring metrics to gold monitoring table"""

    monitoring_dir = "datamart/gold/monitoring/"

    if not os.path.exists(monitoring_dir):
        os.makedirs(monitoring_dir)
        print(f"✓ Created monitoring directory: {monitoring_dir}")

    # Build output path
    date_obj = datetime.strptime(snapshot_date_str, "%Y-%m-%d")
    file_date_str = date_obj.strftime("%Y_%m_%d")
    output_file = f"{monitoring_dir}model_2_metrics_{file_date_str}.parquet"

    # Add metadata
    metrics['snapshot_date'] = snapshot_date_str
    metrics['monitoring_timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Convert to DataFrame and save
    metrics_pdf = pd.DataFrame([metrics])
    df_metrics = spark.createDataFrame(metrics_pdf)

    df_metrics.write.mode('overwrite').parquet(output_file)

    print(f"\n✅ Saved metrics to: {output_file}")
    print(f"   Columns: {df_metrics.columns}")
    print(f"   Rows: {df_metrics.count()}")

    # Also save as JSON for easy reading
    json_output_file = output_file.replace('.parquet', '.json')
    with open(json_output_file, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"✅ Saved metrics (JSON) to: {json_output_file}")

    return output_file


def main():
    parser = argparse.ArgumentParser(description='Model 2 Monitoring: Calculate performance metrics')
    parser.add_argument('--snapshotdate', type=str, required=True,
                        help='Snapshot date for monitoring (YYYY-MM-DD)')

    args = parser.parse_args()
    snapshotdate = args.snapshotdate

    print("="*60)
    print(f"Model 2 Monitoring - Gradient Boosting")
    print("="*60)
    print(f"Snapshot Date: {snapshotdate}")
    print("="*60 + "\n")

    # Initialize Spark
    spark = pyspark.sql.SparkSession.builder \
        .appName("Model2_Monitoring") \
        .config("spark.driver.memory", "4g") \
        .getOrCreate()

    spark.sparkContext.setLogLevel("ERROR")

    try:
        # Step 1: Load predictions
        print("\n[Step 1/4] Loading predictions...")
        df_predictions = load_predictions(snapshotdate, spark)

        # Step 2: Load labels
        print("\n[Step 2/4] Loading labels...")
        df_labels = load_labels(snapshotdate, spark)

        # Step 3: Join predictions and labels
        print("\n[Step 3/4] Joining predictions and labels...")
        df_joined = join_predictions_and_labels(df_predictions, df_labels)

        # Step 4: Calculate and save metrics
        print("\n[Step 4/4] Calculating metrics...")
        metrics = calculate_metrics(df_joined)

        # Step 5: Save metrics
        print("\n[Step 5/5] Saving metrics...")
        output_file = save_metrics(metrics, snapshotdate, spark)

        print("\n" + "="*60)
        print("✅ Model 2 Monitoring Completed Successfully")
        print("="*60)
        print(f"Output: {output_file}")
        print(f"Key Metrics:")
        print(f"  Accuracy: {metrics['accuracy']:.4f}")
        if metrics['roc_auc'] is not None:
            print(f"  ROC-AUC:  {metrics['roc_auc']:.4f}")
        print(f"  F1-Score: {metrics['f1_score']:.4f}")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\n❌ Error during monitoring: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
