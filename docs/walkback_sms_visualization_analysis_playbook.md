# Walkback SMS Visualizations and Analysis Playbook

## Files

- Analysis SQL pack: `sql/walkback_sms_visualization_analysis.sql`
- Base dashboard dataset: `sql/v_apl_walkback_sms_dashboard.sql`

## How to run

1. Open `sql/walkback_sms_visualization_analysis.sql` in BigQuery.
2. Keep script mode enabled (multiple result sets).
3. Set `start_date`, `end_date`, and `min_loan_officer_fas` at the top.
4. Run the script and use each result set for the corresponding visualization below.

---

## Visualization set

### 1) Daily KPI trend (Result Set #1)

- Chart type: line chart
- X-axis: `day`
- Y-axis: `doc_collection_rate` (primary), optional dual-axis with `conversion_rate`
- Color: `delivery_group`
- Tooltip: `fas_units`, `take_rate`, `units_funded`, `dollars_funded`

**Purpose:** Detect day-over-day lift and identify when effect begins after go-live.

---

### 2) Headline scorecard (Result Set #2)

- Chart type: KPI table or big-number tiles
- Row group: `delivery_group`
- Metrics:
  - `fas_units`
  - `doc_collection_rate` (primary)
  - `take_rate`
  - `conversion_rate`
  - `dollars_funded`

**Purpose:** Test vs control headline comparison.

---

### 3) Lift summary (Result Set #3)

- Chart type: compact summary table
- Metrics:
  - `doc_collection_lift_pp`
  - `take_rate_lift_pp`
  - `conversion_rate_lift_pp`
  - relative lift fields

**Purpose:** One-place view of absolute and relative test lift.

---

### 4) UTM channel performance (Result Set #4)

- Chart type: grouped bar chart
- X-axis: `utm_channel`
- Y-axis: `doc_collection_rate`
- Color: `delivery_group`
- Secondary chart option: heatmap for `conversion_rate`

**Purpose:** See where SMS performs best by acquisition channel.

---

### 5) UTM source detail (Result Set #5)

- Chart type: sortable table
- Hierarchy: `utm_channel` > `utm_source`
- Split: `delivery_group`
- Metrics: all KPI rates + `$ funded`

**Purpose:** Pinpoint strong and weak sources inside each channel.

---

### 6) FICO band cut (Result Set #6)

- Chart type: grouped bar chart or matrix
- X-axis: `fico_band`
- Y-axis: `doc_collection_rate` (default)
- Color: `delivery_group`

**Purpose:** Identify whether effect varies by credit quality band.

---

### 7) Loan officer scorecard (Result Set #7)

- Chart type: table with conditional formatting
- Rows: `loan_officer_name`
- Split: `delivery_group`
- Filters: minimum volume threshold (`min_loan_officer_fas`)

**Purpose:** Compare outcomes while controlling for low-volume noise.

---

### 8) Parity QA matrix (Result Set #8)

- Chart type: 2x2 matrix / table
- Rows: `parity_group`
- Columns: `delivery_group`
- Measures: `fas_units`, `doc_collection_rate`, `conversion_rate`

**Purpose:** Validate odd/even assignment behavior and delivery alignment.

---

### 9) SMS timing analysis (Result Set #9)

- Chart type: bar chart
- X-axis: `sms_delay_bucket`
- Y-axis: `doc_collection_rate` (default)
- Optional labels: `take_rate`, `conversion_rate`

**Purpose:** Determine whether send timing affects downstream performance.

---

## Suggested dashboard tabs

1. **Executive**: Result Sets #2 and #3 with quick trend from #1
2. **Performance Over Time**: Result Set #1
3. **Channel & Source**: Result Sets #4 and #5
4. **Risk/Quality Segments**: Result Set #6
5. **Sales Ops View**: Result Set #7
6. **Experiment QA**: Result Sets #8 and #9

## Analysis checklist

- Confirm test/control sample sizes are sufficient (`fas_units`).
- Use doc collection rate as the primary KPI for all segment reads.
- Treat tiny segment cells cautiously (small denominators).
- Track conversion and dollars funded as lagging outcomes.
- Use parity QA weekly to ensure assignment remains stable.

## Recommended narrative structure (weekly readout)

1. **Topline:** test vs control doc collection lift (pp and relative).
2. **Where lift comes from:** top channels/sources and FICO bands.
3. **Operational signal:** LO-level variance and timing insights.
4. **Guardrails:** parity balance, delivery coverage, sample size risks.
