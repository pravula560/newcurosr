-- Refi / FPlus dialer leads: agent transfer summary (losers / gainers / flow matrix).
-- Uses the same CTE pipeline as refi_dialer_agent_transfer_report.sql through contact_transfer_detail.
--
-- Run in BigQuery after validating history timestamp columns (see detail query header).

WITH dialer_campaigns AS (
  SELECT campaign_name
  FROM UNNEST([
    'FFAM FPlus PC Reload',
    'FFAM - FPlus PC Reload',
    'FFAM - FPlus Dialer Reassigned',
    'FFAM - FPlus WalkEmBackWed',
    'FFAM - FPlus Reengagement Dialer',
    'FFAM - FPlus Unable to Contact Dialer',
    'FFAM - FPlus Adverse Action Dialer',
    'FFAM - FPlus PC LOL Dialer',
    'APL - PC Reload Dialer',
    'APL - Dialer Reassigned',
    'APL - WalkEmBackWed Dialer',
    'APL - Reengagement Dialer',
    'APL - Adverse Action Dialer',
    'APL - PC LOL Dialer',
    'APL - PC Reload Dialer',
    'APL - Trying to Contact Dialer',
    'APL - PC Reload',
    'APL - WalkEmBackWed',
    'APL - Dialer Reassigned',
    'APL - Sales Initial Contact',
    'APL - Tally Dialer',
    'APL - Phoenix Team Dialer'
  ]) AS campaign_name
),

dialer_campaign_stats AS (
  WITH dialer_start_end AS (
    WITH dialer_start AS (
      SELECT
        RANK() OVER (
          PARTITION BY campaign_name
          ORDER BY campaign_start_date_time ASC
        ) AS rank,
        campaign_name,
        campaign_start_date_time AS campaign_start_date_time1,
        campaign_end_date_time AS campaign_end_date_time1,
        TIMESTAMP(campaign_start_date_time, 'America/Phoenix') AS campaign_start_date_time,
        TIMESTAMP(campaign_end_date_time, 'America/Phoenix') AS campaign_end_date_time
      FROM `ffn-data-platform.standardized_data.dialer_campaign_stats`
      WHERE DATE(TIMESTAMP(campaign_start_date_time, 'America/Phoenix')) > DATE '2025-01-01'
        AND campaign_name IN (SELECT campaign_name FROM dialer_campaigns)
    ),
    dialer_end AS (
      SELECT
        RANK() OVER (
          PARTITION BY campaign_name
          ORDER BY campaign_start_date_time ASC
        ) AS rank,
        campaign_name,
        campaign_end_date_time AS campaign_end_date_time1
      FROM `ffn-data-platform.standardized_data.dialer_campaign_stats`
      WHERE DATE(TIMESTAMP(campaign_start_date_time, 'America/Phoenix')) > DATE '2020-09-03'
        AND campaign_event IN ('Pause')
        AND campaign_state = 'Paused'
        AND campaign_name IN (SELECT campaign_name FROM dialer_campaigns)
    )
    SELECT
      s.campaign_name,
      s.campaign_end_date_time1 AS start_run_time,
      e.campaign_end_date_time1 AS end_run_time
    FROM dialer_start s
    INNER JOIN dialer_end e
      ON s.rank = e.rank
      AND s.campaign_name = e.campaign_name
  )
  SELECT
    CASE
      WHEN TIMESTAMP(cs.campaign_start_date_time, 'America/Phoenix') <= TIMESTAMP('2021-12-08', 'America/Phoenix')
        THEN TIMESTAMP(d.start_run_time, 'America/Phoenix')
      WHEN TIMESTAMP(cs.campaign_start_date_time, 'America/Phoenix') > TIMESTAMP('2021-12-08', 'America/Phoenix')
        AND TIMESTAMP_DIFF(
          TIMESTAMP(cs.campaign_end_date_time, 'America/Phoenix'),
          TIMESTAMP(cs.campaign_start_date_time, 'America/Phoenix'),
          MINUTE
        ) >= 30
        THEN TIMESTAMP(cs.campaign_start_date_time, 'America/Phoenix')
      ELSE NULL
    END AS start_run_time,
    CASE
      WHEN TIMESTAMP(cs.campaign_start_date_time, 'America/Phoenix') <= TIMESTAMP('2021-12-08', 'America/Phoenix')
        THEN TIMESTAMP(d.end_run_time, 'America/Phoenix')
      WHEN TIMESTAMP(cs.campaign_start_date_time, 'America/Phoenix') > TIMESTAMP('2021-12-08', 'America/Phoenix')
        AND TIMESTAMP_DIFF(
          TIMESTAMP(cs.campaign_end_date_time, 'America/Phoenix'),
          TIMESTAMP(cs.campaign_start_date_time, 'America/Phoenix'),
          MINUTE
        ) >= 30
        THEN TIMESTAMP(cs.campaign_end_date_time, 'America/Phoenix')
      ELSE NULL
    END AS end_run_time,
    cs.campaign_name
  FROM `ffn-data-platform.standardized_data.dialer_campaign_stats` cs
  LEFT JOIN dialer_start_end d
    ON d.campaign_name = cs.campaign_name
  WHERE cs.campaign_name IN (SELECT campaign_name FROM dialer_campaigns)
  GROUP BY 1, 2, 3
),

dialer_contacts AS (
  SELECT
    ch.source_system_id,
    ch.call_placed_datetime,
    ch.campaign_name,
    ch.agent_id AS dialer_agent_id,
    e.full_name AS dialer_agent_name,
    COALESCE(a.application_key, a15.application_key) AS application_key,
    COALESCE(a.funded_date, a15.funded_date) AS funded_date,
    ROW_NUMBER() OVER (
      PARTITION BY COALESCE(a.application_key, a15.application_key)
      ORDER BY ch.call_placed_datetime ASC
    ) AS contact_rank
  FROM dialer_campaign_stats d
  INNER JOIN `ffam-data-platform.standardized_data.inin_dialer_history` ch
    ON d.campaign_name = ch.campaign_name
    AND ch.call_placed_datetime BETWEEN d.start_run_time AND d.end_run_time
  LEFT JOIN `ffam-data-platform.standardized_data.employee_history` e
    ON ch.agent_id = e.inin_username
    AND e.is_active_rec = 1
  LEFT JOIN `ffam-data-platform.standardized_data.fplus_application` a
    ON ch.source_system_id = a.application_key
  LEFT JOIN `ffam-data-platform.standardized_data.fplus_application` a15
    ON a.application_key IS NULL
    AND ch.source_system_id = SUBSTR(a15.application_key, 1, 15)
  WHERE d.start_run_time >= TIMESTAMP('__COHORT_START__', 'America/Phoenix')
__COHORT_END_SQL__
    AND COALESCE(a.application_key, a15.application_key) IS NOT NULL
    AND (
      ch.contacted IS TRUE
      OR SAFE_CAST(ch.contacted AS INT64) = 1
      OR UPPER(TRIM(CAST(ch.contacted AS STRING))) IN ('Y', 'YES', 'TRUE', '1')
    )
__REFI_ONLY_SQL__
),

first_contacts AS (
  SELECT *
  FROM dialer_contacts
  WHERE contact_rank = 1
),

application_history_ranked AS (
  SELECT
    h.application_key,
    TRIM(h.loan_officer_assignment) AS loan_officer_assignment,
    COALESCE(
      TIMESTAMP(h.record_start_datetime, 'America/Phoenix'),
      TIMESTAMP(h.modified_datetime, 'America/Phoenix'),
      TIMESTAMP(h.created_datetime, 'America/Phoenix')
    ) AS history_effective_datetime,
    LAG(TRIM(h.loan_officer_assignment)) OVER (
      PARTITION BY h.application_key
      ORDER BY COALESCE(
        TIMESTAMP(h.record_start_datetime, 'America/Phoenix'),
        TIMESTAMP(h.modified_datetime, 'America/Phoenix'),
        TIMESTAMP(h.created_datetime, 'America/Phoenix')
      )
    ) AS prior_loan_officer_assignment
  FROM `ffam-data-platform.standardized_data.fplus_application_history` h
  WHERE h.loan_officer_assignment IS NOT NULL
    AND TRIM(h.loan_officer_assignment) != ''
),

agent_transfers AS (
  SELECT
    application_key,
    history_effective_datetime AS transfer_datetime,
    prior_loan_officer_assignment AS from_agent_name,
    loan_officer_assignment AS to_agent_name
  FROM application_history_ranked
  WHERE prior_loan_officer_assignment IS NOT NULL
    AND loan_officer_assignment != prior_loan_officer_assignment
),

transfer_before_first_contact AS (
  SELECT
    fc.application_key,
    fc.dialer_agent_name,
    fc.funded_date,
    t.from_agent_name AS pre_contact_losing_agent,
    t.to_agent_name AS pre_contact_gaining_agent,
    TIMESTAMP_DIFF(fc.call_placed_datetime, t.transfer_datetime, HOUR) AS hours_transfer_to_contact,
    CASE
      WHEN fc.dialer_agent_name = t.to_agent_name THEN 'Gaining agent contacted'
      WHEN fc.dialer_agent_name = t.from_agent_name THEN 'Losing agent contacted'
      ELSE 'Other agent contacted'
    END AS pre_contact_dialer_by
  FROM first_contacts fc
  INNER JOIN agent_transfers t
    ON fc.application_key = t.application_key
    AND t.transfer_datetime < fc.call_placed_datetime
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY fc.application_key
    ORDER BY t.transfer_datetime DESC
  ) = 1
),

transfer_after_first_contact AS (
  SELECT
    fc.application_key,
    fc.dialer_agent_name,
    fc.funded_date,
    t.from_agent_name AS post_contact_losing_agent,
    t.to_agent_name AS post_contact_gaining_agent,
    TIMESTAMP_DIFF(t.transfer_datetime, fc.call_placed_datetime, HOUR) AS hours_contact_to_transfer,
    CASE
      WHEN fc.dialer_agent_name = t.to_agent_name THEN 'Gaining agent was dialer contact'
      WHEN fc.dialer_agent_name = t.from_agent_name THEN 'Losing agent was dialer contact'
      ELSE 'Other agent was dialer contact'
    END AS post_contact_dialer_by
  FROM first_contacts fc
  INNER JOIN agent_transfers t
    ON fc.application_key = t.application_key
    AND t.transfer_datetime > fc.call_placed_datetime
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY fc.application_key
    ORDER BY t.transfer_datetime ASC
  ) = 1
),

pre_contact_detail AS (
  SELECT * FROM transfer_before_first_contact
),

post_contact_detail AS (
  SELECT * FROM transfer_after_first_contact
)

-- 1) Agents losing leads BEFORE contact
SELECT
  'Agents Losing Leads (Before Contact)' AS report_section,
  pre_contact_losing_agent AS agent_name,
  COUNT(DISTINCT application_key) AS leads,
  COUNTIF(pre_contact_dialer_by = 'Losing agent contacted') AS dialer_was_losing_agent,
  COUNTIF(pre_contact_dialer_by = 'Gaining agent contacted') AS dialer_was_gaining_agent,
  COUNTIF(pre_contact_dialer_by = 'Other agent contacted') AS dialer_was_other_agent,
  ROUND(AVG(hours_transfer_to_contact), 1) AS avg_hours_to_contact,
  COUNTIF(funded_date IS NOT NULL) AS funded_count,
  ROUND(
    100.0 * COUNTIF(funded_date IS NOT NULL) / NULLIF(COUNT(DISTINCT application_key), 0),
    1
  ) AS funded_rate_pct
FROM pre_contact_detail
GROUP BY 1, 2

UNION ALL

-- 2) Agents gaining leads BEFORE contact
SELECT
  'Agents Gaining Leads (Before Contact)' AS report_section,
  pre_contact_gaining_agent AS agent_name,
  COUNT(DISTINCT application_key) AS leads,
  COUNTIF(pre_contact_dialer_by = 'Losing agent contacted') AS dialer_was_losing_agent,
  COUNTIF(pre_contact_dialer_by = 'Gaining agent contacted') AS dialer_was_gaining_agent,
  COUNTIF(pre_contact_dialer_by = 'Other agent contacted') AS dialer_was_other_agent,
  ROUND(AVG(hours_transfer_to_contact), 1) AS avg_hours_to_contact,
  COUNTIF(funded_date IS NOT NULL) AS funded_count,
  ROUND(
    100.0 * COUNTIF(funded_date IS NOT NULL) / NULLIF(COUNT(DISTINCT application_key), 0),
    1
  ) AS funded_rate_pct
FROM pre_contact_detail
GROUP BY 1, 2

UNION ALL

-- 3) Agents losing leads AFTER contact
SELECT
  'Agents Losing Leads (After Contact)' AS report_section,
  post_contact_losing_agent AS agent_name,
  COUNT(DISTINCT application_key) AS leads,
  COUNTIF(post_contact_dialer_by = 'Losing agent was dialer contact') AS dialer_was_losing_agent,
  COUNTIF(post_contact_dialer_by = 'Gaining agent was dialer contact') AS dialer_was_gaining_agent,
  COUNTIF(post_contact_dialer_by = 'Other agent was dialer contact') AS dialer_was_other_agent,
  ROUND(AVG(hours_contact_to_transfer), 1) AS avg_hours_to_contact,
  COUNTIF(funded_date IS NOT NULL) AS funded_count,
  ROUND(
    100.0 * COUNTIF(funded_date IS NOT NULL) / NULLIF(COUNT(DISTINCT application_key), 0),
    1
  ) AS funded_rate_pct
FROM post_contact_detail
GROUP BY 1, 2

UNION ALL

-- 4) Agents gaining leads AFTER contact
SELECT
  'Agents Gaining Leads (After Contact)' AS report_section,
  post_contact_gaining_agent AS agent_name,
  COUNT(DISTINCT application_key) AS leads,
  COUNTIF(post_contact_dialer_by = 'Losing agent was dialer contact') AS dialer_was_losing_agent,
  COUNTIF(post_contact_dialer_by = 'Gaining agent was dialer contact') AS dialer_was_gaining_agent,
  COUNTIF(post_contact_dialer_by = 'Other agent was dialer contact') AS dialer_was_other_agent,
  ROUND(AVG(hours_contact_to_transfer), 1) AS avg_hours_to_contact,
  COUNTIF(funded_date IS NOT NULL) AS funded_count,
  ROUND(
    100.0 * COUNTIF(funded_date IS NOT NULL) / NULLIF(COUNT(DISTINCT application_key), 0),
    1
  ) AS funded_rate_pct
FROM post_contact_detail
GROUP BY 1, 2

ORDER BY report_section, leads DESC
;

-- Post-contact transfer flow matrix (run separately if needed):
-- SELECT
--   post_contact_losing_agent AS from_agent_name,
--   post_contact_gaining_agent AS to_agent_name,
--   COUNT(DISTINCT application_key) AS leads_transferred,
--   COUNTIF(post_contact_dialer_by = 'Gaining agent was dialer contact') AS gaining_agent_was_dialer,
--   ROUND(
--     100.0 * COUNTIF(post_contact_dialer_by = 'Gaining agent was dialer contact')
--     / NULLIF(COUNT(DISTINCT application_key), 0),
--     1
--   ) AS pct_gaining_agent_was_dialer
-- FROM post_contact_detail
-- GROUP BY 1, 2
-- ORDER BY leads_transferred DESC;
