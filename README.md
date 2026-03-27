# APL Trifurcated Funnel Dashboard Extract

This repository contains a BigQuery extract template and a helper script to
generate a fully-rendered SQL query for the APL trifurcated funnel dashboard.

## Files

- `sql/apl_trifurcated_funnel_dashboard_extract.sql`: SQL template with placeholders.
- `run_apl_trifurcated_funnel.py`: CLI helper that injects filter placeholders.

## Usage

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