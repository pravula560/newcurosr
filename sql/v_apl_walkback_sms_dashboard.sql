-- Walkback SMS dashboard dataset query
-- Target view: ffam-data-platform-loan-ops.report_views.v_apl_walkback_sms
-- Dialect: BigQuery Standard SQL
--
-- This query returns daily KPI cuts by:
--   * experiment group (delivery + odd/even parity)
--   * utm channel
--   * utm source
--   * fico band
--   * loan officer
--
-- Default date window is last full month.

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
),

scored AS (
  SELECT
    *,
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
),

dashboard AS (
  SELECT
    fas_day AS day,
    utm_channel,
    utm_source,
    fico_band,
    loan_officer_name,
    delivery_group,
    parity_group,
    COUNT(DISTINCT application_id) AS fas_units,
    COUNT(DISTINCT IF(docs_collected_flag = 1, application_id, NULL)) AS docs_collected_units,
    SAFE_DIVIDE(
      COUNT(DISTINCT IF(docs_collected_flag = 1, application_id, NULL)),
      COUNT(DISTINCT application_id)
    ) AS doc_collection_rate,
    COUNT(DISTINCT IF(take_flag = 1, application_id, NULL)) AS take_units,
    SAFE_DIVIDE(
      COUNT(DISTINCT IF(take_flag = 1, application_id, NULL)),
      COUNT(DISTINCT application_id)
    ) AS take_rate,
    COUNT(DISTINCT IF(funded_flag = 1, application_id, NULL)) AS units_funded,
    SAFE_DIVIDE(
      COUNT(DISTINCT IF(funded_flag = 1, application_id, NULL)),
      COUNT(DISTINCT application_id)
    ) AS conversion_rate,
    SUM(IF(funded_flag = 1, funded_amount, 0)) AS dollars_funded
  FROM scored
  WHERE fas_day >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH)
    AND fas_day < DATE_TRUNC(CURRENT_DATE(), MONTH)
  GROUP BY
    day,
    utm_channel,
    utm_source,
    fico_band,
    loan_officer_name,
    delivery_group,
    parity_group
)

SELECT *
FROM dashboard
ORDER BY day, utm_channel, utm_source, fico_band, loan_officer_name, delivery_group, parity_group;
