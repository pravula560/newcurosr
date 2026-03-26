#!/usr/bin/env bash
# deploy_apl_funnel_gcs.sh — Upload dashboard + CSV to a GCS bucket for hosting.
#
# Usage:
#   ./deploy_apl_funnel_gcs.sh                         # defaults
#   ./deploy_apl_funnel_gcs.sh -b my-bucket -p prefix  # custom bucket / prefix
#   ./deploy_apl_funnel_gcs.sh --start-date 2025-01-01 # regenerate CSV first
#
# Prerequisites:
#   - gcloud CLI authenticated with appropriate permissions
#   - python3 + google-cloud-bigquery (if --start-date is used)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Defaults
BUCKET="${GCS_BUCKET:-ffam-dashboards}"
PREFIX="apl-trifurcated-funnel"
START_DATE=""
END_DATE=""
ELIGIBLE_ONLY=""
MTD=""

usage() {
  echo "Usage: $0 [-b BUCKET] [-p PREFIX] [--start-date DATE] [--end-date DATE] [--mtd] [--eligible-only]"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -b|--bucket)  BUCKET="$2"; shift 2 ;;
    -p|--prefix)  PREFIX="$2"; shift 2 ;;
    --start-date) START_DATE="$2"; shift 2 ;;
    --end-date)   END_DATE="$2"; shift 2 ;;
    --mtd)        MTD="--mtd"; shift ;;
    --eligible-only) ELIGIBLE_ONLY="--eligible-only"; shift ;;
    -h|--help)    usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

CSV_FILE="${SCRIPT_DIR}/apl_trifurcated_funnel.csv"
HTML_FILE="${SCRIPT_DIR}/apl_trifurcated_funnel_dashboard.html"

# Regenerate CSV if start-date or --mtd supplied
if [[ -n "$START_DATE" || -n "$MTD" ]]; then
  echo "[deploy] Regenerating CSV via run_apl_trifurcated_funnel.py …"
  ARGS=()
  if [[ -n "$MTD" ]]; then
    ARGS+=("$MTD")
  else
    ARGS+=("--start-date" "$START_DATE")
  fi
  [[ -n "$END_DATE" ]] && ARGS+=("--end-date" "$END_DATE")
  [[ -n "$ELIGIBLE_ONLY" ]] && ARGS+=("$ELIGIBLE_ONLY")
  python3 "${SCRIPT_DIR}/run_apl_trifurcated_funnel.py" "${ARGS[@]}"
fi

if [[ ! -f "$CSV_FILE" ]]; then
  echo "[deploy] ERROR: CSV not found at ${CSV_FILE}. Run the Python extract first or pass --start-date."
  exit 1
fi

DEST="gs://${BUCKET}/${PREFIX}"
echo "[deploy] Uploading to ${DEST}/ …"

gsutil -m cp \
  -h "Cache-Control:no-cache, max-age=0" \
  "$HTML_FILE" "${DEST}/index.html"

gsutil -m cp \
  -h "Cache-Control:no-cache, max-age=0" \
  -h "Content-Type:text/csv" \
  "$CSV_FILE" "${DEST}/apl_trifurcated_funnel.csv"

echo "[deploy] Done. Dashboard URL:"
echo "  https://storage.googleapis.com/${BUCKET}/${PREFIX}/index.html"
