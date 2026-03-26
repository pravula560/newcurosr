#!/usr/bin/env bash
set -euo pipefail

# Deploy dashboard bundle to a GCS path for static hosting.
#
# Required:
#   GCS_DEST=gs://your-bucket/path ./deploy_apl_funnel_gcs.sh
#
# Optional:
#   DASHBOARD_FILE=apl_trifurcated_funnel_dashboard.html
#   CSV_FILE=apl_trifurcated_funnel.csv
#   CACHE_CONTROL_HTML="no-cache"
#   CACHE_CONTROL_DATA="no-cache"

GCS_DEST="${GCS_DEST:-}"
DASHBOARD_FILE="${DASHBOARD_FILE:-apl_trifurcated_funnel_dashboard.html}"
CSV_FILE="${CSV_FILE:-apl_trifurcated_funnel.csv}"
CACHE_CONTROL_HTML="${CACHE_CONTROL_HTML:-no-cache}"
CACHE_CONTROL_DATA="${CACHE_CONTROL_DATA:-no-cache}"

if [[ -z "$GCS_DEST" ]]; then
  echo "ERROR: GCS_DEST is required (example: gs://my-bucket/apl-funnel)" >&2
  exit 1
fi

if [[ ! -f "$DASHBOARD_FILE" ]]; then
  echo "ERROR: dashboard file not found: $DASHBOARD_FILE" >&2
  exit 1
fi

if [[ ! -f "$CSV_FILE" ]]; then
  echo "ERROR: CSV file not found: $CSV_FILE" >&2
  exit 1
fi

echo "Deploying dashboard assets to $GCS_DEST"
gsutil -h "Cache-Control:${CACHE_CONTROL_HTML}" cp "$DASHBOARD_FILE" "${GCS_DEST}/index.html"
gsutil -h "Cache-Control:${CACHE_CONTROL_DATA}" cp "$CSV_FILE" "${GCS_DEST}/apl_trifurcated_funnel.csv"

echo "Deployment complete."
