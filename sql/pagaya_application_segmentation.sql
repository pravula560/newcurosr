WITH base AS (
  SELECT
    A.application_key,
    A.loan_id,
    UPPER(TRIM(A.product_line)) AS product_line,
    A.created_datetime,
    A.full_app_submitted_datetime,
    A.prequal_submitted_datetime,
    A.underwriter_decision_datetime,
    A.underwriter_decision,
    A.contract_docs_received_datetime,
    A.funded_date,
    A.funding_datetime,
    A.final_loan_amount,
    A.fico,
    A.`Adjusted_fico_10t`,
    A.flag_eligible_lead,
    CASE
      WHEN (
        (A.pq_product_prioritization = 'PAGAYA' AND A.fa_product_prioritization IS NULL)
        OR A.pq_pagaya_evaluated IS TRUE
        OR A.pq_pagaya_approved IS TRUE
      ) THEN 1
      ELSE 0
    END AS in_pq_cohort,
    CASE WHEN A.pagaya_offers_requested IS TRUE THEN 1 ELSE 0 END AS in_fa_offers_cohort,
    CASE
      WHEN COALESCE(A.`Adjusted_fico_10t`, A.fico) IS NULL THEN 'Unknown'
      WHEN COALESCE(A.`Adjusted_fico_10t`, A.fico) < 640 THEN 'FICO <640'
      WHEN COALESCE(A.`Adjusted_fico_10t`, A.fico) < 700 THEN 'FICO 640–699'
      ELSE 'FICO 700+'
    END AS fico_band,
    CASE WHEN A.full_app_submitted_datetime IS NOT NULL THEN 1 ELSE 0 END AS full_app_submitted,
    CASE WHEN A.underwriter_decision_datetime IS NOT NULL THEN 1 ELSE 0 END AS uw_decisioned,
    CASE
      WHEN A.underwriter_decision_datetime IS NOT NULL
       AND A.underwriter_decision IN ('Approved', 'Conditional Approval')
      THEN 1 ELSE 0
    END AS uw_approved,
    CASE WHEN A.contract_docs_received_datetime IS NOT NULL THEN 1 ELSE 0 END AS contract_signed,
    CASE WHEN A.funding_datetime IS NOT NULL THEN 1 ELSE 0 END AS funded,
    CASE
      WHEN A.funding_datetime IS NOT NULL THEN COALESCE(A.final_loan_amount, 0)
      ELSE 0
    END AS funded_volume,
    CASE
      WHEN A.funding_datetime IS NOT NULL THEN COALESCE(A.final_loan_amount, 0)
      ELSE 0
    END AS origination_dollars
  FROM `ffam-data-platform.standardized_data.fplus_application` A
  WHERE DATE(A.created_datetime) >= '2026-01-01'
)
SELECT
  base.*,
  CASE
    WHEN UPPER(TRIM(base.product_line)) <> 'PAGAYA' THEN ''
    WHEN base.in_pq_cohort = 1 AND base.in_fa_offers_cohort = 1 THEN 'PQ + FA'
    WHEN base.in_pq_cohort = 1 AND base.in_fa_offers_cohort = 0 THEN 'PQ entry'
    WHEN base.in_pq_cohort = 0 AND base.in_fa_offers_cohort = 1 THEN 'FA entry'
    ELSE 'Unknown'
  END AS pagaya_entry_segment
FROM base
;
