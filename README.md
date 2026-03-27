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

## Hosted dashboard (GitHub Pages)

This repo includes a Pages-ready site under `docs/`.

1) In GitHub: **Settings → Pages**
2) **Build and deployment**:
   - Source: **Deploy from a branch**
   - Branch: `main` (or your branch), folder: `/docs`
3) Save, wait for deployment.

Then the hosted dashboard will be available at:

- `https://pravula560.github.io/newcurosr/`

The hosted page loads `docs/apl_trifurcated_funnel.sample.csv` by default. To load your own exported CSV, either:

- Append `?csv=...` (URL-encoded) to the page URL, or
- Paste a CSV URL into the “CSV source” field and click **Load CSV**.