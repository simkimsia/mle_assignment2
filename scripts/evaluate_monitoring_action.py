import argparse
import json
import os
import glob
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import warnings

warnings.filterwarnings("ignore")

# Action Evaluation Script
# Purpose: Evaluate monitoring metrics against thresholds to determine required action
# Input: Monitoring metrics (JSON) + Threshold config (JSON)
# Output: Action recommendation (monitor / active_monitoring / retrain) + detailed report

DATAMART_ROOT_ENV_VAR = "DATAMART_ROOT"
DATAMART_ROOT_CANDIDATES = [
    os.environ.get(DATAMART_ROOT_ENV_VAR),
    "datamart",
    "scripts/datamart",
    "/opt/airflow/scripts/datamart",
]

THRESHOLD_CONFIG_CANDIDATES = [
    "monitoring_thresholds.json",
    "scripts/monitoring_thresholds.json",
    "/opt/airflow/scripts/monitoring_thresholds.json",
]

MODEL_STORE_CANDIDATES = [
    "model_store",
    "scripts/model_store",
    "/opt/airflow/scripts/model_store",
]

OUTPUT_DIR_CANDIDATES = [
    "outputs/actions",
    "scripts/outputs/actions",
    "/opt/airflow/scripts/outputs/actions",
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


def find_threshold_config():
    """Find the threshold configuration file."""
    for candidate in THRESHOLD_CONFIG_CANDIDATES:
        if os.path.exists(candidate):
            return candidate
    return None


def get_output_dir():
    """Get or create output directory for action decisions."""
    for candidate in OUTPUT_DIR_CANDIDATES:
        parent = os.path.dirname(candidate)
        if parent and os.path.isdir(parent):
            os.makedirs(candidate, exist_ok=True)
            return candidate
    # Fallback: create in current directory
    output_dir = "outputs/actions"
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def load_threshold_config(config_path: str) -> Dict:
    """Load monitoring threshold configuration."""
    print(f"\n{'='*60}")
    print("Loading Threshold Configuration")
    print(f"{'='*60}")
    print(f"Config file: {config_path}")

    with open(config_path, 'r') as f:
        config = json.load(f)

    print(f"Version: {config.get('version', 'unknown')}")
    print(f"Last updated: {config.get('last_updated', 'unknown')}")

    # Display threshold summary
    print(f"\nMetrics Configuration:")
    for metric_name, metric_config in config['metrics'].items():
        priority = metric_config['priority']
        biz_thresh = metric_config.get('business_threshold')
        ds_thresh = metric_config.get('data_science_threshold')

        biz_str = f"{biz_thresh:.2f}" if biz_thresh else "N/A"
        ds_str = f"{ds_thresh:.2f}" if ds_thresh else "N/A"

        print(f"  {priority} {metric_config['name']:15} | Biz: {biz_str:5} | DS: {ds_str:5}")

    return config


def load_latest_monitoring_metrics(monitoring_dir: str, model_id: str) -> Tuple[Dict, str]:
    """Load the most recent monitoring metrics for a model."""
    pattern = os.path.join(monitoring_dir, f"{model_id}_metrics_*.json")
    metric_files = sorted(glob.glob(pattern), reverse=True)

    if not metric_files:
        raise FileNotFoundError(
            f"No monitoring metrics found for {model_id} in {monitoring_dir}"
        )

    latest_file = metric_files[0]
    with open(latest_file, 'r') as f:
        metrics = json.load(f)

    return metrics, latest_file


def load_training_baseline(model_store_dir: str, model_id: str) -> Optional[Dict]:
    """Load OOT baseline metrics from model metadata."""
    metadata_path = os.path.join(model_store_dir, model_id, 'metadata.json')

    if not os.path.exists(metadata_path):
        print(f"  ⚠️  No metadata found for {model_id}, skipping baseline comparison")
        return None

    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    return {
        'oot_roc_auc': metadata.get('oot_roc_auc'),
        'oot_accuracy': metadata.get('oot_accuracy'),
        'test_roc_auc': metadata.get('test_roc_auc'),
        'test_accuracy': metadata.get('test_accuracy'),
    }


def evaluate_metric_threshold(
    metric_value: float,
    metric_name: str,
    metric_config: Dict,
    baseline_value: Optional[float] = None
) -> Dict:
    """Evaluate a single metric against its thresholds."""
    result = {
        'metric_name': metric_name,
        'metric_display_name': metric_config['name'],
        'priority': metric_config['priority'],
        'value': metric_value,
        'business_threshold': metric_config.get('business_threshold'),
        'data_science_threshold': metric_config.get('data_science_threshold'),
        'baseline_value': baseline_value,
        'status': 'OK',
        'action': 'monitor',
        'alerts': []
    }

    biz_thresh = metric_config.get('business_threshold')
    ds_thresh = metric_config.get('data_science_threshold')

    # Evaluate against business threshold (if defined)
    if biz_thresh is not None and metric_value < biz_thresh:
        result['status'] = 'CRITICAL'
        result['action'] = 'retrain'
        result['alerts'].append(
            f"❌ {metric_config['name']} ({metric_value:.4f}) below BUSINESS threshold ({biz_thresh:.4f})"
        )

    # Evaluate against data science threshold (if defined and not already critical)
    elif ds_thresh is not None and metric_value < ds_thresh:
        result['status'] = 'WARNING'
        result['action'] = 'active_monitoring'
        result['alerts'].append(
            f"⚠️  {metric_config['name']} ({metric_value:.4f}) below DATA SCIENCE threshold ({ds_thresh:.4f})"
        )

    # Evaluate baseline degradation (if enabled and not already in alert state)
    if result['status'] == 'OK' and metric_config.get('baseline_comparison', {}).get('enabled'):
        if baseline_value is not None:
            max_degradation = metric_config['baseline_comparison']['max_degradation_percent'] / 100.0
            baseline_reference = metric_config['baseline_comparison']['reference']

            degradation_pct = (baseline_value - metric_value) / baseline_value
            if degradation_pct > max_degradation:
                result['status'] = 'WARNING'
                result['action'] = 'active_monitoring'
                result['alerts'].append(
                    f"⚠️  {metric_config['name']} degraded {degradation_pct*100:.1f}% from {baseline_reference} baseline ({baseline_value:.4f})"
                )

    return result


def determine_overall_action(metric_evaluations: List[Dict]) -> Tuple[str, List[str]]:
    """Determine overall action based on all metric evaluations.

    Action priority:
    1. retrain - if any P0 or P1 metric below business threshold
    2. active_monitoring - if any P0 or P1 metric below DS threshold
    3. monitor - all metrics healthy
    """
    p0_p1_metrics = [m for m in metric_evaluations if m['priority'] in ['P0', 'P1']]

    # Check for critical failures (retrain required)
    retrain_alerts = []
    for m in p0_p1_metrics:
        if m['action'] == 'retrain':
            retrain_alerts.extend(m['alerts'])

    if retrain_alerts:
        return 'retrain', retrain_alerts

    # Check for warnings (active monitoring required)
    warning_alerts = []
    for m in p0_p1_metrics:
        if m['action'] == 'active_monitoring':
            warning_alerts.extend(m['alerts'])

    if warning_alerts:
        return 'active_monitoring', warning_alerts

    # All metrics healthy
    return 'monitor', ["✅ All P0 and P1 metrics above data science thresholds"]


def generate_action_report(
    model_id: str,
    metrics: Dict,
    metric_evaluations: List[Dict],
    overall_action: str,
    action_alerts: List[str],
    threshold_config: Dict,
    metrics_file: str
) -> str:
    """Generate detailed action recommendation report."""
    lines = []
    lines.append("=" * 80)
    lines.append(f"MODEL MONITORING ACTION EVALUATION - {model_id.upper()}")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Evaluation Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Monitoring Snapshot: {metrics.get('snapshot_date', 'unknown')}")
    lines.append(f"Monitoring File: {metrics_file}")
    lines.append(f"Total Samples: {metrics.get('total_samples', 'unknown')}")
    lines.append("")

    # Overall action
    action_config = threshold_config['action_levels'][overall_action]
    lines.append("=" * 80)
    lines.append(f"RECOMMENDED ACTION: {overall_action.upper()}")
    lines.append("=" * 80)
    lines.append(f"Description: {action_config['description']}")
    lines.append(f"Action Required: {action_config['action_required']}")
    lines.append(f"Notification: {action_config['notification']}")
    lines.append("")

    # Alerts
    if action_alerts:
        lines.append("Triggered Alerts:")
        for alert in action_alerts:
            lines.append(f"  {alert}")
        lines.append("")

    # Metric details
    lines.append("=" * 80)
    lines.append("METRIC EVALUATION DETAILS")
    lines.append("=" * 80)
    lines.append("")

    # Group by priority
    for priority in ['P0', 'P1', 'P2', 'P3']:
        priority_metrics = [m for m in metric_evaluations if m['priority'] == priority]
        if not priority_metrics:
            continue

        lines.append(f"{priority} Metrics:")
        lines.append("-" * 80)

        for m in priority_metrics:
            lines.append(f"{m['metric_display_name']}:")
            lines.append(f"  Current Value:        {m['value']:.4f}")

            if m['business_threshold'] is not None:
                lines.append(f"  Business Threshold:   {m['business_threshold']:.4f}")
            else:
                lines.append(f"  Business Threshold:   N/A (not monitored by business)")

            if m['data_science_threshold'] is not None:
                lines.append(f"  Data Science Threshold: {m['data_science_threshold']:.4f}")

            if m['baseline_value'] is not None:
                lines.append(f"  Baseline (OOT):       {m['baseline_value']:.4f}")
                delta = m['value'] - m['baseline_value']
                delta_pct = (delta / m['baseline_value']) * 100 if m['baseline_value'] != 0 else 0
                lines.append(f"  Delta from Baseline:  {delta:+.4f} ({delta_pct:+.1f}%)")

            lines.append(f"  Status:               {m['status']}")

            if m['alerts']:
                for alert in m['alerts']:
                    lines.append(f"  {alert}")

            lines.append("")

        lines.append("")

    # Next steps
    lines.append("=" * 80)
    lines.append("RECOMMENDED NEXT STEPS")
    lines.append("=" * 80)

    if overall_action == 'retrain':
        lines.append("1. Initiate emergency retraining workflow")
        lines.append("2. Investigate root cause of performance degradation:")
        lines.append("   - Data drift analysis")
        lines.append("   - Label quality review")
        lines.append("   - Feature distribution changes")
        lines.append("3. Notify stakeholders (Risk team, Product team)")
        lines.append("4. Schedule retraining to complete within 1 week")
        lines.append("5. Prepare rollback plan in case retraining fails")

    elif overall_action == 'active_monitoring':
        lines.append("1. Increase monitoring frequency (weekly instead of monthly)")
        lines.append("2. Investigate potential causes:")
        lines.append("   - Review recent data quality reports")
        lines.append("   - Check for population shifts")
        lines.append("   - Analyze feature importance changes")
        lines.append("3. Prepare retraining plan as contingency")
        lines.append("4. Set up additional alerting for further degradation")
        lines.append("5. Schedule review meeting with ML team")

    else:  # monitor
        lines.append("1. Continue normal monthly monitoring cycle")
        lines.append("2. Archive this monitoring report")
        lines.append("3. No immediate action required")

    lines.append("")
    lines.append("=" * 80)

    return "\n".join(lines)


def save_action_decision(
    model_id: str,
    overall_action: str,
    action_alerts: List[str],
    metric_evaluations: List[Dict],
    metrics: Dict,
    output_dir: str
) -> str:
    """Save action decision to JSON file for downstream processing."""

    snapshot_date = metrics.get('snapshot_date', datetime.now().strftime('%Y-%m-%d'))
    date_str = snapshot_date.replace('-', '_')
    output_file = os.path.join(output_dir, f"{model_id}_action_{date_str}.json")

    decision = {
        'model_id': model_id,
        'snapshot_date': snapshot_date,
        'evaluation_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'action': overall_action,
        'alerts': action_alerts,
        'metric_summary': {
            m['metric_name']: {
                'value': m['value'],
                'status': m['status'],
                'priority': m['priority']
            }
            for m in metric_evaluations
        },
        'total_samples': metrics.get('total_samples'),
        'monitoring_file': metrics.get('source_file', 'unknown')
    }

    with open(output_file, 'w') as f:
        json.dump(decision, f, indent=2)

    return output_file


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate monitoring metrics and determine required action"
    )
    parser.add_argument(
        "--model-id",
        type=str,
        required=True,
        help="Model ID to evaluate (e.g., model_1, model_2)"
    )
    parser.add_argument(
        "--monitoring-dir",
        type=str,
        help="Path to monitoring directory (auto-detected if not provided)"
    )
    parser.add_argument(
        "--threshold-config",
        type=str,
        help="Path to threshold config JSON (auto-detected if not provided)"
    )
    parser.add_argument(
        "--model-store-dir",
        type=str,
        help="Path to model store for baseline comparison (auto-detected if not provided)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Output directory for action decisions (auto-created if not provided)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Model Monitoring Action Evaluation")
    print("=" * 60)
    print(f"Model ID: {args.model_id}")

    try:
        # Find threshold config
        if args.threshold_config:
            threshold_config_path = args.threshold_config
        else:
            threshold_config_path = find_threshold_config()

        if not threshold_config_path:
            print("\n❌ Error: Threshold configuration not found")
            print("   Searched locations:")
            for candidate in THRESHOLD_CONFIG_CANDIDATES:
                print(f"     - {candidate}")
            raise FileNotFoundError("Threshold configuration not found")

        threshold_config = load_threshold_config(threshold_config_path)

        # Find monitoring directory
        if args.monitoring_dir:
            monitoring_dir = args.monitoring_dir
        else:
            monitoring_dir = find_monitoring_dir()

        if not monitoring_dir or not os.path.isdir(monitoring_dir):
            print("\n❌ Error: Monitoring directory not found")
            if monitoring_dir:
                print(f"   Searched: {monitoring_dir}")
            else:
                print("   Searched locations:")
                for root in get_datamart_roots():
                    print(f"     - {os.path.join(root, 'gold/monitoring')}")
            raise FileNotFoundError("Monitoring directory not found")

        # Load latest monitoring metrics
        print(f"\n{'='*60}")
        print(f"Loading Latest Monitoring Metrics for {args.model_id}")
        print(f"{'='*60}")
        print(f"Monitoring directory: {monitoring_dir}")

        metrics, metrics_file = load_latest_monitoring_metrics(monitoring_dir, args.model_id)
        print(f"Loaded: {os.path.basename(metrics_file)}")
        print(f"Snapshot date: {metrics.get('snapshot_date', 'unknown')}")
        print(f"Model type: {metrics.get('model_type', 'unknown')}")

        # Load baseline metrics (optional)
        baseline_metrics = None
        if args.model_store_dir:
            model_store_dir = args.model_store_dir
        else:
            model_store_dir = find_model_store_dir()

        if model_store_dir:
            print(f"\n{'='*60}")
            print(f"Loading Training Baselines for {args.model_id}")
            print(f"{'='*60}")
            baseline_metrics = load_training_baseline(model_store_dir, args.model_id)
            if baseline_metrics:
                print(f"OOT ROC-AUC: {baseline_metrics.get('oot_roc_auc', 'N/A')}")
                print(f"OOT Accuracy: {baseline_metrics.get('oot_accuracy', 'N/A')}")
        else:
            print(f"\n⚠️  Model store not found. Baseline comparison will be skipped.")

        # Evaluate each metric
        print(f"\n{'='*60}")
        print("Evaluating Metrics Against Thresholds")
        print(f"{'='*60}")

        metric_evaluations = []
        for metric_name, metric_config in threshold_config['metrics'].items():
            if metric_name not in metrics:
                print(f"  ⏭️  {metric_name} not found in monitoring metrics, skipping")
                continue

            metric_value = metrics[metric_name]
            baseline_value = baseline_metrics.get(f"oot_{metric_name}") if baseline_metrics else None

            evaluation = evaluate_metric_threshold(
                metric_value=metric_value,
                metric_name=metric_name,
                metric_config=metric_config,
                baseline_value=baseline_value
            )

            metric_evaluations.append(evaluation)

            status_icon = {
                'OK': '✅',
                'WARNING': '⚠️ ',
                'CRITICAL': '❌'
            }.get(evaluation['status'], '❓')

            print(f"  {status_icon} {evaluation['metric_display_name']:15} = {metric_value:.4f} [{evaluation['status']}]")

        # Determine overall action
        print(f"\n{'='*60}")
        print("Determining Overall Action")
        print(f"{'='*60}")

        overall_action, action_alerts = determine_overall_action(metric_evaluations)

        action_icon = {
            'monitor': '✅',
            'active_monitoring': '⚠️ ',
            'retrain': '❌'
        }.get(overall_action, '❓')

        print(f"\n{action_icon} ACTION: {overall_action.upper()}")
        print(f"\nAlert Summary:")
        for alert in action_alerts:
            print(f"  {alert}")

        # Generate detailed report
        report = generate_action_report(
            model_id=args.model_id,
            metrics=metrics,
            metric_evaluations=metric_evaluations,
            overall_action=overall_action,
            action_alerts=action_alerts,
            threshold_config=threshold_config,
            metrics_file=metrics_file
        )

        # Get output directory
        if args.output_dir:
            output_dir = args.output_dir
            os.makedirs(output_dir, exist_ok=True)
        else:
            output_dir = get_output_dir()

        print(f"\nOutput directory: {output_dir}")

        # Save action decision
        decision_file = save_action_decision(
            model_id=args.model_id,
            overall_action=overall_action,
            action_alerts=action_alerts,
            metric_evaluations=metric_evaluations,
            metrics=metrics,
            output_dir=output_dir
        )

        # Save report
        report_file = decision_file.replace('.json', '.txt')
        with open(report_file, 'w') as f:
            f.write(report)

        # Print report
        print("\n" + report)

        print(f"\n{'='*60}")
        print("✅ Action Evaluation Completed")
        print(f"{'='*60}")
        print(f"Decision saved: {decision_file}")
        print(f"Report saved: {report_file}")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"\n❌ Error during action evaluation: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
