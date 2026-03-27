#!/usr/bin/env python3
"""
Builds the APL trifurcated funnel dashboard SQL from template placeholders.
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import List

DEFAULT_PRODUCT_LINES = ["CORE", "PAGAYA", "SUPERPRIME"]
TEMPLATE_PATH = Path("sql/apl_trifurcated_funnel_dashboard_extract.sql")
DEFAULT_OUTPUT = Path("dist/apl_trifurcated_funnel_dashboard_extract.generated.sql")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render SQL for the APL trifurcated funnel dashboard extract."
    )
    parser.add_argument(
        "--start-date",
        help="Cohort start date in YYYY-MM-DD format (inclusive).",
    )
    parser.add_argument(
        "--end-date",
        help="Optional cohort end date in YYYY-MM-DD format (inclusive).",
    )
    parser.add_argument(
        "--mtd",
        action="store_true",
        help=(
            "Use month-to-date bounds based on --as-of-date (or today) and "
            "ignore explicit --start-date/--end-date."
        ),
    )
    parser.add_argument(
        "--as-of-date",
        help="Reference date in YYYY-MM-DD for --mtd (defaults to today).",
    )
    parser.add_argument(
        "--eligible-only",
        action="store_true",
        help="Append SQL filter for flag_eligible_lead = TRUE.",
    )
    parser.add_argument(
        "--product-line",
        dest="product_lines",
        action="append",
        help=(
            "Product line to include (repeatable). Defaults to CORE, PAGAYA, "
            "SUPERPRIME when omitted."
        ),
    )
    parser.add_argument(
        "--template",
        default=str(TEMPLATE_PATH),
        help=f"Template SQL path (default: {TEMPLATE_PATH}).",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"Rendered SQL output path (default: {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print rendered SQL to stdout in addition to writing the output file.",
    )
    return parser.parse_args()


def parse_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{value}'. Expected YYYY-MM-DD."
        ) from exc


def quote_sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def normalize_product_lines(product_lines: List[str] | None) -> List[str]:
    if not product_lines:
        return DEFAULT_PRODUCT_LINES
    normalized = []
    for product_line in product_lines:
        cleaned = product_line.strip().upper()
        if cleaned:
            normalized.append(cleaned)
    if not normalized:
        raise ValueError("At least one non-empty --product-line value is required.")
    return normalized


def resolve_dates(args: argparse.Namespace) -> tuple[dt.date, dt.date | None]:
    if args.mtd:
        as_of = parse_date(args.as_of_date) if args.as_of_date else dt.date.today()
        start = as_of.replace(day=1)
        end = as_of
        return start, end

    if not args.start_date:
        raise ValueError("--start-date is required unless --mtd is set.")
    start = parse_date(args.start_date)
    end = parse_date(args.end_date) if args.end_date else None
    if end is not None and end < start:
        raise ValueError("--end-date cannot be earlier than --start-date.")
    return start, end


def render_sql(
    template: str,
    start_date: dt.date,
    end_date: dt.date | None,
    product_lines: List[str],
    eligible_only: bool,
) -> str:
    product_line_in = ", ".join(quote_sql_string(product_line) for product_line in product_lines)
    created_end_sql = (
        f"    AND DATE(A.created_datetime) <= {quote_sql_string(end_date.isoformat())}"
        if end_date
        else ""
    )
    eligible_sql = "    AND A.flag_eligible_lead IS TRUE" if eligible_only else ""

    rendered = template
    rendered = rendered.replace("__PRODUCT_LINE_IN__", product_line_in)
    rendered = rendered.replace("__CREATED_START__", start_date.isoformat())
    rendered = rendered.replace("__CREATED_END_SQL__", created_end_sql)
    rendered = rendered.replace("__FLAG_ELIGIBLE_SQL__", eligible_sql)
    return rendered


def main() -> int:
    args = parse_args()

    template_path = Path(args.template)
    if not template_path.exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")

    product_lines = normalize_product_lines(args.product_lines)
    start_date, end_date = resolve_dates(args)

    template = template_path.read_text(encoding="utf-8")
    rendered = render_sql(
        template=template,
        start_date=start_date,
        end_date=end_date,
        product_lines=product_lines,
        eligible_only=args.eligible_only,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")

    if args.stdout:
        print(rendered)
    else:
        print(f"Wrote rendered SQL to {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
