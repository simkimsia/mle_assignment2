#!/usr/bin/env python3
"""
seed_inference_backfill.py

Backfill monthly inference outputs once models are trained.

This script is intended to run immediately after the automated training tasks
complete. It looks back a configurable number of months (including the current
snapshot date) and generates any missing prediction parquet files by invoking
the existing inference entry-points.
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dateutil.relativedelta import relativedelta


SCRIPT_DIR = Path(__file__).resolve().parent
PREDICTIONS_DIR = SCRIPT_DIR / "datamart" / "gold" / "predictions"

MODEL_INFERENCE_TARGETS = {
    "model_1": {
        "script": "model_1_inference.py",
        "output_pattern": "model_1_predictions_{date}.parquet",
    },
    "model_2": {
        "script": "model_2_inference.py",
        "output_pattern": "model_2_predictions_{date}.parquet",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill inference outputs for recent months once models exist."
    )
    parser.add_argument(
        "--snapshotdate",
        required=True,
        help="Snapshot date (YYYY-MM-DD) that triggered this run.",
    )
    parser.add_argument(
        "--backfill-months",
        type=int,
        default=6,
        help="Number of consecutive months (including snapshot date) to ensure predictions exist.",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=list(MODEL_INFERENCE_TARGETS.keys()),
        choices=list(MODEL_INFERENCE_TARGETS.keys()),
        help="Subset of models to backfill. Defaults to all configured models.",
    )
    return parser.parse_args()


def month_sequence(snapshot_dt: datetime, months: int):
    """Generate a chronological list of month start dates ending at snapshot_dt."""
    if months < 1:
        raise ValueError("backfill-months must be at least 1")

    return [
        (snapshot_dt - relativedelta(months=offset)).replace(day=1)
        for offset in range(months - 1, -1, -1)
    ]


def ensure_predictions(model_key: str, run_date: datetime):
    """Run inference script for the specified model/date if outputs are missing."""
    target = MODEL_INFERENCE_TARGETS[model_key]
    formatted_date = run_date.strftime("%Y_%m_%d")
    output_path = PREDICTIONS_DIR / target["output_pattern"].format(date=formatted_date)

    if output_path.exists():
        print(
            f"[SKIP] {model_key}: predictions already present for {run_date.strftime('%Y-%m-%d')} -> {output_path}"
        )
        return

    script_path = SCRIPT_DIR / target["script"]
    if not script_path.exists():
        raise FileNotFoundError(f"{model_key} inference script missing: {script_path}")

    cmd = [
        sys.executable,
        str(script_path),
        "--snapshotdate",
        run_date.strftime("%Y-%m-%d"),
    ]

    print(f"[RUN ] {model_key}: generating predictions for {run_date.strftime('%Y-%m-%d')}")
    subprocess.run(cmd, cwd=SCRIPT_DIR, check=True)
    print(f"[DONE] {model_key}: created {output_path}")


def main():
    args = parse_args()
    snapshot_dt = datetime.strptime(args.snapshotdate, "%Y-%m-%d")

    if not PREDICTIONS_DIR.exists():
        print(f"Creating predictions directory: {PREDICTIONS_DIR}")
        PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)

    run_months = month_sequence(snapshot_dt, args.backfill_months)
    print(
        f"Backfilling inference for models {args.models} across dates "
        f"{[dt.strftime('%Y-%m-%d') for dt in run_months]}"
    )

    for model_key in args.models:
        for run_date in run_months:
            ensure_predictions(model_key, run_date)


if __name__ == "__main__":
    main()
