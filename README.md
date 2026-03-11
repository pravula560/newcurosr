# Walkback SMS Dashboard Assets

This repository includes the dashboard query and build spec for the APL Walkback SMS experiment.

- Query: `sql/v_apl_walkback_sms_dashboard.sql`
- Dashboard spec: `docs/walkback_sms_dashboard_spec.md`
- Visualization/analysis SQL pack: `sql/walkback_sms_visualization_analysis.sql`
- Visualization playbook: `docs/walkback_sms_visualization_analysis_playbook.md`
- Standalone HTML dashboard: `dashboard/walkback_sms_test_control_dashboard.html`

## Live BigQuery mode in HTML dashboard

The HTML dashboard can query the provided view directly:

- View: `ffam-data-platform-loan-ops.report_views.v_apl_walkback_sms`
- File: `dashboard/walkback_sms_test_control_dashboard.html`

To use live mode:

1. Open the HTML file in a browser.
2. Enter your OAuth client ID (project/location default to the provided view project).
3. Click **Load from Provided View** (or it auto-loads if OAuth client ID is already saved).

OAuth scope used by the page:

- `https://www.googleapis.com/auth/bigquery`
- `https://www.googleapis.com/auth/cloud-platform`