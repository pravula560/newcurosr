#!/usr/bin/env bash
# refresh_apl_funnel_hourly.sh — Cron-friendly wrapper to refresh the APL funnel CSV.
#
# Intended for hourly or daily scheduling, e.g.:
#   0 * * * * /path/to/refresh_apl_funnel_hourly.sh >> /var/log/apl_funnel_refresh.log 2>&1
#
# By default runs --mtd (month-to-date). Override with START_DATE env var.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

echo "${LOG_PREFIX} Starting APL trifurcated funnel refresh"

ARGS=()
if [[ -n "${START_DATE:-}" ]]; then
  ARGS+=("--start-date" "$START_DATE")
  [[ -n "${END_DATE:-}" ]] && ARGS+=("--end-date" "$END_DATE")
else
  ARGS+=("--mtd")
fi

python3 "${SCRIPT_DIR}/run_apl_trifurcated_funnel.py" "${ARGS[@]}"

echo "${LOG_PREFIX} Refresh complete"
