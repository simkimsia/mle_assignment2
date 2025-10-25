import argparse
import json
import os
import glob
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import numpy as np
import warnings

warnings.filterwarnings("ignore")

# Visualization script for model monitoring metrics
# Purpose: Generate performance and stability visualizations from monitoring gold tables
# Input: datamart/gold/monitoring/*.json files
# Output: outputs/visuals/*.png charts

DATAMART_ROOT_ENV_VAR = "DATAMART_ROOT"
DATAMART_ROOT_CANDIDATES = [
    os.environ.get(DATAMART_ROOT_ENV_VAR),
    "scripts/datamart",
    "/opt/airflow/scripts/datamart",
]

OUTPUT_DIR_CANDIDATES = [
    "outputs/visuals",
    "scripts/outputs/visuals",
    "/opt/airflow/scripts/outputs/visuals",
]

MODEL_STORE_CANDIDATES = [
    "model_store",
    "scripts/model_store",
    "/opt/airflow/scripts/model_store",
]


def get_datamart_roots():
    """Return ordered list of candidate datamart roots (deduplicated)."""
    roots = []
    for candidate in DATAMART_ROOT_CANDIDATES:
        if candidate and candidate not in roots:
            roots.append(candidate.rstrip("/"))
    if not roots:
        roots.append("datamart")
    return roots


def find_monitoring_dir():
    """Find the monitoring directory containing JSON metrics."""
    for root in get_datamart_roots():
        monitoring_dir = os.path.join(root, "gold/monitoring")
        if os.path.isdir(monitoring_dir):
            return monitoring_dir
    return None


def find_model_store_dir():
    """Find the model store directory containing trained model metadata."""
    for candidate in MODEL_STORE_CANDIDATES:
        if os.path.isdir(candidate):
            return candidate
    return None


def get_output_dir():
    """Get or create output directory for visualizations."""
    for candidate in OUTPUT_DIR_CANDIDATES:
        parent = os.path.dirname(candidate)
        if parent and os.path.isdir(parent):
            os.makedirs(candidate, exist_ok=True)
            return candidate
    # Fallback: create in current directory
    output_dir = "outputs/visuals"
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def load_training_metadata(model_store_dir):
    """Load training metadata from model store for baseline comparison."""
    print(f"\n{'='*60}")
    print("Loading Training Baseline Metrics")
    print(f"{'='*60}")
    print(f"Model store directory: {model_store_dir}")

    training_baselines = {}

    # Find all model subdirectories
    model_dirs = [d for d in os.listdir(model_store_dir)
                  if os.path.isdir(os.path.join(model_store_dir, d)) and d.startswith('model_')]

    for model_dir in sorted(model_dirs):
        metadata_path = os.path.join(model_store_dir, model_dir, 'metadata.json')

        if not os.path.exists(metadata_path):
            print(f"  ⚠️  No metadata found for {model_dir}")
            continue

        with open(metadata_path, 'r') as f:
            metadata = json.load(f)

        model_id = metadata.get('model_id', model_dir)

        # Extract training metrics
        baselines = {
            'train_roc_auc': metadata.get('train_roc_auc'),
            'val_roc_auc': metadata.get('val_roc_auc'),
            'test_roc_auc': metadata.get('test_roc_auc'),
            'oot_roc_auc': metadata.get('oot_roc_auc'),
            'train_accuracy': metadata.get('train_accuracy'),
            'val_accuracy': metadata.get('val_accuracy'),
            'test_accuracy': metadata.get('test_accuracy'),
            'oot_accuracy': metadata.get('oot_accuracy'),
            'model_type': metadata.get('model_type', 'unknown'),
            'training_date': metadata.get('training_date'),
        }

        training_baselines[model_id] = baselines
        print(f"  ✓ Loaded baseline metrics for {model_id}")
        print(f"     OOT ROC-AUC: {baselines['oot_roc_auc']:.4f}, Accuracy: {baselines['oot_accuracy']:.4f}")

    print(f"\nLoaded baselines for {len(training_baselines)} models")
    return training_baselines


def load_monitoring_metrics(monitoring_dir):
    """Load all monitoring metrics from JSON files."""
    json_files = glob.glob(os.path.join(monitoring_dir, "*.json"))

    if not json_files:
        raise FileNotFoundError(
            f"No monitoring JSON files found in {monitoring_dir}"
        )

    print(f"\n{'='*60}")
    print("Loading Monitoring Metrics")
    print(f"{'='*60}")
    print(f"Monitoring directory: {monitoring_dir}")
    print(f"Found {len(json_files)} metric files")

    metrics_list = []
    for json_file in json_files:
        with open(json_file, "r") as f:
            metrics = json.load(f)
            metrics["source_file"] = os.path.basename(json_file)
            metrics_list.append(metrics)
            print(f"  ✓ Loaded {os.path.basename(json_file)}")

    df = pd.DataFrame(metrics_list)

    # Parse dates
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])
    df["monitoring_timestamp"] = pd.to_datetime(df["monitoring_timestamp"])

    # Sort by snapshot_date
    df = df.sort_values("snapshot_date")

    print(f"\nLoaded {len(df)} monitoring records")
    print(f"Date range: {df['snapshot_date'].min()} to {df['snapshot_date'].max()}")
    print(f"Models: {df['model_id'].unique().tolist()}")

    return df


def plot_performance_metrics_over_time(df, output_dir, training_baselines=None):
    """Plot primary performance metrics (ROC-AUC, Accuracy, F1) over time with training baseline references."""
    print(f"\n{'='*60}")
    print("Generating Performance Metrics Over Time")
    print(f"{'='*60}")

    # Set style
    sns.set_style("whitegrid")
    plt.rcParams["figure.figsize"] = (14, 10)

    fig, axes = plt.subplots(3, 1, figsize=(14, 10))

    # Map monitoring metrics to training baseline keys
    metrics_to_plot = [
        ("roc_auc", "ROC-AUC", 0.0, 1.0, "Primary Metric", "oot_roc_auc", "test_roc_auc"),
        ("accuracy", "Accuracy", 0.0, 1.0, "Overall Correctness", "oot_accuracy", "test_accuracy"),
        ("f1_score", "F1-Score", 0.0, 1.0, "Precision-Recall Balance", None, None),
    ]

    for idx, metric_config in enumerate(metrics_to_plot):
        metric, label, ymin, ymax, description = metric_config[:5]
        oot_key = metric_config[5] if len(metric_config) > 5 else None
        test_key = metric_config[6] if len(metric_config) > 6 else None

        ax = axes[idx]

        # Plot monitoring data (production performance)
        for model_id in sorted(df["model_id"].unique()):
            model_df = df[df["model_id"] == model_id]
            model_type = model_df["model_type"].iloc[0]

            ax.plot(
                model_df["snapshot_date"],
                model_df[metric],
                marker="o",
                linewidth=2,
                markersize=8,
                label=f"{model_id} Production ({model_type})",
                zorder=10,
            )

            # Add value labels
            for _, row in model_df.iterrows():
                ax.annotate(
                    f'{row[metric]:.3f}',
                    (row["snapshot_date"], row[metric]),
                    textcoords="offset points",
                    xytext=(0, 10),
                    ha="center",
                    fontsize=9,
                    alpha=0.7,
                )

            # Add training baseline reference lines
            if training_baselines and model_id in training_baselines:
                baselines = training_baselines[model_id]

                # OOT baseline (primary reference)
                if oot_key and baselines.get(oot_key) is not None:
                    oot_value = baselines[oot_key]
                    ax.axhline(
                        y=oot_value,
                        color='darkred',
                        linestyle='--',
                        linewidth=1.5,
                        alpha=0.6,
                        label=f'{model_id} OOT Baseline ({oot_value:.3f})' if idx == 0 else None,
                        zorder=5,
                    )
                    # Add annotation for OOT baseline
                    ax.text(
                        0.98,
                        oot_value,
                        f'OOT: {oot_value:.3f}',
                        transform=ax.get_yaxis_transform(),
                        ha='right',
                        va='bottom',
                        fontsize=8,
                        color='darkred',
                        alpha=0.7,
                    )

                # Test baseline (secondary reference)
                if test_key and baselines.get(test_key) is not None:
                    test_value = baselines[test_key]
                    ax.axhline(
                        y=test_value,
                        color='orange',
                        linestyle=':',
                        linewidth=1.2,
                        alpha=0.5,
                        label=f'{model_id} Test Baseline ({test_value:.3f})' if idx == 0 else None,
                        zorder=4,
                    )

        ax.set_ylabel(label, fontsize=12, fontweight="bold")
        ax.set_ylim(ymin, ymax)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="lower right", fontsize=9)

        # Add description
        ax.text(
            0.02,
            0.98,
            description,
            transform=ax.transAxes,
            fontsize=9,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.3),
        )

        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

    axes[-1].set_xlabel("Snapshot Date", fontsize=12, fontweight="bold")

    plt.suptitle(
        "Model Performance Metrics Over Time\n(Monitoring Production Performance)",
        fontsize=16,
        fontweight="bold",
        y=0.995,
    )

    plt.tight_layout()

    output_file = os.path.join(output_dir, "performance_metrics_over_time.png")
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"✓ Saved: {output_file}")
    plt.close()


def plot_confusion_matrix_comparison(df, output_dir):
    """Plot confusion matrices for all models and time points."""
    print(f"\n{'='*60}")
    print("Generating Confusion Matrix Comparison")
    print(f"{'='*60}")

    # Get unique combinations of model and snapshot date
    unique_combos = df[["model_id", "model_type", "snapshot_date"]].drop_duplicates()
    n_combos = len(unique_combos)

    # Calculate grid dimensions
    n_cols = min(3, n_combos)
    n_rows = (n_combos + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 4 * n_rows))
    if n_combos == 1:
        axes = np.array([axes])
    axes = axes.flatten()

    for idx, (_, row_data) in enumerate(unique_combos.iterrows()):
        model_id = row_data["model_id"]
        model_type = row_data["model_type"]
        snapshot_date = row_data["snapshot_date"]

        # Get metrics for this specific combination
        metrics = df[
            (df["model_id"] == model_id) & (df["snapshot_date"] == snapshot_date)
        ].iloc[0]

        # Build confusion matrix
        cm = np.array(
            [
                [metrics["true_negatives"], metrics["false_positives"]],
                [metrics["false_negatives"], metrics["true_positives"]],
            ]
        )

        # Calculate percentages
        cm_pct = cm.astype("float") / cm.sum() * 100

        # Plot heatmap
        ax = axes[idx]
        sns.heatmap(
            cm,
            annot=True,
            fmt="d",
            cmap="Blues",
            cbar=False,
            ax=ax,
            xticklabels=["No Default", "Default"],
            yticklabels=["No Default", "Default"],
        )

        # Add percentage annotations
        for i in range(2):
            for j in range(2):
                ax.text(
                    j + 0.5,
                    i + 0.7,
                    f"({cm_pct[i, j]:.1f}%)",
                    ha="center",
                    va="center",
                    color="gray",
                    fontsize=9,
                )

        ax.set_title(
            f"{model_id}\n{model_type}\n{snapshot_date.strftime('%Y-%m-%d')}",
            fontsize=11,
            fontweight="bold",
        )
        ax.set_ylabel("Actual", fontsize=10)
        ax.set_xlabel("Predicted", fontsize=10)

        # Add metrics text
        metrics_text = (
            f"Accuracy: {metrics['accuracy']:.3f}\n"
            f"Precision: {metrics['precision']:.3f}\n"
            f"Recall: {metrics['recall']:.3f}"
        )
        ax.text(
            1.05,
            0.5,
            metrics_text,
            transform=ax.transAxes,
            fontsize=9,
            verticalalignment="center",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.3),
        )

    # Hide unused subplots
    for idx in range(n_combos, len(axes)):
        axes[idx].axis("off")

    plt.suptitle(
        "Confusion Matrix Comparison Across Models and Time Periods",
        fontsize=16,
        fontweight="bold",
        y=0.995,
    )

    plt.tight_layout()

    output_file = os.path.join(output_dir, "confusion_matrix_comparison.png")
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"✓ Saved: {output_file}")
    plt.close()


def plot_prediction_distribution_stability(df, output_dir):
    """Plot prediction probability distribution statistics over time."""
    print(f"\n{'='*60}")
    print("Generating Prediction Distribution Stability")
    print(f"{'='*60}")

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Mean prediction probability
    ax = axes[0, 0]
    for model_id in sorted(df["model_id"].unique()):
        model_df = df[df["model_id"] == model_id]
        model_type = model_df["model_type"].iloc[0]
        ax.plot(
            model_df["snapshot_date"],
            model_df["mean_prediction_proba"],
            marker="o",
            linewidth=2,
            markersize=8,
            label=f"{model_id} ({model_type})",
        )
    ax.set_ylabel("Mean Prediction Probability", fontsize=11, fontweight="bold")
    ax.set_title("Average Predicted Default Probability", fontsize=12)
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

    # Standard deviation
    ax = axes[0, 1]
    for model_id in sorted(df["model_id"].unique()):
        model_df = df[df["model_id"] == model_id]
        model_type = model_df["model_type"].iloc[0]
        ax.plot(
            model_df["snapshot_date"],
            model_df["std_prediction_proba"],
            marker="o",
            linewidth=2,
            markersize=8,
            label=f"{model_id} ({model_type})",
        )
    ax.set_ylabel("Std Dev of Predictions", fontsize=11, fontweight="bold")
    ax.set_title("Prediction Variability", fontsize=12)
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

    # Median prediction probability
    ax = axes[1, 0]
    for model_id in sorted(df["model_id"].unique()):
        model_df = df[df["model_id"] == model_id]
        model_type = model_df["model_type"].iloc[0]
        ax.plot(
            model_df["snapshot_date"],
            model_df["median_prediction_proba"],
            marker="o",
            linewidth=2,
            markersize=8,
            label=f"{model_id} ({model_type})",
        )
    ax.set_ylabel("Median Prediction Probability", fontsize=11, fontweight="bold")
    ax.set_title("Median Predicted Default Probability", fontsize=12)
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xlabel("Snapshot Date", fontsize=11, fontweight="bold")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

    # Min/Max range (as error bars)
    ax = axes[1, 1]
    for model_id in sorted(df["model_id"].unique()):
        model_df = df[df["model_id"] == model_id]
        model_type = model_df["model_type"].iloc[0]

        # Plot range as filled area
        ax.fill_between(
            model_df["snapshot_date"],
            model_df["min_prediction_proba"],
            model_df["max_prediction_proba"],
            alpha=0.3,
            label=f"{model_id} range",
        )

        # Plot median as line
        ax.plot(
            model_df["snapshot_date"],
            model_df["median_prediction_proba"],
            marker="o",
            linewidth=2,
            markersize=6,
            label=f"{model_id} median",
        )

    ax.set_ylabel("Prediction Probability Range", fontsize=11, fontweight="bold")
    ax.set_title("Min/Median/Max Prediction Probability", fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_xlabel("Snapshot Date", fontsize=11, fontweight="bold")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

    plt.suptitle(
        "Prediction Distribution Stability Over Time\n(Detecting Model Drift)",
        fontsize=16,
        fontweight="bold",
        y=0.995,
    )

    plt.tight_layout()

    output_file = os.path.join(output_dir, "prediction_distribution_stability.png")
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"✓ Saved: {output_file}")
    plt.close()


def plot_model_comparison_summary(df, output_dir):
    """Create a comprehensive model comparison dashboard."""
    print(f"\n{'='*60}")
    print("Generating Model Comparison Summary")
    print(f"{'='*60}")

    # Use the latest snapshot for comparison
    latest_snapshot = df["snapshot_date"].max()
    df_latest = df[df["snapshot_date"] == latest_snapshot]

    if len(df_latest) < 2:
        print("  ⏭️  Only one model available, skipping comparison chart")
        return

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 1. Key metrics comparison (bar chart)
    ax = axes[0, 0]
    metrics = ["roc_auc", "accuracy", "f1_score", "precision", "recall"]
    metric_labels = ["ROC-AUC", "Accuracy", "F1-Score", "Precision", "Recall"]

    x = np.arange(len(metrics))
    width = 0.35

    models = sorted(df_latest["model_id"].unique())
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]

    for idx, model_id in enumerate(models):
        model_data = df_latest[df_latest["model_id"] == model_id].iloc[0]
        values = [model_data[m] for m in metrics]
        model_type = model_data["model_type"]

        ax.bar(
            x + idx * width,
            values,
            width,
            label=f"{model_id} ({model_type})",
            color=colors[idx],
        )

        # Add value labels
        for i, v in enumerate(values):
            ax.text(
                x[i] + idx * width,
                v + 0.01,
                f"{v:.3f}",
                ha="center",
                va="bottom",
                fontsize=9,
            )

    ax.set_ylabel("Score", fontsize=11, fontweight="bold")
    ax.set_title(
        f"Model Performance Comparison\n(Snapshot: {latest_snapshot.strftime('%Y-%m-%d')})",
        fontsize=12,
    )
    ax.set_xticks(x + width / 2)
    ax.set_xticklabels(metric_labels, rotation=45, ha="right")
    ax.legend()
    ax.set_ylim(0, 1.1)
    ax.grid(True, alpha=0.3, axis="y")

    # 2. Confusion matrix metrics (grouped bar)
    ax = axes[0, 1]
    cm_metrics = ["true_positives", "true_negatives", "false_positives", "false_negatives"]
    cm_labels = ["True\nPositives", "True\nNegatives", "False\nPositives", "False\nNegatives"]

    x = np.arange(len(cm_metrics))

    for idx, model_id in enumerate(models):
        model_data = df_latest[df_latest["model_id"] == model_id].iloc[0]
        values = [model_data[m] for m in cm_metrics]

        ax.bar(
            x + idx * width,
            values,
            width,
            label=f"{model_id}",
            color=colors[idx],
        )

        # Add value labels
        for i, v in enumerate(values):
            ax.text(
                x[i] + idx * width,
                v + 5,
                f"{int(v)}",
                ha="center",
                va="bottom",
                fontsize=9,
            )

    ax.set_ylabel("Count", fontsize=11, fontweight="bold")
    ax.set_title("Confusion Matrix Components", fontsize=12)
    ax.set_xticks(x + width / 2)
    ax.set_xticklabels(cm_labels, fontsize=9)
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    # 3. Prediction statistics comparison
    ax = axes[1, 0]
    pred_stats = ["mean_prediction_proba", "median_prediction_proba", "std_prediction_proba"]
    pred_labels = ["Mean", "Median", "Std Dev"]

    x = np.arange(len(pred_stats))

    for idx, model_id in enumerate(models):
        model_data = df_latest[df_latest["model_id"] == model_id].iloc[0]
        values = [model_data[m] for m in pred_stats]

        ax.bar(
            x + idx * width,
            values,
            width,
            label=f"{model_id}",
            color=colors[idx],
        )

        # Add value labels
        for i, v in enumerate(values):
            ax.text(
                x[i] + idx * width,
                v + 0.01,
                f"{v:.3f}",
                ha="center",
                va="bottom",
                fontsize=9,
            )

    ax.set_ylabel("Probability", fontsize=11, fontweight="bold")
    ax.set_title("Prediction Probability Statistics", fontsize=12)
    ax.set_xticks(x + width / 2)
    ax.set_xticklabels(pred_labels)
    ax.legend()
    ax.set_ylim(0, max(df_latest["std_prediction_proba"].max() * 1.2, 0.5))
    ax.grid(True, alpha=0.3, axis="y")

    # 4. Summary text table
    ax = axes[1, 1]
    ax.axis("off")

    summary_data = []
    for model_id in models:
        model_data = df_latest[df_latest["model_id"] == model_id].iloc[0]
        summary_data.append(
            [
                model_id,
                model_data["model_type"],
                f"{model_data['roc_auc']:.4f}",
                f"{model_data['accuracy']:.4f}",
                f"{model_data['f1_score']:.4f}",
                f"{int(model_data['total_samples'])}",
            ]
        )

    table = ax.table(
        cellText=summary_data,
        colLabels=["Model ID", "Type", "ROC-AUC", "Accuracy", "F1", "Samples"],
        cellLoc="center",
        loc="center",
        bbox=[0.1, 0.2, 0.8, 0.6],
    )

    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2)

    # Highlight header
    for i in range(6):
        table[(0, i)].set_facecolor("#40466e")
        table[(0, i)].set_text_props(weight="bold", color="white")

    # Alternate row colors
    for i in range(1, len(summary_data) + 1):
        for j in range(6):
            if i % 2 == 0:
                table[(i, j)].set_facecolor("#f0f0f0")

    ax.text(
        0.5,
        0.9,
        "Model Comparison Summary",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
        transform=ax.transAxes,
    )

    # Add recommendation text
    best_model_id = df_latest.loc[df_latest["roc_auc"].idxmax(), "model_id"]
    best_roc_auc = df_latest["roc_auc"].max()

    recommendation = (
        f"Recommended Model: {best_model_id}\n"
        f"(Highest ROC-AUC: {best_roc_auc:.4f})"
    )

    ax.text(
        0.5,
        0.1,
        recommendation,
        ha="center",
        va="center",
        fontsize=11,
        transform=ax.transAxes,
        bbox=dict(boxstyle="round", facecolor="lightgreen", alpha=0.5),
    )

    plt.suptitle(
        "Comprehensive Model Comparison Dashboard",
        fontsize=16,
        fontweight="bold",
        y=0.995,
    )

    plt.tight_layout()

    output_file = os.path.join(output_dir, "model_comparison_summary.png")
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"✓ Saved: {output_file}")
    plt.close()


def generate_summary_report(df, output_dir):
    """Generate a text summary report of monitoring metrics."""
    print(f"\n{'='*60}")
    print("Generating Summary Report")
    print(f"{'='*60}")

    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("MODEL MONITORING SUMMARY REPORT")
    report_lines.append("=" * 80)
    report_lines.append("")
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")

    # Overall statistics
    report_lines.append(f"Monitoring Period: {df['snapshot_date'].min().strftime('%Y-%m-%d')} to {df['snapshot_date'].max().strftime('%Y-%m-%d')}")
    report_lines.append(f"Number of Time Points: {df['snapshot_date'].nunique()}")
    report_lines.append(f"Models Monitored: {', '.join(sorted(df['model_id'].unique()))}")
    report_lines.append("")

    # Latest snapshot metrics
    latest_snapshot = df["snapshot_date"].max()
    report_lines.append("=" * 80)
    report_lines.append(f"LATEST PERFORMANCE (Snapshot: {latest_snapshot.strftime('%Y-%m-%d')})")
    report_lines.append("=" * 80)
    report_lines.append("")

    df_latest = df[df["snapshot_date"] == latest_snapshot]

    for _, row in df_latest.iterrows():
        report_lines.append(f"{row['model_id'].upper()} - {row['model_type']}")
        report_lines.append("-" * 80)
        report_lines.append(f"  Primary Metric (ROC-AUC):      {row['roc_auc']:.4f}  {'⭐ Best' if row['roc_auc'] == df_latest['roc_auc'].max() else ''}")
        report_lines.append(f"  Accuracy:                      {row['accuracy']:.4f}")
        report_lines.append(f"  F1-Score:                      {row['f1_score']:.4f}")
        report_lines.append(f"  Precision:                     {row['precision']:.4f}")
        report_lines.append(f"  Recall:                        {row['recall']:.4f}")
        report_lines.append("")
        report_lines.append(f"  Total Samples:                 {int(row['total_samples'])}")
        report_lines.append(f"  Actual Positives (Defaults):   {int(row['actual_positives'])} ({100 * row['actual_positives'] / row['total_samples']:.1f}%)")
        report_lines.append(f"  Predicted Positives:           {int(row['predicted_positives'])} ({100 * row['predicted_positives'] / row['total_samples']:.1f}%)")
        report_lines.append("")
        report_lines.append(f"  Confusion Matrix:")
        report_lines.append(f"    True Positives:              {int(row['true_positives'])}")
        report_lines.append(f"    True Negatives:              {int(row['true_negatives'])}")
        report_lines.append(f"    False Positives:             {int(row['false_positives'])}")
        report_lines.append(f"    False Negatives:             {int(row['false_negatives'])}")
        report_lines.append("")
        report_lines.append(f"  Prediction Distribution:")
        report_lines.append(f"    Mean Probability:            {row['mean_prediction_proba']:.4f}")
        report_lines.append(f"    Median Probability:          {row['median_prediction_proba']:.4f}")
        report_lines.append(f"    Std Dev:                     {row['std_prediction_proba']:.4f}")
        report_lines.append(f"    Range: [{row['min_prediction_proba']:.4f}, {row['max_prediction_proba']:.4f}]")
        report_lines.append("")

    # Trend analysis (if multiple time points)
    if df["snapshot_date"].nunique() > 1:
        report_lines.append("=" * 80)
        report_lines.append("TREND ANALYSIS")
        report_lines.append("=" * 80)
        report_lines.append("")

        for model_id in sorted(df["model_id"].unique()):
            model_df = df[df["model_id"] == model_id].sort_values("snapshot_date")

            report_lines.append(f"{model_id.upper()}")
            report_lines.append("-" * 80)

            # Calculate trends
            roc_auc_change = (
                model_df["roc_auc"].iloc[-1] - model_df["roc_auc"].iloc[0]
            )
            accuracy_change = (
                model_df["accuracy"].iloc[-1] - model_df["accuracy"].iloc[0]
            )
            f1_change = model_df["f1_score"].iloc[-1] - model_df["f1_score"].iloc[0]

            report_lines.append(f"  ROC-AUC Change:     {roc_auc_change:+.4f}  {'📈 Improving' if roc_auc_change > 0 else '📉 Degrading' if roc_auc_change < 0 else '➡️ Stable'}")
            report_lines.append(f"  Accuracy Change:    {accuracy_change:+.4f}  {'📈 Improving' if accuracy_change > 0 else '📉 Degrading' if accuracy_change < 0 else '➡️ Stable'}")
            report_lines.append(f"  F1-Score Change:    {f1_change:+.4f}  {'📈 Improving' if f1_change > 0 else '📉 Degrading' if f1_change < 0 else '➡️ Stable'}")
            report_lines.append("")

    # Recommendations
    report_lines.append("=" * 80)
    report_lines.append("RECOMMENDATIONS")
    report_lines.append("=" * 80)
    report_lines.append("")

    best_model = df_latest.loc[df_latest["roc_auc"].idxmax()]
    report_lines.append(f"✓ Best Performing Model: {best_model['model_id']} ({best_model['model_type']})")
    report_lines.append(f"  ROC-AUC: {best_model['roc_auc']:.4f}")
    report_lines.append("")

    # Alert thresholds
    for _, row in df_latest.iterrows():
        alerts = []
        if row["roc_auc"] < 0.75:
            alerts.append("⚠️  ROC-AUC below 0.75 - Consider model retraining")
        if row["accuracy"] < 0.70:
            alerts.append("⚠️  Accuracy below 70% - Review model performance")
        if row["f1_score"] < 0.60:
            alerts.append("⚠️  F1-Score below 0.60 - Check precision-recall balance")

        if alerts:
            report_lines.append(f"{row['model_id'].upper()} Alerts:")
            for alert in alerts:
                report_lines.append(f"  {alert}")
            report_lines.append("")

    report_lines.append("=" * 80)

    # Write report
    output_file = os.path.join(output_dir, "monitoring_summary_report.txt")
    with open(output_file, "w") as f:
        f.write("\n".join(report_lines))

    print(f"✓ Saved: {output_file}")

    # Also print to console
    print("\n" + "\n".join(report_lines))


def main():
    parser = argparse.ArgumentParser(
        description="Visualize model monitoring metrics"
    )
    parser.add_argument(
        "--monitoring-dir",
        type=str,
        help="Path to monitoring directory (auto-detected if not provided)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Path to output directory for visualizations (auto-created if not provided)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Model Monitoring Visualization")
    print("=" * 60)

    # Find monitoring directory
    if args.monitoring_dir:
        monitoring_dir = args.monitoring_dir
    else:
        monitoring_dir = find_monitoring_dir()

    if not monitoring_dir or not os.path.isdir(monitoring_dir):
        print(f"\n❌ Error: Monitoring directory not found")
        if monitoring_dir:
            print(f"   Searched: {monitoring_dir}")
        else:
            print(f"   Searched locations:")
            for root in get_datamart_roots():
                print(f"     - {os.path.join(root, 'gold/monitoring')}")
        return

    # Get output directory
    if args.output_dir:
        output_dir = args.output_dir
        os.makedirs(output_dir, exist_ok=True)
    else:
        output_dir = get_output_dir()

    print(f"\nMonitoring directory: {monitoring_dir}")
    print(f"Output directory:     {output_dir}")

    try:
        # Load metrics
        df = load_monitoring_metrics(monitoring_dir)

        # Load training baselines (optional)
        model_store_dir = find_model_store_dir()
        training_baselines = None
        if model_store_dir:
            try:
                training_baselines = load_training_metadata(model_store_dir)
            except Exception as e:
                print(f"\n⚠️  Warning: Could not load training baselines: {e}")
                print("   Continuing without baseline reference lines...")
        else:
            print(f"\n⚠️  Model store not found. Visualizations will not include training baseline references.")

        # Generate visualizations
        print(f"\n{'='*60}")
        print("Generating Visualizations")
        print(f"{'='*60}")

        plot_performance_metrics_over_time(df, output_dir, training_baselines)
        plot_confusion_matrix_comparison(df, output_dir)
        plot_prediction_distribution_stability(df, output_dir)
        plot_model_comparison_summary(df, output_dir)
        generate_summary_report(df, output_dir)

        print(f"\n{'='*60}")
        print("✅ Visualization Generation Completed Successfully")
        print(f"{'='*60}")
        print(f"\nOutput directory: {output_dir}")
        print("\nGenerated files:")
        print("  1. performance_metrics_over_time.png")
        print("  2. confusion_matrix_comparison.png")
        print("  3. prediction_distribution_stability.png")
        print("  4. model_comparison_summary.png")
        print("  5. monitoring_summary_report.txt")
        print(f"\n{'='*60}\n")

    except Exception as e:
        print(f"\n❌ Error during visualization generation: {str(e)}")
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
