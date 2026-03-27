# APL trifurcated funnel dashboard

Streamlit dashboard backed by a BigQuery extract for the APL trifurcated funnel (Core / Pagaya / Superprime).

## Quickstart

Install:

```bash
python -m pip install -U pip
pip install -e ".[dev]"
```

Run the dashboard:

```bash
streamlit run app/main.py
```

Optional: run an extract locally (writes a parquet file you can load in the dashboard):

```bash
python scripts/run_apl_trifurcated_funnel.py --start-date 2026-01-01 --product-line CORE PAGAYA SUPERPRIME --out data/apl_trifurcated_funnel.parquet
```

## Auth (BigQuery)

This app uses `google-cloud-bigquery`. In cloud environments, use Application Default Credentials (ADC) or set `GOOGLE_APPLICATION_CREDENTIALS`.