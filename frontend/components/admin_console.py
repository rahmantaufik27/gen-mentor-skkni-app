"""
Admin console pages (see pages/admin_dashboard.py for the menu registry).

One render_* function per page, each fed by one backend call
(utils/admin_api.py::admin_view). Tables are st.dataframe with row
selection: pick rows, then use the buttons above the table - that keeps
per-row actions without one widget per row.

Learner detail (render_learner) is not a menu entry: Users, Mastery
Progress and Engagement open it by setting st.session_state.admin_learner_id.

Curriculum pages (KKNI Ladder, Competency Map, Learning Materials,
Question Bank) are read-only - that content lives in the knowledge graph
and data/skkni_ladder.py, and is not edited from here.
"""

from html import escape

import pandas as pd
import plotly.express as px
import streamlit as st

from components.test_analytics_view import _summary_html, _unit_row_html, _units_card_html
from data.skkni_ladder import ACTIVE_LEVEL, LADDER
from utils.admin_api import (
    admin_action, admin_admins, admin_export, admin_learner, admin_lesson, admin_view,
    update_all_users_inference_method, update_inference_method,
)
from utils.theme import confirm_exam_action

BLOOM = ["C1", "C2", "C3", "C4", "C5", "C6"]
INFERENCE_METHODS = ["DBN", "Manual"]


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def _load(name: str, **params):
    result = admin_view(name, **params)
    if not result.get("success"):
        st.error(f"Could not load this page: {result.get('error', 'Unknown error')}")
        return None
    return result


def _flash(result: dict):
    """Remember an action's outcome so it shows after the rerun."""
    st.session_state.admin_flash = ("success", result.get("message", "Done")) if result.get("success") \
        else ("error", result.get("error", "Action failed"))


def show_flash():
    flash = st.session_state.pop("admin_flash", None)
    if flash:
        (st.success if flash[0] == "success" else st.error)(flash[1])


def _do(name: str, **payload):
    _flash(admin_action(name, **payload))
    st.rerun()


def _confirm(title: str, message: str, label: str, name: str, **payload):
    def run():
        result = admin_action(name, **payload)
        if not result.get("success"):
            return result.get("error", "Action failed")
        _flash(result)
        return None
    confirm_exam_action(title, message, label, run)


def _date(iso, with_time: bool = False) -> str:
    if not iso:
        return "-"
    try:
        return pd.to_datetime(iso).strftime("%d %b %Y %H:%M" if with_time else "%d %b %Y")
    except (ValueError, TypeError):
        return str(iso)


def _ago(days) -> str:
    if days is None:
        return "-"
    return "Today" if days == 0 else "Yesterday" if days == 1 else f"{days} days ago"


def _rank(level) -> int:
    try:
        return BLOOM.index(str(level).upper()) + 1
    except ValueError:
        return 0


def _bars(rows: list, color: str = "teal"):
    """Horizontal bars. rows = [(label, value)]; scaled to the largest value."""
    top = max([value for _, value in rows] + [1])
    html = "".join(
        f'<div class="gm-ad-hbar"><div class="gm-ad-hbar-label">{escape(str(label))}</div>'
        f'<div class="gm-ad-hbar-track"><div class="gm-ad-hbar-fill {color}" style="width:{value / top * 100:.1f}%"></div></div>'
        f'<div class="gm-ad-hbar-val">{value}</div></div>'
        for label, value in rows
    )
    st.markdown(f'<div class="gm-ad-card">{html}</div>', unsafe_allow_html=True)


def _open_learner(user_id: str):
    st.session_state.admin_learner_id = user_id
    st.rerun()


def _go(section: str):
    st.session_state.admin_section = section
    st.session_state.admin_learner_id = None
    st.rerun()


def _selected(event, rows: list) -> list:
    return [rows[i] for i in event.selection.rows] if event and event.selection.rows else []


def _learner_table(learners: list, key: str, extra: dict = None):
    """Selectable learner table; returns the selected learner dicts."""
    df = pd.DataFrame([{
        "Learner": l["full_name"], "Email": l["email"], "Stage": l["stage"],
        "Units at target": "-" if l["units_at_target"] is None else f"{l['units_at_target']} / 6",
        **({k: f(l) for k, f in (extra or {}).items()}),
        "Last active": _ago(l["days_since_active"]),
    } for l in learners])
    event = st.dataframe(df, use_container_width=True, hide_index=True, on_select="rerun",
                         selection_mode="multi-row", key=key)
    return _selected(event, learners)


# ----------------------------------------------------------------------
# Overview
# ----------------------------------------------------------------------
def render_overview():
    data = _load("overview")
    if not data:
        return
    st.caption("How far learners have got, and where they are stuck. Test accounts (example.com) are left out.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Learners", data["real_learners"], help=f"Plus {data['test_accounts']} test accounts")
    c2.metric("Pre-Test done", data["tested"])
    c3.metric("Practising", data["practising"], help="At least one Practice session")
    c4.metric("Post-Test passed", data["passed"], help="All six units mastered")

    left, right = st.columns(2)
    with left:
        st.markdown("###### Learners by stage")
        _bars(list(data["stage_counts"].items()))
    with right:
        st.markdown("###### Learners below target, per unit")
        _bars([(u["code"], u["learners"]) for u in data["units_below_target"]], "gold")
        st.caption(f"Out of {data['tested']} tested learner(s).")

    st.markdown("###### Needs attention")
    items = [
        (data["test_accounts"], f"{data['test_accounts']} test accounts are mixed in with real learners.", "Users", "users"),
        (data["unverified"], f"{data['unverified']} account(s) have not confirmed their email.", "Users", "users"),
        (data["quiet"], f"{data['quiet']} tested learner(s) have done nothing for 14 days.", "Engagement", "engagement"),
        (data["unanswered_posts"], f"{data['unanswered_posts']} learner question(s) have no reply.", "Discussions", "discussions"),
        (data["open_sessions"], f"{data['open_sessions']} exam session(s) are open - restarting the backend would discard them.", "Live Exams", "live"),
    ]
    shown = [item for item in items if item[0]]
    if not shown:
        st.success("Nothing needs attention right now.")
    for _, text, label, section in shown:
        text_col, btn_col = st.columns([5, 1])
        text_col.write(text)
        if btn_col.button(f"Open {label}", key=f"attn_{section}_{label}", use_container_width=True):
            _go(section)


# ----------------------------------------------------------------------
# Users
# ----------------------------------------------------------------------
def render_users():
    data = _load("users")
    if not data:
        return
    users = data["users"]
    st.caption("Find a learner, see where they are, and fix account problems.")

    f1, f2, f3, f4 = st.columns([3, 2, 2, 2])
    search = f1.text_input("Search", placeholder="Search by name or email", label_visibility="collapsed").strip().lower()
    stage = f2.selectbox("Stage", ["All stages"] + data["stages"], label_visibility="collapsed")
    email_status = f3.selectbox("Email", ["Any email status", "Confirmed", "Not confirmed"], label_visibility="collapsed")
    account = f4.selectbox("Account", ["Real learners", "All accounts", "Test accounts"], label_visibility="collapsed")

    shown = [u for u in users
             if (not search or search in u["full_name"].lower() or search in u["email"].lower())
             and (stage == "All stages" or u["stage"] == stage)
             and (email_status == "Any email status" or u["email_verified"] == (email_status == "Confirmed"))
             and (account == "All accounts" or u["is_test"] == (account == "Test accounts"))]
    st.caption(f"Showing {len(shown)} of {len(users)} account(s). Select rows, then choose an action.")

    picked = _learner_table(shown, "admin_users_table", {
        "Goal": lambda u: u["goal"], "Inference": lambda u: u["inference_method"],
        "Email confirmed": lambda u: "Yes" if u["email_verified"] else "No",
    }) if shown else []

    one = picked[0] if len(picked) == 1 else None
    a1, a2, a3, a4, a5 = st.columns([2, 2, 2, 2, 2])
    if a1.button("View progress", disabled=not one, use_container_width=True, type="primary"):
        _open_learner(one["id"])
    if a2.button("Send reset link", disabled=not one, use_container_width=True,
                 help="Emails the learner a password reset link"):
        _do("send_reset_link", user_id=one["id"])
    if a3.button("Resend confirmation", disabled=not one, use_container_width=True):
        _do("resend_confirmation", user_id=one["id"])
    method = a4.selectbox("Inference method", INFERENCE_METHODS, label_visibility="collapsed", key="admin_users_method")
    if a5.button(f"Set {method} for {len(picked)} selected", disabled=not picked, use_container_width=True):
        failed = [u["email"] for u in picked if not update_inference_method(u["id"], method).get("success")]
        _flash({"success": not failed, "message": f"Inference method set to {method} for {len(picked)} account(s).",
                "error": "Failed for: " + ", ".join(failed)})
        st.rerun()

    if picked and st.button(f"Delete {len(picked)} selected account(s)", key="admin_users_delete"):
        _confirm("Delete accounts?",
                 f"This permanently deletes {len(picked)} account(s) with their tests, practice sessions, notes and activity.",
                 "Yes, delete", "delete_users", user_ids=[u["id"] for u in picked])
    if not data["mail_enabled"]:
        st.caption("Email is off, so reset links and confirmation emails can't be sent. See Settings.")

    if data["test_accounts"]:
        st.divider()
        st.markdown("###### Test accounts")
        text_col, btn_col = st.columns([4, 2])
        text_col.write(f"{data['test_accounts']} of {len(users)} accounts use an example.com address, created during "
                       "testing. Deleting them also removes their attempts.")
        if btn_col.button(f"Delete {data['test_accounts']} test accounts", use_container_width=True):
            _confirm("Delete all test accounts?",
                     f"This permanently deletes {data['test_accounts']} example.com accounts and everything recorded for them.",
                     "Yes, delete", "delete_test_accounts")


# ----------------------------------------------------------------------
# Learner detail
# ----------------------------------------------------------------------
def render_learner(user_id: str):
    result = admin_learner(user_id)
    if st.button("← Back", key="admin_learner_back"):
        st.session_state.admin_learner_id = None
        st.rerun()
    if not result.get("success"):
        st.error(f"Could not load this learner: {result.get('error', 'Unknown error')}")
        return
    learner = result["learner"]
    journey = result["journey"]

    st.markdown(f"### {escape(learner['full_name'])}")
    st.caption(f"{learner['email']} · joined {_date(learner['created_at'])} · goal: {learner['goal']} · "
               f"inference: {learner['inference_method']} · email {'confirmed' if learner['email_verified'] else 'not confirmed'}"
               + (" · test account" if learner["is_test"] else ""))

    if not learner["tested"]:
        st.info("This learner has not taken the Pre-Test yet, so there is no progress to show.")
    else:
        at_target = learner["units_at_target"]
        left_units = len(journey) - at_target
        st.markdown(_summary_html(
            at_target, len(journey), "pass" if left_units == 0 else "notyet", learner["stage"],
            f"{at_target} of {len(journey)} units at target",
            "Every unit has reached its target level." if left_units == 0
            else f"{left_units} unit(s) still below target. Levels below are the latest from Practice or a Test.",
            [("Practice sessions", learner["practice_sessions"], ""),
             ("Last practice", _date(learner["last_practice"]), ""),
             ("Last active", _ago(learner["days_since_active"]), ""),
             ("Stage", learner["stage"], "")],
        ), unsafe_allow_html=True)

        rows = []
        for unit in journey:
            steps = " → ".join(f"{s['label']} {s['level'] or '-'}" for s in unit["steps"]) or "No results yet"
            note = f'<div class="gm-da-why">{escape(steps)}</div>'
            rows.append(_unit_row_html(unit["code"], unit["title"], _rank(unit["level"]), _rank(unit["target"]), unit["met"], note))
        st.markdown(_units_card_html(
            "Level on each unit",
            "The bar shows the latest level. The line on the right is the unit's history: Pre-Test, each Practice session, Post-Test.",
            "".join(rows)), unsafe_allow_html=True)

    tab_tests, tab_practice, tab_activity, tab_notes = st.tabs(["Tests", "Practice sessions", "Activity", "Notes and reflections"])
    with tab_tests:
        if not result["tests"]:
            st.info("No test taken yet.")
        for test in result["tests"]:
            name = "Pre-Test" if test["stage"] == "pre" else "Post-Test"
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(name, "Passed" if test["passed"] else "Not passed")
            c2.metric("Taken on", _date(test["completed_at"]))
            c3.metric("Correct answers", f"{test['correct_answers']} / {test['total_questions']}")
            c4.metric("Points", f"{test['score']:g}")
            st.dataframe(pd.DataFrame([{"Unit": code, "Level": info["level"] or "-", "Status": info["status"]}
                                       for code, info in sorted(test["units"].items())]),
                         use_container_width=True, hide_index=True)
    with tab_practice:
        sessions = result["practice_sessions"]
        if not sessions:
            st.info("No Practice session yet.")
        else:
            st.dataframe(pd.DataFrame([{
                "Session": f"#{s['number']}", "Date": _date(s["completed_at"], True),
                "Correct": f"{s['correct_answers']} / {s['total_questions']}",
                "Points": f"{s['total_score']:g} / {s['max_possible_score']:g}",
                "Levels after the session": ", ".join(f"{code.split('.', 2)[-1]} {level or '-'}" for code, level in sorted(s["units"].items())),
            } for s in reversed(sessions)]), use_container_width=True, hide_index=True)
    with tab_activity:
        counts = result["activity_counts"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Logins", counts.get("login", 0))
        c2.metric("Materials opened", counts.get("material_view", 0))
        c3.metric("Chatbot messages", counts.get("chatbot_prompt", 0))
        c4.metric("Discussion posts", result["counts"]["discussion_posts"])
        if result["material_views"]:
            st.markdown("###### Materials opened, by unit")
            _bars([(m["unit"], m["views"]) for m in result["material_views"]], "green")
        st.markdown("###### Latest activity")
        labels = {"login": "Logged in", "material_view": "Opened a material", "chatbot_prompt": "Asked the chatbot"}
        st.dataframe(pd.DataFrame([{"When": _date(a["at"], True), "What": labels.get(a["type"], a["type"]), "Unit": a["detail"]}
                                   for a in result["recent_activity"]]), use_container_width=True, hide_index=True)
    with tab_notes:
        c1, c2, c3 = st.columns(3)
        c1.metric("Saved notes", result["counts"]["notes"])
        c2.metric("Free notes", result["counts"]["free_notes"])
        c3.metric("Reflection answers", result["counts"]["reflections"])
        if result["reflections"]:
            st.markdown("###### Reflection answers")
            st.dataframe(pd.DataFrame([{"Question": r["question"].replace("reflect_", "").replace("_", " "),
                                        "Answer": r["answer"], "Updated": _date(r["updated_at"])}
                                       for r in result["reflections"]]), use_container_width=True, hide_index=True)

    st.divider()
    a1, a2, a3, a4 = st.columns(4)
    if a1.button("Send reset link", use_container_width=True, key="learner_reset"):
        _do("send_reset_link", user_id=user_id)
    if a2.button("Resend confirmation", use_container_width=True, key="learner_resend", disabled=learner["email_verified"]):
        _do("resend_confirmation", user_id=user_id)
    method = a3.selectbox("Inference", INFERENCE_METHODS, index=INFERENCE_METHODS.index(learner["inference_method"])
                          if learner["inference_method"] in INFERENCE_METHODS else 0, label_visibility="collapsed")
    if a4.button("Save inference method", use_container_width=True, key="learner_inference"):
        _flash(update_inference_method(user_id, method))
        st.rerun()


# ----------------------------------------------------------------------
# Mastery Progress
# ----------------------------------------------------------------------
def render_mastery():
    include_test = st.toggle("Include test accounts", key="admin_mastery_test")
    data = _load("mastery", include_test="1" if include_test else "")
    if not data:
        return
    st.caption(f"Latest level of each tested learner, by unit ({data['tested']} tested).")
    if not data["tested"]:
        st.info("No learner has taken the Pre-Test yet.")
        return

    st.markdown("###### Learners at each level, per unit")
    palette = ["#DAD9D2", "#F3D9A6", "#F0C24B", "#E0A106", "#4FA57B", "#2C8A5C", "#1C7A4D"]
    legend = "".join(f'<div class="gm-da-legend-item"><div class="gm-da-sw" style="background:{palette[i]}"></div>{label}</div>'
                     for i, label in enumerate(["No level"] + BLOOM))
    rows = ""
    for row in data["distribution"]:
        total = sum(row["counts"]) or 1
        segments = "".join(f'<div style="width:{n / total * 100:.1f}%;background:{palette[i]}" title="{n}"></div>'
                           for i, n in enumerate(row["counts"]) if n)
        rows += (f'<div class="gm-ad-hbar"><div class="gm-ad-hbar-label gm-da-code">{row["code"]}</div>'
                 f'<div class="gm-ad-stack">{segments}</div>'
                 f'<div class="gm-ad-hbar-val wide">{row["at_target"]} of {total} at {row["target"]}+</div></div>')
    st.markdown(f'<div class="gm-ad-card"><div class="gm-da-legend">{legend}</div>{rows}</div>', unsafe_allow_html=True)

    st.markdown("###### Learner by unit")
    learners = data["learners"]
    df = pd.DataFrame([{
        "Learner": l["full_name"],
        **{u["code"].split(".", 2)[-1]: (l["levels"][u["code"]]["level"] or "-") for u in data["units"]},
        "At target": f"{l['units_at_target']} / {len(data['units'])}",
        "Sessions": l["practice_sessions"], "Last practice": _date(l["last_practice"]),
    } for l in learners])
    event = st.dataframe(df, use_container_width=True, hide_index=True, on_select="rerun",
                         selection_mode="single-row", key="admin_mastery_table")
    picked = _selected(event, learners)
    if st.button("View progress", disabled=not picked, type="primary", key="admin_mastery_view"):
        _open_learner(picked[0]["id"])


# ----------------------------------------------------------------------
# Engagement
# ----------------------------------------------------------------------
def render_engagement():
    data = _load("engagement")
    if not data:
        return
    counts = data["counts"]
    st.caption("Who is studying, what they use, and who has gone quiet. Test accounts are left out of the learner counts.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active this week", f"{data['active_this_week']} of {data['real_learners']}")
    c2.metric("Materials opened (30d)", counts.get("material_view", 0))
    c3.metric("Chatbot messages (30d)", counts.get("chatbot_prompt", 0))
    c4.metric("Gone quiet", len(data["quiet"]), help=f"Tested, no activity for {data['quiet_after_days']} days")

    left, right = st.columns(2)
    with left:
        st.markdown("###### Activity in the last 30 days")
        _bars([("Logins", counts.get("login", 0)), ("Materials opened", counts.get("material_view", 0)),
               ("Practice sessions", counts.get("practice_session", 0)), ("Chatbot messages", counts.get("chatbot_prompt", 0)),
               ("Notes saved", counts.get("note_saved", 0)), ("Reflections", counts.get("reflection", 0))])
    with right:
        st.markdown("###### Materials opened, by unit")
        if data["views_by_unit"]:
            _bars([(v["unit"], v["views"]) for v in data["views_by_unit"]], "green")
        else:
            st.info("No material opened in the last 30 days.")
    if data["daily"]:
        st.markdown("###### Events per day")
        # plotly, not st.bar_chart: the built-in chart fails in this environment's altair/typing_extensions pairing
        fig = px.bar(pd.DataFrame(data["daily"]), x="date", y="events")
        fig.update_traces(marker_color="#0E7490")
        fig.update_layout(height=200, margin=dict(t=10, b=10, l=10, r=10), xaxis_title="", yaxis_title="Events",
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True, key="admin_engagement_daily")

    st.markdown("###### Learners who have gone quiet")
    quiet = data["quiet"]
    if not quiet:
        st.success(f"No tested learner has been inactive for {data['quiet_after_days']} days.")
        return
    picked = _learner_table(quiet, "admin_quiet_table")
    b1, b2 = st.columns([1, 1])
    if b1.button("View progress", disabled=len(picked) != 1, use_container_width=True, key="admin_quiet_view"):
        _open_learner(picked[0]["id"])
    targets = picked or quiet
    if b2.button(f"Email a reminder to {len(targets)} learner(s)", disabled=not data["mail_enabled"],
                 use_container_width=True, type="primary", key="admin_quiet_remind"):
        _do("send_reminders", user_ids=[l["id"] for l in targets])
    if not data["mail_enabled"]:
        st.caption("Reminders need email switched on. See Settings.")


# ----------------------------------------------------------------------
# Live Exams
# ----------------------------------------------------------------------
def render_live():
    data = _load("live")
    if not data:
        return
    st.caption("Tests and practice sessions in progress right now.")
    if st.button("Refresh", key="admin_live_refresh"):
        st.rerun()
    sessions = data["sessions"]
    if not sessions:
        st.info("No exam is in progress.")
        return
    st.warning(f"{len(sessions)} session(s) are open. They live in the server's memory, so restarting the backend "
               "now would discard their answers.")
    for s in sessions:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 2, 3, 2])
            c1.markdown(f"**{escape(s['learner'])}**  \n{s['email']}")
            c2.markdown(f"**{s['exam']}**  \nStarted {_date(s['started_at'], True)}")
            c3.progress(s["answered"] / s["total"] if s["total"] else 0, text=f"{s['answered']} of {s['total']} answered")
            if c4.button("End session", key=f"end_{s['session_id']}", use_container_width=True):
                _confirm("End this session?", f"{s['learner']}'s answers so far will be discarded and not scored.",
                         "Yes, end it", "end_session", kind=s["kind"], session_id=s["session_id"])


# ----------------------------------------------------------------------
# Curriculum (read-only)
# ----------------------------------------------------------------------
def render_kkni():
    st.caption("The career ladder shown to learners in onboarding and on the landing page. Read-only here: the ladder "
               "is defined in data/skkni_ladder.py.")
    level = st.radio("Level", sorted(LADDER), index=sorted(LADDER).index(ACTIVE_LEVEL), horizontal=True,
                     format_func=lambda l: f"Level {l}" + (" (live)" if l == ACTIVE_LEVEL else ""))
    live = level == ACTIVE_LEVEL
    roles = "".join(f'<div class="gm-ad-role {"live" if live else ""}">{escape(role)}</div>' for role in LADDER[level])
    st.markdown(f'<div class="gm-ad-card"><div class="gm-ad-roles">{roles}</div></div>', unsafe_allow_html=True)
    if not live:
        st.info("Preview only: learners see these role names on the ladder, but there are no units behind them yet.")
        return
    data = _load("competency_map")
    if not data:
        return
    totals = {t["code"]: t for t in data["totals"]}
    st.markdown("###### Units for this level")
    st.dataframe(pd.DataFrame([{
        "Code": u["code"], "Unit": u["title"], "Target level": u["target"],
        "Elements": totals.get(u["code"], {}).get("elements", 0),
        "Performance criteria": totals.get(u["code"], {}).get("criteria", 0),
        "Reference snippets": totals.get(u["code"], {}).get("reference_snippets", 0),
    } for u in data["units"]]), use_container_width=True, hide_index=True)


def render_competency_map():
    first = _load("competency_map", unit=st.session_state.get("admin_map_unit", ""))
    if not first:
        return
    units = first["units"]
    st.caption("Each unit broken down into its elements and performance criteria, with the questions attached to each.")
    totals = first["totals"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Units", len(units))
    c2.metric("Elements", sum(t["elements"] for t in totals))
    c3.metric("Performance criteria", sum(t["criteria"] for t in totals))
    c4.metric("Criteria without a question", sum(t["criteria_without_questions"] for t in totals))

    codes = [u["code"] for u in units]
    chosen = st.selectbox("Unit", codes, index=codes.index(first["unit_code"]) if first["unit_code"] in codes else 0,
                          format_func=lambda c: f"{c} · {next(u['title'] for u in units if u['code'] == c)}")
    if chosen != first["unit_code"]:
        st.session_state.admin_map_unit = chosen
        st.rerun()
    for element in first["elements"]:
        st.markdown(f"**{escape(element['element'])}**")
        if not element["criteria"]:
            st.caption("No performance criteria recorded.")
            continue
        st.dataframe(pd.DataFrame([{
            "Performance criterion": c["criterion"], "Questions": c["questions"],
            "Status": "Covered" if c["questions"] else "No questions",
        } for c in element["criteria"]]), use_container_width=True, hide_index=True)


def render_materials():
    data = _load("materials")
    if not data:
        return
    st.caption("Slide decks per unit, and the lessons generated from them. A generated lesson is saved once and shown "
               "to every learner.")
    lessons = data["lessons"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Materials", len(data["materials"]))
    c2.metric("Subtopics listed", sum(u["subtopics_listed"] or 0 for u in data["units"]))
    c3.metric("Lessons saved", len(lessons))

    st.markdown("###### By unit")
    st.dataframe(pd.DataFrame([{
        "Unit": u["code"], "Title": u["title"],
        "Subtopics listed": "Not listed yet" if u["subtopics_listed"] is None else u["subtopics_listed"],
        "Lessons saved": u["lessons_generated"], "Times opened": u["views"],
    } for u in data["units"]]), use_container_width=True, hide_index=True)

    st.markdown("###### Materials")
    st.dataframe(pd.DataFrame([{"Material": m["title"], "Unit": m["unit_code"], "Type": m["type"]}
                               for m in data["materials"]]), use_container_width=True, hide_index=True)

    st.markdown("###### Saved lessons")
    if not lessons:
        st.info("No lesson has been generated yet.")
        return
    event = st.dataframe(pd.DataFrame([{
        "Unit": l["unit_code"], "Subtopic": f"{l['subtopic_index'] + 1}. {l['title']}",
        "Length": f"{l['characters']:,} characters", "Generated": _date(l["created_at"], True), "By": l["provider"],
    } for l in lessons]), use_container_width=True, hide_index=True, on_select="rerun",
        selection_mode="single-row", key="admin_lessons_table")
    picked = _selected(event, lessons)
    b1, b2, b3 = st.columns(3)
    show = b1.toggle("Read the selected lesson", disabled=not picked, key="admin_lesson_read")
    if b2.button("Delete the selected lesson", disabled=not picked, use_container_width=True):
        _confirm("Delete this lesson?", "It will be generated again the next time a learner asks for it.",
                 "Yes, delete", "delete_lessons", unit_code=picked[0]["unit_code"], subtopic_index=picked[0]["subtopic_index"])
    if b3.button("Clear all saved lessons", use_container_width=True):
        _confirm("Clear all saved lessons?", "Every lesson and subtopic list will be regenerated on demand. "
                 "Do this after changing the lesson prompt.", "Yes, clear all", "delete_lessons")
    if show and picked:
        lesson = admin_lesson(picked[0]["unit_code"], picked[0]["subtopic_index"])
        if lesson.get("success"):
            with st.container(border=True):
                st.markdown(f"#### {lesson['title']}")
                st.markdown(lesson["material"])


def render_questions():
    include_test = st.toggle("Include answers from test accounts", key="admin_questions_test")
    data = _load("questions", include_test="1" if include_test else "")
    if not data:
        return
    st.caption(f"The question bank behind the Pre-Test, Practice and Post-Test: {data['total_questions']} questions. "
               "Read-only here.")
    st.markdown("###### Coverage: questions per unit and level")
    coverage = pd.DataFrame([{"Unit": code, **levels, "Total": sum(levels.values())}
                             for code, levels in data["coverage"].items()])

    def shade(value):
        if not isinstance(value, (int, float)):
            return ""
        return "background-color:#FBEAEA;color:#B42318;font-weight:700" if value < 3 else ""
    st.dataframe(coverage.style.map(shade, subset=data["levels"]), use_container_width=True, hide_index=True)
    st.caption("Red means fewer than 3 questions at that level, so learners will see repeats.")

    st.markdown("###### Questions")
    items = data["items"]
    if not items:
        st.info("The question bank could not be loaded.")
        return

    def status(i):
        return "Review" if i["review"] else ("Asked" if i["asked"] else "Not asked yet")

    f1, f2, f3, f4 = st.columns([4, 2, 1.4, 1.8])
    search = f1.text_input("Search", placeholder="Search question text", label_visibility="collapsed",
                           key="admin_q_search").strip().lower()
    unit = f2.selectbox("Unit", ["All units"] + [u["code"] for u in data["units"]], label_visibility="collapsed",
                        key="admin_q_unit")
    level = f3.selectbox("Level", ["All levels"] + data["levels"], label_visibility="collapsed", key="admin_q_level")
    flag = f4.selectbox("Status", ["Any status", "Review", "Asked", "Not asked yet"], label_visibility="collapsed",
                        key="admin_q_status")
    shown = [i for i in items
             if (not search or search in i["text"].lower() or any(search in c["text"].lower() for c in i["choices"]))
             and (unit == "All units" or i["unit_code"] == unit)
             and (level == "All levels" or i["level"] == level)
             and (flag == "Any status" or status(i) == flag)]
    st.caption(f"Showing {len(shown)} of {len(items)} questions. Select a row to read the full question and its options.")

    def short_unit(code):
        return ".".join(code.split(".")[-2:])

    table = pd.DataFrame([{
        "Question": i["text"], "Unit": short_unit(i["unit_code"]), "Level": i["level"], "Key": i["key"],
        "Asked": i["asked"], "Correct": "-" if i["correct_pct"] is None else f"{i['correct_pct']}%",
        "Most-picked wrong answer": (f"{i['top_wrong']} · {i['top_wrong_pct']}%"
                                     + (", more than the key" if i["review"] else "")) if i["top_wrong"] else "-",
        "Status": status(i),
    } for i in shown])

    def status_style(value):
        return {"Review": "background-color:rgba(255,198,0,.25);color:#8A6400;font-weight:700",
                "Asked": "background-color:rgba(28,122,77,.12);color:#1C7A4D;font-weight:700",
                "Not asked yet": "color:#6B6F76"}.get(value, "")

    event = st.dataframe(
        table.style.map(status_style, subset=["Status"]) if len(table) else table,
        use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row",
        key="admin_q_table", height=min(38 + 35 * max(len(shown), 1), 640),
        column_config={"Question": st.column_config.TextColumn(width="large")},
    )
    picked = _selected(event, shown)
    if picked:
        q = picked[0]
        options = "".join(
            f'<div class="gm-ad-option {"key" if c["is_correct"] else ""}"><div class="gm-ad-option-id">{c["id"]}</div>'
            f'<div>{escape(c["text"])}</div>{"<div class=gm-ad-option-tag>Key</div>" if c["is_correct"] else ""}</div>'
            for c in q["choices"])
        stats = (f"Asked {q['asked']} time(s) · {q['correct_pct']}% correct"
                 + (f" · most-picked wrong answer {q['top_wrong']} ({q['top_wrong_count']})" if q["top_wrong"] else "")
                 + (f" · left blank {q['unanswered']}" if q["unanswered"] else "")) if q["asked"] else "Not asked in any test yet."
        explanation = f'<div class="gm-da-why">Explanation: {escape(q["explanation"])}</div>' if q["explanation"] else ""
        st.markdown(
            f'<div class="gm-ad-card"><div class="gm-da-code">{q["unit_code"]} · {q["level"]}</div>'
            f'<div class="gm-ad-qtext">{escape(q["text"])}</div>{options}'
            f'<div class="gm-da-why">{stats}</div>{explanation}</div>', unsafe_allow_html=True)

    notes = ("A question is flagged \"Review\" when one wrong answer was picked more often than the key (asked at "
             "least 3 times): the key may be wrong or the wording unclear. Figures come from Pre-Test and Post-Test "
             "answers; Practice answers are not stored per question. Answers from test accounts are left out unless "
             "included above, because automated test runs always pick the first option.")
    if data["old_bank_questions"]:
        notes += (f" {data['old_bank_answers']} recorded answers belong to {data['old_bank_questions']} questions from "
                  "the older question bank, which no longer exist, so they are not shown.")
    st.caption(notes + " Adding, editing or disabling questions is not available here yet: the bank lives in Neo4j.")


# ----------------------------------------------------------------------
# Community
# ----------------------------------------------------------------------
def render_discussions():
    data = _load("discussions")
    if not data:
        return
    posts = data["posts"]
    st.caption("Questions learners post on each unit, unanswered first.")
    if not posts:
        st.info("No discussion post yet.")
        return
    for post in posts:
        with st.container(border=True):
            text_col, btn_col = st.columns([5, 1])
            status = "Best answer chosen" if post["solved"] else f"{post['replies']} repl{'y' if post['replies'] == 1 else 'ies'}" \
                if post["replies"] else "Unanswered"
            text_col.markdown(f"{escape(post['body'])}")
            text_col.caption(f"{post['author']} · {post['unit_code']}"
                             + (f" · on {post['material']}" if post["material"] else "")
                             + f" · {_date(post['created_at'], True)} · {status}")
            if btn_col.button("Remove", key=f"post_{post['id']}", use_container_width=True):
                _confirm("Remove this post?", "The post and its replies are deleted for everyone.",
                         "Yes, remove", "delete_post", post_id=post["id"])
    st.caption("To reply, sign in as a learner and answer in the Discussion page.")


# ----------------------------------------------------------------------
# Reports
# ----------------------------------------------------------------------
def render_gain():
    include_test = st.toggle("Include test accounts", key="admin_gain_test")
    data = _load("gain", include_test="1" if include_test else "")
    if not data:
        return
    st.caption("Pre-Test against Post-Test, for learners who took both.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Took both tests", f"{data['both']} of {data['tested']}")
    c2.metric("Avg. Pre-Test points", "-" if data["pre_avg_score"] is None else data["pre_avg_score"])
    c3.metric("Avg. Post-Test points", "-" if data["post_avg_score"] is None else data["post_avg_score"])
    gain = None if not data["both"] else round(data["post_avg_score"] - data["pre_avg_score"], 1)
    c4.metric("Average gain (points)", "-" if gain is None else gain)
    if not data["both"]:
        st.info("No learner has taken both the Pre-Test and the Post-Test yet. This report fills in once they do.")
        return
    st.markdown("###### Per unit")
    st.dataframe(pd.DataFrame([{
        "Unit": u["code"], "Target": u["target"], "Avg. level before (1-6)": u["pre_avg"],
        "Avg. level after (1-6)": u["post_avg"],
        "Mastered before": f"{u['mastered_before']} / {data['both']}", "Mastered after": f"{u['mastered_after']} / {data['both']}",
    } for u in data["per_unit"]]), use_container_width=True, hide_index=True)
    st.markdown("###### Per learner")
    st.dataframe(pd.DataFrame([{
        "Learner": l["full_name"], "Pre-Test points": l["pre_score"], "Post-Test points": l["post_score"],
        "Practice sessions": l["practice_sessions"], "Post-Test": "Passed" if l["passed"] else "Not passed",
    } for l in data["learners"]]), use_container_width=True, hide_index=True)
    st.caption(f"Based on {data['both']} learner(s); treat averages from a small group as indicative only.")


def render_exports():
    data = _load("exports")
    if not data:
        return
    st.caption("Download the raw data as CSV for analysis outside the app.")
    c1, c2 = st.columns(2)
    anonymize = c1.checkbox("Replace names and emails with anonymous learner IDs", value=True)
    include_test = c2.checkbox("Include test accounts", value=False)
    for dataset in data["datasets"]:
        with st.container(border=True):
            text_col, btn_col = st.columns([4, 1])
            text_col.markdown(f"**{dataset['label']}**  \nOne row per {dataset['one_row_per']} · {dataset['rows']:,} rows in total")
            csv_text = admin_export(dataset["key"], anonymize, include_test)
            btn_col.download_button("Download CSV", csv_text, file_name=f"gamaskill_{dataset['key']}.csv", mime="text/csv",
                                    key=f"export_{dataset['key']}_{anonymize}_{include_test}", use_container_width=True,
                                    disabled=not csv_text)


# ----------------------------------------------------------------------
# System
# ----------------------------------------------------------------------
def render_health():
    data = _load("health")
    if not data:
        return
    st.caption("Whether each part the app depends on is reachable, checked when this page opens.")
    st.dataframe(pd.DataFrame([{"Service": c["service"], "Used for": c["used_for"],
                                "Status": "Up" if c["ok"] else "Off / down", "Detail": c["detail"]}
                               for c in data["checks"]]), use_container_width=True, hide_index=True)
    c1, c2 = st.columns(2)
    c1.metric("Open exam sessions", data["open_sessions"], help="Lost if the backend restarts")
    c2.metric("Saved lessons", data["saved_lessons"], help=f"{data['saved_lesson_characters']:,} characters stored")
    if data["open_sessions"]:
        st.warning("Exam sessions are open. Restarting the backend now would discard their answers.")


def render_settings():
    st.markdown("###### Assessment")
    c1, c2 = st.columns([2, 2])
    method = c1.selectbox("Inference method for every account", INFERENCE_METHODS, key="admin_settings_method")
    c2.write("")
    c2.write("")
    if c2.button("Apply to all accounts", use_container_width=True):
        def run():
            result = update_all_users_inference_method(method)
            if not result.get("success"):
                return result.get("error", "Update failed")
            _flash(result)
            return None
        confirm_exam_action("Apply to all accounts?", f"Every account's inference method becomes {method}.", "Yes, apply", run)

    st.divider()
    st.markdown("###### Email")
    health = admin_view("health")
    email_on = any(c["service"] == "Email" and c["ok"] for c in health.get("checks", []))
    st.write("Confirmation, password reset and reminder emails are **on**." if email_on else
             "Confirmation, password reset and reminder emails are **off**. Put the mail account's app password in "
             "`backend/mail.ini` and set `enabled = true`.")

    st.divider()
    st.markdown("###### Your password")
    with st.form("admin_change_password", clear_on_submit=True):
        current = st.text_input("Current password", type="password")
        new = st.text_input("New password", type="password", help="At least 8 characters")
        again = st.text_input("Confirm new password", type="password")
        if st.form_submit_button("Change password"):
            if new != again:
                st.error("The new passwords do not match.")
            else:
                _do("change_password", current_password=current, new_password=new)

    st.divider()
    st.markdown("###### Admin accounts")
    admins = admin_admins()
    if admins.get("success"):
        st.dataframe(pd.DataFrame([{"Email": a["email"], "Name": a["full_name"],
                                    "Status": "Active" if a["is_active"] else "Deactivated",
                                    "Last sign-in": _date(a["last_login_at"], True)} for a in admins["admins"]]),
                     use_container_width=True, hide_index=True)
        others = [a for a in admins["admins"] if a["email"] != admins["current"]]
        if others:
            c1, c2 = st.columns([3, 2])
            target = c1.selectbox("Admin", others, format_func=lambda a: a["email"], label_visibility="collapsed")
            if c2.button("Reactivate" if not target["is_active"] else "Deactivate", use_container_width=True):
                _do("set_admin_active", email=target["email"], is_active=not target["is_active"])
    with st.form("admin_add_admin", clear_on_submit=True):
        st.write("Add an admin")
        c1, c2, c3 = st.columns(3)
        email = c1.text_input("Email")
        name = c2.text_input("Name")
        password = c3.text_input("Password", type="password", help="At least 8 characters")
        if st.form_submit_button("Add admin"):
            _do("add_admin", email=email, full_name=name, password=password)
