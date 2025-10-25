"""Utility script to explore datamart parquet outputs (defaults to gold layer)."""

import argparse
import re
from pathlib import Path
from typing import Iterable, Optional

from pyspark.sql import SparkSession

TIMESTAMP_PATTERN = re.compile(r"^\d{8}_\d{6}$")


def find_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def find_snapshot_dir(root: Path, snapshot: Optional[str]) -> Path:
    datamart_root = root / "datamart"
    if not datamart_root.exists():
        raise FileNotFoundError(f"Datamart directory not found at {datamart_root}")

    if snapshot:
        candidate = datamart_root / snapshot
        if not candidate.exists():
            raise FileNotFoundError(f"Snapshot '{snapshot}' not found under {datamart_root}")
        return candidate

    snapshot_dirs = sorted(
        [d for d in datamart_root.iterdir() if d.is_dir() and TIMESTAMP_PATTERN.match(d.name)]
    )
    if not snapshot_dirs:
        raise FileNotFoundError(
            f"No timestamped snapshot directories found under {datamart_root}. "
            "Use --base-path to target a custom location."
        )
    latest = snapshot_dirs[-1]
    print(f"Auto-selected latest snapshot: {latest.name}")
    return latest


def resolve_base_path(custom_path: Optional[str], snapshot: Optional[str], layer: str) -> Path:
    if custom_path:
        base = Path(custom_path).expanduser().resolve()
    else:
        repo_root = find_repo_root()
        snapshot_dir = find_snapshot_dir(repo_root, snapshot)
        base = snapshot_dir / layer
    if not base.exists():
        raise FileNotFoundError(f"{layer.title()} path not found: {base}")
    return base


def list_tables(base_path: Path) -> None:
    print(f"Inspecting directory: {base_path}")
    parquet_files = sorted(base_path.glob("**/*.parquet"))
    if not parquet_files:
        print("No parquet files found.")
        return
    for path in parquet_files:
        relative = path.relative_to(base_path)
        print(f"- {relative}")


def inspect_table(
    base_path: Path,
    table: str,
    sample_rows: int,
    show_count: bool,
    columns: Iterable[str],
) -> None:
    spark = SparkSession.builder.appName("Assignment2DatamartInspector").getOrCreate()
    try:
        table_path = (base_path / table).resolve()
        if not table_path.exists():
            raise FileNotFoundError(f"Table path not found: {table_path}")

        df = spark.read.parquet(str(table_path))
        print(f"Schema for {table_path}:")
        df.printSchema()

        if columns:
            missing = [col for col in columns if col not in df.columns]
            if missing:
                print(f"Missing expected columns: {missing}")
            else:
                print("All expected columns present.")

        if sample_rows > 0:
            print(f"\nSample ({sample_rows} rows):")
            df.show(sample_rows, truncate=False)

        if show_count:
            print(f"\nRow count: {df.count()}")
    finally:
        spark.stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect datamart parquet outputs.")
    parser.add_argument(
        "--base-path",
        help="Override layer directory completely (useful when inspecting custom exports).",
    )
    parser.add_argument(
        "--layer",
        choices=["bronze", "silver", "gold"],
        default="gold",
        help="Datamart layer to inspect (default: gold).",
    )
    parser.add_argument(
        "--snapshot",
        help="Timestamped snapshot (e.g., 20240830_235959). Defaults to latest available.",
    )
    parser.add_argument("--table", help="Relative path under the layer directory to inspect.")
    parser.add_argument("--sample", type=int, default=5, help="Number of sample rows to display.")
    parser.add_argument("--count", action="store_true", help="If set, prints the row count.")
    parser.add_argument(
        "--columns",
        nargs="*",
        default=[],
        help="Optional list of columns that must exist in the table.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_path = resolve_base_path(args.base_path, args.snapshot, args.layer)

    if not args.table:
        list_tables(base_path)
    else:
        inspect_table(base_path, args.table, args.sample, args.count, args.columns)


if __name__ == "__main__":
    main()
