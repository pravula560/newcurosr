# APL Trifurcated Funnel Dashboard

This repository contains a lightweight BigQuery-to-CSV extraction flow and a static
dashboard for the APL trifurcated funnel (Core / Pagaya / Superprime).

## Files

- `apl_trifurcated_funnel_query.sql`  
  SQL template with placeholders:
  - `__PRODUCT_LINE_IN__`
  - `__CREATED_START__`
  - `__CREATED_END_SQL__`
  - `__FLAG_ELIGIBLE_SQL__`
- `run_apl_trifurcated_funnel.py`  
  Renders SQL placeholders and runs BigQuery via `bq query --format=csv`.
- `apl_trifurcated_funnel_dashboard.html`  
  Static dashboard that reads `apl_trifurcated_funnel.csv` from the same directory.
- `refresh_apl_funnel_hourly.sh`  
  Example refresh script for cron/Cloud Scheduler hosts.
- `deploy_apl_funnel_gcs.sh`  
  Upload dashboard artifacts to GCS static hosting.

## 1) Extract CSV from BigQuery

Prerequisites:
- Google Cloud SDK with `bq` authenticated
- Access to `ffam-data-platform.standardized_data.fplus_application`

Examples:

```bash
# Open cohort from Jan 1 onward (all eligibility values)
python3 run_apl_trifurcated_funnel.py \
  --start-date 2026-01-01 \
  --output-csv apl_trifurcated_funnel.csv

# Month-to-date with SQL-side eligibility filter
python3 run_apl_trifurcated_funnel.py \
  --mtd \
  --eligible-only \
  --output-csv apl_trifurcated_funnel.csv
```

Useful flags:
- `--end-date YYYY-MM-DD` for an inclusive upper bound
- `--product-lines CORE,PAGAYA,SUPERPRIME`
- `--project <GCP_PROJECT>`
- `--dry-run` to render/inspect SQL without querying

## 2) Run the dashboard

The dashboard fetches `apl_trifurcated_funnel.csv` using browser `fetch()`, so serve
files over HTTP (not `file://`).

```bash
python3 -m http.server 8000
```

Then open:

`http://localhost:8000/apl_trifurcated_funnel_dashboard.html`

## 3) Deploy static assets to GCS

```bash
./deploy_apl_funnel_gcs.sh <GCS_BUCKET>
```

Example:

```bash
./deploy_apl_funnel_gcs.sh gs://my-funnel-dashboard
```