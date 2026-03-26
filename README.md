# APL trifurcated funnel dashboard

This repo contains:

- `sql/apl_trifurcated_funnel_query.sql`: BigQuery extract (Core / Pagaya / Superprime) with placeholders.
- `scripts/run_apl_trifurcated_funnel.py`: CLI runner that renders the SQL and exports a CSV.
- `dashboard/apl_trifurcated_funnel_dashboard.html`: Static dashboard that loads the CSV and provides client-side filtering (including `flag_eligible_lead only`).

## Export the extract (BigQuery → CSV)

Prereqs:

- Python 3
- BigQuery credentials available via standard Google auth (e.g. `gcloud auth application-default login`)

Install deps:

```bash
python3 -m pip install -r requirements.txt
```

Run the extract:

```bash
python3 scripts/run_apl_trifurcated_funnel.py \
  --product-line CORE --product-line PAGAYA --product-line SUPERPRIME \
  --start-date 2026-03-01 \
  --mtd \
  --out data/apl_trifurcated_funnel.csv
```

Optional server-side eligibility filter (dashboard can also filter client-side):

```bash
python3 scripts/run_apl_trifurcated_funnel.py \
  --product-line CORE --product-line PAGAYA --product-line SUPERPRIME \
  --start-date 2026-03-01 \
  --mtd \
  --eligible-only \
  --out data/apl_trifurcated_funnel_eligible_only.csv
```

## Open the dashboard

Option A: open the HTML file directly and upload the CSV:

- Open `dashboard/apl_trifurcated_funnel_dashboard.html` in a browser
- Click **Load extract CSV** and select the exported `data/*.csv`

Option B: serve locally (recommended if you want `?csv=` auto-load):

```bash
python3 -m http.server 8000
```

Then open:

- `http://localhost:8000/dashboard/apl_trifurcated_funnel_dashboard.html`
- or auto-load a CSV via `?csv=/data/apl_trifurcated_funnel.csv`