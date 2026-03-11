-- Walkback SMS visualization + analysis query pack
-- Dialect: BigQuery Standard SQL (script mode)
--
-- Usage:
-- 1) Run the full script.
-- 2) Each SELECT emits a result set for a visualization/table.
-- 3) Override start_date/end_date for custom windows.

DECLARE start_date DATE DEFAULT DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH);
DECLARE end_date DATE DEFAULT DATE_TRUNC(CURRENT_DATE(), MONTH);
DECLARE min_loan_officer_fas INT64 DEFAULT 10;

CREATE TEMP TABLE walkback_base AS
WITH source_data AS (
  SELECT
    application_id,
    application_number,
    full_app_submitted_datetime,
    DATE(full_app_submitted_datetime) AS fas_day,
    app_stage_name,
    app_stage_status,
    app_general_status,
    app_history_start_datetime,
    COALESCE(app_history_end_datetime, CURRENT_TIMESTAMP()) AS app_history_end_datetime,
    state,
    LOWER(COALESCE(utm_source, '')) AS utm_source,
    COALESCE(utm_channel, 'Unknown') AS utm_channel,
    COALESCE(fico_band, 'Unknown') AS fico_band,
    COALESCE(loan_officer_name, 'Unassigned') AS loan_officer_name,
    template_name,
    sms_sent_datetime,
    fullapp_docs_for_uw_received_datetime,
    offer_accepted_datetime,
    funded_datetime,
    COALESCE(funded_amount, 0) AS funded_amount
  FROM `ffam-data-platform-loan-ops.report_views.v_apl_walkback_sms`
),
eligible_apps AS (
  SELECT DISTINCT
    application_id
  FROM source_data
  WHERE app_stage_name = 'Full App Submitted'
    AND app_stage_status = 'In Process'
    AND LOWER(COALESCE(app_general_status, '')) = 'active'
    AND TIMESTAMP_DIFF(app_history_end_datetime, app_history_start_datetime, HOUR) >= 24
    AND state NOT IN ('IA', 'WA')
    AND NOT REGEXP_CONTAINS(
      utm_source,
      r'(refi|ula|mptestutm|reload|achieve_bankrate_ahl)'
    )
),
app_level AS (
  SELECT
    s.application_id,
    ANY_VALUE(s.application_number) AS application_number,
    ANY_VALUE(s.full_app_submitted_datetime) AS full_app_submitted_datetime,
    ANY_VALUE(s.fas_day) AS fas_day,
    ANY_VALUE(s.utm_channel) AS utm_channel,
    ANY_VALUE(s.utm_source) AS utm_source,
    ANY_VALUE(s.fico_band) AS fico_band,
    ANY_VALUE(s.loan_officer_name) AS loan_officer_name,
    MAX(CASE WHEN LOWER(COALESCE(s.template_name, '')) LIKE '%walkback%' THEN 1 ELSE 0 END) AS received_walkback_sms,
    MIN(CASE WHEN LOWER(COALESCE(s.template_name, '')) LIKE '%walkback%' THEN s.sms_sent_datetime END) AS first_walkback_sms_at,
    MAX(CASE WHEN s.fullapp_docs_for_uw_received_datetime IS NOT NULL THEN 1 ELSE 0 END) AS docs_collected_flag,
    MAX(CASE WHEN s.offer_accepted_datetime IS NOT NULL THEN 1 ELSE 0 END) AS take_flag,
    MAX(CASE WHEN s.funded_datetime IS NOT NULL THEN 1 ELSE 0 END) AS funded_flag,
    MAX(CASE WHEN s.funded_datetime IS NOT NULL THEN s.funded_amount ELSE 0 END) AS funded_amount
  FROM source_data s
  INNER JOIN eligible_apps e
    ON s.application_id = e.application_id
  GROUP BY s.application_id
)
SELECT
  application_id,
  application_number,
  full_app_submitted_datetime,
  fas_day,
  utm_channel,
  utm_source,
  fico_band,
  loan_officer_name,
  first_walkback_sms_at,
  docs_collected_flag,
  take_flag,
  funded_flag,
  funded_amount,
  CASE
    WHEN MOD(SAFE_CAST(REGEXP_EXTRACT(CAST(application_number AS STRING), r'(\d+)$') AS INT64), 2) = 1
      THEN 'test_odd'
    ELSE 'control_even'
  END AS parity_group,
  CASE
    WHEN received_walkback_sms = 1 THEN 'test'
    ELSE 'control'
  END AS delivery_group
FROM app_level
WHERE fas_day >= start_date
  AND fas_day < end_date;

-- 1) Daily trend for KPI lines (primary chart)
SELECT
  fas_day AS day,
  delivery_group,
  COUNT(*) AS fas_units,
  SUM(docs_collected_flag) AS docs_collected_units,
  SAFE_DIVIDE(SUM(docs_collected_flag), COUNT(*)) AS doc_collection_rate,
  SUM(take_flag) AS take_units,
  SAFE_DIVIDE(SUM(take_flag), COUNT(*)) AS take_rate,
  SUM(funded_flag) AS units_funded,
  SAFE_DIVIDE(SUM(funded_flag), COUNT(*)) AS conversion_rate,
  SUM(IF(funded_flag = 1, funded_amount, 0)) AS dollars_funded
FROM walkback_base
GROUP BY day, delivery_group
ORDER BY day, delivery_group;

-- 2) Overall test/control KPI table (headline scorecard)
SELECT
  delivery_group,
  COUNT(*) AS fas_units,
  SUM(docs_collected_flag) AS docs_collected_units,
  SAFE_DIVIDE(SUM(docs_collected_flag), COUNT(*)) AS doc_collection_rate,
  SUM(take_flag) AS take_units,
  SAFE_DIVIDE(SUM(take_flag), COUNT(*)) AS take_rate,
  SUM(funded_flag) AS units_funded,
  SAFE_DIVIDE(SUM(funded_flag), COUNT(*)) AS conversion_rate,
  SUM(IF(funded_flag = 1, funded_amount, 0)) AS dollars_funded
FROM walkback_base
GROUP BY delivery_group
ORDER BY delivery_group;

-- 3) Absolute/relative lift summary (test minus control)
WITH agg AS (
  SELECT
    delivery_group,
    COUNT(*) AS fas_units,
    SAFE_DIVIDE(SUM(docs_collected_flag), COUNT(*)) AS doc_collection_rate,
    SAFE_DIVIDE(SUM(take_flag), COUNT(*)) AS take_rate,
    SAFE_DIVIDE(SUM(funded_flag), COUNT(*)) AS conversion_rate
  FROM walkback_base
  GROUP BY delivery_group
),
test AS (
  SELECT * FROM agg WHERE delivery_group = 'test'
),
control AS (
  SELECT * FROM agg WHERE delivery_group = 'control'
)
SELECT
  test.fas_units AS test_fas_units,
  control.fas_units AS control_fas_units,
  test.doc_collection_rate AS test_doc_collection_rate,
  control.doc_collection_rate AS control_doc_collection_rate,
  100 * (test.doc_collection_rate - control.doc_collection_rate) AS doc_collection_lift_pp,
  SAFE_DIVIDE(test.doc_collection_rate - control.doc_collection_rate, control.doc_collection_rate) AS doc_collection_relative_lift,
  test.take_rate AS test_take_rate,
  control.take_rate AS control_take_rate,
  100 * (test.take_rate - control.take_rate) AS take_rate_lift_pp,
  SAFE_DIVIDE(test.take_rate - control.take_rate, control.take_rate) AS take_rate_relative_lift,
  test.conversion_rate AS test_conversion_rate,
  control.conversion_rate AS control_conversion_rate,
  100 * (test.conversion_rate - control.conversion_rate) AS conversion_rate_lift_pp,
  SAFE_DIVIDE(test.conversion_rate - control.conversion_rate, control.conversion_rate) AS conversion_rate_relative_lift
FROM test
CROSS JOIN control;

-- 4) UTM channel cut (stacked bar / heatmap source)
SELECT
  utm_channel,
  delivery_group,
  COUNT(*) AS fas_units,
  SAFE_DIVIDE(SUM(docs_collected_flag), COUNT(*)) AS doc_collection_rate,
  SAFE_DIVIDE(SUM(take_flag), COUNT(*)) AS take_rate,
  SAFE_DIVIDE(SUM(funded_flag), COUNT(*)) AS conversion_rate,
  SUM(IF(funded_flag = 1, funded_amount, 0)) AS dollars_funded
FROM walkback_base
GROUP BY utm_channel, delivery_group
ORDER BY utm_channel, delivery_group;

-- 5) UTM source cut (detail table)
SELECT
  utm_channel,
  utm_source,
  delivery_group,
  COUNT(*) AS fas_units,
  SAFE_DIVIDE(SUM(docs_collected_flag), COUNT(*)) AS doc_collection_rate,
  SAFE_DIVIDE(SUM(take_flag), COUNT(*)) AS take_rate,
  SAFE_DIVIDE(SUM(funded_flag), COUNT(*)) AS conversion_rate,
  SUM(IF(funded_flag = 1, funded_amount, 0)) AS dollars_funded
FROM walkback_base
GROUP BY utm_channel, utm_source, delivery_group
ORDER BY utm_channel, utm_source, delivery_group;

-- 6) FICO band performance cut
SELECT
  fico_band,
  delivery_group,
  COUNT(*) AS fas_units,
  SAFE_DIVIDE(SUM(docs_collected_flag), COUNT(*)) AS doc_collection_rate,
  SAFE_DIVIDE(SUM(take_flag), COUNT(*)) AS take_rate,
  SAFE_DIVIDE(SUM(funded_flag), COUNT(*)) AS conversion_rate,
  SUM(IF(funded_flag = 1, funded_amount, 0)) AS dollars_funded
FROM walkback_base
GROUP BY fico_band, delivery_group
ORDER BY fico_band, delivery_group;

-- 7) Loan officer scorecard (filtered by minimum FAS volume)
WITH lo AS (
  SELECT
    loan_officer_name,
    delivery_group,
    COUNT(*) AS fas_units,
    SAFE_DIVIDE(SUM(docs_collected_flag), COUNT(*)) AS doc_collection_rate,
    SAFE_DIVIDE(SUM(take_flag), COUNT(*)) AS take_rate,
    SAFE_DIVIDE(SUM(funded_flag), COUNT(*)) AS conversion_rate,
    SUM(IF(funded_flag = 1, funded_amount, 0)) AS dollars_funded
  FROM walkback_base
  GROUP BY loan_officer_name, delivery_group
)
SELECT
  loan_officer_name,
  delivery_group,
  fas_units,
  doc_collection_rate,
  take_rate,
  conversion_rate,
  dollars_funded
FROM lo
WHERE fas_units >= min_loan_officer_fas
ORDER BY loan_officer_name, delivery_group;

-- 8) Parity QA matrix (assignment guardrail monitoring)
SELECT
  parity_group,
  delivery_group,
  COUNT(*) AS fas_units,
  SAFE_DIVIDE(SUM(docs_collected_flag), COUNT(*)) AS doc_collection_rate,
  SAFE_DIVIDE(SUM(funded_flag), COUNT(*)) AS conversion_rate
FROM walkback_base
GROUP BY parity_group, delivery_group
ORDER BY parity_group, delivery_group;

-- 9) SMS timing analysis (test only)
SELECT
  CASE
    WHEN first_walkback_sms_at IS NULL THEN 'No SMS'
    WHEN TIMESTAMP_DIFF(first_walkback_sms_at, full_app_submitted_datetime, HOUR) < 24 THEN '<24h'
    WHEN TIMESTAMP_DIFF(first_walkback_sms_at, full_app_submitted_datetime, HOUR) BETWEEN 24 AND 47 THEN '24-47h'
    WHEN TIMESTAMP_DIFF(first_walkback_sms_at, full_app_submitted_datetime, HOUR) BETWEEN 48 AND 71 THEN '48-71h'
    ELSE '72h+'
  END AS sms_delay_bucket,
  COUNT(*) AS fas_units,
  SAFE_DIVIDE(SUM(docs_collected_flag), COUNT(*)) AS doc_collection_rate,
  SAFE_DIVIDE(SUM(take_flag), COUNT(*)) AS take_rate,
  SAFE_DIVIDE(SUM(funded_flag), COUNT(*)) AS conversion_rate
FROM walkback_base
WHERE delivery_group = 'test'
GROUP BY sms_delay_bucket
ORDER BY
  CASE sms_delay_bucket
    WHEN '<24h' THEN 1
    WHEN '24-47h' THEN 2
    WHEN '48-71h' THEN 3
    WHEN '72h+' THEN 4
    ELSE 5
  END;
