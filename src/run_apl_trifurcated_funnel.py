#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
DEFAULT_SQL_PATH = SQL_DIR / "apl_trifurcated_funnel_query.sql"


@dataclass(frozen=True)
class QueryParams:
    product_lines: list[str]
    created_start: str
    created_end_sql: str
    flag_eligible_sql: str


def _quote_sql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _render_product_line_in(product_lines: Iterable[str]) -> str:
    items = [pl.strip().upper() for pl in product_lines if pl.strip()]
    if not items:
        raise ValueError("At least one --product-line is required.")
    return ", ".join(_quote_sql_string(x) for x in items)


def _render_created_end_sql(end_date: Optional[str]) -> str:
    if not end_date:
        return ""
    return f"    AND DATE(A.created_datetime) <= {_quote_sql_string(end_date)}"


def _render_flag_eligible_sql(eligible_only: bool) -> str:
    if not eligible_only:
        return ""
    return "    AND A.flag_eligible_lead = TRUE"


def build_params(
    *,
    product_lines: list[str],
    start_date: str,
    end_date: Optional[str],
    eligible_only: bool,
) -> QueryParams:
    return QueryParams(
        product_lines=product_lines,
        created_start=start_date,
        created_end_sql=_render_created_end_sql(end_date),
        flag_eligible_sql=_render_flag_eligible_sql(eligible_only),
    )


def render_sql(template_sql: str, params: QueryParams) -> str:
    rendered = template_sql
    rendered = rendered.replace("__PRODUCT_LINE_IN__", _render_product_line_in(params.product_lines))
    rendered = rendered.replace("__CREATED_START__", params.created_start)
    rendered = rendered.replace("__CREATED_END_SQL__", params.created_end_sql)
    rendered = rendered.replace("__FLAG_ELIGIBLE_SQL__", params.flag_eligible_sql)
    return rendered


def default_start_date() -> str:
    # Default to current month-to-date start to limit extract size by default.
    today = dt.date.today()
    return today.replace(day=1).isoformat()


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run APL trifurcated funnel GBQ extract and export CSV.",
    )
    p.add_argument(
        "--sql",
        default=str(DEFAULT_SQL_PATH),
        help="Path to SQL template with placeholders.",
    )
    p.add_argument(
        "--product-line",
        action="append",
        required=True,
        help="Product line to include (repeatable). Example: --product-line Core --product-line Pagaya",
    )
    p.add_argument(
        "--start-date",
        default=default_start_date(),
        help="Cohort start date (YYYY-MM-DD) on DATE(created_datetime).",
    )
    p.add_argument(
        "--end-date",
        default=None,
        help="Optional cohort end date (YYYY-MM-DD) on DATE(created_datetime).",
    )
    p.add_argument(
        "--mtd",
        action="store_true",
        help="Set end-date to today (inclusive).",
    )
    p.add_argument(
        "--eligible-only",
        action="store_true",
        help="Apply server-side filter flag_eligible_lead = TRUE.",
    )
    p.add_argument(
        "--out",
        default="dashboard/apl_trifurcated_funnel.csv",
        help="Output CSV path.",
    )
    p.add_argument(
        "--dry-run-sql",
        action="store_true",
        help="Print rendered SQL and exit (no BigQuery call).",
    )
    return p.parse_args(argv)


def _bq_client():
    try:
        from google.cloud import bigquery  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Missing dependency google-cloud-bigquery. Install via: pip install -r requirements.txt"
        ) from e
    return bigquery.Client()


def run_to_csv(rendered_sql: str, out_path: Path) -> None:
    client = _bq_client()
    job = client.query(rendered_sql)
    df = job.result().to_dataframe(create_bqstorage_client=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    end_date = args.end_date
    if args.mtd:
        end_date = dt.date.today().isoformat()

    sql_path = Path(args.sql)
    template_sql = sql_path.read_text(encoding="utf-8")
    params = build_params(
        product_lines=args.product_line,
        start_date=args.start_date,
        end_date=end_date,
        eligible_only=args.eligible_only,
    )
    rendered = render_sql(template_sql, params)

    if args.dry_run_sql:
        sys.stdout.write(rendered)
        if not rendered.endswith("\n"):
            sys.stdout.write("\n")
        return 0

    out = Path(args.out)
    run_to_csv(rendered, out)
    sys.stderr.write(f"Wrote CSV: {out}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
