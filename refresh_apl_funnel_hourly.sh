#!/usr/bin/env bash
set -euo pipefail

# Refreshes APL trifurcated funnel CSV and compiled SQL.
# Intended to run from cron/hourly scheduler.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

# Override via environment variables when needed.
: "${APL_FUNNEL_START_DATE:=2026-01-01}"
: "${APL_FUNNEL_PRODUCT_LINES:=CORE,PAGAYA,SUPERPRIME}"
: "${APL_FUNNEL_PROJECT:=}"

CMD=(
  python3 run_apl_trifurcated_funnel.py
  --start-date "${APL_FUNNEL_START_DATE}"
  --product-lines "${APL_FUNNEL_PRODUCT_LINES}"
  --output-csv apl_trifurcated_funnel.csv
  --compiled-sql-out apl_trifurcated_funnel_query.compiled.sql
)

if [[ -n "${APL_FUNNEL_PROJECT}" ]]; then
  CMD+=(--project "${APL_FUNNEL_PROJECT}")
fi

"${CMD[@]}"

echo "Refresh complete: apl_trifurcated_funnel.csv"
