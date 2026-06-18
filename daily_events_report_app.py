#!/usr/bin/env python3
"""
Local interactive report for daily events channel extracts.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd
import plotly.express as px
import streamlit as st

EXPECTED_COLUMNS = {
    "event_date",
    "utm_channel",
    "lead_type",
    "eligible_leads",
    "lc_assigned_leads",
    "contacts_made",
    "full_app_submitted_leads",
    "combined_full_app_approved_leads",
    "contract_out_leads",
    "contract_signed_leads",
    "funded_leads",
    "originated_loan_amount",
}

METRIC_COLUMNS = [
    "eligible_leads",
    "lc_assigned_leads",
    "contacts_made",
    "full_app_submitted_leads",
    "combined_full_app_approved_leads",
    "contract_out_leads",
    "contract_signed_leads",
    "funded_leads",
]

FUNNEL_LABELS = [
    ("Eligible Leads", "eligible_leads"),
    ("LC Assigned", "lc_assigned_leads"),
    ("Contacts Made", "contacts_made"),
    ("Full App Submitted", "full_app_submitted_leads"),
    ("Full App Approved", "combined_full_app_approved_leads"),
    ("Contract Out", "contract_out_leads"),
    ("Contract Signed", "contract_signed_leads"),
    ("Funded", "funded_leads"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--data",
        default="data/daily_events_channel_report.csv",
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
            "Run the BigQuery extract first or use data/sample_daily_events_channel_report.csv."
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
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    for col in METRIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["originated_loan_amount"] = pd.to_numeric(
        df["originated_loan_amount"], errors="coerce"
    ).fillna(0)
    df["utm_channel"] = df["utm_channel"].fillna("").astype(str)
    df["lead_type"] = df["lead_type"].fillna("").astype(str)
    return df


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filters")

    channels = sorted(df["utm_channel"].unique().tolist())
    selected_channels = st.sidebar.multiselect(
        "UTM channel", options=channels, default=channels
    )

    lead_types = sorted(df["lead_type"].unique().tolist())
    selected_lead_types = st.sidebar.multiselect(
        "Lead type", options=lead_types, default=lead_types
    )

    min_date = df["event_date"].min()
    max_date = df["event_date"].max()
    selected_dates = st.sidebar.date_input(
        "Event date range",
        value=(min_date.date(), max_date.date()),
        min_value=min_date.date(),
        max_value=max_date.date(),
    )

    filtered = df.copy()
    if selected_channels:
        filtered = filtered[filtered["utm_channel"].isin(selected_channels)]
    if selected_lead_types:
        filtered = filtered[filtered["lead_type"].isin(selected_lead_types)]

    if isinstance(selected_dates, Iterable) and len(selected_dates) == 2:
        start_date, end_date = selected_dates
        filtered = filtered[
            filtered["event_date"].dt.date.between(start_date, end_date)
        ]
    return filtered


def funnel_totals(df: pd.DataFrame) -> pd.DataFrame:
    totals = {col: df[col].sum() for _, col in FUNNEL_LABELS}
    rows: list[dict[str, float | str]] = []
    base = max(totals[FUNNEL_LABELS[0][1]], 1)
    previous = base

    for label, col in FUNNEL_LABELS:
        current = totals[col]
        rows.append(
            {
                "step": label,
                "count": current,
                "step_conversion": (current / previous) if previous else 0,
                "overall_conversion": (current / base) if base else 0,
            }
        )
        previous = max(current, 1)

    return pd.DataFrame(rows)


def daily_totals(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("event_date", as_index=False)[METRIC_COLUMNS + ["originated_loan_amount"]]
        .sum()
        .sort_values("event_date")
    )


def breakdown_table(df: pd.DataFrame, dimension: str) -> pd.DataFrame:
    agg = df.groupby(dimension, dropna=False)[METRIC_COLUMNS + ["originated_loan_amount"]].sum()
    agg = agg.reset_index().sort_values("eligible_leads", ascending=False)
    return agg


def main() -> None:
    args = parse_args()
    st.set_page_config(page_title="Daily Events Channel Report", layout="wide")
    st.title("Daily Events Channel Report")
    st.caption(
        "Funnel metrics by event_date, utm_channel, and lead_type "
        "(from fplus_application_daily_events_detail_max)."
    )

    try:
        df = load_data(args.data)
    except Exception as exc:  # pragma: no cover
        st.error(str(exc))
        st.info(
            "Generate data locally:\n"
            "1. python run_fplus_daily_events_report.py --start-date 2026-05-01\n"
            "2. bq query ... --output_file=data/daily_events_channel_report.csv\n"
            "3. streamlit run daily_events_report_app.py -- --data data/daily_events_channel_report.csv"
        )
        st.stop()

    filtered = apply_filters(df)
    totals = {col: filtered[col].sum() for col in METRIC_COLUMNS}
    originated = filtered["originated_loan_amount"].sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Eligible Leads", f"{int(totals['eligible_leads']):,}")
    c2.metric("Full App Submitted", f"{int(totals['full_app_submitted_leads']):,}")
    c3.metric("Funded Leads", f"{int(totals['funded_leads']):,}")
    c4.metric("Originated Loan Amount", f"${originated:,.0f}")

    st.subheader("Funnel Conversion")
    funnel_df = funnel_totals(filtered)
    st.dataframe(
        funnel_df.assign(
            step_conversion=(funnel_df["step_conversion"] * 100).round(2).astype(str) + "%",
            overall_conversion=(funnel_df["overall_conversion"] * 100).round(2).astype(str) + "%",
        ),
        use_container_width=True,
        hide_index=True,
    )

    fig_funnel = px.funnel(
        funnel_df,
        y="step",
        x="count",
        title="Lead Funnel (filtered totals)",
    )
    st.plotly_chart(fig_funnel, use_container_width=True)

    st.subheader("Daily Trend")
    daily = daily_totals(filtered)
    trend_metric = st.selectbox(
        "Metric",
        options=METRIC_COLUMNS,
        index=METRIC_COLUMNS.index("funded_leads"),
    )
    fig_trend = px.line(
        daily,
        x="event_date",
        y=trend_metric,
        markers=True,
        title=f"Daily {trend_metric.replace('_', ' ')}",
    )
    st.plotly_chart(fig_trend, use_container_width=True)

    st.subheader("Breakdown by UTM Channel")
    by_channel = breakdown_table(filtered, "utm_channel")
    st.dataframe(by_channel, use_container_width=True, hide_index=True)
    st.plotly_chart(
        px.bar(
            by_channel.head(15),
            x="utm_channel",
            y="funded_leads",
            title="Top UTM Channels by Funded Leads",
        ),
        use_container_width=True,
    )

    st.subheader("Breakdown by Lead Type")
    by_lead_type = breakdown_table(filtered, "lead_type")
    st.dataframe(by_lead_type, use_container_width=True, hide_index=True)

    st.subheader("Detail Rows")
    detail = filtered.sort_values(["event_date", "utm_channel", "lead_type"])
    st.dataframe(detail, use_container_width=True, hide_index=True)
    st.download_button(
        "Download filtered CSV",
        data=detail.to_csv(index=False),
        file_name="daily_events_channel_report_filtered.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
