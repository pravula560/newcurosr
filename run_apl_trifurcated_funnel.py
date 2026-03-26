#!/usr/bin/env python3
"""Run the APL trifurcated funnel BigQuery extract and write CSV for the dashboard.

Usage examples
--------------
  # Open cohort from 2025-01-01, all eligibility values
  python run_apl_trifurcated_funnel.py --start-date 2025-01-01

  # MTD cohort (first of current month through yesterday)
  python run_apl_trifurcated_funnel.py --mtd

  # Bounded cohort, eligible leads only
  python run_apl_trifurcated_funnel.py --start-date 2025-01-01 --end-date 2025-03-31 --eligible-only

  # Custom output path
  python run_apl_trifurcated_funnel.py --start-date 2025-01-01 -o /tmp/funnel.csv
"""

from __future__ import annotations

import argparse
import datetime
import os
import pathlib
import sys

try:
    from google.cloud import bigquery
except ImportError:
    sys.exit(
        "google-cloud-bigquery is required.  Install with:\n"
        "  pip install google-cloud-bigquery db-dtypes"
    )

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
SQL_FILE = SCRIPT_DIR / "apl_trifurcated_funnel_query.sql"
DEFAULT_CSV = SCRIPT_DIR / "apl_trifurcated_funnel.csv"

PRODUCT_LINES = ("'CORE'", "'PAGAYA'", "'SUPERPRIME'")


def _build_query(
    start_date: str,
    end_date: str | None = None,
    eligible_only: bool = False,
) -> str:
    sql = SQL_FILE.read_text()
    sql = sql.replace("__PRODUCT_LINE_IN__", ", ".join(PRODUCT_LINES))
    sql = sql.replace("__CREATED_START__", start_date)

    if end_date:
        sql = sql.replace(
            "__CREATED_END_SQL__",
            f"    AND DATE(A.created_datetime) <= '{end_date}'",
        )
    else:
        sql = sql.replace("__CREATED_END_SQL__", "")

    if eligible_only:
        sql = sql.replace(
            "__FLAG_ELIGIBLE_SQL__",
            "    AND A.flag_eligible_lead = TRUE",
        )
    else:
        sql = sql.replace("__FLAG_ELIGIBLE_SQL__", "")

    return sql


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="APL trifurcated funnel BigQuery extract",
    )
    date_group = parser.add_mutually_exclusive_group(required=True)
    date_group.add_argument(
        "--start-date",
        help="Cohort start date (YYYY-MM-DD)",
    )
    date_group.add_argument(
        "--mtd",
        action="store_true",
        help="Month-to-date: first of current month through yesterday",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="Optional cohort end date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--eligible-only",
        action="store_true",
        help="Filter to flag_eligible_lead = TRUE in BQ (reduces data transferred)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=str(DEFAULT_CSV),
        help="Output CSV path (default: %(default)s)",
    )
    parser.add_argument(
        "--project",
        default=os.getenv("GCP_PROJECT", "ffam-data-platform"),
        help="GCP project id (default: %(default)s)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the rendered SQL and exit without running",
    )
    args = parser.parse_args(argv)

    if args.mtd:
        today = datetime.date.today()
        args.start_date = today.replace(day=1).isoformat()
        args.end_date = (today - datetime.timedelta(days=1)).isoformat()

    return args


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    sql = _build_query(args.start_date, args.end_date, args.eligible_only)

    if args.dry_run:
        print(sql)
        return

    print(f"[INFO] Cohort: {args.start_date} → {args.end_date or '(open)'}")
    print(f"[INFO] Eligible only: {args.eligible_only}")
    print(f"[INFO] Output: {args.output}")

    client = bigquery.Client(project=args.project)
    print("[INFO] Running BigQuery extract …")
    df = client.query(sql).to_dataframe()
    print(f"[INFO] Rows returned: {len(df):,}")

    out_path = pathlib.Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"[INFO] CSV written to {out_path}")

    for pl in ("CORE", "PAGAYA", "SUPERPRIME"):
        subset = df[df["product_line"] == pl]
        loans = subset["application_key"].nunique()
        funds = subset.loc[
            subset["funding_datetime"].notna(), "loan_id"
        ].nunique()
        volume = subset["origination_dollars"].sum()
        print(f"  {pl:12s}  loans={loans:>7,}  funded={funds:>7,}  volume=${volume:>14,.2f}")


if __name__ == "__main__":
    main()
