"""
Data Analytics page body: Pre-Test / Practice / Post-Test tabs.

Answer-first layout (see the approved "Data Analytics Redesign" mockup):
a summary band in plain words, then ONE level bar per unit (C1-C6, filled
to the level reached, target level outlined) in place of the old pie chart,
bar chart and unit table, then the next step as a button.

All HTML is built from <div>s on single lines: the base typography rule in
main.css colors p/span/label/li directly (so those tags ignore an inherited
color), and st.markdown treats indented lines as a code block.
"""

from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st

from utils.gating import get_learning_gating
from utils.materials_api import get_all_units
from utils.practice_api import get_practice_analytics
from utils.quiz_api import get_mastery_summary, get_test_analytics

BLOOM_LEVELS = ["C1", "C2", "C3", "C4", "C5", "C6"]


def _rank(level) -> int:
    """C1=1 ... C6=6; 0 when there is no level yet."""
    try:
        return BLOOM_LEVELS.index(str(level).upper()) + 1
    except ValueError:
        return 0


def _fmt_date(iso_date) -> str:
    if not iso_date:
        return "-"
    try:
        return pd.to_datetime(iso_date).strftime("%d %b %Y")
    except (ValueError, TypeError):
        return str(iso_date)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _unit_titles() -> dict:
    """Full unit code -> human-readable title; empty on failure."""
    result = get_all_units()
    return {u.get("unit_code"): u.get("title") or "" for u in result.get("units", [])} if result.get("units") else {}


def _summary_html(done: int, total: int, pill_cls: str, pill_text: str, headline: str, body: str, facts: list) -> str:
    pct = (done / total * 100) if total else 0
    facts_html = "".join(
        f'<div class="gm-da-fact"><div class="gm-da-fact-k">{escape(k)}</div>'
        f'<div class="gm-da-fact-v">{escape(str(v))}<div class="gm-da-fact-small">{escape(small)}</div></div></div>'
        for k, v, small in facts
    )
    return (
        '<div class="gm-da-card gm-da-summary">'
        '<div class="gm-da-verdict">'
        f'<div class="gm-da-ring" style="background: conic-gradient(#1C7A4D {pct:.1f}%, #EFEFEA 0)"><div class="gm-da-ring-in">{done}/{total}</div></div>'
        '<div class="gm-da-verdict-text">'
        f'<div class="gm-da-pill {pill_cls}">{escape(pill_text)}</div>'
        f'<div class="gm-da-headline">{escape(headline)}</div>'
        f'<div class="gm-da-body">{escape(body)}</div>'
        '</div></div>'
        f'<div class="gm-da-facts">{facts_html}</div>'
        '</div>'
    )


def _unit_row_html(code: str, title: str, level_rank: int, target_rank: int, met: bool, note_html: str) -> str:
    segs = []
    for i in range(1, 7):
        cls = "gm-da-seg"
        if i <= level_rank:
            cls += " mastered" if met else " reached"
        if i == target_rank:
            cls += " target"
        segs.append(f'<div class="{cls}">C{i}</div>')
    if met:
        chip = '<div class="gm-da-chip mastered">Target met</div>'
    else:
        left = max(target_rank - level_rank, 1)
        chip = f'<div class="gm-da-chip remedial">{_plural(left, "level")} to go</div>'
    return (
        '<div class="gm-da-unit">'
        f'<div><div class="gm-da-code">{escape(code)}</div><div class="gm-da-title">{escape(title)}</div></div>'
        f'<div class="gm-da-track-wrap"><div class="gm-da-track">{"".join(segs)}</div></div>'
        f'<div class="gm-da-gap">{chip}{note_html}</div>'
        '</div>'
    )


def _units_card_html(heading: str, sub: str, rows_html: str, show_reached: bool = True) -> str:
    legend = (
        ('<div class="gm-da-legend-item"><div class="gm-da-sw reached"></div>Reached, below target</div>' if show_reached else "")
        + '<div class="gm-da-legend-item"><div class="gm-da-sw mastered"></div>Reached, target met</div>'
        '<div class="gm-da-legend-item"><div class="gm-da-sw todo"></div>Not reached</div>'
        '<div class="gm-da-legend-item"><div class="gm-da-sw target"></div>Target level</div>'
    )
    return (
        '<div class="gm-da-card">'
        f'<div class="gm-da-h2">{escape(heading)}</div><div class="gm-da-sub">{escape(sub)}</div>'
        f'<div class="gm-da-legend">{legend}</div>'
        f'<div class="gm-da-units">{rows_html}</div>'
        '</div>'
    )


def _next_step(key: str, heading: str, body: str, button_label: str, page_key: str):
    """Navy "next step" band with one real button that navigates."""
    with st.container(key=f"gm_da_next_{key}"):
        st.markdown(
            f'<div class="gm-da-next-h">{escape(heading)}</div><div class="gm-da-next-p">{escape(body)}</div>',
            unsafe_allow_html=True,
        )
        if st.button(button_label, key=f"gm_da_next_btn_{key}"):
            st.session_state.current_page = page_key
            st.rerun()


def render_test_analytics(code_map: dict):
    analytics = get_test_analytics()
    if not analytics.get("success"):
        st.error(f"Failed to load Test Analytics: {analytics.get('error', 'Unknown error')}")
        return

    stages = analytics.get("stages", {}) or {}
    pre_data, post_data = stages.get("pre"), stages.get("post")
    titles = _unit_titles()
    gating = get_learning_gating()

    st.caption("Where you stand on each competency unit, and what to do next.")
    tab_pre, tab_practice, tab_post = st.tabs(["1 · Pre-Test", "2 · Practice", "3 · Post-Test"])
    with tab_pre:
        if pre_data:
            _render_stage(pre_data, "pre", None, post_data is not None, code_map, titles, gating)
        else:
            st.info("You haven't taken your Pre-Test yet. It measures your starting level on all six units.")
            if st.button("Go to the Pre-Test", key="gm_da_go_pretest", type="primary"):
                st.session_state.current_page = "test"
                st.rerun()
    with tab_practice:
        _render_practice(pre_data, post_data, code_map, titles)
    with tab_post:
        if post_data:
            _render_stage(post_data, "post", pre_data, True, code_map, titles, gating)
        else:
            _render_post_locked(pre_data, gating)


def _render_stage(stage_data: dict, stage: str, baseline: dict, post_taken: bool, code_map: dict, titles: dict, gating: dict):
    """One Test stage: summary band, a level bar per unit, next step."""
    units = stage_data.get("units", [])
    total_units = len(units)
    mastered = sum(1 for u in units if u.get("mastery_status") == "Mastered")
    remaining = total_units - mastered
    passed = stage_data.get("status") == "PASS"
    stage_name = "Pre-Test" if stage == "pre" else "Post-Test"

    if passed:
        body = "Every unit reached its target level."
    else:
        body = (
            f"You pass when all {total_units} units reach their target level. "
            f"{_plural(remaining, 'unit')} {'is' if remaining == 1 else 'are'} still below target."
        )
    score = stage_data.get("score", 0)
    facts = [
        ("Taken on", _fmt_date(stage_data.get("completed_at")), ""),
        ("Points", f"{score:g}" if isinstance(score, (int, float)) else score, ""),
    ]
    total_q = stage_data.get("total_questions") or 0
    if total_q:
        facts.append(("Correct answers", stage_data.get("correct_answers", 0), f"of {total_q}"))
    facts.append(("Units to improve", remaining, f"of {total_units}"))

    st.markdown(
        _summary_html(
            mastered, total_units, "pass" if passed else "notyet",
            "Passed" if passed else "Not passed yet",
            f"{mastered} of {total_units} units mastered", body, facts,
        ),
        unsafe_allow_html=True,
    )

    baseline_rank = {u["unit_code"]: _rank(u.get("unit_mastery_level")) for u in (baseline or {}).get("units", [])}
    rows = []
    for u in sorted(units, key=lambda x: code_map.get(x["unit_code"], x["unit_code"])):
        full_code = code_map.get(u["unit_code"], u["unit_code"])
        level_rank, target_rank = _rank(u.get("unit_mastery_level")), _rank(u.get("target_level"))
        met = u.get("mastery_status") == "Mastered"
        now = f"C{level_rank}" if level_rank else "No level yet"
        if u["unit_code"] in baseline_rank:
            before = baseline_rank[u["unit_code"]]
            delta = level_rank - before
            before_label = f"C{before}" if before else "no level"
            if delta > 0:
                note = f'<div class="gm-da-delta">▲ {_plural(delta, "level")} since Pre-Test ({before_label} → {now})</div>'
            elif delta < 0:
                note = f'<div class="gm-da-why">▼ {_plural(-delta, "level")} since Pre-Test ({before_label} → {now})</div>'
            else:
                note = f'<div class="gm-da-why">No change since Pre-Test ({before_label})</div>'
        else:
            note = f'<div class="gm-da-why">Now {now} · needs C{target_rank}</div>'
        rows.append(_unit_row_html(full_code, titles.get(full_code, ""), level_rank, target_rank, met, note))

    st.markdown(
        _units_card_html(
            f"Your level on each unit ({stage_name})",
            "Each bar runs from C1 to C6. The filled part is the level you reached; the outlined box is the level you need.",
            "".join(rows),
        ),
        unsafe_allow_html=True,
    )

    if stage == "pre" and not post_taken:
        if remaining:
            _next_step(
                "pre", f"Next step: practise your {_plural(remaining, 'weakest unit')}",
                "Practice questions are picked from the units below target. Each session updates your level, "
                "and the Post-Test unlocks once every unit reaches its target.",
                "Go to Practice", "practice",
            )
        elif gating.get("post_test_available"):
            _next_step("pre", "Next step: take the Post-Test", "Every unit is at its target level.", "Go to the Post-Test", "test")
    elif stage == "post" and not passed:
        _next_step(
            "post", f"Next step: keep practising {_plural(remaining, 'unit')}",
            "Practice keeps recommending the units that are still below target.",
            "Go to Practice", "practice",
        )


def _render_practice(pre_data: dict, post_data: dict, code_map: dict, titles: dict):
    """Practice tab: latest Practice level per unit against the latest Test."""
    test_data = post_data or pre_data
    if not test_data:
        st.info("Practice opens after your Pre-Test. Your Practice progress will show here.")
        return

    analytics = get_practice_analytics()
    if not analytics.get("success"):
        st.error(f"Failed to load Practice Analytics: {analytics.get('error', 'Unknown error')}")
        return
    summary = get_mastery_summary()
    recommended = set(summary.get("effective_remedial_units", [])) if summary.get("success") else set()

    progression = analytics.get("progression", [])
    total_sessions = analytics.get("total_sessions", 0)
    df = pd.DataFrame(progression)
    latest_rank, last_session = {}, None
    if not df.empty:
        df["completed_at"] = pd.to_datetime(df["completed_at"])
        df = df.sort_values("completed_at")
        latest_rank = {code: _rank(level) for code, level in df.groupby("unit_code")["unit_mastery_level"].last().items()}
        last_session = df["completed_at"].max()

    units = test_data.get("units", [])
    total_units = len(units)
    test_name = "Post-Test" if post_data else "Pre-Test"
    rows, improved = [], 0
    for u in sorted(units, key=lambda x: code_map.get(x["unit_code"], x["unit_code"])):
        code = u["unit_code"]
        full_code = code_map.get(code, code)
        before = _rank(u.get("unit_mastery_level"))
        target_rank = _rank(u.get("target_level"))
        now_rank = latest_rank.get(code, before)
        met = code not in recommended
        before_label = f"C{before}" if before else "no level"
        if code not in latest_rank:
            note = f'<div class="gm-da-why">Not practised yet ({test_name}: {before_label})</div>'
        elif now_rank > before:
            improved += 1
            note = f'<div class="gm-da-delta">▲ {_plural(now_rank - before, "level")} since {test_name} ({before_label} → C{now_rank})</div>'
        elif now_rank < before:
            note = f'<div class="gm-da-why">Latest session C{now_rank} ({test_name}: {before_label})</div>'
        else:
            note = f'<div class="gm-da-why">No change since {test_name} ({before_label})</div>'
        rows.append(_unit_row_html(full_code, titles.get(full_code, ""), now_rank, target_rank, met, note))

    at_target = total_units - len(recommended)
    all_done = not recommended
    st.markdown(
        _summary_html(
            at_target, total_units, "pass" if all_done else "notyet",
            "All units at target" if all_done else ("In progress" if total_sessions else "Not started"),
            f"{at_target} of {total_units} units at target",
            "Nothing is left to practise." if all_done
            else f"{_plural(len(recommended), 'unit')} still {'needs' if len(recommended) == 1 else 'need'} work. "
                 "Practice keeps recommending them until each one reaches its target.",
            [
                ("Sessions done", total_sessions, ""),
                ("Last session", _fmt_date(last_session) if last_session is not None else "-", ""),
                ("Units improved", improved, f"of {total_units}"),
                ("Still recommended", len(recommended), "units"),
            ],
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        _units_card_html(
            f"Progress since your {test_name}",
            f"The bars show your latest Practice level on each unit. The note on the right shows how far it moved since the {test_name}.",
            "".join(rows),
        ),
        unsafe_allow_html=True,
    )

    if not df.empty:
        st.markdown('<div class="gm-da-h2 gm-da-h2-loose">Session history</div>', unsafe_allow_html=True)
        st.caption("Newest first. One row per unit practised in a session.")
        st.dataframe(_history_table(df, code_map), use_container_width=True, hide_index=True)

    if recommended:
        names = ", ".join(sorted(code_map.get(c, c) for c in recommended))
        _next_step(
            "practice", f"Next step: {_plural(len(recommended), 'unit')} left to reach target",
            f"Your next Practice session will focus on {names}.",
            "Continue Practice" if total_sessions else "Start Practice", "practice",
        )
    elif not post_data:
        _next_step("practice", "Next step: take the Post-Test", "Every unit is at its target level.", "Go to the Post-Test", "test")


def _history_table(df: pd.DataFrame, code_map: dict) -> pd.DataFrame:
    """One row per unit per Practice session, with the level before it."""
    h = df.copy()
    h["rank"] = h["unit_mastery_level"].apply(_rank)
    order = {ts: i + 1 for i, ts in enumerate(sorted(h["completed_at"].unique()))}
    h["Session"] = h["completed_at"].map(order).map(lambda n: f"#{n}")
    h = h.sort_values(["unit_code", "completed_at"])
    h["Before"] = h.groupby("unit_code")["unit_mastery_level"].shift(1).fillna("-")
    prev_rank = h.groupby("unit_code")["rank"].shift(1)

    def change(row_rank, row_prev):
        if pd.isna(row_prev):
            return "First session"
        diff = int(row_rank - row_prev)
        if diff > 0:
            return f"▲ {_plural(diff, 'level')}"
        if diff < 0:
            return f"▼ {_plural(-diff, 'level')}"
        return "No change"

    h["Change"] = [change(r, p) for r, p in zip(h["rank"], prev_rank)]
    h["Unit"] = h["unit_code"].map(lambda c: code_map.get(c, c))
    h = h.sort_values(["completed_at", "unit_code"], ascending=[False, True])
    h["Date"] = h["completed_at"].dt.strftime("%d %b %Y %H:%M")
    return h.rename(columns={"unit_mastery_level": "After"})[["Date", "Session", "Unit", "Before", "After", "Change"]]


def _render_post_locked(pre_data: dict, gating: dict):
    """Post-Test not taken yet: say what unlocks it, as a checklist."""
    if gating.get("post_test_available"):
        st.markdown(
            '<div class="gm-da-card gm-da-locked"><div class="gm-da-pill pass">Unlocked</div>'
            '<div class="gm-da-headline">Your Post-Test is ready</div>'
            '<div class="gm-da-body">Every unit reached its target level in Practice. '
            'The Post-Test confirms that progress across all six units.</div></div>',
            unsafe_allow_html=True,
        )
        if st.button("Go to the Post-Test", key="gm_da_go_posttest", type="primary"):
            st.session_state.current_page = "test"
            st.rerun()
        return

    summary = get_mastery_summary()
    total_units = len((pre_data or {}).get("units", [])) or 6
    left = len(summary.get("effective_remedial_units", [])) if summary.get("success") and pre_data else total_units
    done = total_units - left

    def item(ok: bool, n: int, text: str) -> str:
        dot = '<div class="gm-da-dot done">✓</div>' if ok else f'<div class="gm-da-dot open">{n}</div>'
        return f'<div class="gm-da-check">{dot}{escape(text)}</div>'

    checklist = (
        item(bool(pre_data), 1, "Pre-Test taken")
        + item(left == 0 and bool(pre_data), 2, f"All {total_units} units at target in Practice ({done} of {total_units} so far)")
        + item(False, 3, "Take the Post-Test")
    )
    st.markdown(
        '<div class="gm-da-card gm-da-locked"><div class="gm-da-pill locked">Locked</div>'
        '<div class="gm-da-headline">Post-Test opens when every unit reaches its target</div>'
        f'<div class="gm-da-body">You are {_plural(left, "unit")} away. Once taken, this tab shows the same summary '
        'and unit bars as the Pre-Test tab, with the change since your Pre-Test.</div>'
        f'<div class="gm-da-checklist">{checklist}</div></div>',
        unsafe_allow_html=True,
    )
