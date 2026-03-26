# APL Trifurcated Funnel Dashboard

This repo contains:

- `sql/apl_trifurcated_funnel_query.sql`: Parameterized BigQuery extract query (Core / Pagaya / Superprime).
- `src/run_apl_trifurcated_funnel.py`: Exports the query result to CSV using BigQuery.
- `dashboard/apl_trifurcated_funnel_dashboard.html`: Self-contained dashboard that loads the CSV and renders funnel views with client-side filters.

## Quickstart

1) Install deps

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Export CSV from BigQuery

```bash
python src/run_apl_trifurcated_funnel.py \
  --product-line CORE --product-line PAGAYA --product-line SUPERPRIME \
  --start-date 2026-01-01 \
  --out apl_trifurcated_funnel.csv
```

Optional:

- `--eligible-only` to apply `flag_eligible_lead = TRUE` server-side (dashboard can also filter client-side).
- `--end-date YYYY-MM-DD` for a closed cohort window, or omit for open cohort.
- `--mtd` sets start/end to month-to-date.

3) Open the dashboard

- Open `dashboard/apl_trifurcated_funnel_dashboard.html` in a browser.
- Choose the exported CSV file when prompted (or drag/drop it onto the page).