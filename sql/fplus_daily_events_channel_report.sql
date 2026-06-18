-- Daily funnel metrics by event_date, utm_channel, and lead_type.
-- Source: fplus_application_daily_events_detail_max with employee-history join.
--
-- Placeholders (see run_fplus_daily_events_report.py):
--   __EVENT_START__     inclusive event_date lower bound (YYYY-MM-DD)
--   __EVENT_END_SQL__   optional upper bound fragment
SELECT
  fdm.event_date,
  fdm.utm_channel,
  fdm.lead_type,
  SUM(fdm.eligible_leads) AS eligible_leads,
  SUM(fdm.lc_assigned_leads) AS lc_assigned_leads,
  SUM(fdm.contacts_made) AS contacts_made,
  SUM(fdm.full_app_submitted_leads) AS full_app_submitted_leads,
  SUM(fdm.combined_full_app_approved_leads) AS combined_full_app_approved_leads,
  SUM(fdm.contract_out_leads) AS contract_out_leads,
  SUM(fdm.contract_signed_leads) AS contract_signed_leads,
  SUM(fdm.funded_leads) AS funded_leads,
  SUM(fdm.originated_loan_amount) AS originated_loan_amount
FROM `ffam-data-platform-loan-ops.data_models.fplus_application_daily_events_detail_max` fdm
LEFT JOIN `ffam-data-platform.standardized_data.fplus_application` a
  ON a.application_key = fdm.application_key
LEFT JOIN `ffam-data-platform.standardized_data.fplus_sf_employee_history_bridge` eb
  ON eb.sf_employee_id = fdm.loan_officer_id
LEFT JOIN `ffam-data-platform.standardized_data.employee_history` eh
  ON eb.employee_key = eh.employee_key
  AND DATE_SUB(
    DATE_ADD(DATE_TRUNC(DATE(fdm.event_date), MONTH), INTERVAL 1 MONTH),
    INTERVAL 1 DAY
  ) BETWEEN eh.start_date AND eh.end_date
WHERE fdm.event_date >= '__EVENT_START__'
__EVENT_END_SQL__
GROUP BY 1, 2, 3
