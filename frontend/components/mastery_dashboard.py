"""
User Mastery Level dashboard for the My Profile page.

Renders unconditionally from whatever the backend's /api/quiz/mastery-summary
endpoint returns - including the "never taken a quiz" default state - so this
component never needs to know how mastery is computed. If the inference
algorithm behind that endpoint changes later, nothing here has to change.
"""

from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.quiz_api import get_mastery_summary

STATUS_COLORS = {
    "Mastered": "#0ca30c",
    "Remedial": "#d03b3b",
}


def _format_date(iso_date: str) -> str:
    if not iso_date:
        return "Never"
    try:
        return datetime.fromisoformat(iso_date).strftime("%b %d, %Y %H:%M")
    except ValueError:
        return iso_date


def render_mastery_dashboard():
    """Render the mastery-level dashboard section of My Profile."""
    summary = get_mastery_summary()

    if not summary.get("success"):
        st.error(f"Failed to load mastery dashboard: {summary.get('error', 'Unknown error')}")
        return

    units = summary.get("units", [])
    current_status = summary.get("current_status", "FAIL")
    total_attempts = summary.get("total_attempts", 0)
    latest_attempt_date = summary.get("latest_attempt_date")

    # --- Stat tiles ---------------------------------------------------
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            label="Current Status",
            value=current_status,
            help="PASS requires all six units to be Mastered"
        )
    with col2:
        st.metric(
            label="Total Quiz Attempts",
            value=total_attempts,
            help="Number of quizzes you have completed"
        )
    with col3:
        st.metric(
            label="Latest Quiz Date",
            value=_format_date(latest_attempt_date),
            help="Date of your most recent completed quiz"
        )

    if not units:
        return

    df = pd.DataFrame(units)

    st.markdown("")
    chart_col1, chart_col2 = st.columns(2)

    # --- Pie chart: Mastered vs Remedial -------------------------------
    with chart_col1:
        st.markdown("###### Mastered vs Remedial")
        status_counts = (
            df["mastery_status"]
            .value_counts()
            .reindex(["Mastered", "Remedial"], fill_value=0)
            .reset_index()
        )
        status_counts.columns = ["mastery_status", "count"]

        pie_fig = px.pie(
            status_counts,
            names="mastery_status",
            values="count",
            color="mastery_status",
            color_discrete_map=STATUS_COLORS,
            hole=0.4,
        )
        pie_fig.update_traces(textinfo="label+value", hovertemplate="%{label}: %{value} units")
        pie_fig.update_layout(
            showlegend=True,
            legend_title_text="",
            margin=dict(t=10, b=10, l=10, r=10),
        )
        st.plotly_chart(pie_fig, use_container_width=True)

    # --- Bar chart: unit score distribution -----------------------------
    with chart_col2:
        st.markdown("###### Unit Score Distribution")
        bar_fig = px.bar(
            df,
            x="unit_code",
            y="unit_score",
            color="mastery_status",
            color_discrete_map=STATUS_COLORS,
            text="unit_score",
        )
        bar_fig.update_traces(textposition="outside", cliponaxis=False)
        bar_fig.update_layout(
            yaxis=dict(title="Score", range=[0, 21], gridcolor="#e1e0d9"),
            xaxis=dict(title="Unit Code"),
            legend_title_text="",
            margin=dict(t=10, b=10, l=10, r=10),
        )
        st.plotly_chart(bar_fig, use_container_width=True)

    # --- Table -----------------------------------------------------------
    st.markdown("###### Unit Mastery Detail")
    table_df = df.rename(columns={
        "unit_code": "Unit Code",
        "unit_mastery_level": "Knowledge Level",
        "target_level": "Target Level",
        "mastery_status": "Status",
    })[["Unit Code", "Knowledge Level", "Target Level", "Status"]]
    table_df["Knowledge Level"] = table_df["Knowledge Level"].fillna("-")

    st.dataframe(table_df, use_container_width=True, hide_index=True)
