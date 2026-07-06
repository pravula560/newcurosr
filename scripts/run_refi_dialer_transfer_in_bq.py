#!/usr/bin/env python3
"""
Render the refi dialer agent transfer SQL, validate against BigQuery schema,
dry-run, and optionally execute.

Requires Application Default Credentials, e.g.:
  export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json
  export GCP_PROJECT_ID=ffam-data-platform
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from run_refi_dialer_agent_transfer_report import render_template  # noqa: E402

DEFAULT_PROJECT = "ffam-data-platform"
DATASET = "standardized_data"
HISTORY_TABLE = "fplus_application_history"
DIALER_TABLE = "inin_dialer_history"

HISTORY_TS_CANDIDATES = [
    "record_start_datetime",
    "effective_start_datetime",
    "modified_datetime",
    "last_modified_datetime",
    "updated_datetime",
    "created_datetime",
    "record_end_datetime",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run or execute refi dialer transfer SQL in BigQuery.")
    parser.add_argument("--start-date", default="2026-01-01", help="Inclusive contact start date YYYY-MM-DD.")
    parser.add_argument("--end-date", help="Optional inclusive contact end date YYYY-MM-DD.")
    parser.add_argument("--refi-only", action="store_true", help="Restrict to refinance applications.")
    parser.add_argument("--query", choices=("detail", "summary", "both"), default="detail")
    parser.add_argument("--project", default=os.environ.get("GCP_PROJECT_ID", DEFAULT_PROJECT))
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute query after successful dry run (default: dry run only).",
    )
    parser.add_argument(
        "--output-csv",
        help="When --execute is set, write query results to this CSV path.",
    )
    parser.add_argument(
        "--history-ts-column",
        help="Override history ordering column on fplus_application_history.",
    )
    return parser.parse_args()


def ensure_credentials() -> None:
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return
    raw = os.environ.get("GCP_SA_KEY_JSON")
    if not raw:
        raise RuntimeError(
            "BigQuery credentials not found. Set GOOGLE_APPLICATION_CREDENTIALS or GCP_SA_KEY_JSON."
        )
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        handle.write(raw)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = handle.name


def get_client(project: str):
    from google.cloud import bigquery

    return bigquery.Client(project=project)


def fetch_columns(client, table_name: str) -> set[str]:
    sql = f"""
    SELECT column_name
    FROM `{DEFAULT_PROJECT}.{DATASET}.INFORMATION_SCHEMA.COLUMNS`
    WHERE table_name = '{table_name}'
    """
    return {row.column_name for row in client.query(sql).result()}


def history_ts_expr(column: str) -> str:
    return f"TIMESTAMP(h.{column}, 'America/Phoenix')"


def pick_history_ts_expr(columns: set[str], override: str | None) -> str:
    if override:
        if override not in columns:
            raise RuntimeError(
                f"Requested history column '{override}' not found on {HISTORY_TABLE}. "
                f"Available: {sorted(columns)}"
            )
        return history_ts_expr(override)

    for candidate in HISTORY_TS_CANDIDATES:
        if candidate in columns:
            return history_ts_expr(candidate)

    datetime_cols = sorted(
        name
        for name in columns
        if name.endswith("_datetime") or name.endswith("_timestamp") or name.endswith("_date")
    )
    raise RuntimeError(
        f"No known history timestamp column on {HISTORY_TABLE}. "
        f"Datetime-like columns: {datetime_cols}. "
        f"Pass --history-ts-column explicitly."
    )


def inject_history_ts(sql: str, history_ts_expr: str) -> str:
    return sql.replace("__HISTORY_TS_EXPR__", history_ts_expr)


def render_sql(args: argparse.Namespace, template_name: str) -> str:
    template_path = ROOT / "sql" / template_name
    sql = render_template(template_path, args.start_date, args.end_date, args.refi_only)
    return sql


def dry_run(client, sql: str) -> None:
    job_config = client._default_query_job_config()
    from google.cloud import bigquery

    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    job = client.query(sql, job_config=job_config)
    print(
        f"Dry run OK. Estimated bytes processed: {job.total_bytes_processed:,} "
        f"({job.total_bytes_processed / (1024 ** 3):.2f} GB)"
    )


def execute_to_csv(client, sql: str, output_csv: Path) -> int:
    rows = client.query(sql).result()
    import csv

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = None
        count = 0
        for row in rows:
            row_dict = dict(row.items())
            if writer is None:
                writer = csv.DictWriter(handle, fieldnames=list(row_dict.keys()))
                writer.writeheader()
            writer.writerow(row_dict)
            count += 1
    print(f"Wrote {count} rows to {output_csv}")
    return count


def main() -> int:
    args = parse_args()
    ensure_credentials()
    client = get_client(args.project)

    history_columns = fetch_columns(client, HISTORY_TABLE)
    dialer_columns = fetch_columns(client, DIALER_TABLE)
    print(f"{HISTORY_TABLE} columns ({len(history_columns)}): "
          f"{', '.join(sorted(history_columns)[:12])}{'...' if len(history_columns) > 12 else ''}")
    print(f"{DIALER_TABLE} has call_placed_datetime: {'call_placed_datetime' in dialer_columns}")
    print(f"{DIALER_TABLE} has contacted: {'contacted' in dialer_columns}")

    history_ts = pick_history_ts_expr(history_columns, args.history_ts_column)
    print(f"Using history timestamp expression: {history_ts}")

    templates = []
    if args.query in ("detail", "both"):
        templates.append(("refi_dialer_agent_transfer_report.sql", "dist/refi_dialer_agent_transfer_report.generated.sql"))
    if args.query in ("summary", "both"):
        templates.append(("refi_dialer_agent_transfer_summary.sql", "dist/refi_dialer_agent_transfer_summary.generated.sql"))

    for template_file, output_file in templates:
        sql = inject_history_ts(render_sql(args, template_file), history_ts)
        out_path = ROOT / output_file
        out_path.write_text(sql, encoding="utf-8")
        print(f"\n=== {template_file} ===")
        print(f"Rendered: {out_path}")
        try:
            dry_run(client, sql)
        except Exception as exc:
            print(f"Dry run failed: {exc}", file=sys.stderr)
            return 1

        if args.execute:
            if not args.output_csv and args.query == "both":
                print("Skipping execute for batch mode without distinct output paths.", file=sys.stderr)
                continue
            csv_path = Path(args.output_csv or f"dist/{Path(template_file).stem}.csv")
            execute_to_csv(client, sql, csv_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
