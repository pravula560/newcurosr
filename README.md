# APL Trifurcated Funnel Dashboard

Interactive dashboard for the **Core / Pagaya / Superprime** application-to-funding funnel.

## Components

| File | Purpose |
|---|---|
| `apl_trifurcated_funnel_query.sql` | BigQuery extract with placeholder filters |
| `run_apl_trifurcated_funnel.py` | Python CLI to run the query and produce a CSV |
| `apl_trifurcated_funnel_dashboard.html` | Self-contained HTML/JS dashboard (load CSV client-side) |
| `deploy_apl_funnel_gcs.sh` | Upload dashboard + CSV to GCS for hosting |
| `refresh_apl_funnel_hourly.sh` | Cron wrapper for hourly/daily refresh |

## Quick Start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Run the BigQuery extract (month-to-date example)
python run_apl_trifurcated_funnel.py --mtd

# 3. Open the dashboard in a browser and load the CSV
open apl_trifurcated_funnel_dashboard.html
```

## Python CLI Options

```
python run_apl_trifurcated_funnel.py --start-date 2025-01-01            # open cohort
python run_apl_trifurcated_funnel.py --mtd                               # month-to-date
python run_apl_trifurcated_funnel.py --start-date 2025-01-01 --end-date 2025-03-31
python run_apl_trifurcated_funnel.py --mtd --eligible-only               # server-side filter
python run_apl_trifurcated_funnel.py --mtd --dry-run                     # print SQL, don't run
```

## Dashboard Views

1. **Overview** — KPI cards, funnel table by product line, conversion line chart, volume bar chart
2. **Pagaya Segments** — PQ entry / FA entry / PQ+FA breakdown with funnel and doughnut charts
3. **FICO Analysis** — Funnel by FICO band × product line, approval rate and volume charts
4. **Trends** — Daily lead volume, daily funded dollars, cumulative originations, daily approval rate

### Client-side Filters

- **flag_eligible_lead only** checkbox — filters to eligible leads without re-running the query
- **FICO Band** dropdown
- **Product Line** dropdown

## Deployment

```bash
# Upload to GCS (regenerates CSV first)
./deploy_apl_funnel_gcs.sh --mtd

# Custom bucket
./deploy_apl_funnel_gcs.sh --mtd -b my-bucket -p dashboards/apl-funnel
```

## Scheduling

```bash
# Hourly cron (month-to-date)
0 * * * * /path/to/refresh_apl_funnel_hourly.sh >> /var/log/apl_funnel.log 2>&1

# Custom date range
START_DATE=2025-01-01 END_DATE=2025-06-30 /path/to/refresh_apl_funnel_hourly.sh
```
