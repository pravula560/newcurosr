# APL Walkback SMS Dashboard Spec

## Data source

- Primary source query: `sql/v_apl_walkback_sms_dashboard.sql`
- View referenced in query: `ffam-data-platform-loan-ops.report_views.v_apl_walkback_sms`
- Default date scope: last full month (change in SQL `WHERE` clause if needed)

## Inclusion logic

Applications are included only when they satisfy all of the following:

1. Stage/status is `Full App Submitted` / `In Process`
2. Stage duration is at least 24 hours using app history start/end (end date coalesced to `CURRENT_TIMESTAMP()` if still open)
3. General application status is `active`
4. `utm_source` does not contain:
   - `refi`
   - `ula`
   - `mptestutm`
   - `reload`
   - `achieve_bankrate_ahl`
5. State is not `IA` or `WA`

## Test and control classification

- `delivery_group`
  - `test`: app received at least one SMS where `template_name LIKE '%walkback%'`
  - `control`: app did not receive walkback SMS
- `parity_group`
  - `test_odd` for odd app number
  - `control_even` for even app number

Both fields are exposed so you can monitor both assignment parity and actual delivery.

## KPI definitions

- `fas_units`: distinct eligible applications
- `docs_collected_units`: distinct apps with `fullapp_docs_for_uw_received_datetime` present
- `doc_collection_rate`: `docs_collected_units / fas_units`
- `take_units`: distinct apps with `offer_accepted_datetime` present
- `take_rate`: `take_units / fas_units`
- `units_funded`: distinct apps with `funded_datetime` present
- `conversion_rate`: `units_funded / fas_units`
- `dollars_funded`: sum of funded amount for funded apps

## Required cuts (dimensions)

- Day (`day`)
- UTM Channel (`utm_channel`)
- UTM Source (`utm_source`)
- FICO Band (`fico_band`)
- Loan Officer (`loan_officer_name`)
- Grouping:
  - `delivery_group`
  - `parity_group`

## Suggested dashboard layout (Tableau)

1. **Top KPI tiles**
   - Doc Collection Rate
   - Take Rate
   - Conversion Rate
   - Units Funded
   - $ Funded
2. **Trend chart**
   - X-axis: Day
   - Y-axis: Doc Collection Rate
   - Color: Delivery Group
3. **Group comparison table**
   - Rows: Delivery Group
   - Columns: FAS, Docs Collected, Doc Collection Rate, Take Rate, Conversion Rate, Units Funded, $ Funded
4. **Breakout heatmap or table**
   - Rows: UTM Channel > UTM Source
   - Columns: Delivery Group
   - Measure: Doc Collection Rate (default), toggle to other KPIs
5. **Loan Officer performance table**
   - Rows: Loan Officer
   - Columns: same KPI set, split by Delivery Group

## Global filters

- Date (`day`)
- UTM Channel
- UTM Source
- FICO Band
- Loan Officer
- Delivery Group
- Parity Group

## Validation checks before launch

1. Confirm eligible app counts by day are non-zero beginning Wednesday/Thursday after launch.
2. Confirm walkback template hits are present and tagged as `delivery_group = test`.
3. Compare odd/even split to ensure holdout remains close to intended allocation.
4. Spot-check 10 records for doc collection and funded flag correctness.
