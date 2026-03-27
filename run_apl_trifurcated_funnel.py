#!/usr/bin/env python3
"""
Extract APL trifurcated-funnel data from BigQuery and write to Parquet/CSV.

Renders the parameterised SQL in sql/apl_trifurcated_funnel.sql, executes it
against BigQuery, and writes the result to data/apl_trifurcated_funnel.parquet
(+ optional CSV).

Usage examples
--------------
# Open cohort from 2025-01-01, all product lines, all eligibility flags:
  python run_apl_trifurcated_funnel.py --start-date 2025-01-01

# MTD cohort (first of current month -> today), eligible leads only:
  python run_apl_trifurcated_funnel.py --mtd --eligible-only

# Bounded cohort with end date and CSV output:
  python run_apl_trifurcated_funnel.py --start-date 2025-01-01 --end-date 2025-03-31 --csv

# Specific product lines:
  python run_apl_trifurcated_funnel.py --start-date 2025-01-01 --product-lines CORE PAGAYA
"""

from __future__ import annotations

import argparse
import datetime
import os
import pathlib
import sys
import textwrap

import pandas as pd

SQL_PATH = pathlib.Path(__file__).resolve().parent / "sql" / "apl_trifurcated_funnel.sql"
DATA_DIR = pathlib.Path(__file__).resolve().parent / "data"

DEFAULT_PRODUCT_LINES = ("CORE", "PAGAYA", "SUPERPRIME")


def _render_sql(
    start_date: str,
    end_date: str | None,
    product_lines: tuple[str, ...],
    eligible_only: bool,
) -> str:
    """Replace placeholders in the raw SQL template and return final query."""
    raw = SQL_PATH.read_text()

    pl_clause = ", ".join(f"'{p.upper()}'" for p in product_lines)
    raw = raw.replace("__PRODUCT_LINE_IN__", pl_clause)
    raw = raw.replace("__CREATED_START__", start_date)

    if end_date:
        raw = raw.replace(
            "__CREATED_END_SQL__",
            f"    AND DATE(A.created_datetime) <= '{end_date}'",
        )
    else:
        raw = raw.replace("__CREATED_END_SQL__", "")

    if eligible_only:
        raw = raw.replace(
            "__FLAG_ELIGIBLE_SQL__",
            "    AND A.flag_eligible_lead = TRUE",
        )
    else:
        raw = raw.replace("__FLAG_ELIGIBLE_SQL__", "")

    return raw


def _run_query(sql: str, project: str | None = None) -> pd.DataFrame:
    """Execute *sql* against BigQuery and return a DataFrame."""
    try:
        from google.cloud import bigquery
    except ImportError:
        sys.exit(
            "google-cloud-bigquery is required.  Install with:\n"
            "  pip install google-cloud-bigquery db-dtypes pyarrow"
        )

    client = bigquery.Client(project=project)
    print("Running query against BigQuery …")
    df = client.query(sql).to_dataframe()
    print(f"  → {len(df):,} rows returned.")
    return df


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract APL trifurcated-funnel data from BigQuery.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              %(prog)s --start-date 2025-01-01
              %(prog)s --mtd --eligible-only
              %(prog)s --start-date 2025-01-01 --end-date 2025-03-31 --csv
        """),
    )

    date_grp = parser.add_mutually_exclusive_group(required=True)
    date_grp.add_argument(
        "--start-date",
        help="Cohort start date (YYYY-MM-DD). Required unless --mtd is used.",
    )
    date_grp.add_argument(
        "--mtd",
        action="store_true",
        help="Month-to-date: start = 1st of current month, end = today.",
    )

    parser.add_argument(
        "--end-date",
        default=None,
        help="Optional cohort end date (YYYY-MM-DD).  Omit for open cohort.",
    )
    parser.add_argument(
        "--product-lines",
        nargs="+",
        default=list(DEFAULT_PRODUCT_LINES),
        help="Product lines to include (default: CORE PAGAYA SUPERPRIME).",
    )
    parser.add_argument(
        "--eligible-only",
        action="store_true",
        help="Filter to flag_eligible_lead = TRUE in SQL.",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Also write a CSV alongside the Parquet file.",
    )
    parser.add_argument(
        "--project",
        default=None,
        help="GCP project ID (defaults to Application Default Credentials project).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print rendered SQL without executing.",
    )

    args = parser.parse_args(argv)

    if args.mtd:
        today = datetime.date.today()
        args.start_date = today.replace(day=1).isoformat()
        args.end_date = today.isoformat()

    return args


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    sql = _render_sql(
        start_date=args.start_date,
        end_date=args.end_date,
        product_lines=tuple(args.product_lines),
        eligible_only=args.eligible_only,
    )

    if args.dry_run:
        print(sql)
        return

    df = _run_query(sql, project=args.project)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    parquet_path = DATA_DIR / "apl_trifurcated_funnel.parquet"
    df.to_parquet(parquet_path, index=False)
    print(f"Parquet written → {parquet_path}")

    if args.csv:
        csv_path = DATA_DIR / "apl_trifurcated_funnel.csv"
        df.to_csv(csv_path, index=False)
        print(f"CSV written    → {csv_path}")


if __name__ == "__main__":
    main()
