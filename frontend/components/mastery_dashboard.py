"""
My Profile dashboard: Test Analytics + Practice Analytics.

Test Analytics renders unconditionally from whatever the backend's
/api/quiz/mastery-summary endpoint returns - including the "never taken a
test" default state - so this component never needs to know how mastery is
computed. If the inference algorithm behind that endpoint changes later,
nothing here has to change.

Practice Analytics is backed by /api/practice/analytics (total completed
sessions + a per-unit Knowledge Level snapshot for each session - see
backend/services/practice_service.py::get_practice_analytics). It never
reads from quiz_attempts/user_mastery_level - Test remains the sole source
of mastery truth; this section only visualizes Practice's own history.
"""

from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.quiz_api import get_mastery_summary, get_unit_code_map, get_test_analytics
from utils.practice_api import get_practice_analytics
from utils.theme import SUCCESS, PRIMARY, TEXT, BORDER

# Charts use the brand palette's success/primary colors so status coloring
# stays consistent with the rest of the UI (see utils/theme.py)
STATUS_COLORS = {
    "Mastered": SUCCESS,
    "Remedial": PRIMARY,
}

CHART_LAYOUT_DEFAULTS = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="-apple-system, Segoe UI, Roboto, sans-serif", color=TEXT),
)

# Matches services/mastery_inference.py::BLOOM_LEVELS - kept as a small local
# mapping since the frontend never imports backend modules directly.
BLOOM_LEVELS = ["C1", "C2", "C3", "C4", "C5", "C6"]


def _level_rank(level) -> int:
    """Ordinal rank of a Bloom level (C1=1 ... C6=6); 0 if unset/unrecognized."""
    if not level:
        return 0
    try:
        return BLOOM_LEVELS.index(str(level).upper()) + 1
    except ValueError:
        return 0


def _format_date(iso_date: str) -> str:
    if not iso_date:
        return "Never"
    try:
        return datetime.fromisoformat(iso_date).strftime("%d-%m-%Y")
    except ValueError:
        return iso_date


def _get_code_map() -> dict:
    """Truncated -> full unit_code map (see utils/quiz_api.py::get_unit_code_map). Falls back to
    an empty map on failure so callers can always .get(code, code) without special-casing errors."""
    result = get_unit_code_map()
    return result.get("unit_codes", {}) if result.get("success") else {}


def render_mastery_dashboard():
    """Render the My Profile dashboard: Test Analytics + Practice Analytics."""
    code_map = _get_code_map()

    with st.container(border=True):
        _render_test_analytics(code_map)

    # st.markdown("")

    # with st.container(border=True):
    #     _render_practice_analytics(code_map)


def _render_test_analytics(code_map: dict):
    """
    Test Analytics, split by stage: a Pre-Test tab and a Post-Test tab, each
    showing that stage's status/date/score, Mastered vs Remedial, per-unit
    Knowledge Level, and unit table. The per-stage rendering
    (_render_stage_analytics) is identical for both, so the two stages stay
    directly comparable and the existing chart/table structure is preserved.
    """
    st.markdown("#### 📊 Data Analytics")

    analytics = get_test_analytics()
    if not analytics.get("success"):
        st.error(f"Failed to load Test Analytics: {analytics.get('error', 'Unknown error')}")
        return

    stages = analytics.get("stages", {}) or {}
    pre_data = stages.get("pre")
    post_data = stages.get("post")
    # practice_data = stages.get("practice")

    tab_pre, tab_practice, tab_post = st.tabs(["Pre-Test", "Practice", "Post-Test"])
    with tab_pre:
        if pre_data:
            _render_stage_analytics(pre_data, code_map, key_prefix="pre")
        else:
            st.info("You haven't taken your Pre-Test yet. Head to the Test page to begin.")
    with tab_practice:
        _render_practice_analytics(code_map)
    with tab_post:
        if post_data:
            _render_stage_analytics(post_data, code_map, key_prefix="post")
        else:
            st.info(
                "You haven't taken your Post-Test yet. It unlocks once you've cleared "
                "every Practice recommendation (all units at their target Knowledge Level)."
            )


def _render_stage_analytics(stage_data: dict, code_map: dict, key_prefix: str):
    """Render one Test stage's analytics: status/date/score tiles, Mastered vs
    Remedial pie, per-unit Knowledge Level bar, and the unit summary table."""
    units = stage_data.get("units", [])
    status = stage_data.get("status", "FAIL")
    completed_at = stage_data.get("completed_at")
    score = stage_data.get("score", 0)

    # --- Stat tiles ---------------------------------------------------
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            label="Status",
            value=status,
            help="PASS requires all six units to be Mastered"
        )
    with col2:
        st.metric(
            label="Date",
            value=_format_date(completed_at),
            help="Date you completed this Test stage"
        )
    with col3:
        st.metric(
            label="Total Points",
            value=f"{score:g}" if isinstance(score, (int, float)) else score,
            help="Total points scored on this Test stage"
        )

    if not units:
        return

    df = pd.DataFrame(units)
    df["full_unit_code"] = df["unit_code"].map(lambda c: code_map.get(c, c))

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
            **CHART_LAYOUT_DEFAULTS,
        )
        st.plotly_chart(pie_fig, use_container_width=True, key=f"{key_prefix}_pie")

    # --- Bar chart: per-unit Knowledge Level ----------------------------
    with chart_col2:
        st.markdown("###### Per-Unit Knowledge Level")
        df["level_rank"] = df["unit_mastery_level"].apply(_level_rank)
        df["level_label"] = df["unit_mastery_level"].fillna("-")

        bar_fig = px.bar(
            df,
            x="full_unit_code",
            y="level_rank",
            color="mastery_status",
            color_discrete_map=STATUS_COLORS,
            text="level_label",
        )
        bar_fig.update_traces(textposition="outside", cliponaxis=False)
        bar_fig.update_layout(
            yaxis=dict(
                title="Knowledge Level",
                tickmode="array",
                tickvals=[0, 1, 2, 3, 4, 5, 6],
                ticktext=["-"] + BLOOM_LEVELS,
                range=[0, 6.8],
                gridcolor=BORDER,
            ),
            xaxis=dict(title="Unit Code"),
            legend_title_text="",
            margin=dict(t=10, b=10, l=10, r=10),
            **CHART_LAYOUT_DEFAULTS,
        )
        st.plotly_chart(bar_fig, use_container_width=True, key=f"{key_prefix}_bar")

    # --- Table -----------------------------------------------------------
    st.markdown("###### Unit Summary")
    table_df = df.rename(columns={
        "full_unit_code": "Unit",
        "unit_mastery_level": "Knowledge Level",
        "target_level": "Target",
        "mastery_status": "Status",
    })[["Unit", "Knowledge Level", "Target", "Status"]]
    table_df["Knowledge Level"] = table_df["Knowledge Level"].fillna("-")

    st.dataframe(table_df, use_container_width=True, hide_index=True, key=f"{key_prefix}_table")


def _render_practice_analytics(code_map: dict):
    """Practice Analytics: total sessions, current recommended unit(s), Knowledge Level progression."""
    # st.markdown("#### 📝 Practice Analytics")

    analytics = get_practice_analytics()
    if not analytics.get("success"):
        st.error(f"Failed to load Practice Analytics: {analytics.get('error', 'Unknown error')}")
        return

    mastery_summary = get_mastery_summary()
    # Units Remedial per the latest Test AND not yet demonstrated Mastered
    # in Practice since that Test (see MasteryService.get_effective_remedial_units) -
    # this is the SAME adaptive set Practice itself recommends from, so
    # "Currently recommended" here tracks the latest Practice result, not
    # just the Placement Test, once Practice sessions exist. Recommendations
    # only exist once a Test has synced real mastery data to the knowledge
    # graph, so gate on has_attempts to avoid showing a misleading count.
    recommended_units = (
        mastery_summary.get("effective_remedial_units", [])
        if mastery_summary.get("success") and mastery_summary.get("has_attempts") else []
    )
    # target_level per unit, for the Practice History Status column - same
    # rule as Test Analytics (see MasteryService: Mastered iff inferred
    # level >= target_level), applied here to each session's inferred level.
    target_by_unit = (
        {u["unit_code"]: u.get("target_level") for u in mastery_summary.get("units", [])}
        if mastery_summary.get("success") else {}
    )

    total_sessions = analytics.get("total_sessions", 0)
    progression = analytics.get("progression", [])

    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            label="Total Practice Sessions",
            value=total_sessions,
            help="Number of Practice sessions you have completed"
        )
    with col2:
        st.metric(
            label="Recommended Unit(s) for Practice",
            value=len(recommended_units),
            help="Units still Remedial after your latest Practice results (or your latest Test, before your first Practice session) - the same units Practice questions are sourced from"
        )

    
    if recommended_units:
        full_recommended = [code_map.get(c, c) for c in recommended_units]
        st.info("Currently recommended: " + ", ".join(full_recommended))
    else:
        st.info("All units Mastered - nothing currently recommended for Practice.")

    if not progression:
        st.info("No Practice sessions yet. Complete a Practice session to see your progression here.")
        return

    st.markdown("")
    st.markdown("###### Knowledge Level Progression")

    df = pd.DataFrame(progression)
    df["completed_at"] = pd.to_datetime(df["completed_at"])
    df["full_unit_code"] = df["unit_code"].map(lambda c: code_map.get(c, c))
    df = df.sort_values("completed_at")

    line_fig = px.line(
        df,
        x="completed_at",
        y="level_rank",
        color="full_unit_code",
        markers=True,
    )
    line_fig.update_layout(
        yaxis=dict(
            title="Knowledge Level",
            tickmode="array",
            tickvals=[1, 2, 3, 4, 5, 6],
            ticktext=BLOOM_LEVELS,
            range=[0.5, 6.5],
            gridcolor=BORDER,
        ),
        xaxis=dict(title="Practice Session Date"),
        legend_title_text="Unit",
        margin=dict(t=10, b=10, l=10, r=10),
        **CHART_LAYOUT_DEFAULTS,
    )
    st.plotly_chart(line_fig, use_container_width=True)

    # --- Table: Practice History -----------------------------------------
    st.markdown("")
    st.markdown("###### Practice History")

    history_df = df.copy()

    # Exercises Number: 1-based ordinal of each distinct Practice session in
    # chronological order - units practiced in the same session share the
    # same number (mirrors Test History's "Attempt N" numbering).
    session_order = {ts: i + 1 for i, ts in enumerate(sorted(history_df["completed_at"].unique()))}
    history_df["session_number"] = history_df["completed_at"].map(session_order)

    # Previous Level: this unit's level the last time it was practiced
    # before this session (chronological shift within each unit's own history).
    history_df = history_df.sort_values(["unit_code", "completed_at"])
    history_df["previous_level"] = history_df.groupby("unit_code")["unit_mastery_level"].shift(1)
    history_df["previous_rank"] = history_df.groupby("unit_code")["level_rank"].shift(1)

    def _progress(row):
        if pd.isna(row["previous_rank"]):
            return "New"
        if row["level_rank"] > row["previous_rank"]:
            return "Improved"
        if row["level_rank"] < row["previous_rank"]:
            return "Declined"
        return "No Change"

    history_df["progress"] = history_df.apply(_progress, axis=1)
    history_df["previous_level"] = history_df["previous_level"].fillna("-")

    # Status: same rule as Test Analytics - Mastered iff this session's
    # inferred Knowledge Level meets or exceeds the unit's configured target.
    def _mastery_status(row):
        target = target_by_unit.get(row["unit_code"])
        if not target:
            return "-"
        return "Mastered" if row["level_rank"] >= _level_rank(target) else "Remedial"

    history_df["mastery_status"] = history_df.apply(_mastery_status, axis=1)

    history_df = history_df.sort_values(["completed_at", "unit_code"], ascending=[False, True])

    table_df = history_df.rename(columns={
        "completed_at": "Date",
        "session_number": "Exercises Number",
        "full_unit_code": "Unit",
        "previous_level": "Previous Level",
        "unit_mastery_level": "Current Level",
        "mastery_status": "Status",
        "progress": "Progress",
    })[["Date", "Exercises Number", "Unit", "Previous Level", "Current Level", "Status", "Progress"]]
    table_df["Date"] = table_df["Date"].dt.strftime("%d-%m-%Y %H:%M")

    st.dataframe(table_df, use_container_width=True, hide_index=True)
