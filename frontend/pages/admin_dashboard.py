"""
Admin Dashboard - entry point for the admin module.

Deliberately separate from main.py/learner_profile.py (the learner
interface): its own st.set_page_config(), its own auth guard
(admin_logged_in + the login token, not the learner's logged_in), and its
own grouped sidebar (components/admin_shell.py).

To add an admin page: write a render_* function in
components/admin_console.py and add one entry to ADMIN_MENU below.
"""

import streamlit as st

from components import admin_console as console
from components.admin_shell import require_admin_authentication, render_admin_sidebar, render_admin_header
from utils.admin_api import admin_logout
from utils.theme import inject_theme

st.set_page_config(page_title="Admin - GAMASKILL", page_icon="🛠️", layout="wide", initial_sidebar_state="expanded")
st.set_option("client.showSidebarNavigation", False)

inject_theme()

require_admin_authentication()

# (group label, [(section key, menu label, page title, render function)])
ADMIN_MENU = [
    ("", [("overview", "Overview", "Overview", console.render_overview)]),
    ("Learners", [
        ("users", "Users", "Users", console.render_users),
        ("mastery", "Mastery Progress", "Mastery Progress", console.render_mastery),
        ("engagement", "Engagement", "Engagement", console.render_engagement),
        ("live", "Live Exams", "Live Exams", console.render_live),
    ]),
    ("Curriculum", [
        ("kkni", "KKNI Ladder", "KKNI Ladder", console.render_kkni),
        ("map", "Competency Map", "Competency Map", console.render_competency_map),
        ("materials", "Learning Materials", "Learning Materials", console.render_materials),
        ("questions", "Question Bank", "Question Bank", console.render_questions),
    ]),
    ("Community", [("discussions", "Discussions", "Discussions", console.render_discussions)]),
    ("Reports", [
        ("gain", "Learning Gain", "Learning Gain", console.render_gain),
        ("exports", "Data Exports", "Data Exports", console.render_exports),
    ]),
    ("System", [
        ("health", "System Health", "System Health", console.render_health),
        ("settings", "Settings", "Settings", console.render_settings),
    ]),
]
SECTIONS = {key: (title, render) for _, items in ADMIN_MENU for key, _, title, render in items}

if st.session_state.get("admin_section") not in SECTIONS:
    st.session_state.admin_section = "overview"

render_admin_sidebar(
    active=st.session_state.admin_section,
    groups=[(label, [(key, menu_label) for key, menu_label, _, _ in items]) for label, items in ADMIN_MENU],
)

learner_id = st.session_state.get("admin_learner_id")
title, render = SECTIONS[st.session_state.admin_section]

if render_admin_header("Learner progress" if learner_id else title):
    admin_logout()
    st.session_state.admin_logged_in = False
    st.session_state.admin_email = None
    st.session_state.admin_token = None
    st.switch_page("pages/admin_login.py")

console.show_flash()

if learner_id:
    console.render_learner(learner_id)
else:
    render()

# A call above may have found the sign-in expired (see utils/admin_api.py).
if not st.session_state.get("admin_logged_in"):
    st.switch_page("pages/admin_login.py")
