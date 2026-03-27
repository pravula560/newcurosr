#!/usr/bin/env python3
"""
Generate realistic sample data for the APL Trifurcated Funnel Dashboard.

This creates a Parquet file at data/apl_trifurcated_funnel.parquet that can be
used to demo the dashboard without a BigQuery connection.

Usage:
    python generate_sample_data.py              # 10 000 rows
    python generate_sample_data.py --rows 50000 # custom count
"""

from __future__ import annotations

import argparse
import pathlib
import random

import numpy as np
import pandas as pd

DATA_DIR = pathlib.Path(__file__).resolve().parent / "data"

PRODUCT_LINES = ["CORE", "PAGAYA", "SUPERPRIME"]
PL_WEIGHTS = [0.50, 0.35, 0.15]

FICO_MEAN = {"CORE": 680, "PAGAYA": 650, "SUPERPRIME": 740}
FICO_STD = {"CORE": 50, "PAGAYA": 60, "SUPERPRIME": 30}

FULL_APP_RATE = {"CORE": 0.60, "PAGAYA": 0.55, "SUPERPRIME": 0.70}
UW_RATE = {"CORE": 0.80, "PAGAYA": 0.75, "SUPERPRIME": 0.85}
APPROVAL_RATE = {"CORE": 0.65, "PAGAYA": 0.55, "SUPERPRIME": 0.80}
CONTRACT_RATE = {"CORE": 0.70, "PAGAYA": 0.65, "SUPERPRIME": 0.75}
FUND_RATE = {"CORE": 0.85, "PAGAYA": 0.80, "SUPERPRIME": 0.90}

LOAN_MEAN = {"CORE": 15_000, "PAGAYA": 12_000, "SUPERPRIME": 25_000}
LOAN_STD = {"CORE": 8_000, "PAGAYA": 6_000, "SUPERPRIME": 10_000}


def generate(n_rows: int = 10_000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    random.seed(seed)

    records = []
    start = pd.Timestamp("2025-01-01")
    end = pd.Timestamp("2025-12-31")

    for i in range(n_rows):
        pl = rng.choice(PRODUCT_LINES, p=PL_WEIGHTS)

        created = start + pd.Timedelta(days=int(rng.integers(0, (end - start).days)))
        fico = int(np.clip(rng.normal(FICO_MEAN[pl], FICO_STD[pl]), 500, 850))
        adjusted_fico = fico + int(rng.integers(-10, 11))
        eligible = rng.random() < 0.75

        has_full_app = rng.random() < FULL_APP_RATE[pl]
        full_app_dt = created + pd.Timedelta(hours=int(rng.integers(1, 72))) if has_full_app else pd.NaT
        prequal_dt = created + pd.Timedelta(minutes=int(rng.integers(5, 120)))

        has_uw = has_full_app and rng.random() < UW_RATE[pl]
        uw_dt = full_app_dt + pd.Timedelta(hours=int(rng.integers(4, 168))) if has_uw else pd.NaT
        is_approved = has_uw and rng.random() < APPROVAL_RATE[pl]
        uw_decision = (
            rng.choice(["Approved", "Conditional Approval"], p=[0.7, 0.3])
            if is_approved
            else "Declined"
        ) if has_uw else None

        has_contract = is_approved and rng.random() < CONTRACT_RATE[pl]
        contract_dt = uw_dt + pd.Timedelta(hours=int(rng.integers(12, 240))) if has_contract else pd.NaT

        has_funded = has_contract and rng.random() < FUND_RATE[pl]
        funding_dt = contract_dt + pd.Timedelta(hours=int(rng.integers(24, 336))) if has_funded else pd.NaT
        funded_date = funding_dt.date() if has_funded else None

        loan_amt = max(1_000, int(rng.normal(LOAN_MEAN[pl], LOAN_STD[pl]))) if has_funded else None
        loan_id = f"LN-{i:07d}" if has_funded else None

        pq_prio = rng.choice(["PAGAYA", "CORE", None], p=[0.4, 0.4, 0.2]) if pl == "PAGAYA" else None
        fa_prio = rng.choice(["PAGAYA", "CORE", None], p=[0.3, 0.3, 0.4]) if pl == "PAGAYA" else None
        pq_eval = bool(rng.random() < 0.5) if pl == "PAGAYA" else False
        pq_approved = bool(rng.random() < 0.3) if pl == "PAGAYA" else False
        offers_req = bool(rng.random() < 0.4) if pl == "PAGAYA" else False

        in_pq = int(
            (pq_prio == "PAGAYA" and fa_prio is None) or pq_eval or pq_approved
        ) if pl == "PAGAYA" else 0
        in_fa = int(offers_req) if pl == "PAGAYA" else 0

        fico_val = adjusted_fico if adjusted_fico else fico
        if fico_val is None:
            fico_band = "Unknown"
        elif fico_val < 640:
            fico_band = "FICO <640"
        elif fico_val < 700:
            fico_band = "FICO 640-699"
        else:
            fico_band = "FICO 700+"

        if pl != "PAGAYA":
            seg = ""
        elif in_pq and in_fa:
            seg = "PQ + FA"
        elif in_pq:
            seg = "PQ entry"
        elif in_fa:
            seg = "FA entry"
        else:
            seg = "Unknown"

        records.append(
            {
                "application_key": f"APP-{i:07d}",
                "loan_id": loan_id,
                "product_line": pl,
                "created_datetime": created,
                "full_app_submitted_datetime": full_app_dt,
                "prequal_submitted_datetime": prequal_dt,
                "underwriter_decision_datetime": uw_dt,
                "underwriter_decision": uw_decision,
                "contract_docs_received_datetime": contract_dt,
                "funded_date": funded_date,
                "funding_datetime": funding_dt,
                "final_loan_amount": loan_amt,
                "fico": fico,
                "adjusted_fico_10t": adjusted_fico,
                "flag_eligible_lead": eligible,
                "in_pq_cohort": in_pq,
                "in_fa_offers_cohort": in_fa,
                "fico_band": fico_band,
                "full_app_submitted": int(has_full_app),
                "uw_decisioned": int(has_uw),
                "uw_approved": int(is_approved),
                "contract_signed": int(has_contract),
                "funded": int(has_funded),
                "funded_volume": loan_amt if has_funded else 0,
                "origination_dollars": loan_amt if has_funded else 0,
                "pagaya_entry_segment": seg,
            }
        )

    return pd.DataFrame(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate sample funnel data.")
    parser.add_argument("--rows", type=int, default=10_000, help="Number of rows to generate.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    args = parser.parse_args()

    df = generate(n_rows=args.rows, seed=args.seed)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "apl_trifurcated_funnel.parquet"
    df.to_parquet(path, index=False)
    print(f"Wrote {len(df):,} rows → {path}")


if __name__ == "__main__":
    main()
