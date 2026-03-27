# APL Trifurcated Funnel Dashboard

Interactive Streamlit dashboard for the **Core / Pagaya / Superprime** application funnel, powered by a BigQuery extract from `fplus_application`.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Generate sample data (no BigQuery required)
python generate_sample_data.py

# 3. Launch the dashboard
streamlit run dashboard.py
```

## Project Structure

```
├── dashboard.py                  # Streamlit dashboard (main entry point)
├── run_apl_trifurcated_funnel.py # BigQuery extract CLI
├── generate_sample_data.py       # Sample data generator for demos
├── sql/
│   └── apl_trifurcated_funnel.sql  # Parameterised BigQuery query
├── data/                         # Parquet/CSV output (git-ignored)
├── requirements.txt
└── README.md
```

## BigQuery Extract

`run_apl_trifurcated_funnel.py` renders the parameterised SQL template, executes it against BigQuery, and writes the result to `data/apl_trifurcated_funnel.parquet`.

```bash
# Open cohort from a start date
python run_apl_trifurcated_funnel.py --start-date 2025-01-01

# Month-to-date, eligible leads only
python run_apl_trifurcated_funnel.py --mtd --eligible-only

# Bounded cohort with CSV output
python run_apl_trifurcated_funnel.py --start-date 2025-01-01 --end-date 2025-03-31 --csv

# Specific product lines
python run_apl_trifurcated_funnel.py --start-date 2025-01-01 --product-lines CORE PAGAYA

# Dry run (print SQL without executing)
python run_apl_trifurcated_funnel.py --start-date 2025-01-01 --dry-run
```

### CLI Arguments

| Argument | Description |
|---|---|
| `--start-date` | Cohort start date (`YYYY-MM-DD`). Required unless `--mtd`. |
| `--mtd` | Month-to-date mode (start = 1st of month, end = today). |
| `--end-date` | Optional cohort end date. Omit for open-ended. |
| `--product-lines` | Space-separated list (default: `CORE PAGAYA SUPERPRIME`). |
| `--eligible-only` | SQL-side filter on `flag_eligible_lead = TRUE`. |
| `--csv` | Also write CSV alongside Parquet. |
| `--project` | GCP project ID override. |
| `--dry-run` | Print rendered SQL; skip execution. |

## Dashboard Features

### View 1 — Overall Funnel
- **KPI cards**: Total leads, funded loans, origination dollars, lead-to-funded conversion.
- **Funnel bar chart**: Side-by-side volume by product line at each funnel step.
- **Conversion curve**: Lead-to-step percentage by product line.
- **Origination dollars** and **FICO distribution** charts.
- **FICO-band conversion** curves.
- **Daily trend**: Leads and funded counts over time.

### View 2 — Pagaya Entry Segment Deep-Dive
- Breaks down Pagaya applications by entry segment (**PQ entry**, **FA entry**, **PQ + FA**).
- Segment-level funnel comparison chart.
- Detail table with volume and conversion metrics.

### Sidebar Filters
- **Product line** multi-select.
- **Eligible leads only** checkbox (client-side filter on `flag_eligible_lead`).
- **Cohort date range** picker.
- **FICO band** multi-select.

## SQL Template

The query in `sql/apl_trifurcated_funnel.sql` uses four placeholders:

| Placeholder | Replaced with |
|---|---|
| `__PRODUCT_LINE_IN__` | Comma-separated quoted product-line list |
| `__CREATED_START__` | Start date string |
| `__CREATED_END_SQL__` | `AND DATE(...) <= 'end'` or blank |
| `__FLAG_ELIGIBLE_SQL__` | `AND flag_eligible_lead = TRUE` or blank |

## Validation Rules

- **LOANS** = `COUNT(DISTINCT application_key)` by product line
- **FUNDS** = `COUNT(DISTINCT loan_id) WHERE funding_datetime IS NOT NULL`
- Funded volume and origination dollars use `funding_datetime` (not `funded_date`)
