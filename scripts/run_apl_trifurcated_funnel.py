#!/usr/bin/env python3

import argparse
import csv
import datetime as dt
import os
from pathlib import Path
from typing import Iterable

from google.cloud import bigquery


DEFAULT_SQL_PATH = Path(__file__).resolve().parents[1] / "sql" / "apl_trifurcated_funnel_query.sql"


def _parse_date(s: str) -> dt.date:
    try:
        return dt.date.fromisoformat(s)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid date '{s}' (expected YYYY-MM-DD)") from e


def _product_line_in(values: Iterable[str]) -> str:
    vals = []
    for v in values:
        v = v.strip()
        if not v:
            continue
        vals.append(f"'{v.upper()}'")
    if not vals:
        raise ValueError("At least one product line is required")
    return ", ".join(vals)


def _render_sql(
    template: str,
    *,
    product_lines: list[str],
    created_start: dt.date,
    created_end: dt.date | None,
    eligible_only: bool,
) -> str:
    created_end_sql = ""
    if created_end is not None:
        created_end_sql = f"    AND DATE(A.created_datetime) <= '{created_end.isoformat()}'"

    flag_eligible_sql = ""
    if eligible_only:
        flag_eligible_sql = "    AND A.flag_eligible_lead IS TRUE"

    rendered = template
    rendered = rendered.replace("__PRODUCT_LINE_IN__", _product_line_in(product_lines))
    rendered = rendered.replace("__CREATED_START__", created_start.isoformat())
    rendered = rendered.replace("__CREATED_END_SQL__", created_end_sql)
    rendered = rendered.replace("__FLAG_ELIGIBLE_SQL__", flag_eligible_sql)
    return rendered


def main() -> int:
    ap = argparse.ArgumentParser(description="Run APL trifurcated funnel extract in BigQuery and export to CSV.")
    ap.add_argument("--sql", default=str(DEFAULT_SQL_PATH), help="Path to SQL template file")
    ap.add_argument(
        "--product-line",
        action="append",
        required=True,
        help="Product line to include. Repeatable. Examples: CORE, PAGAYA, SUPERPRIME",
    )
    ap.add_argument("--start-date", type=_parse_date, required=True, help="Cohort start date (YYYY-MM-DD)")
    ap.add_argument("--end-date", type=_parse_date, default=None, help="Optional cohort end date (YYYY-MM-DD)")
    ap.add_argument("--mtd", action="store_true", help="Set end-date to today (UTC)")
    ap.add_argument("--eligible-only", action="store_true", help="Apply server-side filter A.flag_eligible_lead IS TRUE")
    ap.add_argument("--project", default=os.getenv("BQ_PROJECT"), help="BigQuery project override")
    ap.add_argument("--location", default=os.getenv("BQ_LOCATION", "US"), help="BigQuery location (default US)")
    ap.add_argument(
        "--out",
        default=str(Path("data") / "apl_trifurcated_funnel.csv"),
        help="Output CSV path",
    )
    ap.add_argument("--dry-run", action="store_true", help="Print rendered SQL only")

    args = ap.parse_args()

    created_end = args.end_date
    if args.mtd and created_end is None:
        created_end = dt.datetime.now(dt.UTC).date()

    template = Path(args.sql).read_text(encoding="utf-8")
    sql = _render_sql(
        template,
        product_lines=args.product_line,
        created_start=args.start_date,
        created_end=created_end,
        eligible_only=args.eligible_only,
    )

    if args.dry_run:
        print(sql)
        return 0

    client = bigquery.Client(project=args.project, location=args.location)
    job = client.query(sql)
    result = job.result()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [f.name for f in result.schema]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        row_count = 0
        for row in result:
            w.writerow(dict(row))
            row_count += 1

    print(f"Wrote {out_path} ({row_count} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

