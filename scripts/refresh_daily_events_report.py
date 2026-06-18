#!/usr/bin/env python3
"""
Render daily events report SQL, execute in BigQuery, and write CSV output.
"""

from __future__ import annotations

import argparse
import datetime as dt
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
    parser = argparse.ArgumentParser(
        description="Refresh daily events channel report CSV from BigQuery."
    )
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD inclusive start.")
    parser.add_argument("--end-date", help="YYYY-MM-DD inclusive end.")
    parser.add_argument("--mtd", action="store_true", help="Use month-to-date bounds.")
    parser.add_argument("--as-of-date", help="YYYY-MM-DD date for --mtd.")
    parser.add_argument(
        "--destination-csv",
        default="docs/data/daily_events_channel_report.csv",
        help="Output CSV path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sql_path = Path("dist/fplus_daily_events_channel_report.generated.sql")
    destination = Path(args.destination_csv)
    destination.parent.mkdir(parents=True, exist_ok=True)

    render_cmd = [
        "python3",
        "run_fplus_daily_events_report.py",
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

    run(render_cmd)

    bq_cmd = [
        "bq",
        "query",
        "--nouse_legacy_sql",
        "--format=csv",
        "--max_rows=10000000",
        f"--output_file={destination}",
        sql_path.read_text(encoding="utf-8"),
    ]
    run(bq_cmd)

    stamp = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    print(f"Updated {destination} at {stamp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
