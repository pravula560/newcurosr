#!/usr/bin/env python3
"""
Render SQL for the daily events channel report from template placeholders.
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

TEMPLATE_PATH = Path("sql/fplus_daily_events_channel_report.sql")
DEFAULT_OUTPUT = Path("dist/fplus_daily_events_channel_report.generated.sql")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render SQL for the fplus daily events channel report."
    )
    parser.add_argument(
        "--start-date",
        help="Event start date in YYYY-MM-DD format (inclusive).",
    )
    parser.add_argument(
        "--end-date",
        help="Optional event end date in YYYY-MM-DD format (inclusive).",
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
) -> str:
    event_end_sql = (
        f"  AND fdm.event_date <= {quote_sql_string(end_date.isoformat())}"
        if end_date
        else ""
    )

    rendered = template
    rendered = rendered.replace("__EVENT_START__", start_date.isoformat())
    rendered = rendered.replace("__EVENT_END_SQL__", event_end_sql)
    return rendered


def main() -> int:
    args = parse_args()

    template_path = Path(args.template)
    if not template_path.exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")

    start_date, end_date = resolve_dates(args)
    template = template_path.read_text(encoding="utf-8")
    rendered = render_sql(
        template=template,
        start_date=start_date,
        end_date=end_date,
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
