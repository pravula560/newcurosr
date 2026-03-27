#!/usr/bin/env python3
"""
Interactive dashboard for APL trifurcated funnel extracts.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd
import plotly.express as px
import streamlit as st


EXPECTED_COLUMNS = {
    "application_key",
    "loan_id",
    "product_line",
    "created_datetime",
    "flag_eligible_lead",
    "fico_band",
    "in_pq_cohort",
    "in_fa_offers_cohort",
    "pagaya_entry_segment",
    "full_app_submitted",
    "uw_decisioned",
    "uw_approved",
    "contract_signed",
    "funded",
    "origination_dollars",
}

FUNNEL_STEPS = [
    ("Applications", "application_key"),
    ("Full App Submitted", "full_app_submitted"),
    ("UW Decisioned", "uw_decisioned"),
    ("UW Approved", "uw_approved"),
    ("Contract Signed", "contract_signed"),
    ("Funded", "funded"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--data",
        default="data/apl_trifurcated_funnel.csv",
        help="Path to CSV or Parquet extract file.",
    )
    args, _ = parser.parse_known_args()
    return args


@st.cache_data(show_spinner=False)
def load_data(path: str) -> pd.DataFrame:
    data_path = Path(path)
    if not data_path.exists():
        raise FileNotFoundError(
            f"Data file not found at '{data_path}'. "
            "Provide --data path/to/extract.csv or .parquet."
        )

    if data_path.suffix.lower() == ".csv":
        df = pd.read_csv(data_path)
    elif data_path.suffix.lower() in {".parquet", ".pq"}:
        df = pd.read_parquet(data_path)
    else:
        raise ValueError("Unsupported input format. Use CSV or Parquet.")

    missing = EXPECTED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(
            "Input is missing required columns: " + ", ".join(sorted(missing))
        )

    df = df.copy()
    df["created_datetime"] = pd.to_datetime(df["created_datetime"], errors="coerce")
    for col in [
        "full_app_submitted",
        "uw_decisioned",
        "uw_approved",
        "contract_signed",
        "funded",
        "in_pq_cohort",
        "in_fa_offers_cohort",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    df["origination_dollars"] = pd.to_numeric(
        df["origination_dollars"], errors="coerce"
    ).fillna(0)
    return df


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filters")

    product_lines = sorted(df["product_line"].dropna().astype(str).unique().tolist())
    selected_product_lines = st.sidebar.multiselect(
        "Product line", options=product_lines, default=product_lines
    )

    eligible_only = st.sidebar.checkbox("flag_eligible_lead only", value=False)

    fico_bands = sorted(df["fico_band"].dropna().astype(str).unique().tolist())
    selected_fico = st.sidebar.multiselect(
        "FICO band", options=fico_bands, default=fico_bands
    )

    pagaya_segments = sorted(
        df["pagaya_entry_segment"].fillna("").astype(str).unique().tolist()
    )
    selected_segments = st.sidebar.multiselect(
        "Pagaya entry segment", options=pagaya_segments, default=pagaya_segments
    )

    min_date = df["created_datetime"].min()
    max_date = df["created_datetime"].max()
    selected_dates = st.sidebar.date_input(
        "Created date range",
        value=(min_date.date(), max_date.date()),
        min_value=min_date.date(),
        max_value=max_date.date(),
    )

    filtered = df.copy()
    if selected_product_lines:
        filtered = filtered[filtered["product_line"].astype(str).isin(selected_product_lines)]
    if eligible_only:
        filtered = filtered[filtered["flag_eligible_lead"] == True]  # noqa: E712
    if selected_fico:
        filtered = filtered[filtered["fico_band"].astype(str).isin(selected_fico)]
    if selected_segments:
        filtered = filtered[
            filtered["pagaya_entry_segment"].fillna("").astype(str).isin(selected_segments)
        ]

    if isinstance(selected_dates, Iterable) and len(selected_dates) == 2:
        start_date, end_date = selected_dates
        filtered = filtered[
            filtered["created_datetime"].dt.date.between(start_date, end_date)
        ]
    return filtered


def funnel_counts(df: pd.DataFrame) -> pd.DataFrame:
    counts: list[dict[str, float]] = []
    base_count = df["application_key"].nunique()
    previous = max(base_count, 1)

    for step_name, column in FUNNEL_STEPS:
        if column == "application_key":
            current = base_count
        else:
            current = df.loc[df[column] == 1, "application_key"].nunique()
        counts.append(
            {
                "step": step_name,
                "applications": current,
                "step_conversion": (current / previous) if previous else 0,
                "overall_conversion": (current / base_count) if base_count else 0,
            }
        )
        previous = max(current, 1)
    return pd.DataFrame(counts)


def main() -> None:
    args = parse_args()
    st.set_page_config(page_title="APL Trifurcated Funnel Dashboard", layout="wide")
    st.title("APL Trifurcated Funnel Dashboard")
    st.caption("Core / Pagaya / Superprime funnel performance from GBQ extract.")

    try:
        df = load_data(args.data)
    except Exception as exc:  # pragma: no cover
        st.error(str(exc))
        st.stop()

    filtered = apply_filters(df)

    loans = filtered["application_key"].nunique()
    funds = filtered.loc[filtered["funded"] == 1, "loan_id"].nunique()
    origination_dollars = filtered.loc[filtered["funded"] == 1, "origination_dollars"].sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("LOANS (distinct application_key)", f"{loans:,}")
    c2.metric("FUNDS (distinct loan_id funded)", f"{funds:,}")
    c3.metric("Origination Dollars", f"${origination_dollars:,.0f}")

    st.subheader("Funnel Conversion")
    funnel_df = funnel_counts(filtered)
    st.dataframe(
        funnel_df.assign(
            step_conversion=(funnel_df["step_conversion"] * 100).round(2).astype(str) + "%",
            overall_conversion=(funnel_df["overall_conversion"] * 100).round(2).astype(str) + "%",
        ),
        use_container_width=True,
        hide_index=True,
    )

    fig = px.funnel(
        funnel_df,
        y="step",
        x="applications",
        title="Application Funnel",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Product Line Breakdown")
    by_product = (
        filtered.groupby("product_line", dropna=False)
        .agg(
            loans=("application_key", "nunique"),
            funds=("loan_id", lambda s: s[filtered.loc[s.index, "funded"] == 1].nunique()),
            origination_dollars=(
                "origination_dollars",
                lambda s: s[filtered.loc[s.index, "funded"] == 1].sum(),
            ),
        )
        .reset_index()
        .sort_values("loans", ascending=False)
    )
    st.dataframe(by_product, use_container_width=True, hide_index=True)

    bar = px.bar(
        by_product,
        x="product_line",
        y=["loans", "funds"],
        barmode="group",
        title="Loans vs Funds by Product Line",
    )
    st.plotly_chart(bar, use_container_width=True)


if __name__ == "__main__":
    main()
