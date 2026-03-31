#!/usr/bin/env python3
"""
Render query SQL, execute in BigQuery, and write docs/data/latest.csv.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path


def run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            + " ".join(cmd)
            + "\n\nSTDOUT:\n"
            + result.stdout
            + "\nSTDERR:\n"
            + result.stderr
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh dashboard CSV from BigQuery.")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD inclusive cohort start.")
    parser.add_argument("--end-date", help="YYYY-MM-DD inclusive cohort end.")
    parser.add_argument("--mtd", action="store_true", help="Use month-to-date bounds.")
    parser.add_argument("--as-of-date", help="YYYY-MM-DD date for --mtd.")
    parser.add_argument("--eligible-only", action="store_true", help="Filter to eligible leads only.")
    parser.add_argument(
        "--destination-csv",
        default="docs/data/latest.csv",
        help="Output CSV path for static dashboard.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sql_path = Path("dist/apl_trifurcated_funnel_dashboard_extract.generated.sql")
    destination = Path(args.destination_csv)
    destination.parent.mkdir(parents=True, exist_ok=True)

    render_cmd = [
        "python3",
        "run_apl_trifurcated_funnel.py",
        "--start-date",
        args.start_date,
        "--output",
        str(sql_path),
    ]
    if args.end_date:
        render_cmd.extend(["--end-date", args.end_date])
    if args.mtd:
        render_cmd.append("--mtd")
    if args.as_of_date:
        render_cmd.extend(["--as-of-date", args.as_of_date])
    if args.eligible_only:
        render_cmd.append("--eligible-only")

    run(render_cmd)

    # BigQuery CLI writes CSV directly to file.
    bq_cmd = [
        "bq",
        "query",
        "--nouse_legacy_sql",
        "--format=csv",
        f"--max_rows=10000000",
        f"--output_file={destination}",
    ]
    bq_cmd.append(sql_path.read_text(encoding="utf-8"))
    run(bq_cmd)

    # Write a small metadata file so the static dashboard can show freshness.
    row_count = 0
    with destination.open("r", encoding="utf-8") as f:
        # Subtract one for header when present.
        row_count = max(sum(1 for _ in f) - 1, 0)

    stamp = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    metadata = {
        "refreshed_at_utc": stamp,
        "source_table": "ffam-data-platform.standardized_data.fplus_application",
        "cohort_start_date": args.start_date,
        "cohort_end_date": args.end_date or None,
        "mtd": bool(args.mtd),
        "as_of_date": args.as_of_date or None,
        "eligible_only": bool(args.eligible_only),
        "row_count": row_count,
        "csv_path": str(destination),
    }
    metadata_path = destination.parent / "latest.metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Updated {destination} at {stamp}")
    print(f"Updated {metadata_path} with refresh metadata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
