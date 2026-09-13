"""
Data Analytics + Engagement pages - the performance/behavioral dashboards
that used to live under My Profile before it became a pure account-identity
page (see components/user_profile.py). Two public entry points:

  - render_data_analytics(): the proactive nudge banner + Test Analytics
    (Pre-Test/Practice/Post-Test tabs).
  - render_engagement(): Behavioral and Engagement Tracking, standalone
    (badges, peer benchmark, streaks, recent activity).

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
from utils.practice_api import get_practice_analytics, get_learning_path_stats
from utils.theme import SUCCESS, ACCENT, PRIMARY, TEXT, BORDER

# Charts use the brand palette's success/accent colors so status coloring
# stays consistent with the rest of the UI (see utils/theme.py). Remedial
# uses ACCENT rather than PRIMARY - PRIMARY is the navy brand/nav color now,
# not an attention color, so it no longer reads as "needs work" next to
# Mastered's green the way the old red PRIMARY did.
STATUS_COLORS = {
    "Mastered": SUCCESS,
    "Remedial": ACCENT,
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


def render_data_analytics():
    """Render the Data Analytics page: Test Analytics (Pre-Test/Practice/
    Post-Test). The nudge banner that used to open this page now lives on
    My Profile's Overview tab instead - see render_nudge_banner below and
    components/user_profile.py."""
    code_map = _get_code_map()

    with st.container(border=True):
        _render_test_analytics(code_map)


def render_engagement():
    """Render the Engagement page, standalone (it used to be a 4th tab
    inside Data Analytics - now its own menu entry, see
    pages/learner_profile.py)."""
    code_map = _get_code_map()
    with st.container(border=True):
        st.markdown("#### 📈 Engagement")
        _render_engagement_analytics(code_map)


def render_nudge_banner():
    """
    One context-aware banner - the first thing a user sees on login, on My
    Profile's Overview tab (see components/user_profile.py; My Profile is
    the post-login landing page, pages/learner_profile.py). Picks the
    single most relevant message instead of stacking several:

      1. Never done anything substantive yet -> point them at a first step.
      2. Away for a few days -> welcome back + resume prompt.
      3. Still has Remedial units -> nudge toward Practice.
      4. Otherwise (recently active, nothing Remedial) -> quiet positive
         reinforcement of their streak, or nothing at all with no streak.

    Deliberately measures "last substantive activity" from Materials/
    Chatbot/Practice/Test timestamps, NOT last_active_date/login - logging
    in to view this very page always counts as "active today" (see
    services/learning_path_stats_service.py::ACTIVITY_LOGIN), so a
    login-based signal would never actually detect a gap.
    """
    stats = get_learning_path_stats()
    if not stats.get("success"):
        return  # nudges are a nice-to-have; never block the dashboard on this

    substantive_dates = [
        stats.get("latest_material_activity"),
        stats.get("latest_chatbot_interaction"),
        stats.get("latest_practice_interaction"),
        stats.get("latest_test_interaction"),
    ]
    substantive_dates = [d for d in substantive_dates if d]

    remedial_units = stats.get("remedial_units", 0)

    if not substantive_dates:
        st.info(
            "👋 **Welcome!** Get started with a **Placement Test**, or browse **Reading Materials** "
            "for a quick first look."
        )
        return

    days_since = (datetime.now() - max(datetime.fromisoformat(d) for d in substantive_dates)).days

    if days_since >= 3:
        st.warning(
            f"⏰ It's been **{days_since} days** since your last study session. "
            + (
                f"You still have **{remedial_units} unit(s)** to master - jump back into Practice or Reading Materials."
                if remedial_units else "Come back and keep your momentum going!"
            )
        )
    elif remedial_units > 0:
        st.info(
            f"🎯 You have **{remedial_units} unit(s)** still Remedial. "
            "Keep practicing to move them to Mastered."
        )
    else:
        streak = stats.get("current_streak_days", 0)
        if streak >= 2:
            st.success(f"🔥 **{streak}-day streak!** All units Mastered and still going - great consistency.")


def _render_test_analytics(code_map: dict):
    """
    Test Analytics, split by stage: a Pre-Test tab and a Post-Test tab, each
    showing that stage's status/date/score, Mastered vs Remedial, per-unit
    Knowledge Level, and unit table. The per-stage rendering
    (_render_stage_analytics) is identical for both, so the two stages stay
    directly comparable and the existing chart/table structure is preserved.
    """
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


def _render_engagement_analytics(code_map: dict):
    """
    Behavioral and Engagement Tracking: how consistently the user shows up
    (streaks, active days, recent activity, which learning methods they
    actually use) - deliberately separate from the Test/Practice tabs above,
    which are about performance (scores, mastery), not behavior.

    Backed by get_learning_path_stats() (see
    backend/services/learning_path_stats_service.py::_engagement_stats),
    which unifies the generic user_activity log (materials viewed, chatbot
    prompts, logins) with Practice/Test completion timestamps - no separate
    endpoint needed here.
    """
    stats = get_learning_path_stats()
    if not stats.get("success"):
        st.error(f"Failed to load Engagement stats: {stats.get('error', 'Unknown error')}")
        return

    st.caption("How consistently you're showing up to learn - separate from how well you're scoring.")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "Current Streak", f"{stats.get('current_streak_days', 0)}d",
            help="Consecutive days with at least one learning activity, up to today"
        )
    with col2:
        st.metric(
            "Longest Streak", f"{stats.get('longest_streak_days', 0)}d",
            help="Your longest-ever run of consecutive active days"
        )
    with col3:
        st.metric(
            "Active Days (30d)", stats.get("active_days_last_30", 0),
            help="Days with at least one activity in the last 30 days"
        )
    with col4:
        st.metric(
            "Last Active", _format_date(stats.get("last_active_date")),
            help="Most recent day you did anything countable (materials, chatbot, practice, test, or login)"
        )

    st.markdown("")
    st.markdown("###### Recent Activity (last 30 days)")
    daily = stats.get("daily_activity", [])
    if not daily:
        st.info("No activity recorded yet - browse a material, chat with the tutor, or start a Practice/Test session.")
    else:
        df = pd.DataFrame(daily)
        df["date"] = pd.to_datetime(df["date"])
        # Zero-fill every day in the window so gaps in activity show as
        # gaps in the chart, not as a shorter x-axis.
        full_range = pd.DataFrame({"date": pd.date_range(end=pd.Timestamp.today().normalize(), periods=30)})
        merged = full_range.merge(df, on="date", how="left").fillna(0)
        merged["count"] = merged["count"].astype(int)

        bar_fig = px.bar(merged, x="date", y="count")
        bar_fig.update_traces(marker_color=PRIMARY)
        bar_fig.update_layout(
            yaxis=dict(title="Activities", gridcolor=BORDER, dtick=1),
            xaxis=dict(title=""),
            margin=dict(t=10, b=10, l=10, r=10),
            **CHART_LAYOUT_DEFAULTS,
        )
        st.plotly_chart(bar_fig, use_container_width=True, key="engagement_daily_bar")

    st.markdown("")
    st.markdown("###### Activity Breakdown")
    breakdown = {
        "📄 Materials Viewed": stats.get("materials_viewed", 0),
        "💬 Chatbot Prompts": stats.get("chatbot_attempts", 0),
        "📝 Practice Sessions": stats.get("practice_sessions", 0),
        "📊 Test Attempts": stats.get("test_attempts", 0),
        "🔑 Logins": stats.get("logins", 0),
    }
    for col, (label, value) in zip(st.columns(len(breakdown)), breakdown.items()):
        with col:
            st.metric(label, value)

    st.markdown("")
    st.markdown("###### Badges")
    _render_badges(stats)

    st.markdown("")
    st.markdown("###### Peer Benchmark")
    _render_peer_benchmark(stats, code_map)


def _render_peer_benchmark(stats: dict, code_map: dict):
    """
    Anonymous peer comparison - the "Collaborative/Peer-Based
    Personalization" feature without any social surface: every learner's
    mastery folds into aggregate counts/percentages only, nobody's
    individual data is ever shown to anybody else (see
    LearningPathStatsService._peer_benchmark_stats).
    """
    total_learners = stats.get("peer_total_learners", 0)
    if total_learners < 2:
        st.info("Peer benchmarking unlocks once more learners have Test data to compare against.")
        return

    percentile = stats.get("peer_mastered_percentile")
    avg_mastered = stats.get("peer_avg_mastered_units", 0)
    my_mastered = stats.get("mastered_units", 0)

    st.markdown(
        f"You've mastered **{my_mastered}** unit(s) - at or ahead of **{percentile}%** of "
        f"**{total_learners}** learners who've taken a Test (peer average: **{avg_mastered}**)."
    )

    peer_pct = stats.get("peer_unit_mastery_pct") or {}
    if peer_pct:
        df = pd.DataFrame([
            {"Unit": code_map.get(code, code), "pct": pct}
            for code, pct in sorted(peer_pct.items())
        ])
        bar_fig = px.bar(df, x="Unit", y="pct")
        bar_fig.update_traces(marker_color=ACCENT)
        bar_fig.update_layout(
            yaxis=dict(title="% of peers Mastered", range=[0, 100], gridcolor=BORDER),
            xaxis=dict(title=""),
            margin=dict(t=10, b=10, l=10, r=10),
            **CHART_LAYOUT_DEFAULTS,
        )
        st.plotly_chart(bar_fig, use_container_width=True, key="peer_benchmark_bar")


def _badge_definitions(stats: dict) -> list:
    """
    Badge thresholds, each checked against a single monotonic counter
    already in the stats dict (longest_streak_days/mastered_units/*_viewed/
    *_attempts/active_days_total never decrease) - so "earned" is a pure,
    stable function of the current totals. No separate "badges earned"
    table needed: nothing to persist, nothing that can get out of sync.
    """
    mastered = stats.get("mastered_units", 0)
    total_units = stats.get("total_units", 0)
    longest_streak = stats.get("longest_streak_days", 0)

    return [
        {"icon": "🔥", "label": "3-Day Streak", "desc": "Reach a 3-day learning streak",
         "earned": longest_streak >= 3},
        {"icon": "🔥", "label": "7-Day Streak", "desc": "Reach a 7-day learning streak",
         "earned": longest_streak >= 7},
        {"icon": "🔥", "label": "30-Day Streak", "desc": "Reach a 30-day learning streak",
         "earned": longest_streak >= 30},
        {"icon": "🎯", "label": "First Mastery", "desc": "Master your first unit",
         "earned": mastered >= 1},
        {"icon": "🏆", "label": "All Units Mastered", "desc": "Master every unit",
         "earned": total_units > 0 and mastered >= total_units},
        {"icon": "📚", "label": "Curious Mind", "desc": "View 10 learning materials",
         "earned": stats.get("materials_viewed", 0) >= 10},
        {"icon": "💬", "label": "Chatty Learner", "desc": "Send 10 chatbot messages",
         "earned": stats.get("chatbot_attempts", 0) >= 10},
        {"icon": "📝", "label": "Practice Pro", "desc": "Complete 10 Practice sessions",
         "earned": stats.get("practice_sessions", 0) >= 10},
        {"icon": "🗓️", "label": "Committed Learner", "desc": "Be active on 10 different days",
         "earned": stats.get("active_days_total", 0) >= 10},
    ]


def _render_badges(stats: dict):
    """Grid of badge cards - earned ones in full color with an accent
    border, locked ones dimmed - see the .gm-badge-tile CSS in main.css."""
    badges = _badge_definitions(stats)
    earned_count = sum(1 for b in badges if b["earned"])
    st.caption(f"{earned_count} of {len(badges)} earned")

    cols = st.columns(3)
    for i, badge in enumerate(badges):
        state_class = "gm-badge-tile-earned" if badge["earned"] else "gm-badge-tile-locked"
        with cols[i % 3]:
            st.markdown(
                f"""
                <div class="gm-badge-tile {state_class}">
                    <div class="gm-badge-tile-icon">{badge['icon']}</div>
                    <div class="gm-badge-tile-label">{badge['label']}</div>
                    <div class="gm-badge-tile-desc">{badge['desc']}</div>
                </div>
                """,
                unsafe_allow_html=True,
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
