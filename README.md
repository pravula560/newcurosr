# APL Trifurcated Funnel Dashboard Extract

This repository contains a BigQuery extract template and a helper script to
generate a fully-rendered SQL query for the APL trifurcated funnel dashboard.

## Files

- `sql/apl_trifurcated_funnel_dashboard_extract.sql`: SQL template with placeholders.
- `run_apl_trifurcated_funnel.py`: CLI helper that injects filter placeholders.

## Usage

## Dashboard (local)

This repo also includes a small local dashboard that reads the extract output
(exported from BigQuery) and computes funnel metrics client-side.

1) Run the extract SQL in BigQuery and export results to a local file (CSV or Parquet).

2) Start the dashboard:

```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

streamlit run dashboard_app.py -- \
  --data /path/to/apl_trifurcated_funnel_extract.csv
```

The dashboard supports filters for product line, eligibility, FICO band, Pagaya entry segment,
and a cohort date range (based on `created_datetime`).

## Shareable HTML dashboard (manager access)

This repo includes a static dashboard at `docs/index.html` that runs fully in the browser.
It does not require Python or Streamlit to view.

Use it by uploading an extract CSV in the page (export from BigQuery).

To share externally:

1. Push this branch to GitHub.
2. In repository settings, enable GitHub Pages:
   - Source: `GitHub Actions`
3. The included workflow (`.github/workflows/pages.yml`) will deploy `docs/` on push.
4. Share the Pages URL:
   - `https://<org-or-user>.github.io/<repo>/`

## Automatic data refresh (with credentials)

You can fully automate dashboard data refresh into `docs/data/latest.csv` using GitHub Actions.

### 1) Add GitHub repository secrets

In `Settings -> Secrets and variables -> Actions`, add:

- `GCP_SA_KEY_JSON`: full JSON of a BigQuery service-account key
- `BQ_PROJECT_ID`: GCP project ID (example: `ffam-data-platform`)

The service account needs at least:

- BigQuery Job User (`roles/bigquery.jobUser`)
- BigQuery Data Viewer (`roles/bigquery.dataViewer`) on the dataset/table queried

### 2) Run the refresh workflow

Use workflow: `.github/workflows/refresh-dashboard-data.yml`

- Scheduled daily (`cron`)
- Supports manual run (`workflow_dispatch`) with inputs:
  - `start_date` (YYYY-MM-DD)
  - `end_date` (optional YYYY-MM-DD)
  - `eligible_only` (true/false)
  - `mtd` (true/false)

It will:

1. Render SQL from `sql/apl_trifurcated_funnel_dashboard_extract.sql`
2. Execute query in BigQuery
3. Write results to `docs/data/latest.csv`
4. Commit and push to `main`

After push, GitHub Pages redeploys and your manager sees updated data automatically.

Generate SQL for all product lines from an open cohort start date:

```bash
python run_apl_trifurcated_funnel.py \
  --start-date 2026-01-01 \
  --output dist/apl_trifurcated_funnel.sql
```

Filter to only eligible leads:

```bash
python run_apl_trifurcated_funnel.py \
  --start-date 2026-01-01 \
  --eligible-only
```

Apply explicit cohort end date:

```bash
python run_apl_trifurcated_funnel.py \
  --start-date 2026-01-01 \
  --end-date 2026-02-01
```

Use month-to-date upper bound:

```bash
python run_apl_trifurcated_funnel.py \
  --mtd
```

Limit to selected product lines:

```bash
python run_apl_trifurcated_funnel.py \
  --start-date 2026-01-01 \
  --product-line core \
  --product-line pagaya
```

By default the script writes SQL to `dist/apl_trifurcated_funnel_dashboard_extract.generated.sql`.
Use `--stdout` to print to console.

## Daily events channel report (local → dev)

Aggregated daily funnel metrics by `event_date`, `utm_channel`, and `lead_type`
from `fplus_application_daily_events_detail_max`.

### Files

- `sql/fplus_daily_events_channel_report.sql`: SQL template with date placeholders.
- `run_fplus_daily_events_report.py`: CLI helper that injects date filters.
- `scripts/refresh_daily_events_report.py`: Render + BigQuery + write CSV (needs `bq` CLI).

### Step 1 — Render SQL locally

```bash
python run_fplus_daily_events_report.py \
  --start-date 2026-05-01 \
  --output dist/fplus_daily_events_channel_report.generated.sql
```

Optional end date or month-to-date:

```bash
python run_fplus_daily_events_report.py \
  --start-date 2026-05-01 \
  --end-date 2026-06-01

python run_fplus_daily_events_report.py --mtd
```

### Step 2 — Run in BigQuery and export CSV

BigQuery Console: paste `dist/fplus_daily_events_channel_report.generated.sql`, run, save as CSV.

Or with authenticated `bq` CLI:

```bash
bq query \
  --nouse_legacy_sql \
  --format=csv \
  --max_rows=10000000 \
  --output_file=/tmp/daily_events_channel_report.csv \
  "$(cat dist/fplus_daily_events_channel_report.generated.sql)"
```

Validate row counts and totals in the CSV before promoting.

### Step 3 — Test locally

Open the CSV in Excel/Sheets, or load into your own notebook. This report is
aggregated (not row-level applications), so it does not use `dashboard_app.py`.

### Step 4 — Move to dev (shared repo + Pages)

1. Copy refreshed data into the static site folder:

```bash
cp /tmp/daily_events_channel_report.csv docs/data/daily_events_channel_report.csv
```

2. Commit SQL + data on a branch and open a PR to `main`:

```bash
git checkout -b cursor/fplus-daily-events-report-3146
git add sql/fplus_daily_events_channel_report.sql \
  run_fplus_daily_events_report.py \
  scripts/refresh_daily_events_report.py \
  docs/data/daily_events_channel_report.csv
git commit -m "Add daily events channel report extract"
git push -u origin cursor/fplus-daily-events-report-3146
```

3. Merge the PR. GitHub Pages redeploys `docs/` automatically.

4. Share the CSV URL (after deploy):

`https://<org-or-user>.github.io/<repo>/data/daily_events_channel_report.csv`

### Step 5 — Automate refresh (optional)

With `GCP_SA_KEY_JSON` and `BQ_PROJECT_ID` secrets already configured, run locally:

```bash
python scripts/refresh_daily_events_report.py --start-date 2026-05-01
```

Then commit and push `docs/data/daily_events_channel_report.csv` if you want
that file updated on the shared site.