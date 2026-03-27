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
   - Source: `Deploy from a branch`
   - Branch: `cursor/apl-trifurcated-funnel-dashboard-d2ff`
   - Folder: `/docs`
3. Share the Pages URL:
   - `https://<org-or-user>.github.io/<repo>/`

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