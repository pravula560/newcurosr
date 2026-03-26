#!/usr/bin/env python3
"""
Run the APL trifurcated funnel BigQuery extract and write a CSV.

This script renders placeholders in apl_trifurcated_funnel_query.sql and executes
the query via the `bq` CLI.
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import shlex
import subprocess
import sys
from typing import Iterable, List


DEFAULT_PRODUCT_LINES = ("CORE", "PAGAYA", "SUPERPRIME")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run APL trifurcated funnel BigQuery extract."
    )
    parser.add_argument(
        "--sql-template",
        default="apl_trifurcated_funnel_query.sql",
        help="Path to SQL template with placeholders.",
    )
    parser.add_argument(
        "--compiled-sql-out",
        default="apl_trifurcated_funnel_query.compiled.sql",
        help="Where to save rendered SQL.",
    )
    parser.add_argument(
        "--output-csv",
        default="apl_trifurcated_funnel.csv",
        help="Destination CSV file path.",
    )
    parser.add_argument(
        "--product-lines",
        default=",".join(DEFAULT_PRODUCT_LINES),
        help="Comma-separated product lines. Defaults to CORE,PAGAYA,SUPERPRIME.",
    )
    parser.add_argument(
        "--start-date",
        help="Cohort start date (YYYY-MM-DD). Required unless --mtd is provided.",
    )
    parser.add_argument(
        "--end-date",
        help="Optional cohort end date (YYYY-MM-DD), inclusive.",
    )
    parser.add_argument(
        "--mtd",
        action="store_true",
        help="Use month-to-date window (first day of current month through today).",
    )
    parser.add_argument(
        "--eligible-only",
        action="store_true",
        help="Apply SQL filter `flag_eligible_lead = TRUE` in extract.",
    )
    parser.add_argument(
        "--project",
        help="Optional GCP project for bq CLI (--project_id).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render and print SQL only; do not execute BigQuery query.",
    )
    return parser.parse_args()


def validate_iso_date(value: str) -> dt.date:
    try:
        return dt.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"Invalid date '{value}'. Expected YYYY-MM-DD.") from exc


def resolve_date_window(args: argparse.Namespace) -> tuple[dt.date, dt.date | None]:
    if args.mtd:
        today = dt.date.today()
        start = today.replace(day=1)
        end = today
        return start, end

    if not args.start_date:
        raise ValueError("Provide --start-date YYYY-MM-DD or use --mtd.")

    start = validate_iso_date(args.start_date)
    end = validate_iso_date(args.end_date) if args.end_date else None

    if end and end < start:
        raise ValueError("--end-date cannot be earlier than --start-date.")
    return start, end


def parse_product_lines(product_lines_arg: str) -> List[str]:
    items = [part.strip().upper() for part in product_lines_arg.split(",")]
    values = [item for item in items if item]
    if not values:
        raise ValueError("At least one product line is required.")
    return values


def sql_literal(value: str) -> str:
    # Basic single-quote escaping for SQL string literals.
    return "'" + value.replace("'", "''") + "'"


def build_product_line_in(product_lines: Iterable[str]) -> str:
    return ", ".join(sql_literal(p) for p in product_lines)


def render_sql(
    template_sql: str,
    product_lines: List[str],
    start_date: dt.date,
    end_date: dt.date | None,
    eligible_only: bool,
) -> str:
    created_end_sql = (
        f"    AND DATE(A.created_datetime) <= '{end_date.isoformat()}'" if end_date else ""
    )
    eligible_sql = "    AND A.flag_eligible_lead IS TRUE" if eligible_only else ""
    rendered = (
        template_sql.replace("__PRODUCT_LINE_IN__", build_product_line_in(product_lines))
        .replace("__CREATED_START__", start_date.isoformat())
        .replace("__CREATED_END_SQL__", created_end_sql)
        .replace("__FLAG_ELIGIBLE_SQL__", eligible_sql)
    )
    return rendered


def run_bigquery(sql: str, output_csv_path: pathlib.Path, project: str | None) -> int:
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["bq"]
    if project:
        cmd.extend(["--project_id", project])
    cmd.extend(
        [
            "query",
            "--use_legacy_sql=false",
            "--format=csv",
            sql,
        ]
    )

    print("Executing BigQuery command:")
    print("  " + shlex.join(cmd[:-1]) + " '<SQL omitted>'")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise RuntimeError(f"bq query failed with exit code {result.returncode}.")

    output_csv_path.write_text(result.stdout, encoding="utf-8")

    line_count = result.stdout.count("\n")
    # CSV output includes one header line when non-empty.
    row_count = max(line_count - 1, 0)
    return row_count


def main() -> int:
    try:
        args = parse_args()
        start_date, end_date = resolve_date_window(args)
        product_lines = parse_product_lines(args.product_lines)

        sql_template_path = pathlib.Path(args.sql_template)
        sql_template = sql_template_path.read_text(encoding="utf-8")
        rendered_sql = render_sql(
            template_sql=sql_template,
            product_lines=product_lines,
            start_date=start_date,
            end_date=end_date,
            eligible_only=args.eligible_only,
        )

        compiled_sql_path = pathlib.Path(args.compiled_sql_out)
        compiled_sql_path.parent.mkdir(parents=True, exist_ok=True)
        compiled_sql_path.write_text(rendered_sql, encoding="utf-8")
        print(f"Wrote compiled SQL: {compiled_sql_path}")

        if args.dry_run:
            print("\n--- BEGIN RENDERED SQL ---\n")
            print(rendered_sql)
            print("\n--- END RENDERED SQL ---")
            return 0

        output_csv_path = pathlib.Path(args.output_csv)
        row_count = run_bigquery(rendered_sql, output_csv_path, args.project)
        print(f"Wrote CSV: {output_csv_path} ({row_count} rows)")
        return 0

    except Exception as exc:  # pylint: disable=broad-except
        sys.stderr.write(f"ERROR: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
