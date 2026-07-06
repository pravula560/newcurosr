-- Refi / FPlus dialer leads: agent ownership transfer analysis when contact is made.
--
-- Detects loan_officer_assignment changes in fplus_application_history and attributes
-- losing vs gaining agents for dialer-contacted applications.
--
-- Prerequisites (verify in BigQuery before first run):
--   SELECT column_name, data_type
--   FROM `ffam-data-platform.standardized_data.INFORMATION_SCHEMA.COLUMNS`
--   WHERE table_name = 'fplus_application_history'
--     AND column_name IN (
--       'loan_officer_assignment', 'record_start_datetime',
--       'modified_datetime', 'created_datetime', 'is_active_rec'
--     );
--
-- If history ordering column differs, update history_effective_datetime below.
--
-- Placeholders (rendered by run_refi_dialer_agent_transfer_report.py):
--   __COHORT_START__  inclusive campaign run start (YYYY-MM-DD)
--   __COHORT_END_SQL__ optional upper bound on campaign run start
--   __REFI_ONLY_SQL__ optional refinance filter on fplus_application

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
        campaign_event,
        campaign_name,
        campaign_start_date_time AS campaign_start_date_time1,
        campaign_end_date_time AS campaign_end_date_time1,
        TIMESTAMP(campaign_start_date_time, 'America/Phoenix') AS campaign_start_date_time,
        TIMESTAMP(campaign_end_date_time, 'America/Phoenix') AS campaign_end_date_time,
        period_end_date_time,
        total_agent_count,
        total_dialer_call_count
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
        campaign_event,
        campaign_name,
        TIMESTAMP(campaign_start_date_time, 'America/Phoenix') AS campaign_start_date_time,
        TIMESTAMP(campaign_end_date_time, 'America/Phoenix') AS campaign_end_date_time,
        campaign_end_date_time AS campaign_end_date_time1,
        period_end_date_time,
        total_agent_count,
        total_dialer_call_count,
        campaign_start_date_time AS periodstarttimeUTC_e
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
    cs.campaign_name,
    MAX(campaign_filter_size) AS cs_filtersize_apps,
    MAX(cs.total_agent_count) AS dialer_agents,
    SUM(total_dialer_call_count) AS cs_dialer_calls
  FROM `ffn-data-platform.standardized_data.dialer_campaign_stats` cs
  LEFT JOIN dialer_start_end d
    ON d.campaign_name = cs.campaign_name
  WHERE cs.campaign_name IN (SELECT campaign_name FROM dialer_campaigns)
  GROUP BY 1, 2, 3
),

dialer_contacts AS (
  SELECT
    ch.source_system_id,
    ch.contacted,
    ch.call_placed_datetime,
    ch.campaign_name,
    ch.agent_id AS dialer_agent_id,
    e.full_name AS dialer_agent_name,
    e.manager_full_name,
    e.fplus_roster_team,
    e.fplus_roster_manager,
    e.fplus_roster_lo_name,
    d.start_run_time,
    d.end_run_time,
    COALESCE(a.application_key, a15.application_key) AS application_key,
    COALESCE(a.loan_id, a15.loan_id) AS loan_id,
    COALESCE(a.applicant_id, a15.applicant_id) AS applicant_id,
    COALESCE(a.funded_date, a15.funded_date) AS funded_date,
    COALESCE(a.final_loan_amount, a15.final_loan_amount) AS final_loan_amount,
    COALESCE(a.prequal_submitted_datetime, a15.prequal_submitted_datetime) AS prequal_submitted_datetime,
    COALESCE(a.product_line, a15.product_line) AS product_line,
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
    ) AS prior_loan_officer_assignment,
    LEAD(COALESCE(
      TIMESTAMP(h.record_start_datetime, 'America/Phoenix'),
      TIMESTAMP(h.modified_datetime, 'America/Phoenix'),
      TIMESTAMP(h.created_datetime, 'America/Phoenix')
    )) OVER (
      PARTITION BY h.application_key
      ORDER BY COALESCE(
        TIMESTAMP(h.record_start_datetime, 'America/Phoenix'),
        TIMESTAMP(h.modified_datetime, 'America/Phoenix'),
        TIMESTAMP(h.created_datetime, 'America/Phoenix')
      )
    ) AS next_history_effective_datetime
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

lo_at_contact AS (
  SELECT
    fc.application_key,
    hr.loan_officer_assignment AS lo_at_contact
  FROM first_contacts fc
  LEFT JOIN application_history_ranked hr
    ON fc.application_key = hr.application_key
    AND hr.history_effective_datetime <= fc.call_placed_datetime
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY fc.application_key
    ORDER BY hr.history_effective_datetime DESC
  ) = 1
),

-- Most recent ownership transfer before the first dialer contact.
transfer_before_first_contact AS (
  SELECT
    fc.application_key,
    t.transfer_datetime AS pre_contact_transfer_datetime,
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

-- First ownership transfer after the first dialer contact.
transfer_after_first_contact AS (
  SELECT
    fc.application_key,
    t.transfer_datetime AS post_contact_transfer_datetime,
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

contact_transfer_detail AS (
  SELECT
    fc.application_key,
    fc.loan_id,
    fc.applicant_id,
    fc.product_line,
    fc.campaign_name,
    fc.call_placed_datetime,
    lac.lo_at_contact,
    fc.dialer_agent_id,
    fc.dialer_agent_name,
    fc.manager_full_name,
    fc.fplus_roster_team,
    fc.fplus_roster_manager,
    fc.fplus_roster_lo_name,
    fc.prequal_submitted_datetime,
    fc.funded_date,
    fc.final_loan_amount,
    pre.pre_contact_transfer_datetime,
    pre.pre_contact_losing_agent,
    pre.pre_contact_gaining_agent,
    pre.hours_transfer_to_contact,
    pre.pre_contact_dialer_by,
    post.post_contact_transfer_datetime,
    post.post_contact_losing_agent,
    post.post_contact_gaining_agent,
    post.hours_contact_to_transfer,
    post.post_contact_dialer_by,
    CASE
      WHEN pre.application_key IS NOT NULL AND post.application_key IS NOT NULL
        THEN 'Transfer before and after contact'
      WHEN pre.application_key IS NOT NULL
        THEN 'Transfer before contact only'
      WHEN post.application_key IS NOT NULL
        THEN 'Transfer after contact only'
      ELSE 'No agent transfer'
    END AS transfer_timing
  FROM first_contacts fc
  LEFT JOIN lo_at_contact lac
    ON fc.application_key = lac.application_key
  LEFT JOIN transfer_before_first_contact pre
    ON fc.application_key = pre.application_key
  LEFT JOIN transfer_after_first_contact post
    ON fc.application_key = post.application_key
  WHERE pre.application_key IS NOT NULL
     OR post.application_key IS NOT NULL
)

-- Detail grain: one row per contacted application with a pre- and/or post-contact transfer.
SELECT
  application_key,
  loan_id,
  applicant_id,
  product_line,
  campaign_name,
  call_placed_datetime,
  lo_at_contact,
  transfer_timing,
  pre_contact_transfer_datetime,
  pre_contact_losing_agent,
  pre_contact_gaining_agent,
  hours_transfer_to_contact,
  pre_contact_dialer_by,
  post_contact_transfer_datetime,
  post_contact_losing_agent,
  post_contact_gaining_agent,
  hours_contact_to_transfer,
  post_contact_dialer_by,
  dialer_agent_id,
  dialer_agent_name,
  manager_full_name,
  fplus_roster_team,
  fplus_roster_manager,
  fplus_roster_lo_name,
  prequal_submitted_datetime,
  funded_date,
  final_loan_amount,
  CASE WHEN funded_date IS NOT NULL THEN 1 ELSE 0 END AS funded_flag
FROM contact_transfer_detail
ORDER BY call_placed_datetime DESC
;
