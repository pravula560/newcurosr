#!/usr/bin/env python3
"""
Render SQL for the refi / FPlus dialer agent transfer report.
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

DEFAULT_DETAIL_TEMPLATE = Path("sql/refi_dialer_agent_transfer_report.sql")
DEFAULT_SUMMARY_TEMPLATE = Path("sql/refi_dialer_agent_transfer_summary.sql")
DEFAULT_OUTPUT_DIR = Path("dist")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render SQL for dialer agent transfer gain/loss reporting."
    )
    parser.add_argument(
        "--start-date",
        default="2026-01-01",
        help="Inclusive campaign run start date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--end-date",
        help="Optional inclusive campaign run end date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--refi-only",
        action="store_true",
        help=(
            "Restrict to refinance applications. Update the SQL predicate if your "
            "refinance indicator column differs from loan_purpose."
        ),
    )
    parser.add_argument(
        "--query",
        choices=("detail", "summary", "both"),
        default="both",
        help="Which rendered SQL file(s) to write.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for generated SQL files.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print rendered SQL to stdout instead of writing files.",
    )
    return parser.parse_args()


def render_template(template_path: Path, start_date: str, end_date: str | None, refi_only: bool) -> str:
    text = template_path.read_text(encoding="utf-8")
    end_sql = ""
    if end_date:
        end_sql = (
            f"    AND d.start_run_time <= TIMESTAMP('{end_date} 23:59:59', 'America/Phoenix')"
        )
    refi_sql = ""
    if refi_only:
        refi_sql = """
    AND (
      UPPER(TRIM(COALESCE(a.loan_purpose, a15.loan_purpose, ''))) LIKE '%REFI%'
      OR UPPER(TRIM(COALESCE(a.loan_purpose, a15.loan_purpose, ''))) LIKE '%REFIN%'
    )"""
    return (
        text.replace("__COHORT_START__", start_date)
        .replace("__COHORT_END_SQL__", end_sql)
        .replace("__REFI_ONLY_SQL__", refi_sql)
    )


def main() -> None:
    args = parse_args()
    if args.end_date:
        dt.date.fromisoformat(args.end_date)
    dt.date.fromisoformat(args.start_date)

    jobs: list[tuple[str, Path]] = []
    if args.query in ("detail", "both"):
        jobs.append(("refi_dialer_agent_transfer_report.generated.sql", DEFAULT_DETAIL_TEMPLATE))
    if args.query in ("summary", "both"):
        jobs.append(("refi_dialer_agent_transfer_summary.generated.sql", DEFAULT_SUMMARY_TEMPLATE))

    rendered_blocks: list[str] = []
    for output_name, template_path in jobs:
        rendered = render_template(template_path, args.start_date, args.end_date, args.refi_only)
        rendered_blocks.append(rendered)
        if not args.stdout:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            out_path = args.output_dir / output_name
            out_path.write_text(rendered, encoding="utf-8")
            print(f"Wrote {out_path}")

    if args.stdout:
        print("\n\n".join(rendered_blocks))


if __name__ == "__main__":
    main()
