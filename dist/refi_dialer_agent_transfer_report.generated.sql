-- Refi / FPlus dialer leads: agent ownership transfer analysis when contact is made.
-- Reads dialer contacts directly from inin_dialer_history (no dialer_campaign_stats).
--
-- Placeholders (rendered by run_refi_dialer_agent_transfer_report.py):
--   2026-01-01  inclusive contact date start (YYYY-MM-DD)
--    optional upper bound on call_placed_datetime
--    optional refinance filter on fplus_application

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
  FROM `ffam-data-platform.standardized_data.inin_dialer_history` ch
  INNER JOIN dialer_campaigns dc
    ON ch.campaign_name = dc.campaign_name
  LEFT JOIN `ffam-data-platform.standardized_data.employee_history` e
    ON ch.agent_id = e.inin_username
    AND e.is_active_rec = 1
  LEFT JOIN `ffam-data-platform.standardized_data.fplus_application` a
    ON ch.source_system_id = a.application_key
  LEFT JOIN `ffam-data-platform.standardized_data.fplus_application` a15
    ON a.application_key IS NULL
    AND ch.source_system_id = SUBSTR(a15.application_key, 1, 15)
  WHERE ch.call_placed_datetime >= TIMESTAMP('2026-01-01', 'America/Phoenix')

    AND COALESCE(a.application_key, a15.application_key) IS NOT NULL
    AND (
      ch.contacted IS TRUE
      OR SAFE_CAST(ch.contacted AS INT64) = 1
      OR UPPER(TRIM(CAST(ch.contacted AS STRING))) IN ('Y', 'YES', 'TRUE', '1')
    )

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
