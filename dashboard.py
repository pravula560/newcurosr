#!/usr/bin/env python3
"""
APL Trifurcated Funnel Dashboard  (Core / Pagaya / Superprime)

Launch:
    streamlit run dashboard.py

Data source
-----------
The dashboard reads from ``data/apl_trifurcated_funnel.parquet``.
Generate that file with ``run_apl_trifurcated_funnel.py`` (BigQuery extract)
or supply your own Parquet/CSV via the sidebar uploader.
"""

from __future__ import annotations

import pathlib
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="APL Trifurcated Funnel",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* metric cards */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #f8f9fc 0%, #eef1f8 100%);
        border: 1px solid #dde3ee;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    }
    div[data-testid="stMetric"] label {
        font-size: 0.82rem;
        color: #5a6a85;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 1.7rem;
        font-weight: 700;
        color: #1a2744;
    }
    /* tables */
    thead th {
        background-color: #2c3e6b !important;
        color: white !important;
        font-weight: 600 !important;
    }
    /* sidebar */
    section[data-testid="stSidebar"] > div:first-child {
        background: linear-gradient(180deg, #1e2a4a 0%, #2c3e6b 100%);
    }
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] .stMarkdown p {
        color: #c8d3e8 !important;
    }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: #ffffff !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PARQUET_PATH = pathlib.Path(__file__).resolve().parent / "data" / "apl_trifurcated_funnel.parquet"

PRODUCT_LINE_COLORS = {
    "CORE": "#3366cc",
    "PAGAYA": "#e67e22",
    "SUPERPRIME": "#27ae60",
}

FUNNEL_STEPS_ORDERED = [
    "Leads",
    "Full App Submitted",
    "UW Decisioned",
    "UW Approved",
    "Contract Signed",
    "Funded",
]

FUNNEL_COLS = {
    "Full App Submitted": "full_app_submitted",
    "UW Decisioned": "uw_decisioned",
    "UW Approved": "uw_approved",
    "Contract Signed": "contract_signed",
    "Funded": "funded",
}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading data …")
def load_parquet(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df.columns = [c.lower() for c in df.columns]
    return _normalise(df)


def load_upload(upload) -> pd.DataFrame:
    if upload.name.endswith(".csv"):
        df = pd.read_csv(upload)
    else:
        df = pd.read_parquet(upload)
    df.columns = [c.lower() for c in df.columns]
    return _normalise(df)


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    if "product_line" in df.columns:
        df["product_line"] = df["product_line"].astype(str).str.strip().str.upper()
    if "created_datetime" in df.columns:
        df["created_datetime"] = pd.to_datetime(df["created_datetime"], errors="coerce")
        df["created_date"] = df["created_datetime"].dt.date
    for col in ("flag_eligible_lead",):
        if col in df.columns:
            df[col] = df[col].astype(bool)
    for col in FUNNEL_COLS.values():
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    for col in ("funded_volume", "origination_dollars", "final_loan_amount"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def _fmt_dollar(val: float) -> str:
    if val >= 1e9:
        return f"${val / 1e9:,.2f}B"
    if val >= 1e6:
        return f"${val / 1e6:,.2f}M"
    if val >= 1e3:
        return f"${val / 1e3:,.1f}K"
    return f"${val:,.0f}"


def _fmt_pct(val: float) -> str:
    return f"{val:.1f}%"


def _pct(num: int | float, den: int | float) -> float:
    return (num / den * 100) if den else 0.0


# ---------------------------------------------------------------------------
# Build funnel summary
# ---------------------------------------------------------------------------
def build_funnel(df: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame with one row per funnel step and columns for each product line + total."""
    product_lines = sorted(df["product_line"].dropna().unique())

    rows: list[dict[str, Any]] = []
    for step in FUNNEL_STEPS_ORDERED:
        row: dict[str, Any] = {"Step": step}
        if step == "Leads":
            total = len(df)
            for pl in product_lines:
                row[pl] = int((df["product_line"] == pl).sum())
        else:
            col = FUNNEL_COLS[step]
            total = int(df[col].sum())
            for pl in product_lines:
                row[pl] = int(df.loc[df["product_line"] == pl, col].sum())
        row["Total"] = total
        rows.append(row)

    return pd.DataFrame(rows)


def build_conversion_table(funnel_df: pd.DataFrame) -> pd.DataFrame:
    """Step-over-step and step-over-leads conversion rates."""
    cols = [c for c in funnel_df.columns if c != "Step"]
    records = []
    for i, step in enumerate(funnel_df["Step"]):
        rec: dict[str, Any] = {"Step": step}
        for c in cols:
            curr = funnel_df.iloc[i][c]
            leads = funnel_df.iloc[0][c]
            prev = funnel_df.iloc[i - 1][c] if i > 0 else leads
            rec[f"{c} (vs Leads)"] = _fmt_pct(_pct(curr, leads))
            rec[f"{c} (vs Prev)"] = _fmt_pct(_pct(curr, prev)) if i > 0 else "—"
        records.append(rec)
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def funnel_bar_chart(funnel_df: pd.DataFrame) -> go.Figure:
    product_lines = [c for c in funnel_df.columns if c not in ("Step", "Total")]

    fig = go.Figure()
    for pl in product_lines:
        fig.add_trace(
            go.Bar(
                x=funnel_df["Step"],
                y=funnel_df[pl],
                name=pl,
                marker_color=PRODUCT_LINE_COLORS.get(pl, "#888"),
                text=funnel_df[pl].apply(lambda v: f"{v:,}"),
                textposition="outside",
            )
        )

    fig.update_layout(
        barmode="group",
        title=dict(text="Funnel Volume by Product Line", font_size=18),
        xaxis_title="Funnel Step",
        yaxis_title="Applications",
        legend_title="Product Line",
        template="plotly_white",
        height=480,
        margin=dict(t=60, b=40),
    )
    return fig


def funnel_conversion_chart(funnel_df: pd.DataFrame) -> go.Figure:
    product_lines = [c for c in funnel_df.columns if c not in ("Step", "Total")]
    fig = go.Figure()
    for pl in product_lines:
        leads = funnel_df.iloc[0][pl]
        rates = [_pct(funnel_df.iloc[i][pl], leads) for i in range(len(funnel_df))]
        fig.add_trace(
            go.Scatter(
                x=funnel_df["Step"],
                y=rates,
                mode="lines+markers+text",
                name=pl,
                line=dict(color=PRODUCT_LINE_COLORS.get(pl, "#888"), width=2.5),
                marker=dict(size=8),
                text=[f"{r:.1f}%" for r in rates],
                textposition="top center",
            )
        )

    fig.update_layout(
        title=dict(text="Lead-to-Step Conversion Rate (%)", font_size=18),
        xaxis_title="Funnel Step",
        yaxis_title="% of Leads",
        legend_title="Product Line",
        template="plotly_white",
        height=420,
        margin=dict(t=60, b=40),
    )
    return fig


def origination_bar_chart(df: pd.DataFrame) -> go.Figure:
    agg = (
        df.groupby("product_line", as_index=False)["origination_dollars"]
        .sum()
        .sort_values("origination_dollars", ascending=False)
    )
    fig = px.bar(
        agg,
        x="product_line",
        y="origination_dollars",
        color="product_line",
        color_discrete_map=PRODUCT_LINE_COLORS,
        text=agg["origination_dollars"].apply(_fmt_dollar),
        title="Origination Dollars by Product Line",
        labels={"product_line": "Product Line", "origination_dollars": "Origination $"},
    )
    fig.update_layout(
        template="plotly_white",
        showlegend=False,
        height=400,
        margin=dict(t=50, b=40),
    )
    fig.update_traces(textposition="outside")
    return fig


def fico_distribution_chart(df: pd.DataFrame) -> go.Figure:
    order = ["FICO <640", "FICO 640-699", "FICO 700+", "Unknown"]
    fico_agg = (
        df.groupby(["fico_band", "product_line"], as_index=False)
        .agg(count=("application_key", "count"))
    )
    fico_agg["fico_band"] = pd.Categorical(fico_agg["fico_band"], categories=order, ordered=True)
    fico_agg = fico_agg.sort_values("fico_band")

    fig = px.bar(
        fico_agg,
        x="fico_band",
        y="count",
        color="product_line",
        barmode="group",
        color_discrete_map=PRODUCT_LINE_COLORS,
        title="FICO Band Distribution",
        labels={"fico_band": "FICO Band", "count": "Applications", "product_line": "Product Line"},
    )
    fig.update_layout(template="plotly_white", height=400, margin=dict(t=50, b=40))
    return fig


def daily_trend_chart(df: pd.DataFrame) -> go.Figure:
    daily = (
        df.groupby(["created_date", "product_line"], as_index=False)
        .agg(leads=("application_key", "count"), funded=("funded", "sum"))
    )
    fig = go.Figure()
    for pl in sorted(daily["product_line"].unique()):
        sub = daily[daily["product_line"] == pl].sort_values("created_date")
        fig.add_trace(
            go.Scatter(
                x=sub["created_date"],
                y=sub["leads"],
                name=f"{pl} — Leads",
                mode="lines",
                line=dict(color=PRODUCT_LINE_COLORS.get(pl, "#888"), width=2),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=sub["created_date"],
                y=sub["funded"],
                name=f"{pl} — Funded",
                mode="lines",
                line=dict(color=PRODUCT_LINE_COLORS.get(pl, "#888"), width=2, dash="dot"),
            )
        )

    fig.update_layout(
        title=dict(text="Daily Leads & Funded Applications", font_size=18),
        xaxis_title="Date",
        yaxis_title="Count",
        legend_title="Product Line",
        template="plotly_white",
        height=420,
        margin=dict(t=60, b=40),
    )
    return fig


def pagaya_segment_chart(df: pd.DataFrame) -> go.Figure:
    pag = df[df["product_line"] == "PAGAYA"].copy()
    if pag.empty:
        fig = go.Figure()
        fig.add_annotation(text="No Pagaya data in current selection", showarrow=False, font_size=14)
        fig.update_layout(height=400)
        return fig

    seg_agg = (
        pag.groupby("pagaya_entry_segment", as_index=False)
        .agg(
            leads=("application_key", "count"),
            funded=("funded", "sum"),
            volume=("origination_dollars", "sum"),
        )
    )
    seg_order = ["PQ entry", "FA entry", "PQ + FA", "Unknown"]
    seg_agg["pagaya_entry_segment"] = pd.Categorical(
        seg_agg["pagaya_entry_segment"], categories=seg_order, ordered=True
    )
    seg_agg = seg_agg.sort_values("pagaya_entry_segment")

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=seg_agg["pagaya_entry_segment"],
            y=seg_agg["leads"],
            name="Leads",
            marker_color="#e67e22",
            text=seg_agg["leads"].apply(lambda v: f"{v:,}"),
            textposition="outside",
        )
    )
    fig.add_trace(
        go.Bar(
            x=seg_agg["pagaya_entry_segment"],
            y=seg_agg["funded"],
            name="Funded",
            marker_color="#d35400",
            text=seg_agg["funded"].apply(lambda v: f"{v:,}"),
            textposition="outside",
        )
    )
    fig.update_layout(
        barmode="group",
        title=dict(text="Pagaya Entry Segment — Leads vs Funded", font_size=18),
        xaxis_title="Pagaya Entry Segment",
        yaxis_title="Count",
        template="plotly_white",
        height=420,
        margin=dict(t=60, b=40),
    )
    return fig


def pagaya_segment_funnel_chart(df: pd.DataFrame) -> go.Figure:
    pag = df[df["product_line"] == "PAGAYA"].copy()
    if pag.empty:
        fig = go.Figure()
        fig.add_annotation(text="No Pagaya data in current selection", showarrow=False, font_size=14)
        fig.update_layout(height=400)
        return fig

    seg_order = ["PQ entry", "FA entry", "PQ + FA", "Unknown"]
    seg_colors = {"PQ entry": "#e67e22", "FA entry": "#2980b9", "PQ + FA": "#8e44ad", "Unknown": "#95a5a6"}

    fig = go.Figure()
    for seg in seg_order:
        sub = pag[pag["pagaya_entry_segment"] == seg]
        if sub.empty:
            continue
        counts = [len(sub)]
        for step_col in FUNNEL_COLS.values():
            counts.append(int(sub[step_col].sum()))
        fig.add_trace(
            go.Scatter(
                x=FUNNEL_STEPS_ORDERED,
                y=[_pct(c, counts[0]) for c in counts],
                mode="lines+markers",
                name=seg,
                line=dict(color=seg_colors.get(seg, "#888"), width=2.5),
                marker=dict(size=7),
            )
        )

    fig.update_layout(
        title=dict(text="Pagaya Conversion Curves by Entry Segment", font_size=18),
        xaxis_title="Funnel Step",
        yaxis_title="% of Leads",
        template="plotly_white",
        height=420,
        margin=dict(t=60, b=40),
    )
    return fig


def fico_funnel_chart(df: pd.DataFrame) -> go.Figure:
    fico_order = ["FICO <640", "FICO 640-699", "FICO 700+", "Unknown"]
    fico_colors = {"FICO <640": "#e74c3c", "FICO 640-699": "#f39c12", "FICO 700+": "#27ae60", "Unknown": "#95a5a6"}

    fig = go.Figure()
    for band in fico_order:
        sub = df[df["fico_band"] == band]
        if sub.empty:
            continue
        counts = [len(sub)]
        for step_col in FUNNEL_COLS.values():
            counts.append(int(sub[step_col].sum()))
        fig.add_trace(
            go.Scatter(
                x=FUNNEL_STEPS_ORDERED,
                y=[_pct(c, counts[0]) for c in counts],
                mode="lines+markers",
                name=band,
                line=dict(color=fico_colors.get(band, "#888"), width=2.5),
                marker=dict(size=7),
            )
        )

    fig.update_layout(
        title=dict(text="Funnel Conversion by FICO Band", font_size=18),
        xaxis_title="Funnel Step",
        yaxis_title="% of Leads",
        template="plotly_white",
        height=420,
        margin=dict(t=60, b=40),
    )
    return fig


# ---------------------------------------------------------------------------
# Sidebar + data loading
# ---------------------------------------------------------------------------
def sidebar_and_data() -> pd.DataFrame | None:
    st.sidebar.markdown("## 📊 APL Trifurcated Funnel")
    st.sidebar.markdown("---")

    upload = st.sidebar.file_uploader(
        "Upload Parquet / CSV",
        type=["parquet", "csv"],
        help="Override the default data/apl_trifurcated_funnel.parquet",
    )

    if upload is not None:
        df = load_upload(upload)
    elif PARQUET_PATH.exists():
        df = load_parquet(str(PARQUET_PATH))
    else:
        st.sidebar.warning(
            "No data found. Run `run_apl_trifurcated_funnel.py` first or upload a file."
        )
        return None

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Filters")

    all_pl = sorted(df["product_line"].dropna().unique())
    selected_pl = st.sidebar.multiselect(
        "Product Line",
        options=all_pl,
        default=all_pl,
    )
    if not selected_pl:
        selected_pl = all_pl

    eligible_only = False
    if "flag_eligible_lead" in df.columns:
        eligible_only = st.sidebar.checkbox("Eligible leads only", value=False)

    if "created_date" in df.columns and not df["created_date"].isna().all():
        min_dt = df["created_date"].min()
        max_dt = df["created_date"].max()
        date_range = st.sidebar.date_input(
            "Cohort date range",
            value=(min_dt, max_dt),
            min_value=min_dt,
            max_value=max_dt,
        )
    else:
        date_range = None

    if "fico_band" in df.columns:
        all_fico = sorted(df["fico_band"].dropna().unique())
        selected_fico = st.sidebar.multiselect("FICO Band", options=all_fico, default=all_fico)
    else:
        selected_fico = None

    mask = df["product_line"].isin(selected_pl)
    if eligible_only:
        mask &= df["flag_eligible_lead"] == True  # noqa: E712
    if date_range and len(date_range) == 2:
        mask &= df["created_date"] >= date_range[0]
        mask &= df["created_date"] <= date_range[1]
    if selected_fico:
        mask &= df["fico_band"].isin(selected_fico)

    filtered = df[mask].copy()

    st.sidebar.markdown("---")
    st.sidebar.metric("Rows loaded", f"{len(df):,}")
    st.sidebar.metric("After filters", f"{len(filtered):,}")

    return filtered


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    df = sidebar_and_data()

    st.markdown("# APL Trifurcated Funnel Dashboard")
    st.markdown(
        "Unified funnel view across **Core**, **Pagaya**, and **Superprime** product lines.  "
        "Use the sidebar to filter by product line, date range, FICO band, and eligibility flag."
    )

    if df is None or df.empty:
        st.info("No data to display. Adjust filters or upload a data file.")
        return

    # ----- KPI row -----
    total_leads = len(df)
    total_funded = int(df["funded"].sum())
    total_volume = df["origination_dollars"].sum()
    overall_conv = _pct(total_funded, total_leads)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Leads", f"{total_leads:,}")
    k2.metric("Funded Loans", f"{total_funded:,}")
    k3.metric("Origination $", _fmt_dollar(total_volume))
    k4.metric("Lead → Funded %", _fmt_pct(overall_conv))

    # ----- View 1 : Overall Funnel -----
    st.markdown("---")
    st.markdown("## View 1 — Overall Funnel")

    funnel_df = build_funnel(df)

    col_chart, col_conv = st.columns(2)
    with col_chart:
        st.plotly_chart(funnel_bar_chart(funnel_df), use_container_width=True)
    with col_conv:
        st.plotly_chart(funnel_conversion_chart(funnel_df), use_container_width=True)

    with st.expander("Funnel volume table", expanded=True):
        st.dataframe(
            funnel_df.style.format(
                {c: "{:,.0f}" for c in funnel_df.columns if c != "Step"}
            ),
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("Conversion rate table"):
        conv_df = build_conversion_table(funnel_df)
        st.dataframe(conv_df, use_container_width=True, hide_index=True)

    # ----- Origination + FICO -----
    st.markdown("---")
    col_orig, col_fico = st.columns(2)
    with col_orig:
        st.plotly_chart(origination_bar_chart(df), use_container_width=True)
    with col_fico:
        st.plotly_chart(fico_distribution_chart(df), use_container_width=True)

    # ----- FICO funnel -----
    st.plotly_chart(fico_funnel_chart(df), use_container_width=True)

    # ----- Daily trend -----
    if "created_date" in df.columns:
        st.markdown("---")
        st.markdown("## Daily Trend")
        st.plotly_chart(daily_trend_chart(df), use_container_width=True)

    # ----- View 2 : Pagaya Deep-Dive -----
    st.markdown("---")
    st.markdown("## View 2 — Pagaya Entry Segment Deep-Dive")
    st.markdown(
        "Breaks down Pagaya applications by **entry segment** (PQ entry, FA entry, PQ + FA) "
        "to compare funnel performance across origination channels."
    )

    pag = df[df["product_line"] == "PAGAYA"]
    if pag.empty:
        st.info("No Pagaya data in current selection.")
    else:
        seg_k1, seg_k2, seg_k3 = st.columns(3)
        seg_k1.metric("Pagaya Leads", f"{len(pag):,}")
        seg_k2.metric("Pagaya Funded", f"{int(pag['funded'].sum()):,}")
        seg_k3.metric(
            "Pagaya Origination $",
            _fmt_dollar(pag["origination_dollars"].sum()),
        )

        col_seg1, col_seg2 = st.columns(2)
        with col_seg1:
            st.plotly_chart(pagaya_segment_chart(df), use_container_width=True)
        with col_seg2:
            st.plotly_chart(pagaya_segment_funnel_chart(df), use_container_width=True)

        with st.expander("Pagaya segment detail table"):
            seg_tbl = (
                pag.groupby("pagaya_entry_segment", as_index=False)
                .agg(
                    Leads=("application_key", "count"),
                    Full_App=("full_app_submitted", "sum"),
                    UW_Decisioned=("uw_decisioned", "sum"),
                    UW_Approved=("uw_approved", "sum"),
                    Contract_Signed=("contract_signed", "sum"),
                    Funded=("funded", "sum"),
                    Volume=("origination_dollars", "sum"),
                )
            )
            seg_tbl["Lead→Funded %"] = seg_tbl.apply(
                lambda r: _fmt_pct(_pct(r["Funded"], r["Leads"])), axis=1
            )
            seg_tbl["Volume"] = seg_tbl["Volume"].apply(_fmt_dollar)
            st.dataframe(seg_tbl, use_container_width=True, hide_index=True)

    # ----- Raw data preview -----
    st.markdown("---")
    with st.expander("Raw data preview (first 500 rows)"):
        st.dataframe(df.head(500), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
